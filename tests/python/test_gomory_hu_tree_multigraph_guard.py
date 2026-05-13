"""br-r37-c1-yj4b3: regression tests for gomory_hu_tree multigraph guard.

nx rejects MultiGraph/MultiDiGraph explicitly with NetworkXError
('MultiGraph and MultiDiGraph not supported (yet).') before any
capacity check. fnx's wrapper previously fell through to the
infinite-capacity check on MultiGraph and surfaced NetworkXUnbounded
— wrong error class.
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


def test_multigraph_raises_networkx_error_not_unbounded():
    g = fnx.MultiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXError, match="MultiGraph"):
        fnx.gomory_hu_tree(g)


def test_multigraph_with_capacities_still_rejected_first():
    """Even with explicit capacities, MultiGraph should be rejected
    before any capacity-related check fires."""
    g = fnx.MultiGraph()
    g.add_edge(0, 1, capacity=5)
    g.add_edge(1, 2, capacity=5)
    with pytest.raises(fnx.NetworkXError, match="MultiGraph"):
        fnx.gomory_hu_tree(g)


def test_directed_still_rejected_first():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.gomory_hu_tree(g)


@needs_nx
def test_matches_nx_exception_class_on_multigraph():
    fg = fnx.MultiGraph()
    fg.add_edge(0, 1)
    ng = nx.MultiGraph()
    ng.add_edge(0, 1)
    with pytest.raises(nx.NetworkXError):
        nx.gomory_hu_tree(ng)
    with pytest.raises(fnx.NetworkXError):
        fnx.gomory_hu_tree(fg)


def test_simple_undirected_with_capacities_still_works():
    g = fnx.Graph()
    g.add_edge(0, 1, capacity=2)
    g.add_edge(1, 2, capacity=3)
    g.add_edge(0, 2, capacity=1)
    tree = fnx.gomory_hu_tree(g)
    assert tree.number_of_nodes() == 3
