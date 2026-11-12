"""Parity for connectivity / Eulerian predicates on graphs with self-loops.

Bead br-r37-c1-792dv. The Rust _raw_node_connectivity,
_raw_edge_connectivity, _raw_has_eulerian_path, and _raw_is_eulerian
all silently mishandled self-loops:

  - edge/node_connectivity ignored the +2 degree contribution that
    a self-loop makes in nx's min-degree-bound calculation. Examples:
      * fnx.edge_connectivity(Graph([(1,1)]))         -> 0  (nx: 2)
      * fnx.node_connectivity(Graph([(1,1)]))         -> 0  (nx: 2)
      * fnx.edge_connectivity(Graph([(1,1),(1,2),(2,2)])) -> 1  (nx: 3)
      * fnx.node_connectivity(...)                   -> 2  (nx: 3)

  - has_eulerian_path / is_eulerian returned False on graphs where
    the self-loops kept all degrees even but the helper either
    ignored self-loops or special-cased 1-node graphs:
      * fnx.has_eulerian_path(Graph([(1,2),(2,3),(3,1),(1,1)])) -> False  (nx: True)
      * fnx.is_eulerian(...)                                    -> False  (nx: True)

The fix delegates these four functions to nx whenever the graph has
at least one self-loop, leaving the Rust fast path intact for the
common no-self-loop case.
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
# Single-node graph with a self-loop
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("node", [0, 1, "x"])
def test_single_node_self_loop_connectivity_matches_nx(node):
    G = fnx.Graph([(node, node)])
    GX = nx.Graph([(node, node)])
    assert fnx.edge_connectivity(G) == nx.edge_connectivity(GX) == 2
    assert fnx.node_connectivity(G) == nx.node_connectivity(GX) == 2


@needs_nx
@pytest.mark.parametrize("node", [0, 1, "x"])
def test_single_node_self_loop_eulerian_predicates_match_nx(node):
    G = fnx.Graph([(node, node)])
    GX = nx.Graph([(node, node)])
    assert fnx.has_eulerian_path(G) is nx.has_eulerian_path(GX) is True
    assert fnx.is_eulerian(G) is nx.is_eulerian(GX) is True


# ---------------------------------------------------------------------------
# Multi-node graphs with self-loops
# ---------------------------------------------------------------------------

@needs_nx
def test_K3_plus_self_loop_eulerian_matches_nx():
    """A triangle plus one self-loop: still Eulerian under nx (all
    degrees even when self-loop counts +2). Pre-fix fnx returned
    False for both predicates."""
    edges = [(1, 2), (2, 3), (3, 1), (1, 1)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    assert fnx.has_eulerian_path(G) is nx.has_eulerian_path(GX) is True
    assert fnx.is_eulerian(G) is nx.is_eulerian(GX) is True


@needs_nx
def test_two_self_loops_plus_bridge_connectivity_matches_nx():
    """Two-node graph: self-loop on each node + a bridge between
    them. Each node has degree 3 (1 from self-loop ×2 + 1 from
    bridge). nx returns 3 (min-degree bound on the complete graph
    branch); fnx pre-fix returned 1 for edge and 2 for node
    connectivity."""
    edges = [(1, 1), (1, 2), (2, 2)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    assert fnx.edge_connectivity(G) == nx.edge_connectivity(GX) == 3
    assert fnx.node_connectivity(G) == nx.node_connectivity(GX) == 3


@needs_nx
def test_self_loop_plus_chain_eulerian_path_matches_nx():
    """Self-loop on node 1 attached to a 1→2→3 chain. nx says
    has_eulerian_path=True (1→1→2→3 traverses all edges once);
    pre-fix fnx returned False because the helper miscounted
    odd-degree vertices."""
    edges = [(1, 1), (1, 2), (2, 3)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    assert fnx.has_eulerian_path(G) is nx.has_eulerian_path(GX) is True


# ---------------------------------------------------------------------------
# Regression guard for the no-self-loop fast path
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("graph_factory_name", ["path_graph", "cycle_graph", "complete_graph"])
def test_no_self_loop_fast_path_unchanged(graph_factory_name):
    """The Rust fast path remains the default when no self-loop is
    present — make sure the new self-loop guard doesn't accidentally
    capture clean graphs."""
    G = getattr(fnx, graph_factory_name)(5)
    GX = getattr(nx, graph_factory_name)(5)
    assert fnx.edge_connectivity(G) == nx.edge_connectivity(GX)
    assert fnx.node_connectivity(G) == nx.node_connectivity(GX)
    assert fnx.has_eulerian_path(G) == nx.has_eulerian_path(GX)
    assert fnx.is_eulerian(G) == nx.is_eulerian(GX)


@needs_nx
def test_disconnected_graph_with_self_loops_still_returns_zero_connectivity():
    """Drop-in: a self-loop in one component does not promote the
    whole-graph connectivity past zero on a disconnected input.
    Both fnx and nx return 0 (and has_eulerian_path=False)."""
    G = fnx.Graph([(1, 1), (2, 3)])
    GX = nx.Graph([(1, 1), (2, 3)])
    assert fnx.edge_connectivity(G) == nx.edge_connectivity(GX) == 0
    assert fnx.node_connectivity(G) == nx.node_connectivity(GX) == 0
    assert fnx.has_eulerian_path(G) is nx.has_eulerian_path(GX) is False
