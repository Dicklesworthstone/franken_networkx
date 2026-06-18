"""Packaging guard for NetworkX backend-info metadata."""

from __future__ import annotations

import os
import subprocess
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


def _backend_registered_with_networkx() -> bool:
    """True when the installed entry_points actually registered fnx with nx.

    bd-devh2: the backend-info entry point must load before
    ``franken_networkx`` itself, while NetworkX is still importing. If
    the installed wheel is stale, nx may fail to register fnx as a
    backend or may trip the import-cycle guard below.
    """
    try:
        return "franken_networkx" in nx.path_graph.backends
    except (AttributeError, TypeError):
        return False


_needs_registered_backend = pytest.mark.skipif(
    not _backend_registered_with_networkx(),
    reason=(
        "fnx is not registered with the running nx dispatcher — most "
        "likely a stale installed wheel has the wrong backend_info "
        "entry point. Rebuild the wheel via 'maturin develop' or "
        "'pip install -e .' to re-link fnx_backend_info."
    ),
)


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
    # bd-devh2: NetworkX loads backend_info entry points while
    # networkx.__init__ is still partially initialized. A package-local
    # target imports franken_networkx.__init__ first and can panic while
    # the PyO3 extension imports nx exceptions. Keep this as a top-level
    # module that does not import franken_networkx or networkx.
    assert _backend_info_entry_point() == "fnx_backend_info:get_backend_info"
    assert (ROOT / "python" / "fnx_backend_info.py").is_file()


def test_backend_info_module_loads_and_exports_get_backend_info():
    # Import the top-level backend_info module and confirm its
    # get_backend_info() contract still holds without importing the
    # franken_networkx package.
    import fnx_backend_info as _bi

    info = _bi.get_backend_info()
    assert info["short_summary"]
    assert "shortest_path" in info["functions"]


def test_backend_info_modules_star_export_public_entrypoint():
    import fnx_backend_info as top_level_info
    import franken_networkx.backend_info as package_info

    for module in (top_level_info, package_info):
        assert module.__all__ == ["get_backend_info"]
        namespace = {}
        exec(f"from {module.__name__} import *", namespace)
        assert namespace["get_backend_info"] is module.get_backend_info
        assert "_supported_algorithm_names" not in namespace


def test_backend_module_star_exports_dispatch_surface():
    assert set(fnx_backend.__all__) == {
        "BackendInterface",
        "backend_interface",
        "get_backend_info",
    }
    namespace = {}
    exec("from franken_networkx.backend import *", namespace)
    assert namespace["BackendInterface"] is fnx_backend.BackendInterface
    assert namespace["backend_interface"] is fnx_backend.backend_interface
    assert namespace["get_backend_info"] is fnx_backend.get_backend_info
    assert "_SUPPORTED_ALGORITHMS" not in namespace


def test_networkx_imports_before_franken_networkx_backend_package():
    env = os.environ.copy()
    python_path = str(ROOT / "python")
    env["PYTHONPATH"] = (
        python_path
        if not env.get("PYTHONPATH")
        else python_path + os.pathsep + env["PYTHONPATH"]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import networkx as nx; assert 'franken_networkx' in nx.path_graph.backends",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@_needs_registered_backend
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


@_needs_registered_backend
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
