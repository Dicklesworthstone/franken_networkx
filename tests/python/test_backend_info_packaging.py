"""Packaging guard for NetworkX backend-info metadata."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import networkx as nx
import franken_networkx as fnx

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


def test_readme_core_generators_dispatch_through_networkx_backend():
    generator_cases = [
        ("path_graph", (5,), {}, 5, 4),
        ("cycle_graph", (5,), {}, 5, 5),
        ("star_graph", (4,), {}, 5, 4),
        ("complete_graph", (4,), {}, 4, 6),
        ("empty_graph", (3,), {}, 3, 0),
        ("gnp_random_graph", (6, 0.4), {"seed": 7}, 6, None),
        ("watts_strogatz_graph", (8, 2, 0.25), {"seed": 7}, 8, None),
        ("barabasi_albert_graph", (8, 2), {"seed": 7}, 8, None),
    ]
    for name, args, kwargs, expected_nodes, expected_edges in generator_cases:
        assert "franken_networkx" in getattr(nx, name).backends
        generated = getattr(nx, name)(*args, backend="franken_networkx", **kwargs)
        assert isinstance(generated, (nx.Graph, fnx.Graph))
        assert generated.number_of_nodes() == expected_nodes
        if expected_edges is not None:
            assert generated.number_of_edges() == expected_edges
