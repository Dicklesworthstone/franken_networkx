"""Packaging guard for NetworkX backend-info metadata."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import networkx as nx
import franken_networkx as fnx
import franken_networkx.backend as fnx_backend
import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


ROOT = Path(__file__).resolve().parents[2]


def _backend_info_entry_point() -> str:
    """Return the configured entry-point string for the networkx.backend_info group."""
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is None:
        # Pre-3.11 fallback: regex out the line we care about.
        import re
        m = re.search(
            r"\[project\.entry-points\.\"networkx\.backend_info\"\][^\[]*?"
            r"franken_networkx\s*=\s*\"([^\"]+)\"",
            pyproject_text,
            re.DOTALL,
        )
        return m.group(1) if m else ""
    pyproject = tomllib.loads(pyproject_text)
    return (
        pyproject.get("project", {})
        .get("entry-points", {})
        .get("networkx.backend_info", {})
        .get("franken_networkx", "")
    )


def test_backend_info_entry_point_targets_package_module():
    # br-r37-c1-opu0s: backend-info metadata lives at
    # franken_networkx.backend_info (br-r37-c1-bocpu); the previous
    # top-level python/fnx_backend_info.py shim was never installed
    # into the wheel and triggered an nx RuntimeWarning at import.
    assert _backend_info_entry_point() == "franken_networkx.backend_info:get_backend_info"
    assert (ROOT / "python" / "franken_networkx" / "backend_info.py").is_file()


def test_backend_info_module_loads_and_exports_get_backend_info():
    # Import the package-local backend_info module and confirm its
    # get_backend_info() contract still holds.
    from franken_networkx import backend_info as _bi
    info = _bi.get_backend_info()
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


def test_readme_dispatchable_io_conversion_helpers_dispatch_through_backend(tmp_path):
    np = pytest.importorskip("numpy")
    scipy_sparse = pytest.importorskip("scipy.sparse")

    edge_path = tmp_path / "edges.txt"
    edge_path.write_text("1 2\n2 3\n", encoding="utf-8")
    adj_path = tmp_path / "adj.txt"
    adj_path.write_text("1 2 3\n2 3\n", encoding="utf-8")
    graphml_path = tmp_path / "graph.graphml"
    nx.write_graphml(nx.path_graph(3), graphml_path)

    graph_cases = [
        ("read_edgelist", (edge_path,), {"nodetype": int}, 3, 2),
        ("read_adjlist", (adj_path,), {"nodetype": int}, 3, 3),
        ("read_graphml", (graphml_path,), {}, 3, 2),
        (
            "node_link_graph",
            (nx.node_link_data(nx.path_graph(3), edges="links"),),
            {"edges": "links"},
            3,
            2,
        ),
        ("from_numpy_array", (np.eye(3),), {}, 3, 3),
        ("from_scipy_sparse_array", (scipy_sparse.eye(3, format="csr"),), {}, 3, 3),
        ("from_dict_of_dicts", ({0: {1: {}}, 1: {2: {}}, 2: {}},), {}, 3, 2),
        ("from_dict_of_lists", ({0: [1], 1: [2], 2: []},), {}, 3, 2),
        ("from_edgelist", ([(0, 1), (1, 2)],), {}, 3, 2),
        ("convert_node_labels_to_integers", (nx.path_graph(["a", "b", "c"]),), {}, 3, 2),
    ]
    for name, args, kwargs, expected_nodes, expected_edges in graph_cases:
        assert "franken_networkx" in getattr(nx, name).backends
        generated = getattr(nx, name)(*args, backend="franken_networkx", **kwargs)
        assert isinstance(generated, (nx.Graph, fnx.Graph))
        assert generated.number_of_nodes() == expected_nodes
        assert generated.number_of_edges() == expected_edges

    path = nx.path_graph(3)
    array = nx.to_numpy_array(path, backend="franken_networkx")
    assert array.shape == (3, 3)
    assert array.sum() == 4

    sparse_array = nx.to_scipy_sparse_array(path, backend="franken_networkx")
    assert sparse_array.shape == (3, 3)
    assert sparse_array.nnz == 4

    assert nx.to_dict_of_lists(path, backend="franken_networkx") == {
        0: [1],
        1: [0, 2],
        2: [1],
    }
    assert sorted(nx.to_edgelist(path, backend="franken_networkx")) == [
        (0, 1, {}),
        (1, 2, {}),
    ]


def test_readme_non_dispatchable_helpers_stay_out_of_backend_registry():
    non_dispatchable = [
        "write_edgelist",
        "write_adjlist",
        "write_graphml",
        "node_link_data",
        "to_dict_of_dicts",
    ]
    info = fnx_backend.get_backend_info()
    for name in non_dispatchable:
        assert not hasattr(getattr(nx, name), "backends")
        assert name not in info["functions"]
