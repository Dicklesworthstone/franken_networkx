"""Packaging guard for NetworkX backend-info metadata."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


ROOT = Path(__file__).resolve().parents[2]


def _maturin_include_paths() -> set[str]:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is None:
        return {"fnx_backend_info.py"} if 'include = ["fnx_backend_info.py"]' in pyproject_text else set()
    pyproject = tomllib.loads(pyproject_text)
    include = pyproject["tool"]["maturin"].get("include", [])
    paths = set()
    for entry in include:
        if isinstance(entry, str):
            paths.add(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.add(entry["path"])
    return paths


def test_fnx_backend_info_is_explicitly_included_for_maturin():
    assert "fnx_backend_info.py" in _maturin_include_paths()
    assert (ROOT / "python" / "fnx_backend_info.py").is_file()


def test_fnx_backend_info_loads_without_importing_package():
    sys.modules.pop("franken_networkx", None)
    module_path = ROOT / "python" / "fnx_backend_info.py"
    module_globals = runpy.run_path(str(module_path), run_name="fnx_backend_info_under_test")

    assert "franken_networkx" not in sys.modules
    info = module_globals["get_backend_info"]()
    assert info["short_summary"]
    assert "shortest_path" in info["functions"]
