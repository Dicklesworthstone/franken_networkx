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


def test_helpers_reject_differences():
    """nodes_equal and edges_equal are only ever handed IDENTICAL lists above.

    Both are called as `helper(list(g1...), list(g2...))` on graphs built the
    same way, so a helper that returned True unconditionally passes every
    existing assertion. These are the false cases.
    """
    assert nodes_equal([1, 2, 3], [1, 2]) is False        # different length
    assert nodes_equal([1, 2], [1, 3]) is False           # different member
    assert edges_equal([(0, 1)], [(0, 2)]) is False
    assert edges_equal([(0, 1), (1, 2)], [(0, 1)]) is False


def test_helpers_ignore_order():
    """Order-insensitivity is why these helpers exist instead of `==`."""
    assert nodes_equal([1, 2, 3], [3, 1, 2]) is True
    assert edges_equal([(0, 1), (1, 2)], [(1, 2), (0, 1)]) is True
    # On an undirected edge list the endpoint order is not significant either.
    assert edges_equal([(0, 1)], [(1, 0)]) is True


def test_edges_equal_compares_edge_data():
    """The 3-tuple form carries attributes and is a separate comparison path."""
    assert edges_equal([(0, 1, {"w": 1})], [(0, 1, {"w": 1})]) is True
    assert edges_equal([(0, 1, {"w": 1})], [(0, 1, {"w": 2})]) is False


def test_different_graph_types_are_not_equal():
    """The module docstring claims this and nothing asserted it."""
    undirected = fnx.Graph([(0, 1)])
    directed = fnx.DiGraph([(0, 1)])
    multi = fnx.MultiGraph([(0, 1)])

    assert graphs_equal(undirected, directed) is False
    assert graphs_equal(undirected, multi) is False


def test_node_and_graph_attributes_break_equality():
    """Only EDGE attributes were covered; a graph carries two more attribute maps."""
    red = fnx.Graph(); red.add_node(0, colour="red"); red.add_edge(0, 1)
    blue = fnx.Graph(); blue.add_node(0, colour="blue"); blue.add_edge(0, 1)
    assert graphs_equal(red, blue) is False

    named_x = fnx.Graph([(0, 1)]); named_x.graph["name"] = "x"
    named_y = fnx.Graph([(0, 1)]); named_y.graph["name"] = "y"
    assert graphs_equal(named_x, named_y) is False

    # ...and the same values still compare equal, so the checks above are not
    # simply reporting False for everything.
    same = fnx.Graph([(0, 1)]); same.graph["name"] = "x"
    assert graphs_equal(named_x, same) is True
