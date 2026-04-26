"""Parity for ``node_connectivity`` / ``edge_connectivity`` on null graph.

Bead br-r37-c1-turq0. fnx silently returned 0 on the null graph (zero
nodes) for both ``node_connectivity`` and ``edge_connectivity``; nx
raises ``NetworkXPointlessConcept('Connectivity is undefined for the
null graph.')``. Drop-in code that catches that exception to gate
empty-graph paths failed to trigger on fnx — the silent value masks
the contract violation.

Single-node case (returns 0 on both libraries) is unchanged by the fix.
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


@needs_nx
def test_node_connectivity_null_graph_raises_pointless_concept():
    G = fnx.empty_graph(0)
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.node_connectivity(G)
    nx_g = nx.empty_graph(0)
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.node_connectivity(nx_g)
    # Same message as nx for parity.
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_edge_connectivity_null_graph_raises_pointless_concept():
    G = fnx.empty_graph(0)
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.edge_connectivity(G)
    nx_g = nx.empty_graph(0)
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.edge_connectivity(nx_g)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_node_connectivity_single_node_returns_zero():
    """Single-node case should match nx (returns 0, no exception)."""
    G = fnx.empty_graph(1)
    nx_g = nx.empty_graph(1)
    assert fnx.node_connectivity(G) == nx.node_connectivity(nx_g) == 0


@needs_nx
def test_edge_connectivity_single_node_returns_zero():
    G = fnx.empty_graph(1)
    nx_g = nx.empty_graph(1)
    assert fnx.edge_connectivity(G) == nx.edge_connectivity(nx_g) == 0


@needs_nx
def test_node_connectivity_normal_case_unchanged():
    """K4 should still report κ=3."""
    assert fnx.node_connectivity(fnx.complete_graph(4)) == 3


@needs_nx
def test_edge_connectivity_normal_case_unchanged():
    assert fnx.edge_connectivity(fnx.complete_graph(4)) == 3


@needs_nx
def test_node_connectivity_two_isolated_nodes_returns_zero():
    """Two isolated nodes (n>=1, no edges) — connectivity is 0, not
    PointlessConcept; only the null graph (n=0) gets the exception."""
    G = fnx.empty_graph(2)
    nx_g = nx.empty_graph(2)
    assert fnx.node_connectivity(G) == nx.node_connectivity(nx_g) == 0


@needs_nx
def test_node_connectivity_with_st_pair_on_null_graph_also_raises():
    """Even when s and t are passed, the null graph should still raise."""
    G = fnx.empty_graph(0)
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.node_connectivity(G, s=0, t=1)
