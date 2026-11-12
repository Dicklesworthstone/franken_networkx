"""br-r37-c1-tki2w: regression tests for connected_double_edge_swap guard order.

nx applies decorators in reverse declaration order; ``@not_implemented_for("directed")``
fires before the function body. fnx previously checked node count first, so
a 3-node DiGraph got "Graph has fewer than four nodes" (NetworkXError)
rather than nx's "not implemented for directed type" (NetworkXNotImplemented).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


def test_three_node_digraph_raises_not_implemented():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.connected_double_edge_swap(g)


def test_four_node_digraph_raises_not_implemented():
    g = fnx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        g.add_edge(u, v)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.connected_double_edge_swap(g)


def test_empty_digraph_raises_not_implemented_first():
    """Even an empty DiGraph should hit the directed guard first
    (which matches nx — the @not_implemented_for decorator runs before
    the function body's empty-graph check)."""
    g = fnx.DiGraph()
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.connected_double_edge_swap(g)


def test_three_node_undirected_still_raises_fewer_than_four():
    """Undirected branch unchanged."""
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXError, match="fewer than four"):
        fnx.connected_double_edge_swap(g)


def test_empty_undirected_still_raises_pointless_concept():
    g = fnx.Graph()
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.connected_double_edge_swap(g)
