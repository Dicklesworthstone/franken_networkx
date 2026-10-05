"""The INSTALLED franken_networkx must not drift from the repo shim.

WHY THIS EXISTS. `conftest.py` already refuses to run when the in-tree
`_fnx.abi3.so` is older than the Rust sources, and it puts `<repo>/python` at
the front of `sys.path` — so pytest always tests the repo shim against the
in-tree extension, and the existing guard keeps that pair honest.

Nothing guarded the OTHER package. A plain `python3 -c "import
franken_networkx"`, and therefore every benchmark, profiler run and one-off
timing script that does not replicate conftest's `sys.path` surgery, imports
the INSTALLED copy out of site-packages instead. That copy has its own
lifecycle: `maturin develop` refreshes it, a rebuilt wheel refreshes it, and
nothing at all refreshes it if neither is run.

WHAT THAT COST, concretely. Measured 2026-08-16, the installed shim was 62761
lines against the repo's 65512 — 2751 lines and twelve days behind, missing
`_fnx_captured_row` entirely. The multigraph row lookup `G.adj[u]` at
2000-character keys read 0.1568x against networkx through the installed shim
and 0.8530x through the repo shim: the same call, the same extension, a 5.4x
difference in the reported ratio, and the stale reading pointed straight at a
"defect" that had already been fixed. A whole investigation was spent on the
wrong half of a call because the substrate was silently old.

The extension is checked by CONTENT, not mtime. Wheel builds normalise their
timestamps — the installed `_fnx.abi3.so` carries an mtime of 1980-01-01 — so
the mtime comparison that works for the in-tree copy cannot work here.

These tests SKIP when there is no separate installed copy (running purely out
of the checkout is a legitimate setup). They only speak up when an installed
copy exists AND disagrees, which is exactly the situation in which timings
taken outside pytest are measuring something other than the working tree.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import site
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_PKG = REPO_ROOT / "python" / "franken_networkx"

_REBUILD_HINT = (
    "Refresh the installed copy so out-of-pytest timings measure the working "
    "tree (for example: rch exec -- maturin develop --features pyo3/abi3-py310), "
    "or delete the installed copy so imports fall through to the checkout."
)


def _candidate_site_dirs() -> list[Path]:
    dirs: list[str] = []
    try:
        dirs.extend(site.getsitepackages())
    except AttributeError:  # pragma: no cover - virtualenv shims
        pass
    try:
        user_site = site.getusersitepackages()
    except AttributeError:  # pragma: no cover
        user_site = None
    if isinstance(user_site, str):
        dirs.append(user_site)
    elif isinstance(user_site, (list, tuple)):
        dirs.extend(user_site)
    dirs.extend(p for p in sys.path if p)
    seen, out = set(), []
    for entry in dirs:
        path = Path(entry)
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _installed_package_dir() -> Path | None:
    """The franken_networkx package pytest is NOT using, if one exists."""
    repo_python = REPO_ROOT / "python"
    for directory in _candidate_site_dirs():
        if directory.resolve() == repo_python.resolve():
            continue
        candidate = directory / "franken_networkx"
        if (candidate / "__init__.py").is_file():
            return candidate
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def installed_pkg() -> Path:
    pkg = _installed_package_dir()
    if pkg is None:
        pytest.skip("no installed franken_networkx outside the checkout")
    return pkg


def test_installed_shim_matches_the_repo_shim(installed_pkg: Path) -> None:
    """The Python half. This is the half that drifted, and it drifts silently:
    a stale `.py` changes measured behaviour with no import error to notice."""
    installed_init = installed_pkg / "__init__.py"
    repo_init = REPO_PKG / "__init__.py"
    if not repo_init.is_file():
        pytest.skip("no repo shim to compare against")

    if _sha256(installed_init) == _sha256(repo_init):
        return

    installed_lines = installed_init.read_text(errors="replace").count("\n")
    repo_lines = repo_init.read_text(errors="replace").count("\n")
    pytest.fail(
        "the INSTALLED franken_networkx shim differs from the repo shim, so "
        "anything importing it outside pytest is measuring different code:\n"
        f"  installed : {installed_init} ({installed_lines} lines)\n"
        f"  repo      : {repo_init} ({repo_lines} lines)\n"
        f"  delta     : {repo_lines - installed_lines:+d} lines\n"
        "pytest is unaffected (conftest puts the repo shim first); BENCHMARKS "
        "AND PROFILING SCRIPTS ARE NOT.\n"
        f"{_REBUILD_HINT}"
    )


def test_installed_extension_matches_the_in_tree_extension(installed_pkg: Path) -> None:
    """The native half, compared by CONTENT.

    Wheel builds normalise timestamps, so the installed `.so` carries a 1980
    mtime and the mtime comparison conftest uses for the in-tree copy is
    meaningless here. Bytes are the only usable signal.
    """
    installed_so = installed_pkg / "_fnx.abi3.so"
    repo_so = REPO_PKG / "_fnx.abi3.so"
    if not installed_so.is_file() or not repo_so.is_file():
        pytest.skip("no extension pair to compare")

    installed_digest, repo_digest = _sha256(installed_so), _sha256(repo_so)
    assert installed_digest == repo_digest, (
        "the INSTALLED _fnx extension differs from the in-tree one, so timings "
        "taken outside pytest exercise different native code:\n"
        f"  installed : {installed_so} sha256={installed_digest[:16]}\n"
        f"  in-tree   : {repo_so} sha256={repo_digest[:16]}\n"
        f"{_REBUILD_HINT}"
    )


def test_the_import_pytest_resolves_is_the_repo_checkout() -> None:
    """Pins the assumption the two tests above are written against.

    If conftest ever stops front-loading `<repo>/python`, pytest would begin
    testing the installed copy while these comparisons still described the
    checkout — and the whole file would be reasoning about the wrong pair.
    """
    import franken_networkx

    resolved = Path(franken_networkx.__file__).resolve()
    expected = (REPO_PKG / "__init__.py").resolve()
    assert resolved == expected, (
        f"pytest imported {resolved}, not the repo shim at {expected}; the "
        "installed-vs-repo comparisons in this file assume the checkout wins"
    )


# Archive checks belong with installed-package identity, not a second release
# checker. These real in-memory containers exercise the DSR builder's checker;
# they are unit-level planted inputs, not proof of a published wheel/source build.
@pytest.fixture(scope="module")
def release_recipe():
    path = REPO_ROOT / "scripts" / "dsr_release_wheels.py"
    spec = importlib.util.spec_from_file_location("fnx_dsr_release_recipe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _license_archive(kind, metadata, entries):
    stream = io.BytesIO()
    prefix = "franken_networkx-1.2.3"
    metadata_path = f"{prefix}.dist-info/METADATA" if kind == "wheel" else f"{prefix}/PKG-INFO"
    if kind == "wheel":
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(metadata_path, metadata)
            for path, data in entries:
                entry = zipfile.ZipInfo(path)
                entry.create_system = 3
                if isinstance(data, tuple):
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(entry, data[1].encode())
                else:
                    entry.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(entry, data)
        stream.seek(0)
        return zipfile.ZipFile(stream)
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for path, data in [(metadata_path, metadata), *entries]:
            entry = tarfile.TarInfo(path)
            if isinstance(data, tuple):
                entry.type = tarfile.SYMTYPE
                entry.linkname = data[1]
                archive.addfile(entry)
            else:
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
    stream.seek(0)
    return tarfile.open(fileobj=stream, mode="r:")


def _license_member(kind, name="LICENSE"):
    prefix = "franken_networkx-1.2.3"
    return f"{prefix}.dist-info/licenses/{name}" if kind == "wheel" else f"{prefix}/{name}"


def _license_metadata(extra="License-File: LICENSE\n"):
    return f"Metadata-Version: 2.4\nName: franken-networkx\nVersion: 1.2.3\n{extra}\nREADME body\n".encode()


def _validate_licenses(recipe, kind, archive, licenses):
    validate = recipe.validate_wheel_licenses if kind == "wheel" else recipe.validate_sdist_licenses
    return validate(archive, "1.2.3", licenses)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_dsr_license_members_match_frozen_source_bytes(release_recipe, kind):
    licenses = {"LICENSE": (REPO_ROOT / "LICENSE").read_bytes(), "crates/NOTICE": b"crate license\n"}
    metadata = _license_metadata("".join(f"License-File: {name}\n" for name in licenses))
    entries = [(_license_member(kind, name), data) for name, data in licenses.items()]
    with _license_archive(kind, metadata, entries) as archive:
        result = _validate_licenses(release_recipe, kind, archive, licenses)
        assert result.get_all("License-File") == list(licenses)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("defect", ["missing", "wrong_bytes", "linked_member", "linked_parent", "duplicate"])
def test_dsr_rejects_missing_changed_linked_or_ambiguous_licenses(release_recipe, kind, defect):
    data = (REPO_ROOT / "LICENSE").read_bytes()
    member = _license_member(kind)
    entries = [(member, data)]
    if defect == "missing":
        entries = []  # The real v0.2.3 source archive's defect.
    elif defect == "wrong_bytes":
        entries = [(member, b"different license\n")]
    elif defect == "linked_member":
        entries = [(member, ("symlink", "../../outside/LICENSE"))]
    elif defect == "linked_parent":
        entries.append((str(Path(member).parent), ("symlink", "../../outside")))
    else:
        entries.append((member, data))
    with _license_archive(kind, _license_metadata(), entries) as archive, pytest.raises(ValueError):
        _validate_licenses(release_recipe, kind, archive, {"LICENSE": data})


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("name", ["../LICENSE", "/LICENSE", "a/../LICENSE", "a//LICENSE", "./LICENSE", "C:/LICENSE", "a\\LICENSE"])
def test_dsr_rejects_unsafe_license_metadata_paths(release_recipe, kind, name):
    data = b"license\n"
    metadata = _license_metadata(f"License-File: {name}\n")
    with (
        _license_archive(kind, metadata, [(_license_member(kind, name), data)]) as archive,
        pytest.raises(ValueError, match="unsafe archive path"),
    ):
        _validate_licenses(release_recipe, kind, archive, {name: data})


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize(
    "metadata",
    [
        _license_metadata(""),
        _license_metadata("License-File: LICENSE\nLicense-File: LICENSE\n"),
        _license_metadata("License-File: UNKNOWN\n"),
        _license_metadata().replace(b"Name: franken-networkx", b"Name: wrong-package"),
        _license_metadata().replace(b"Version: 1.2.3", b"Version: 1.2.4"),
        _license_metadata().replace(b"Version: 1.2.3", b"Version: 1.2.3\nVersion: 1.2.3"),
        _license_metadata().replace(b"Name: franken-networkx", b"Name: franken-networkx\nName: franken-networkx"),
        b"not a metadata header\n",
    ],
)
def test_dsr_rejects_malformed_or_wrong_candidate_metadata(release_recipe, kind, metadata):
    data = (REPO_ROOT / "LICENSE").read_bytes()
    with (
        _license_archive(kind, metadata, [(_license_member(kind), data)]) as archive,
        pytest.raises(ValueError),
    ):
        _validate_licenses(release_recipe, kind, archive, {"LICENSE": data})


def test_sdist_recipe_explicitly_includes_the_workspace_license():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    includes = project["tool"]["maturin"]["include"]
    assert any(entry["path"] == "LICENSE" and "sdist" in entry["format"] for entry in includes)


# These retained small Git trees/archives are controlled integrity inputs,
# not proof that a real wheel compiled or that the generic DSR gate is fixed.
@pytest.mark.parametrize("state", ["absent", "empty", "cached", "file", "linked"])
def test_dsr_build_requires_a_fresh_target_without_deleting_previous_work(release_recipe, tmp_path, state):
    target = tmp_path / "candidate-target"
    if state == "empty":
        target.mkdir()
    elif state == "cached":
        target.mkdir()
        (target / "old-compiled-input").write_bytes(b"previous retained build")
    elif state == "file":
        target.write_bytes(b"previous retained file")
    elif state == "linked":
        retained = tmp_path / "retained-target"
        retained.mkdir()
        target.symlink_to(retained, target_is_directory=True)
    if state in ("absent", "empty"):
        release_recipe.require_fresh_build_target(target)
    else:
        with pytest.raises(ValueError, match="fresh.*DSR target"):
            release_recipe.require_fresh_build_target(target)
        assert target.exists()
        if state == "cached":
            assert (target / "old-compiled-input").read_bytes() == b"previous retained build"
        elif state == "file":
            assert target.read_bytes() == b"previous retained file"
        else:
            assert target.is_symlink() and retained.is_dir()


@pytest.fixture
def binding_tree(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    entries = {"Cargo.toml": "[workspace]\n", "Cargo.lock": "version = 4\n",
               "pyproject.toml": "[project]\nname = 'franken-networkx'\n",
               "LICENSE": "retained fixture license\n", "scripts/dsr_release_wheels.py": "# fixture recipe\n",
               "crates/example/Cargo.toml": "[package]\nname = 'example'\nversion = '1.0.0'\n",
               "crates/example/src/lib.rs": "pub fn value() -> u32 { 1 }\n"}
    for name, content in entries.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], timeout=30)
    git("init", "--quiet")
    git("add", "--", *entries)
    git("-c", "user.name=DSR fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "controlled binding inputs")
    config = tmp_path / "selected-dsr.yaml"
    config.write_text("tools: {}\n")
    return root, config, git


@pytest.mark.parametrize("state", ["clean", "dirty", "untracked"])
def test_dsr_build_binding_accepts_stable_actual_source_bytes(release_recipe, binding_tree, state):
    root, config, _git = binding_tree
    source = root / "crates/example/src/lib.rs"
    if state == "dirty":
        source.write_text("pub fn value() -> u32 { 2 }\n")
    elif state == "untracked":
        source = source.with_name("untracked.rs")
        source.write_text("pub fn untracked() -> u32 { 3 }\n")
    frozen = release_recipe.snapshot_build_inputs(root, [config])
    assert frozen["files"][source.relative_to(root).as_posix()]["sha256"] == _sha256(source)
    assert frozen["configs"][str(config)] == _sha256(config)
    release_recipe.require_same_inputs(root, frozen, [config])


@pytest.mark.parametrize("state", ["dirty", "untracked"])
def test_dsr_binding_detects_byte_changes_when_porcelain_is_identical(release_recipe, binding_tree, state):
    root, config, git = binding_tree
    source = root / "crates/example/src/lib.rs"
    if state == "untracked":
        source = source.with_name("untracked.rs")
    source.write_text("pub fn value() -> u32 { 2 }\n")
    porcelain = git("status", "--porcelain", "--untracked-files=all")
    frozen = release_recipe.snapshot_build_inputs(root, [config])
    source.write_text("pub fn value() -> u32 { 3 }\n")
    # Planted negative for the actual generic DSR defect: its old input did
    # not change, while this source-byte comparison must reject the run.
    assert git("status", "--porcelain", "--untracked-files=all") == porcelain
    with pytest.raises(ValueError, match="candidate source/config moved"):
        release_recipe.require_same_inputs(root, frozen, [config])


@pytest.mark.parametrize("change", ["config", "new_source", "missing_source", "linked_source"])
def test_dsr_binding_rejects_config_and_source_topology_movement(release_recipe, binding_tree, change):
    root, config, _git = binding_tree
    frozen = release_recipe.snapshot_build_inputs(root, [config])
    source = root / "crates/example/src/lib.rs"
    if change == "config":
        config.write_text("tools: {different: {}}\n")
    elif change == "new_source":
        source.with_name("new.rs").write_text("pub fn new() {}\n")
    elif change == "missing_source":
        source.rename(root / "retained-original.rs")  # Preserve every byte; no deletion.
    else:
        source.with_name("linked.rs").symlink_to(source)
    with pytest.raises(ValueError, match="moved|not a regular file"):
        release_recipe.require_same_inputs(root, frozen, [config])


@pytest.mark.parametrize("state", ["absent", "appeared", "linked"])
def test_dsr_binding_tracks_previously_absent_optional_configuration(release_recipe, binding_tree, state):
    root, config, _git = binding_tree
    optional = config.with_name("optional-cargo-config.toml")
    frozen = release_recipe.snapshot_build_inputs(root, [config, optional])
    assert frozen["configs"][str(optional)] is None
    if state == "absent":
        release_recipe.require_same_inputs(root, frozen, [config, optional])
    else:
        if state == "appeared":
            optional.write_text("[build]\njobs = 1\n")
        else:
            optional.symlink_to(config)
        with pytest.raises(ValueError, match="moved|not a regular file"):
            release_recipe.require_same_inputs(root, frozen, [config, optional])


def test_dsr_configuration_inventory_includes_missing_ancestor_and_cargo_home_paths(release_recipe, binding_tree):
    root, config, _git = binding_tree
    dsr_home = config.parent / "dsr-home"
    cargo_home = config.parent / "cargo-home"
    paths = release_recipe.build_configuration_paths(root, dsr_home, cargo_home, config)
    assert config in paths
    assert dsr_home / "repos.d/franken_networkx.yaml" in paths
    assert root / ".cargo/config.toml" in paths
    assert root.parent / ".cargo/config" in paths
    assert cargo_home / "config.toml" in paths
    assert len(paths) == len(set(paths))


def test_dsr_binding_excludes_only_declared_non_build_coordination(release_recipe, binding_tree):
    root, config, _git = binding_tree
    frozen = release_recipe.snapshot_build_inputs(root, [config])
    coordination = root / ".beads/issues.jsonl"
    coordination.parent.mkdir()
    coordination.write_text('{"id":"fixture-coordination"}\n')
    release_recipe.require_same_inputs(root, frozen, [config])
    assert frozen["scope"] == "release-build-inputs"  # Not full-suite authority.


@pytest.mark.parametrize("external", [False, True])
def test_dsr_dependency_graph_binds_internal_paths_and_refuses_unbound_paths(release_recipe, binding_tree, external):
    root, config, _git = binding_tree
    manifest = root / "crates/example/Cargo.toml"
    if external:
        manifest = config.with_name("external-Cargo.toml")
        manifest.write_text("[package]\nname = 'external'\n")
    metadata = {"packages": [{"id": "fixture-path-id", "name": "example", "version": "1.0.0",
                              "source": None, "manifest_path": str(manifest)}],
                "resolve": {"nodes": [{"id": "fixture-path-id", "features": ["b", "a"], "dependencies": []}]}}
    if external:
        with pytest.raises(ValueError, match="unbound out-of-tree dependency"):
            release_recipe.normalized_dependency_graph(root, metadata)
    else:
        graph = release_recipe.normalized_dependency_graph(root, metadata)
        assert graph["packages"] == ["example@1.0.0::path:crates/example/Cargo.toml"]
        assert graph["nodes"][0]["features"] == ["a", "b"]


@pytest.fixture
def artifact_binding(release_recipe, binding_tree, tmp_path):
    root, config, _git = binding_tree
    # Explicit synthetic archive bytes for checker tests; never imported.
    wheel = tmp_path / "controlled.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("franken_networkx/_fnx.abi3.so", b"controlled-native-bytes")
        archive.writestr("franken_networkx/__init__.py", b"# controlled Python bytes\n")
    native = tmp_path / "fnx-extension"
    native.write_bytes(b"controlled-native-bytes")
    sdist = tmp_path / "controlled.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        entry = tarfile.TarInfo("controlled/source.txt")
        data = b"controlled source bytes\n"
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    candidate = {"inputs": release_recipe.snapshot_build_inputs(root, [config]),
                 "graphs": {"fixture-target": {"packages": ["fixture"], "nodes": []}},
                 "maturin": "fixture-build-tool", "rustc": "fixture-toolchain", "cargo": "fixture-cargo",
                 "build_environment": {}}
    identity = release_recipe._json_hash(candidate)
    records = [release_recipe.bind_artifact(path, kind, identity)
               for path, kind in [(wheel, "wheel"), (native, "native"), (sdist, "sdist")]]
    return {"schema": "fnx-dsr-build-binding-v1", "candidate": candidate,
            "candidate_id": identity, "artifacts": records}


def test_dsr_artifact_binding_joins_actual_archive_and_payload_bytes(release_recipe, artifact_binding):
    release_recipe.verify_artifact_binding(artifact_binding)
    release_recipe.verify_artifact_binding(json.loads(json.dumps(artifact_binding)))
    wheel, native, sdist = artifact_binding["artifacts"]
    assert wheel["native_sha256"] == native["sha256"]
    assert all(record["sha256"] == _sha256(Path(record["path"])) for record in [wheel, native, sdist])


@pytest.mark.parametrize("kind", ["wheel", "native", "sdist"])
def test_dsr_old_binding_cannot_accept_replaced_artifact_bytes(release_recipe, artifact_binding, kind):
    record = next(record for record in artifact_binding["artifacts"] if record["kind"] == kind)
    path = Path(record["path"])
    if kind == "wheel":
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("unexpected.py", b"different package bytes\n")
    else:
        with path.open("ab") as stream:
            stream.write(b"different artifact bytes")
    with pytest.raises(ValueError, match="candidate artifact mismatch"):
        release_recipe.verify_artifact_binding(artifact_binding)


@pytest.mark.parametrize("field", ["inputs", "graphs", "maturin", "rustc", "cargo", "build_environment"])
def test_dsr_binding_refuses_missing_required_candidate_field(release_recipe, artifact_binding, field):
    candidate = artifact_binding["candidate"]
    candidate.pop(field)
    artifact_binding["candidate_id"] = release_recipe._json_hash(candidate)
    with pytest.raises(ValueError, match="missing|required|invalid"):
        release_recipe.verify_artifact_binding(artifact_binding)


@pytest.mark.parametrize("field", ["sha256", "path", "native_sha256", "python_members", "candidate_id"])
def test_dsr_binding_refuses_missing_artifact_fields(release_recipe, artifact_binding, field):
    artifact_binding["artifacts"][0].pop(field)
    with pytest.raises(ValueError, match="missing|mismatch|different candidate"):
        release_recipe.verify_artifact_binding(artifact_binding)


def test_dsr_payload_must_come_from_one_bound_wheel(release_recipe, artifact_binding):
    record = next(record for record in artifact_binding["artifacts"] if record["kind"] == "native")
    Path(record["path"]).write_bytes(b"unrelated native build")
    record["sha256"] = _sha256(Path(record["path"]))
    with pytest.raises(ValueError, match="native payload does not join"):
        release_recipe.verify_artifact_binding(artifact_binding)


@pytest.mark.parametrize("wrong", ["python", "prefix"])
def test_dsr_loaded_verifier_refuses_a_different_selected_interpreter_before_import(release_recipe, artifact_binding, wrong):
    python = sys.executable + "-other" if wrong == "python" else sys.executable
    prefix = sys.prefix + "-other" if wrong == "prefix" else sys.prefix
    with pytest.raises(ValueError, match="interpreter/venv mismatch"):
        release_recipe.verify_loaded_candidate(artifact_binding, python, prefix,
                                                artifact_binding["artifacts"][0]["path"], "3.6.1")
