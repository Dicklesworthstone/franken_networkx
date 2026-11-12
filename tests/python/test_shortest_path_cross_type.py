"""br-r37-c1-phy2p: regression — shortest-path family accepts nx graph
args via boundary coercion. Continues the cross-type sweep from
br-r37-c1-i2uub (union), jwdzp (diff/iso/GED), 9rd4z (power/vf2pp).

Affected: shortest_path, dijkstra_path, bellman_ford_path, astar_path.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_weighted_graph(cls):
    g = cls()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=2)
    g.add_edge(0, 2, weight=10)
    return g


@needs_nx
def test_shortest_path_accepts_nx_graph():
    ng = _make_weighted_graph(nx.Graph)
    assert fnx.shortest_path(ng, 0, 2) == [0, 2]  # unweighted: direct edge


@needs_nx
def test_shortest_path_accepts_nx_graph_weighted():
    ng = _make_weighted_graph(nx.Graph)
    assert fnx.shortest_path(ng, 0, 2, weight="weight") == [0, 1, 2]


@needs_nx
def test_dijkstra_path_accepts_nx_graph():
    ng = _make_weighted_graph(nx.Graph)
    assert fnx.dijkstra_path(ng, 0, 2, weight="weight") == [0, 1, 2]


@needs_nx
def test_bellman_ford_path_accepts_nx_graph():
    ng = _make_weighted_graph(nx.Graph)
    assert fnx.bellman_ford_path(ng, 0, 2, weight="weight") == [0, 1, 2]


@needs_nx
def test_astar_path_accepts_nx_graph():
    ng = _make_weighted_graph(nx.Graph)
    assert fnx.astar_path(ng, 0, 2, weight="weight") == [0, 1, 2]


@needs_nx
def test_shortest_path_no_regression_fnx_input():
    """Same-type call still works."""
    fg = _make_weighted_graph(fnx.Graph)
    assert fnx.shortest_path(fg, 0, 2, weight="weight") == [0, 1, 2]
    assert fnx.dijkstra_path(fg, 0, 2, weight="weight") == [0, 1, 2]


@needs_nx
def test_shortest_path_nx_digraph():
    ng = nx.DiGraph()
    ng.add_edge(0, 1, weight=1)
    ng.add_edge(1, 2, weight=1)
    assert fnx.shortest_path(ng, 0, 2) == [0, 1, 2]


@needs_nx
def test_dijkstra_path_nx_missing_node():
    """The pre-existing NodeNotFound contract survives the coercion."""
    ng = nx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        fnx.dijkstra_path(ng, 99, 0)
