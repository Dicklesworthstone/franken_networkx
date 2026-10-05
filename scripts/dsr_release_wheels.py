#!/usr/bin/env python3
"""Build source-bound wheels and a native-library proof payload inside DSR.

DSR collects the extension extracted from the primary wheel as its native
payload and collects the wheel files themselves as additional release assets.
Every build uses DSR's isolated Cargo home and target directory.
"""

import configparser
import email
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from email import policy
from pathlib import Path, PurePosixPath

import tomllib


def _safe_archive_path(name):
    """License metadata is a relative POSIX path, never an extraction target."""
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError(f"unsafe archive path: {name!r}")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"unsafe archive path: {name!r}")
    return PurePosixPath(name)


def _distribution_metadata(raw, version, source_licenses):
    metadata = email.message_from_bytes(raw, policy=policy.default)
    if metadata.defects or len(metadata.get_all("Name", [])) != 1 or len(metadata.get_all("Version", [])) != 1:
        raise ValueError("malformed or ambiguous package metadata")
    name = re.sub(r"[-_.]+", "-", str(metadata["Name"])).lower()
    if name != "franken-networkx" or str(metadata["Version"]) != version:
        raise ValueError("package name/version does not match the candidate")
    licenses = metadata.get_all("License-File", [])
    if not licenses or len(set(licenses)) != len(licenses):
        raise ValueError("missing or duplicate License-File metadata")
    for license_file in licenses:
        _safe_archive_path(license_file)
        if license_file not in source_licenses:
            raise ValueError(f"license has no frozen source bytes: {license_file!r}")
    if set(licenses) != set(source_licenses):
        raise ValueError("declared licenses do not match the frozen source licenses")
    return metadata, licenses


def _zip_regular_bytes(archive, name):
    members = [entry for entry in archive.infolist() if entry.filename == name]
    if len(members) != 1:
        raise ValueError(f"expected one regular archive member: {name}")
    member = members[0]
    kind = stat.S_IFMT(member.external_attr >> 16)
    if member.is_dir() or kind not in (0, stat.S_IFREG):
        raise ValueError(f"archive member is not a regular file: {name}")
    for parent in PurePosixPath(name).parents:
        for entry in archive.infolist():
            if entry.filename.rstrip("/") == str(parent) and stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError(f"archive member has a linked parent: {name}")
    return archive.read(member)


def _tar_regular_bytes(archive, name):
    members = [entry for entry in archive.getmembers() if entry.name == name]
    if len(members) != 1 or not members[0].isfile():
        raise ValueError(f"expected one regular archive member: {name}")
    for parent in PurePosixPath(name).parents:
        for entry in archive.getmembers():
            if entry.name.rstrip("/") == str(parent) and (entry.issym() or entry.islnk()):
                raise ValueError(f"archive member has a linked parent: {name}")
    with archive.extractfile(members[0]) as stream:
        return stream.read()


def validate_wheel_licenses(archive, version, source_licenses):
    """Validate actual wheel members, without extracting untrusted paths."""
    metadata_path = f"franken_networkx-{version}.dist-info/METADATA"
    metadata, licenses = _distribution_metadata(
        _zip_regular_bytes(archive, metadata_path), version, source_licenses
    )
    for license_file in licenses:
        path = f"franken_networkx-{version}.dist-info/licenses/{license_file}"
        if _zip_regular_bytes(archive, path) != source_licenses[license_file]:
            raise ValueError(f"wheel license differs from frozen source: {license_file}")
    return metadata


