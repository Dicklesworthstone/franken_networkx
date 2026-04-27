"""Parity for Rust-direct re-exports that were missing the
@not_implemented_for('multigraph') guard.

Bead br-r37-c1-2dwen. Three functions previously imported directly
from the Rust ``_fnx`` extension (with no Python wrapper) silently
accepted MultiGraph input where nx raises NetworkXNotImplemented:

  - ``maximal_matching``
  - ``tree_broadcast_center``
  - ``tree_broadcast_time``

Each is now wrapped with a thin Python guard that adds the
multigraph (and, where applicable, the directed) check before
delegating to the Rust impl. The guard ordering mirrors nx's
empirical behavior on combined inputs (MultiDiGraph specifically).

Scoped out of br-r37-c1-tqimg because the original audit only
covered fns that already had Python wrappers.
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


# ---------------------------------------------------------------------------
# maximal_matching: nx decorator stack is @multigraph @directed (top to
# bottom). nx raises 'directed' for MultiDiGraph (inner runs first).
# ---------------------------------------------------------------------------

@needs_nx
def test_maximal_matching_multigraph_raises():
    G = fnx.MultiGraph([(1, 2), (2, 3)])
    GX = nx.MultiGraph([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for multigraph type$",
    ):
        fnx.maximal_matching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for multigraph type$",
    ):
        nx.maximal_matching(GX)


@needs_nx
def test_maximal_matching_digraph_raises():
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        fnx.maximal_matching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        nx.maximal_matching(GX)


@needs_nx
def test_maximal_matching_multidigraph_yields_directed_message():
    """Decorator-ordering parity: for MultiDiGraph (both directed
    AND multigraph), nx's inner ``@not_implemented_for('directed')``
    decorator runs first and 'directed' wins."""
    G = fnx.MultiDiGraph([(1, 2), (2, 3)])
    GX = nx.MultiDiGraph([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        fnx.maximal_matching(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        nx.maximal_matching(GX)


# ---------------------------------------------------------------------------
# tree_broadcast_center / tree_broadcast_time: decorator stack is
# @directed @multigraph. nx raises 'multigraph' for MultiDiGraph.
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("fn_name", ["tree_broadcast_center", "tree_broadcast_time"])
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_tree_broadcast_multigraph_raises(fn_name, cls_name):
    """Both Multi* yield 'multigraph' for these — nx's inner
    ``@not_implemented_for('multigraph')`` decorator fires first."""
    f = getattr(fnx, fn_name)
    n = getattr(nx, fn_name)
    G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for multigraph type$",
    ):
        f(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for multigraph type$",
    ):
        n(GX)


@needs_nx
@pytest.mark.parametrize("fn_name", ["tree_broadcast_center", "tree_broadcast_time"])
def test_tree_broadcast_digraph_raises(fn_name):
    f = getattr(fnx, fn_name)
    n = getattr(nx, fn_name)
    G = fnx.DiGraph([(1, 2)])
    GX = nx.DiGraph([(1, 2)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        f(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        n(GX)


# ---------------------------------------------------------------------------
# Cross-class catching
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "fn_name", ["maximal_matching", "tree_broadcast_center", "tree_broadcast_time"]
)
def test_multigraph_caught_by_nx_class(fn_name):
    G = fnx.MultiGraph([(1, 2)])
    try:
        getattr(fnx, fn_name)(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        f"fnx.{fn_name} should raise NetworkXNotImplemented on MultiGraph"
    )


# ---------------------------------------------------------------------------
# Regression: simple Graph still works
# ---------------------------------------------------------------------------

@needs_nx
def test_maximal_matching_simple_graph_unchanged():
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    f = sorted(map(frozenset, fnx.maximal_matching(G)))
    n = sorted(map(frozenset, nx.maximal_matching(GX)))
    assert f == n


@needs_nx
def test_tree_broadcast_center_simple_graph_unchanged():
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    assert fnx.tree_broadcast_center(G) == nx.tree_broadcast_center(GX)


@needs_nx
def test_tree_broadcast_time_simple_graph_unchanged():
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    assert fnx.tree_broadcast_time(G) == nx.tree_broadcast_time(GX)
    # node= kwarg still works
    assert fnx.tree_broadcast_time(G, node=2) == nx.tree_broadcast_time(GX, node=2)
