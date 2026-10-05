#!/usr/bin/env python3
"""Build source-bound wheels and a native-library proof payload inside DSR.

DSR collects the extension extracted from the primary wheel as its native
payload and collects the wheel files themselves as additional release assets.
Every build uses DSR's isolated Cargo home and target directory.
"""

import argparse
import configparser
import email
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from email import policy
from pathlib import Path, PurePosixPath

import tomllib


_BUILD_INPUTS = (
    "Cargo.toml", "Cargo.lock", "pyproject.toml", "rust-toolchain.toml",
    "LICENSE", "README.md", "CHANGELOG.md", ".gitignore", ".cargo", ".dsr",
    "crates", "python", "scripts",
)


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _regular_hash(path):
    """Hash actual bytes, refusing links and files moving during the read."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"binding input is not a regular file: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError(f"binding input moved during read: {path}")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = path.stat()
    identity = lambda state: (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns)
    if identity(before) != identity(after) or identity(after) != identity(current) or path.is_symlink():
        raise ValueError(f"binding input moved during read: {path}")
    return digest.hexdigest()


def snapshot_build_inputs(root, configs=()):
    """Release-build inputs, not a claim to snapshot the whole quality suite.

    Git selects tracked and non-ignored untracked inputs; its porcelain
    statuses are never the digest. Coordination state, historical benchmark
    artifacts and tests are outside this explicit release-build scope.
    """
    root = Path(root).resolve(strict=True)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], timeout=60)
    head = git("rev-parse", "HEAD").decode().strip()
    def names():
        paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *_BUILD_INPUTS)
        return sorted({os.fsdecode(path) for path in paths.split(b"\0") if path})
    selected = names()
    files = {}
    for name in selected:
        relative = _safe_archive_path(name)
        if any(part in ("target", "__pycache__") for part in relative.parts):
            continue
        path = root / name
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            raise ValueError(f"binding input has a linked parent: {name}")
        files[name] = {"sha256": _regular_hash(path), "executable": bool(path.stat().st_mode & 0o111)}
    for required in ("Cargo.toml", "Cargo.lock", "pyproject.toml", "LICENSE", "scripts/dsr_release_wheels.py"):
        if required not in files:
            raise ValueError(f"missing required build input: {required}")
    configuration = {str(Path(path).absolute()): _regular_hash(path) for path in configs}
    if names() != selected or git("rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("source inventory moved during snapshot")
    return {"head": head, "files": files, "configs": configuration, "scope": "release-build-inputs"}


def require_same_inputs(root, frozen, configs=()):
    current = snapshot_build_inputs(root, configs)
    if current != frozen:
        changed = sorted(name for name in frozen["files"].keys() | current["files"].keys()
                         if frozen["files"].get(name) != current["files"].get(name))
        raise ValueError(f"candidate source/config moved: {changed or 'HEAD or DSR configuration'}")


def require_fresh_build_target(path):
    """An old compiled cache cannot establish this candidate's source chain."""
    path = Path(path).absolute()
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f"use a fresh regular DSR target directory: {path}")
    if path.exists() and next(path.iterdir(), None) is not None:
        raise ValueError(f"use a fresh DSR target; previous build cache retained: {path}")


def normalized_dependency_graph(root, metadata):
    """Keep selected features/edges, reject unresolved or external path inputs."""
    root = Path(root).resolve(strict=True)
    identities, packages = {}, []
    for package in metadata["packages"]:
        source = package["source"]
        if source is None:
            manifest = Path(package["manifest_path"]).resolve(strict=True)
            try:
                source = "path:" + manifest.relative_to(root).as_posix()
            except ValueError as error:
                raise ValueError(f"unbound out-of-tree dependency: {package['name']}") from error
            if not any(source[5:] == path or source[5:].startswith(path + "/") for path in _BUILD_INPUTS):
                raise ValueError(f"dependency outside build-input scope: {source}")
        elif not source.startswith("registry+"):
            raise ValueError(f"unbound non-registry dependency: {source}")
        identity = f"{package['name']}@{package['version']}::{source}"
        identities[package["id"]] = identity
        packages.append(identity)
    if len(set(packages)) != len(packages) or not metadata.get("resolve"):
        raise ValueError("ambiguous or unresolved dependency graph")
    nodes = [{"package": identities[node["id"]], "features": sorted(node["features"]),
              "dependencies": sorted(identities[dependency] for dependency in node["dependencies"])}
             for node in metadata["resolve"]["nodes"]]
    return {"packages": sorted(packages), "nodes": sorted(nodes, key=lambda node: node["package"])}


