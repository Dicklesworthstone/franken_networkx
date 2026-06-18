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


def test_complete_graph_has_no_selfloops():
    # complete_graph(n) is simple -> no self-loops.
    for n in (3, 4, 5):
        assert fnx.number_of_selfloops(fnx.complete_graph(n)) == 0
