"""Graph-equality utility semantics (graphs_equal / nodes_equal / edges_equal).

These comparison utilities must behave as equality predicates:
  - reflexive: graphs_equal(G, G) is True;
  - two graphs built from the same nodes/edges are equal;
  - changing any node or edge breaks equality;
  - graphs of different types are not equal;
  - attribute differences break equality.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
from franken_networkx.utils import graphs_equal, nodes_equal, edges_equal
import franken_networkx as fnx


def _pair(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g1 = fnx.Graph(); g1.add_nodes_from(range(n)); g1.add_edges_from(edges)
    g2 = fnx.Graph(); g2.add_nodes_from(range(n)); g2.add_edges_from(edges)
    return g1, g2, n, edges


@pytest.mark.parametrize("seed", range(30))
def test_equal_graphs_and_reflexivity(seed):
    g1, g2, n, edges = _pair(seed)
    assert graphs_equal(g1, g1)            # reflexive
    assert graphs_equal(g1, g2)            # same construction -> equal
    assert nodes_equal(list(g1.nodes()), list(g2.nodes()))
    assert edges_equal(list(g1.edges()), list(g2.edges()))


@pytest.mark.parametrize("seed", range(30))
def test_modification_breaks_equality(seed):
    g1, g2, n, edges = _pair(seed)
    non_edges = [(u, v) for u in range(n) for v in range(u + 1, n) if not g2.has_edge(u, v)]
    if non_edges:
        g3 = g2.copy()
        g3.add_edge(*non_edges[0])
        assert not graphs_equal(g1, g3)    # an extra edge -> not equal
    g4 = g2.copy()
    g4.add_node("extra")
    assert not graphs_equal(g1, g4)        # an extra node -> not equal


def test_attribute_difference_breaks_equality():
    a = fnx.Graph(); a.add_edge(0, 1, weight=1)
    b = fnx.Graph(); b.add_edge(0, 1, weight=2)
    assert not graphs_equal(a, b)          # same structure, different edge attr

    c = fnx.Graph(); c.add_edge(0, 1, weight=1)
    assert graphs_equal(a, c)