def bind_artifact(path, kind, candidate_id):
    path = Path(path).absolute()
    record = {"path": str(path), "kind": kind, "candidate_id": candidate_id, "sha256": _regular_hash(path)}
    if kind == "wheel":
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.startswith("franken_networkx/_fnx.")
                       and name.endswith((".so", ".pyd"))]
            if len(members) != 1:
                raise ValueError("ambiguous native extension in candidate wheel")
            record["native_member"] = members[0]
            record["native_sha256"] = hashlib.sha256(_zip_regular_bytes(archive, members[0])).hexdigest()
            record["python_members"] = {name: hashlib.sha256(_zip_regular_bytes(archive, name)).hexdigest()
                                        for name in archive.namelist()
                                        if name.endswith((".py", ".pyi"))}
    if _regular_hash(path) != record["sha256"]:
        raise ValueError(f"candidate artifact moved during binding: {path}")
    return record


def verify_artifact_binding(binding):
    if (binding.get("schema") != "fnx-dsr-build-binding-v1" or not binding.get("candidate")
            or binding.get("candidate_id") != _json_hash(binding["candidate"]) or not binding.get("artifacts")):
        raise ValueError("missing or invalid candidate binding")
    candidate = binding["candidate"]
    if (not all(candidate.get(key) for key in ("inputs", "graphs", "maturin", "rustc", "cargo"))
            or "build_environment" not in candidate
            or not all(candidate["inputs"].get(key) for key in ("head", "files", "configs", "scope"))
            or candidate["inputs"]["scope"] != "release-build-inputs"):
        raise ValueError("missing required candidate fields")
    kinds = set()
    for record in binding["artifacts"]:
        if record.get("candidate_id") != binding["candidate_id"] or record.get("kind") not in ("wheel", "sdist", "native"):
            raise ValueError("artifact belongs to a different candidate")
        if not all(record.get(key) for key in ("path", "sha256")):
            raise ValueError("missing artifact binding fields")
        current = bind_artifact(record["path"], record["kind"], binding["candidate_id"])
        if current != record:
            raise ValueError(f"candidate artifact mismatch: {record['path']}")
        kinds.add(record["kind"])
    if not {"wheel", "native"}.issubset(kinds):
        raise ValueError("missing wheel/native candidate artifacts")
    if not any(record["kind"] == "wheel" and record["native_sha256"] == native["sha256"]
               for record in binding["artifacts"] for native in binding["artifacts"] if native["kind"] == "native"):
        raise ValueError("native payload does not join the candidate wheel")


