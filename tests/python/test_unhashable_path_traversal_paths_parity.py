"""Parity for path-finding / traversal fns on unhashable source.

Bead br-r37-c1-c4agn (continuation of br-r37-c1-i9whv). Seven more
node-parameter functions raised the wrong exception class on
unhashable inputs:

  dijkstra_path             fnx: NodeNotFound  nx: TypeError
  bellman_ford_path         fnx: NodeNotFound  nx: TypeError
  node_connected_component  fnx: NodeNotFound  nx: TypeError
  bfs_edges                 fnx: NetworkXError nx: TypeError
  dfs_edges                 fnx: NetworkXError nx: TypeError
  dfs_tree                  fnx: NetworkXError nx: TypeError
  descendants_at_distance   fnx: NodeNotFound  nx: NetworkXError

The first six now hash-check up front and raise TypeError matching
nx (Python's built-in ``hash()`` raises ``TypeError: unhashable
type: '<type>'``).

``descendants_at_distance`` is special: nx pre-validates the
source against ``G.nodes`` and raises ``NetworkXError("The node
{source} is not in the graph.")`` — it never reaches a hash
operation that would TypeError. Match nx's exact class and
message: hash-check still happens (via Python's ``hash()`` call)
but the resulting TypeError is translated to NetworkXError.
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# Functions that should raise TypeError eagerly
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dijkstra_path_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.dijkstra_path(G, val, 1)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.dijkstra_path(GX, val, 1)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bellman_ford_path_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.bellman_ford_path(G, val, 1)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.bellman_ford_path(GX, val, 1)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_node_connected_component_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.node_connected_component(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.node_connected_component(GX, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bfs_edges_unhashable_raises_typeerror(val):
    """``list(bfs_edges(g, unhashable))`` raises TypeError on both
    libraries. fnx's hash-check fires eagerly (on call); nx's fires
    lazily (on iteration via ``adj[source]``). Materialize via
    ``list()`` so both code paths reach the TypeError."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(fnx.bfs_edges(G, val))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.bfs_edges(GX, val))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dfs_edges_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(fnx.dfs_edges(G, val))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.dfs_edges(GX, val))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dfs_tree_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.dfs_tree(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.dfs_tree(GX, val)


# ---------------------------------------------------------------------------
# descendants_at_distance: nx raises NetworkXError, not TypeError
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_descendants_at_distance_unhashable_raises_networkxerror(val):
    """nx's descendants_at_distance pre-validates against G.nodes
    and raises NetworkXError, not TypeError. Match nx's class and
    message."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(
        fnx.NetworkXError,
        match=r"The node .* is not in the graph\.",
    ):
        fnx.descendants_at_distance(G, val, 1)
    with pytest.raises(
        nx.NetworkXError,
        match=r"The node .* is not in the graph\.",
    ):
        nx.descendants_at_distance(GX, val, 1)


# ---------------------------------------------------------------------------
# Regression — hashable / missing inputs still work the prior way
# ---------------------------------------------------------------------------

@needs_nx
def test_dijkstra_path_missing_hashable_still_raises_node_not_found():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound):
        fnx.dijkstra_path(G, 99, 1)
    with pytest.raises(nx.NodeNotFound):
        nx.dijkstra_path(GX, 99, 1)


@needs_nx
def test_bfs_edges_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert list(fnx.bfs_edges(G, 1)) == list(nx.bfs_edges(GX, 1))


@needs_nx
def test_dfs_tree_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert sorted(fnx.dfs_tree(G, 1).edges()) == sorted(nx.dfs_tree(GX, 1).edges())


@needs_nx
def test_descendants_at_distance_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert fnx.descendants_at_distance(G, 1, 1) == nx.descendants_at_distance(GX, 1, 1)
