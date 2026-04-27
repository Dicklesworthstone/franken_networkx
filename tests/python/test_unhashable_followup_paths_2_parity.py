"""Parity for bellman_ford_path_length, dfs_*_nodes, immediate_dominators,
dominance_frontiers on unhashable / missing inputs.

Bead br-r37-c1-mz7g4 (sixth follow-up to the unhashable-node series:
br-r37-c1-m0io3 → -g438p → -i9whv → -c4agn → -ybw1s).

Five drifts found in the post-ybw1s probe:

  bellman_ford_path_length    fnx: NodeNotFound       nx: TypeError
  dfs_preorder_nodes          fnx: NetworkXError      nx: TypeError
  dfs_postorder_nodes         fnx: NetworkXError      nx: TypeError
  immediate_dominators        fnx: <silent ok>        nx: NetworkXError
  dominance_frontiers         fnx: <silent ok>        nx: NetworkXError

The first three need eager hash-validation (TypeError on unhashable to
match nx).  ``immediate_dominators`` and ``dominance_frontiers`` need
``start in G`` membership pre-checks (silent-False on unhashable, then
NetworkXError) — fnx was silently computing whereas nx pre-validates.
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
# bellman_ford_path_length — TypeError on unhashable source
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bellman_ford_path_length_unhashable_source_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.bellman_ford_path_length(G, val, 1)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.bellman_ford_path_length(GX, val, 1)


# ---------------------------------------------------------------------------
# dfs_preorder_nodes / dfs_postorder_nodes — TypeError on unhashable source
# (eager — fires at call time, not at first ``next()``)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dfs_preorder_nodes_unhashable_source_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.dfs_preorder_nodes(G, val)
    # nx is lazy — only raises on first next()
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.dfs_preorder_nodes(GX, val))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dfs_postorder_nodes_unhashable_source_raises_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.dfs_postorder_nodes(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.dfs_postorder_nodes(GX, val))


# ---------------------------------------------------------------------------
# immediate_dominators / dominance_frontiers — NetworkXError on unhashable/missing
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_immediate_dominators_unhashable_start_raises_networkxerror(val):
    """nx pre-checks ``start in G`` (silent-False on unhashable) and
    raises NetworkXError. fnx was silently computing whatever the
    Rust impl produced — now matches."""
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"start is not in G"):
        fnx.immediate_dominators(G, val)
    with pytest.raises(nx.NetworkXError, match=r"start is not in G"):
        nx.immediate_dominators(GX, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dominance_frontiers_unhashable_start_raises_networkxerror(val):
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"start is not in G"):
        fnx.dominance_frontiers(G, val)
    with pytest.raises(nx.NetworkXError, match=r"start is not in G"):
        nx.dominance_frontiers(GX, val)


@needs_nx
def test_immediate_dominators_missing_hashable_start_raises_networkxerror():
    """Hashable but absent start node — same NetworkXError contract."""
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"start is not in G"):
        fnx.immediate_dominators(G, 99)
    with pytest.raises(nx.NetworkXError, match=r"start is not in G"):
        nx.immediate_dominators(GX, 99)


@needs_nx
def test_dominance_frontiers_missing_hashable_start_raises_networkxerror():
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"start is not in G"):
        fnx.dominance_frontiers(G, 99)
    with pytest.raises(nx.NetworkXError, match=r"start is not in G"):
        nx.dominance_frontiers(GX, 99)


# ---------------------------------------------------------------------------
# Regression — hashable inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_bellman_ford_path_length_hashable_unchanged():
    G = fnx.Graph([(1, 2, {"weight": 3.0}), (2, 3, {"weight": 4.0})])
    GX = nx.Graph([(1, 2, {"weight": 3.0}), (2, 3, {"weight": 4.0})])
    assert fnx.bellman_ford_path_length(G, 1, 3) == nx.bellman_ford_path_length(GX, 1, 3)


@needs_nx
def test_dfs_preorder_nodes_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert list(fnx.dfs_preorder_nodes(G, 1)) == list(nx.dfs_preorder_nodes(GX, 1))


@needs_nx
def test_dfs_postorder_nodes_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert list(fnx.dfs_postorder_nodes(G, 1)) == list(nx.dfs_postorder_nodes(GX, 1))


@needs_nx
def test_immediate_dominators_hashable_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (1, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3), (1, 3)])
    assert dict(fnx.immediate_dominators(G, 1)) == dict(nx.immediate_dominators(GX, 1))


@needs_nx
def test_dominance_frontiers_hashable_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (1, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3), (1, 3)])
    f = fnx.dominance_frontiers(G, 1)
    n = nx.dominance_frontiers(GX, 1)
    assert {k: set(v) for k, v in f.items()} == {k: set(v) for k, v in n.items()}
