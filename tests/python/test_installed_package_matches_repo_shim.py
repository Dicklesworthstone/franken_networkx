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
import site
import stat
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
