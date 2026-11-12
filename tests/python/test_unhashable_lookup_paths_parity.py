"""Parity for node-lookup paths on unhashable inputs.

Bead br-r37-c1-i9whv (third follow-up to br-r37-c1-m0io3 / -g438p).
Eight more node-lookup paths raised the wrong exception class on
unhashable inputs:

  g.neighbors(unhashable)        fnx: NetworkXError    nx: TypeError
  g.adj[unhashable]              fnx: KeyError         nx: TypeError
  g.nodes[unhashable]            fnx: KeyError         nx: TypeError
  g[unhashable]                  fnx: KeyError         nx: TypeError
  g.remove_edge(unhashable, 2)   fnx: NetworkXError    nx: TypeError
  g.remove_nodes_from([unhashable])  fnx: silently OK  nx: TypeError
  descendants(g, unhashable)     fnx: NetworkXError    nx: TypeError
  ancestors(g, unhashable)       fnx: NetworkXError    nx: TypeError

Drop-in code that does ``pytest.raises(TypeError)`` on these
wouldn't trigger on fnx because each wrapper either caught the
underlying TypeError and re-raised something else, or silently
returned False from a membership check that should have raised.

Note: ``is_isolate`` is intentionally NOT in scope — nx's impl
``G.degree(n) == 0`` accepts unhashable list as nbunch (returning
a degree view) and silently returns False, which is itself
arguably an nx leaky abstraction; matching that behavior would
be undesirable.
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
# neighbors / adj[] / nodes[] / g[]
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_neighbors_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(G.neighbors(val))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(GX.neighbors(val))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_adj_getitem_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.adj[val]
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.adj[val]


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_nodes_getitem_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.nodes[val]
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.nodes[val]


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_graph_getitem_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G[val]
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX[val]


# ---------------------------------------------------------------------------
# remove_edge / remove_nodes_from
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_remove_edge_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.remove_edge(val, 2)
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.remove_edge(val, 2)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_remove_nodes_from_unhashable_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.remove_nodes_from([val])
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.remove_nodes_from([val])


# ---------------------------------------------------------------------------
# descendants / ancestors
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_descendants_unhashable_raises_typeerror(val):
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.descendants(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.descendants(GX, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_ancestors_unhashable_raises_typeerror(val):
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.ancestors(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.ancestors(GX, val)


# ---------------------------------------------------------------------------
# Regression — hashable / missing inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_neighbors_missing_node_still_raises_networkxerror():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError):
        list(G.neighbors(99))
    with pytest.raises(nx.NetworkXError):
        list(GX.neighbors(99))


@needs_nx
def test_adj_getitem_missing_node_still_raises_keyerror():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(KeyError):
        G.adj[99]
    with pytest.raises(KeyError):
        GX.adj[99]


@needs_nx
def test_remove_edge_missing_endpoint_still_raises_networkxerror():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError):
        G.remove_edge(99, 1)
    with pytest.raises(nx.NetworkXError):
        GX.remove_edge(99, 1)


@needs_nx
def test_remove_nodes_from_missing_hashable_silently_skipped():
    """Pre-existing parity: remove_nodes_from silently skips missing
    hashable nodes (per nx contract). The hash-check fix only raises
    on unhashable inputs; missing-but-hashable inputs continue to be
    skipped."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    G.remove_nodes_from([99, 1])
    GX.remove_nodes_from([99, 1])
    assert sorted(G.nodes()) == sorted(GX.nodes()) == [2]


@needs_nx
def test_descendants_missing_node_still_raises_networkxerror():
    G = fnx.DiGraph([(1, 2)])
    GX = nx.DiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXError):
        fnx.descendants(G, 99)
    with pytest.raises(nx.NetworkXError):
        nx.descendants(GX, 99)
