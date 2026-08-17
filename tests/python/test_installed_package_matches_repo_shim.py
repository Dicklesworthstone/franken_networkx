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
import site
import sys
from pathlib import Path

import pytest

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
