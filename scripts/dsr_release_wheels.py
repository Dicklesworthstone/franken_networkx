#!/usr/bin/env python3
"""Build source-bound wheels and a native-library proof payload inside DSR.

DSR collects the extension extracted from the primary wheel as its native
payload and collects the wheel files themselves as additional release assets.
Every build uses DSR's isolated Cargo home and target directory.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    target = os.environ["CARGO_BUILD_TARGET"]
    if sys.platform == "darwin" and shutil.disk_usage("/").free < 15 * 1024**3:
        raise SystemExit("Darwin host root has less than the required 15 GiB free")
    target_dir = Path(os.environ["CARGO_TARGET_DIR"]).resolve()
    output = target_dir / target / "release"
    output.mkdir(parents=True, exist_ok=True)
    maturin = os.environ.get("FNX_MATURIN") or shutil.which("maturin")
    if not maturin:
        raise SystemExit("maturin must be installed on the DSR build host")
    if subprocess.check_output([maturin, "--version"], text=True).strip() != "maturin 1.12.4":
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
        subprocess.run(command, cwd=root, env=env, check=True)
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
        subprocess.run([maturin, "sdist", "--out", str(output)], cwd=root, check=True)
        sdist = output / f"franken_networkx-{version}.tar.gz"
        if not sdist.is_file():
            raise SystemExit("maturin did not produce the contracted source distribution")
        with tarfile.open(sdist, "r:gz") as archive:
            if f"franken_networkx-{version}/python/fnx_backend_info.py" not in archive.getnames():
                raise SystemExit("backend discovery shim missing from the source distribution")


if __name__ == "__main__":
    main()
