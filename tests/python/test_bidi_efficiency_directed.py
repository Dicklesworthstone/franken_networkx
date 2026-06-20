"""br-r37-c1-t2gyx: regression tests for bidirectional_shortest_path
and efficiency directed-graph handling."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_bidirectional_shortest_path_digraph_matches_nx():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 3)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.bidirectional_shortest_path(g, 0, 3) == nx.bidirectional_shortest_path(gx, 0, 3)


@needs_nx
def test_bidirectional_shortest_path_multidigraph_matches_nx():
    g = fnx.MultiDiGraph()
    gx = nx.MultiDiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.bidirectional_shortest_path(g, 0, 2) == nx.bidirectional_shortest_path(gx, 0, 2)


@needs_nx
def test_bidirectional_shortest_path_multigraph_tiebreak_matches_nx():
    g = fnx.MultiGraph()
    gx = nx.MultiGraph()
    for edge in [("s", "a"), ("s", "b"), ("b", "t"), ("a", "t"), ("s", "a")]:
        g.add_edge(*edge)
        gx.add_edge(*edge)

    assert fnx.bidirectional_shortest_path(g, "s", "t") == (
        nx.bidirectional_shortest_path(gx, "s", "t")
    )
    assert fnx.shortest_path(g, "s", "t") == nx.shortest_path(gx, "s", "t")


def test_bidirectional_shortest_path_undirected_unchanged():
    g = fnx.path_graph(5)
    assert fnx.bidirectional_shortest_path(g, 0, 4) == [0, 1, 2, 3, 4]


def test_efficiency_directed_raises():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.efficiency(g, 0, 2)


def test_efficiency_multidigraph_raises():
    g = fnx.MultiDiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.efficiency(g, 0, 2)


def test_efficiency_undirected_still_works():
    g = fnx.path_graph(3)
    assert fnx.efficiency(g, 0, 2) == 0.5  # 1 / distance(0,2)=2