def validate_sdist_licenses(archive, version, source_licenses):
    """Catch the published missing-root-LICENSE defect before signing/upload."""
    prefix = f"franken_networkx-{version}"
    metadata, licenses = _distribution_metadata(
        _tar_regular_bytes(archive, f"{prefix}/PKG-INFO"), version, source_licenses
    )
    for license_file in licenses:
        if _tar_regular_bytes(archive, f"{prefix}/{license_file}") != source_licenses[license_file]:
            raise ValueError(f"sdist license differs from frozen source: {license_file}")
    return metadata


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    source_licenses = {"LICENSE": (root / "LICENSE").read_bytes()}
    target = os.environ["CARGO_BUILD_TARGET"]
    if sys.platform == "darwin" and shutil.disk_usage("/").free < 15 * 1024**3:
        raise SystemExit("Darwin host root has less than the required 15 GiB free")
    target_dir = Path(os.environ["CARGO_TARGET_DIR"]).resolve()
    output = target_dir / target / "release"
    output.mkdir(parents=True, exist_ok=True)
    maturin = os.environ.get("FNX_MATURIN") or shutil.which("maturin")
    if not maturin:
        raise SystemExit("maturin must be installed on the DSR build host")
    # ubs:ignore — executable is trusted DSR host configuration; argv-only, no shell.
    if subprocess.check_output([maturin, "--version"], text=True, timeout=30).strip() != "maturin 1.12.4":
        raise SystemExit("this release recipe requires qualified maturin 1.12.4")

    platforms = {
        "x86_64-unknown-linux-gnu": "manylinux_2_17_x86_64.manylinux2014_x86_64",
        "aarch64-unknown-linux-gnu": "manylinux_2_17_aarch64.manylinux2014_aarch64",
        "x86_64-apple-darwin": "macosx_10_12_x86_64",
        "aarch64-apple-darwin": "macosx_11_0_arm64",
        "x86_64-pc-windows-msvc": "win_amd64",
        "x86_64-unknown-linux-musl": "musllinux_1_2_x86_64",
    }

    def build(triple):
        command = [maturin, "build", "--release", "--locked", "--target", triple,
                   "--target-dir", str(target_dir), "--out", str(output)]
        env = os.environ.copy()
        env["CARGO_BUILD_TARGET"] = triple
        if triple.endswith("-gnu"):
            command += ["--zig", "--compatibility", "manylinux_2_17"]
        elif triple.endswith("-musl"):
            command += ["--zig", "--compatibility", "musllinux_1_2"]
        elif triple.endswith("-apple-darwin"):
            env["MACOSX_DEPLOYMENT_TARGET"] = "10.12" if triple.startswith("x86_64") else "11.0"
        elif triple.endswith("-msvc"):
            # Maturin's bundled cargo-xwin backend activates automatically.
            # Keep the downloaded SDK inside this DSR target's isolated tree.
            env["XWIN_CACHE_DIR"] = str(target_dir / "xwin-cache")
            env["XWIN_CROSS_COMPILER"] = "clang"
            if env.get("FNX_LLVM_BIN"):
                env["PATH"] = env["FNX_LLVM_BIN"] + os.pathsep + env["PATH"]
            if not shutil.which("llvm-dlltool", path=env["PATH"]):
                raise SystemExit("llvm-dlltool is required to generate the ABI3 Python import library")
            if not env.get("XWIN_MSVC_SYSROOT_DOWNLOAD_URL"):
                raise SystemExit("DSR must pin XWIN_MSVC_SYSROOT_DOWNLOAD_URL for the Windows SDK")
        # ubs:ignore — trusted DSR host tool/configuration, passed as argv without a shell.
        subprocess.run(command, cwd=root, env=env, check=True, timeout=1800)
        wheel = output / f"franken_networkx-{version}-cp310-abi3-{platforms[triple]}.whl"
        if not wheel.is_file():
            raise SystemExit(f"maturin did not produce the contracted wheel: {wheel.name}")
        with zipfile.ZipFile(wheel) as archive:
            if "fnx_backend_info.py" not in archive.namelist():
                raise SystemExit(f"backend discovery shim missing from {wheel.name}")
            members = [name for name in archive.namelist()
                       if name.startswith("franken_networkx/_fnx.")
                       and name.endswith((".so", ".pyd"))]
            if len(members) != 1:
                raise SystemExit(f"expected one native extension in {wheel.name}: {members}")
            native = archive.read(members[0])
            wheel_metadata = [name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")]
            tags = {f"Tag: cp310-abi3-{platform}" for platform in platforms[triple].split(".")}
            if len(wheel_metadata) != 1 or not tags.issubset(set(archive.read(wheel_metadata[0]).decode().splitlines())):
                raise SystemExit(f"wheel tag does not match its contracted filename: {wheel.name}")
            metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            entry_paths = [name for name in archive.namelist() if name.endswith(".dist-info/entry_points.txt")]
            if len(metadata_paths) != 1 or len(entry_paths) != 1:
                raise SystemExit(f"package metadata or entry points missing from {wheel.name}")
            validate_wheel_licenses(archive, version, source_licenses)
            entry_points = configparser.ConfigParser()
            entry_points.optionxform = str
            entry_points.read_string(archive.read(entry_paths[0]).decode())
            expected = tomllib.loads((root / "pyproject.toml").read_text())["project"]["entry-points"]
            actual = {group: dict(entry_points[group]) for group in entry_points.sections()}
            if actual != expected:
                raise SystemExit(f"backend entry points do not match pyproject in {wheel.name}")
        return wheel, native

    wheel, native = build(target)
    payload = output / ("fnx-extension.exe" if target.endswith("-msvc") else "fnx-extension")
    payload.write_bytes(native)
    payload.chmod(0o755)
    if target.endswith("-msvc"):
        # DSR's Windows additional-artifact collector appends .exe to its
        # source lookup, while preserving the published wheel basename.
        shutil.copyfile(wheel, output / f"{wheel.name}.exe")
    if target == "x86_64-unknown-linux-gnu":
        build("x86_64-unknown-linux-musl")
        # ubs:ignore — trusted DSR host tool/configuration; argv-only, no shell.
        subprocess.run([maturin, "sdist", "--out", str(output)], cwd=root, check=True, timeout=120)
        sdist = output / f"franken_networkx-{version}.tar.gz"
        if not sdist.is_file():
            raise SystemExit("maturin did not produce the contracted source distribution")
        with tarfile.open(sdist, "r:gz") as archive:
            validate_sdist_licenses(archive, version, source_licenses)
            if f"franken_networkx-{version}/python/fnx_backend_info.py" not in archive.getnames():
                raise SystemExit("backend discovery shim missing from the source distribution")


if __name__ == "__main__":
    main()
