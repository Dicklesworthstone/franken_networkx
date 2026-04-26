"""Parity for ``ego_graph`` node iteration order.

Bead br-r37-c1-fauol. fnx.ego_graph constructed nodes_within as a set
and iterated in arbitrary hash order. nx.ego_graph uses
``G.subgraph(sp).copy()`` which iterates in G's original insertion
order (filtered to the ego set).

Drop-in code that iterates ``list(ego_graph(G, n, r).nodes())`` got
different orders.
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


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("radius", [1, 2, 3])
def test_ego_graph_node_order_matches_networkx(radius):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.ego_graph(g, "c", radius=radius).nodes())
    n = list(nx.ego_graph(gx, "c", radius=radius).nodes())
    assert f == n


@needs_nx
def test_ego_graph_center_false_node_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.ego_graph(g, "c", radius=2, center=False).nodes())
    n = list(nx.ego_graph(gx, "c", radius=2, center=False).nodes())
    assert f == n


@needs_nx
def test_ego_graph_path_graph_int_nodes():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=2).nodes())
    n = list(nx.ego_graph(gx, 2, radius=2).nodes())
    assert f == n == [0, 1, 2, 3, 4]


@needs_nx
def test_ego_graph_digraph_node_order():
    dg = fnx.DiGraph([(0, 1), (1, 2), (0, 3)])
    dgx = nx.DiGraph([(0, 1), (1, 2), (0, 3)])
    f = list(fnx.ego_graph(dg, 0, radius=2).nodes())
    n = list(nx.ego_graph(dgx, 0, radius=2).nodes())
    assert f == n == [0, 1, 2, 3]


@needs_nx
def test_ego_graph_undirected_kwarg_on_digraph():
    dg = fnx.DiGraph([(0, 1), (1, 2), (3, 0)])
    dgx = nx.DiGraph([(0, 1), (1, 2), (3, 0)])
    f = list(fnx.ego_graph(dg, 0, radius=1, undirected=True).nodes())
    n = list(nx.ego_graph(dgx, 0, radius=1, undirected=True).nodes())
    assert f == n


@needs_nx
def test_ego_graph_weighted_distance():
    g = fnx.Graph()
    gx = nx.Graph()
    g.add_edge("a", "b", weight=1)
    g.add_edge("b", "c", weight=2)
    gx.add_edge("a", "b", weight=1)
    gx.add_edge("b", "c", weight=2)
    f = list(fnx.ego_graph(g, "a", radius=2, distance="weight").nodes())
    n = list(nx.ego_graph(gx, "a", radius=2, distance="weight").nodes())
    assert f == n


@needs_nx
def test_ego_graph_edges_match_networkx():
    """Sanity: edges still match (not just nodes)."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=1).edges())
    n = list(nx.ego_graph(gx, 2, radius=1).edges())
    assert sorted(f) == sorted(n)


@needs_nx
def test_ego_graph_radius_zero_only_center():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=0).nodes())
    n = list(nx.ego_graph(gx, 2, radius=0).nodes())
    assert f == n == [2]