def verify_loaded_candidate(binding, expected_python, expected_prefix, wheel_path, oracle_version):
    """Called in the selected fresh interpreter, not a parent-process guess."""
    verify_artifact_binding(binding)
    if str(Path(sys.executable).absolute()) != str(Path(expected_python).absolute()) or Path(sys.prefix).resolve() != Path(expected_prefix).resolve():
        raise ValueError("candidate interpreter/venv mismatch")
    wheels = [record for record in binding["artifacts"]
              if record["kind"] == "wheel" and record["path"] == str(Path(wheel_path).resolve())]
    if len(wheels) != 1:
        raise ValueError("selected wheel is not in the candidate binding")
    import franken_networkx
    import networkx
    wheel = wheels[0]
    loaded = Path(franken_networkx._fnx.__file__).resolve(strict=True)
    package = Path(franken_networkx.__file__).resolve(strict=True).parent
    site_dir = Path(sysconfig.get_path("purelib")).resolve(strict=True)
    if package != site_dir / "franken_networkx" or loaded != site_dir / wheel["native_member"]:
        raise ValueError("candidate package/extension shadowed outside selected venv")
    if _regular_hash(loaded) != wheel["native_sha256"]:
        raise ValueError("loaded extension differs from candidate wheel")
    for member, digest in wheel["python_members"].items():
        _safe_archive_path(member)
        if _regular_hash(site_dir / member) != digest:
            raise ValueError(f"installed Python member differs from candidate wheel: {member}")
    if networkx.__version__ != oracle_version:
        raise ValueError("candidate oracle version mismatch")
    return {"candidate_id": binding["candidate_id"], "python": sys.executable,
            "prefix": sys.prefix, "python_version": sys.version, "oracle_version": networkx.__version__,
            "package": str(package), "extension": str(loaded), "so_sha256": _regular_hash(loaded)}


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
    if not os.environ.get("DSR_RUN_ID"):
        raise SystemExit("this build recipe must be invoked by DSR")
    config_dir = Path(os.environ.get("DSR_CONFIG_DIR", Path.home() / ".config/dsr"))
    configs = [Path(os.environ.get("DSR_REPOS_FILE", config_dir / "repos.yaml"))]
    build_config = config_dir / "repos.d/franken_networkx.yaml"
    if build_config.exists():
        configs.append(build_config)
    for directory in (root, *root.parents, Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))):
        cargo_dir = directory if directory == Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")) else directory / ".cargo"
        for name in ("config", "config.toml"):
            path = cargo_dir / name
            if path.exists() and path not in configs:
                configs.append(path)
    frozen = snapshot_build_inputs(root, configs)
    version = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    source_licenses = {"LICENSE": (root / "LICENSE").read_bytes()}
    target = os.environ["CARGO_BUILD_TARGET"]
    if sys.platform == "darwin" and shutil.disk_usage("/").free < 15 * 1024**3:
        raise SystemExit("Darwin host root has less than the required 15 GiB free")
    target_dir = Path(os.environ["CARGO_TARGET_DIR"]).absolute()
    require_fresh_build_target(target_dir)
    output = Path(os.environ.get("FNX_DSR_OUTPUT_DIR", target_dir / target / "release")).resolve()
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
    triples = [target] + (["x86_64-unknown-linux-musl"] if target == "x86_64-unknown-linux-gnu" else [])
    graphs = {}
    features = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["maturin"]["features"]
    for triple in triples:
        raw = subprocess.check_output(["cargo", "metadata", "--locked", "--format-version", "1",
                                       "--manifest-path", "crates/fnx-python/Cargo.toml", "--features", ",".join(features),
                                       "--filter-platform", triple], cwd=root, timeout=180)
        graphs[triple] = normalized_dependency_graph(root, json.loads(raw))
    candidate = {"inputs": frozen, "graphs": graphs, "maturin": "1.12.4",
                 "rustc": subprocess.check_output(["rustc", "-Vv"], text=True, timeout=30),
                 "cargo": subprocess.check_output(["cargo", "-V"], text=True, timeout=30),
                 "build_environment": {name: os.environ.get(name) for name in
                                       ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_TARGET", "CARGO_BUILD_JOBS")}}
    candidate_id = _json_hash(candidate)
    artifacts = []
    binding_path = output / "fnx-candidate.json"
    if binding_path.exists():
        raise SystemExit(f"use fresh DSR output; previous candidate retained: {binding_path}")
    require_same_inputs(root, frozen, configs)
    print(json.dumps({"event": "candidate-start", "candidate_id": candidate_id, "input_count": len(frozen["files"]),
                      "scope": frozen["scope"]}), flush=True)

    def build(triple):
        require_same_inputs(root, frozen, configs)
        contracted = output / f"franken_networkx-{version}-cp310-abi3-{platforms[triple]}.whl"
        if contracted.exists():
            raise SystemExit(f"use fresh DSR output; previous wheel retained: {contracted}")
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
        require_same_inputs(root, frozen, configs)
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
        artifacts.append(bind_artifact(wheel, "wheel", candidate_id))
        return wheel, native

    wheel, native = build(target)
    payload = output / ("fnx-extension.exe" if target.endswith("-msvc") else "fnx-extension")
    if payload.exists():
        raise SystemExit(f"previous native payload retained: {payload}")
    payload.write_bytes(native)
    payload.chmod(0o755)
    artifacts.append(bind_artifact(payload, "native", candidate_id))
    if target.endswith("-msvc"):
        # DSR's Windows additional-artifact collector appends .exe to its
        # source lookup, while preserving the published wheel basename.
        shutil.copyfile(wheel, output / f"{wheel.name}.exe")
    if target == "x86_64-unknown-linux-gnu":
        build("x86_64-unknown-linux-musl")
        sdist = output / f"franken_networkx-{version}.tar.gz"
        if sdist.exists():
            raise SystemExit(f"previous source distribution retained: {sdist}")
        require_same_inputs(root, frozen, configs)
        # The source archive is produced below only after all wheel inputs remained stable.
        # ubs:ignore — trusted DSR host tool/configuration; argv-only, no shell.
        subprocess.run([maturin, "sdist", "--out", str(output)], cwd=root, check=True, timeout=120)
        require_same_inputs(root, frozen, configs)
        if not sdist.is_file():
            raise SystemExit("maturin did not produce the contracted source distribution")
        with tarfile.open(sdist, "r:gz") as archive:
            validate_sdist_licenses(archive, version, source_licenses)
            if f"franken_networkx-{version}/python/fnx_backend_info.py" not in archive.getnames():
                raise SystemExit("backend discovery shim missing from the source distribution")
        artifacts.append(bind_artifact(sdist, "sdist", candidate_id))
    require_same_inputs(root, frozen, configs)
    binding = {"schema": "fnx-dsr-build-binding-v1", "candidate": candidate,
               "candidate_id": candidate_id, "artifacts": artifacts}
    verify_artifact_binding(binding)
    with binding_path.open("x") as stream:
        json.dump(binding, stream, sort_keys=True, indent=2)
    print(json.dumps({"event": "candidate-built", "candidate_id": candidate_id,
                      "binding_path": str(binding_path), "binding_sha256": _regular_hash(binding_path),
                      "artifacts": artifacts}), flush=True)


def verify_main():
    parser = argparse.ArgumentParser(description="Verify DSR-built bytes in the explicitly selected Python process")
    parser.add_argument("--verify-binding", type=Path, required=True)
    parser.add_argument("--expected-binding-sha", required=True)
    parser.add_argument("--expected-python", required=True)
    parser.add_argument("--expected-prefix", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--oracle-version", required=True)
    args = parser.parse_args()
    if not os.environ.get("DSR_RUN_ID"):
        raise SystemExit("candidate verification must be invoked by DSR")
    if _regular_hash(args.verify_binding) != args.expected_binding_sha:
        raise ValueError("selected DSR binding bytes changed")
    binding = json.loads(args.verify_binding.read_bytes())
    verify_artifact_binding(binding)
    frozen = binding["candidate"]["inputs"]
    require_same_inputs(Path(__file__).resolve().parents[1], frozen, tuple(frozen["configs"]))
    report = verify_loaded_candidate(binding, args.expected_python, args.expected_prefix, args.wheel, args.oracle_version)
    if _regular_hash(args.verify_binding) != args.expected_binding_sha:
        raise ValueError("selected DSR binding moved during verification")
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    else:
        verify_main()
