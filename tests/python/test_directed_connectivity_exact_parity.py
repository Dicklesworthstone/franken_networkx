"""Directed connectivity exact-value parity (asymmetric s,t).

Directed local connectivity is asymmetric: the number of node/edge-disjoint
paths from s to t need not equal t to s. This is the domain where two P1
node_connectivity bugs were fixed earlier this cycle (adjacency / directed
undercount), so it warrants exact-value pinning in BOTH directions plus the
global measures.

No mocks: real fnx and real networkx on identically-built digraphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.connectivity as fc
import networkx.algorithms.connectivity as nc


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [
        (u, v) for u in range(n) for v in range(n)
        if u != v and r.random() < 0.35
    ]
    fg = fnx.DiGraph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.DiGraph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, r


@pytest.mark.parametrize("seed", range(50))
def test_local_connectivity_both_directions(seed):
    fg, ng, n, r = _digraph(seed)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        # Forward and reverse local node connectivity match nx exactly.
        assert fc.local_node_connectivity(fg, s, t) == (
            nc.local_node_connectivity(ng, s, t)
        )
        assert fc.local_node_connectivity(fg, t, s) == (
            nc.local_node_connectivity(ng, t, s)
        )
        assert fc.local_edge_connectivity(fg, s, t) == (
            nc.local_edge_connectivity(ng, s, t)
        )


@pytest.mark.parametrize("seed", range(50))
def test_global_directed_connectivity(seed):
    fg, ng, n, r = _digraph(seed)
    assert fnx.node_connectivity(fg) == nx.node_connectivity(ng)
    assert fnx.edge_connectivity(fg) == nx.edge_connectivity(ng)


def test_directed_connectivity_is_genuinely_asymmetric():
    # A directed path 0->1->2 has connectivity 1 forward, 0 backward — confirming
    # the asymmetry is real (and fnx tracks it, matching nx).
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert fc.local_node_connectivity(fg, 0, 2) == nc.local_node_connectivity(ng, 0, 2)
    assert fc.local_node_connectivity(fg, 2, 0) == nc.local_node_connectivity(ng, 2, 0)
    assert fc.local_node_connectivity(fg, 0, 2) != fc.local_node_connectivity(fg, 2, 0)


@pytest.mark.parametrize("seed", range(50))
def test_local_edge_connectivity_reverse_direction(seed):
    """The node version checks both directions; the edge version checks one.

    Edge connectivity is asymmetric on a digraph just as node connectivity is —
    measured, the sampled pairs differ in that direction on 103 of 150 — so the
    reverse call is a distinct value and was never compared with networkx.
    """
    fg, ng, n, r = _digraph(seed)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        assert fc.local_edge_connectivity(fg, t, s) == (
            nc.local_edge_connectivity(ng, t, s)
        )


def test_the_family_is_genuinely_asymmetric():
    """Guards "both directions": if conn(s,t) always equalled conn(t,s), the
    forward and reverse assertions would be checking one number twice."""
    asymmetric = 0
    sampled = 0
    for seed in range(50):
        fg, _, n, r = _digraph(seed)
        for _ in range(3):
            s, t = r.sample(range(n), 2)
            sampled += 1
            if fc.local_node_connectivity(fg, s, t) != fc.local_node_connectivity(fg, t, s):
                asymmetric += 1
    # Measured 99 of 150.
    assert asymmetric >= 40, f"only {asymmetric} of {sampled} sampled pairs are asymmetric"


def test_source_equals_target_contracts_differ():
    """s == t is not handled uniformly by the two local measures.

    local_node_connectivity answers 1 — a node is connected to itself — while
    local_edge_connectivity refuses. Both match networkx, and the split is easy
    to assume away.
    """
    fg, ng, _, _ = _digraph(0)

    assert fc.local_node_connectivity(fg, 0, 0) == nc.local_node_connectivity(ng, 0, 0) == 1
    with pytest.raises(fnx.NetworkXError):
        fc.local_edge_connectivity(fg, 0, 0)
    with pytest.raises(nx.NetworkXError):
        nc.local_edge_connectivity(ng, 0, 0)


def test_global_measures_on_a_disconnected_digraph():
    """29 of the 50 draws are not strongly connected, but none is built to be
    disconnected outright; both global measures are 0 there."""
    fg = fnx.DiGraph([(0, 1), (2, 3)])
    ng = nx.DiGraph([(0, 1), (2, 3)])

    assert fnx.node_connectivity(fg) == nx.node_connectivity(ng) == 0
    assert fnx.edge_connectivity(fg) == nx.edge_connectivity(ng) == 0
