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
