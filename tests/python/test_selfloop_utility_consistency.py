"""Self-loop utility consistency (number_of_selfloops / selfloop_edges / ...).

The self-loop utilities must agree with each other and with the adjacency:
  - number_of_selfloops(G) == len(list(selfloop_edges(G)));
  - for a simple graph == len(list(nodes_with_selfloops(G)));
  - every selfloop edge is (v, v);
  - nodes_with_selfloops(G) == {v : G.has_edge(v, v)};
  - removing the self-loop edges leaves number_of_selfloops == 0.
These utilities have many internal callers, so their mutual consistency matters.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph_with_selfloops(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    g = fnx.Graph(); g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u, n):  # u == v allows a self-loop
            if r.random() < 0.3:
                g.add_edge(u, v)
    return g


@pytest.mark.parametrize("seed", range(40))
def test_selfloop_counts_agree(seed):
    g = _graph_with_selfloops(seed)
    nsl = fnx.number_of_selfloops(g)
    edges = list(fnx.selfloop_edges(g))
    nodes = list(fnx.nodes_with_selfloops(g))

    assert nsl == len(edges)
    assert nsl == len(nodes)                        # simple graph: 1 loop per node
    assert all(u == v for u, v in edges)            # each is (v, v)
    assert set(nodes) == {v for v in g if g.has_edge(v, v)}


@pytest.mark.parametrize("seed", range(40))
def test_removing_selfloops_zeroes_the_count(seed):
    g = _graph_with_selfloops(seed)
    h = g.copy()
    h.remove_edges_from(list(fnx.selfloop_edges(h)))
    assert fnx.number_of_selfloops(h) == 0
    assert list(fnx.nodes_with_selfloops(h)) == []
    # Zeroing the count is also achieved by removing EVERY edge, so pin that the
    # removal took the loops and nothing else.
    assert {frozenset((u, v)) for u, v in h.edges()} == {
        frozenset((u, v)) for u, v in g.edges() if u != v
    }
    assert set(h.nodes()) == set(g.nodes())


@pytest.mark.parametrize("seed", range(30))
def test_multigraph_counts_loops_with_multiplicity(seed):
    """On a MultiGraph one node can carry several loops, so the two counts differ.

    The docstring above says "for a simple graph" about that equality; this is
    the case where the caveat bites, and it was never exercised.
    """
    r = random.Random(seed)
    n = r.randint(4, 9)
    m = fnx.MultiGraph(); m.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u, n):
            for _ in range(r.randint(0, 2)):
                m.add_edge(u, v)

    nsl = fnx.number_of_selfloops(m)
    assert nsl == len(list(fnx.selfloop_edges(m)))        # counts multiplicity
    # Per NODE, not per loop — so this is an inequality here, not an equality.
    assert nsl >= len(list(fnx.nodes_with_selfloops(m)))
    assert set(fnx.nodes_with_selfloops(m)) == {v for v in m if m.has_edge(v, v)}


def test_multigraph_counts_strictly_diverge_somewhere():
    """Guards the test above: `>=` is trivially true if they never differ."""
    m = fnx.MultiGraph(); m.add_edges_from([(0, 0), (0, 0), (1, 1), (2, 3)])
    assert fnx.number_of_selfloops(m) == 3
    assert len(list(fnx.nodes_with_selfloops(m))) == 2


@pytest.mark.parametrize("kwargs, expected", [
    ({}, [(0, 0), (1, 1)]),
    ({"data": True}, [(0, 0, {"w": 5}), (1, 1, {})]),
    ({"data": "w"}, [(0, 0, 5), (1, 1, None)]),
    ({"data": "w", "default": -1}, [(0, 0, 5), (1, 1, -1)]),
])
def test_selfloop_edges_data_variants(kwargs, expected):
    """data / default are separate code paths through the same utility."""
    g = fnx.Graph(); g.add_edge(0, 0, w=5); g.add_edge(1, 1); g.add_edge(2, 3)
    assert list(fnx.selfloop_edges(g, **kwargs)) == expected


def test_selfloop_edges_keys_on_multigraph():
    m = fnx.MultiGraph(); m.add_edges_from([(0, 0), (0, 0), (1, 1), (2, 3)])
    assert list(fnx.selfloop_edges(m, keys=True)) == [(0, 0, 0), (0, 0, 1), (1, 1, 0)]


def test_directed_selfloops():
    """A directed loop is one arc, counted once, and is its own reverse."""
    d = fnx.DiGraph(); d.add_edges_from([(0, 0), (1, 2), (2, 2)])
    assert fnx.number_of_selfloops(d) == 2
    assert list(fnx.selfloop_edges(d)) == [(0, 0), (2, 2)]
    assert set(fnx.nodes_with_selfloops(d)) == {0, 2}
    assert d.in_degree(0) == d.out_degree(0) == 1


def test_complete_graph_has_no_selfloops():
    # complete_graph(n) is simple -> no self-loops.
    for n in (3, 4, 5):
        assert fnx.number_of_selfloops(fnx.complete_graph(n)) == 0
