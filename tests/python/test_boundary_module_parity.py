"""br-r37-c1-oxb5n: boundary submodule import parity."""

from __future__ import annotations

import importlib
import inspect
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def _boundary_pair(seed, *, directed):
    rng = random.Random(seed)
    f_graph = fnx.DiGraph() if directed else fnx.Graph()
    n_graph = nx.DiGraph() if directed else nx.Graph()
    f_graph.add_nodes_from(range(7))
    n_graph.add_nodes_from(range(7))
    pairs = (
        ((u, v) for u in range(7) for v in range(7) if u != v)
        if directed
        else ((u, v) for u in range(7) for v in range(u + 1, 7))
    )
    for u, v in pairs:
        if rng.random() < 0.34:
            attrs = {
                "weight": (seed + u * 11 + v * 7) % 13,
                "label": f"{seed}:{u}->{v}",
            }
            f_graph.add_edge(u, v, **attrs)
            n_graph.add_edge(u, v, **attrs)
    return f_graph, n_graph


def test_boundary_module_is_directly_importable():
    module = importlib.import_module("franken_networkx.boundary")

    _expect(module.edge_boundary is fnx.edge_boundary, "edge_boundary should use fnx wrapper")
    _expect(module.node_boundary is fnx.node_boundary, "node_boundary should use fnx wrapper")


def test_boundary_module_public_surface_matches_networkx():
    fnx_boundary = importlib.import_module("franken_networkx.boundary")
    nx_boundary = importlib.import_module("networkx.algorithms.boundary")

    nx_public = {name for name in dir(nx_boundary) if not name.startswith("_")}
    fnx_public = {name for name in dir(fnx_boundary) if not name.startswith("_")}

    missing = nx_public - fnx_public
    _expect(not missing, f"franken_networkx.boundary missing {sorted(missing)}")


def test_boundary_module_signatures_match_networkx():
    fnx_boundary = importlib.import_module("franken_networkx.boundary")
    nx_boundary = importlib.import_module("networkx.algorithms.boundary")

    for name in ("edge_boundary", "node_boundary"):
        fnx_view = str(inspect.signature(getattr(fnx_boundary, name)))
        nx_view = str(inspect.signature(getattr(nx_boundary, name)))
        _expect(fnx_view == nx_view, f"{name}: fnx {fnx_view} != nx {nx_view}")


def test_boundary_module_functions_match_networkx_values():
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    _expect(
        list(fnx.boundary.edge_boundary(fnx_graph, [0, 1]))
        == list(nx.edge_boundary(nx_graph, [0, 1])),
        "edge_boundary values should match NetworkX",
    )
    _expect(
        fnx.boundary.node_boundary(fnx_graph, [0, 1])
        == nx.node_boundary(nx_graph, [0, 1]),
        "node_boundary values should match NetworkX",
    )


def test_algorithms_boundary_path_uses_fnx_module():
    direct = importlib.import_module("franken_networkx.boundary")
    through_algorithms = importlib.import_module("franken_networkx.algorithms.boundary")

    _expect(through_algorithms is direct, "algorithms.boundary should use the fnx module")
    _expect(
        list(through_algorithms.edge_boundary(fnx.path_graph(5), [0, 1]))
        == list(nx.edge_boundary(nx.path_graph(5), [0, 1])),
        "algorithms.boundary should match NetworkX values",
    )


def test_node_boundary_goldens():
    graph = fnx.path_graph(5)
    digraph = fnx.DiGraph([(0, 1), (2, 0), (0, 3), (3, 4)])

    assert fnx.boundary.node_boundary(graph, [0, 1]) == {2}
    assert fnx.boundary.node_boundary(graph, [0, 1], [3, 4]) == set()
    assert fnx.boundary.node_boundary(graph, []) == set()
    assert fnx.boundary.node_boundary(digraph, [0]) == {1, 3}


def test_edge_boundary_goldens():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=7)
    graph.add_edge(1, 2)
    graph.add_edge(1, 3, weight=5)
    digraph = fnx.DiGraph([(0, 1), (2, 0), (0, 3), (3, 4)])

    assert list(fnx.boundary.edge_boundary(graph, [0, 1])) == [(1, 2), (1, 3)]
    assert list(
        fnx.boundary.edge_boundary(graph, [0, 1], data="weight", default=-1)
    ) == [(1, 2, -1), (1, 3, 5)]
    assert list(fnx.boundary.edge_boundary(digraph, [0])) == [(0, 1), (0, 3)]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(12))
def test_node_boundary_random_differential_matches_networkx(directed, seed):
    f_graph, n_graph = _boundary_pair(seed, directed=directed)
    source_nodes = {node for node in f_graph if (node + seed) % 3 == 0}
    target_nodes = {node for node in f_graph if (node + seed) % 2 == 0}

    assert fnx.boundary.node_boundary(f_graph, source_nodes) == nx.node_boundary(
        n_graph, source_nodes
    )
    assert fnx.boundary.node_boundary(
        f_graph, source_nodes, target_nodes
    ) == nx.node_boundary(n_graph, source_nodes, target_nodes)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize(
    ("data", "default"),
    [(False, None), (True, None), ("weight", -1)],
)
def test_edge_boundary_random_differential_matches_networkx(directed, seed, data, default):
    f_graph, n_graph = _boundary_pair(seed, directed=directed)
    source_nodes = {node for node in f_graph if (node + seed) % 3 == 0}
    target_nodes = {node for node in f_graph if (node + seed) % 2 == 0}
    kwargs = {"data": data}
    if default is not None:
        kwargs["default"] = default

    assert list(fnx.boundary.edge_boundary(f_graph, source_nodes, **kwargs)) == list(
        nx.edge_boundary(n_graph, source_nodes, **kwargs)
    )
    assert list(
        fnx.boundary.edge_boundary(f_graph, source_nodes, target_nodes, **kwargs)
    ) == list(nx.edge_boundary(n_graph, source_nodes, target_nodes, **kwargs))
