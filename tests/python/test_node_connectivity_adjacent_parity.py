"""Local node connectivity for ADJACENT node pairs (br-r37-c1-cqlms).

``node_connectivity(G, s, t)`` routed adjacent ``s, t`` to a vertex-split
max-flow kernel that cannot separate adjacent nodes and so returned 0.
networkx instead counts the direct edge as one node-independent path
(local kappa(0, 4) on K5 is 4, not 0). The wrapper now delegates adjacent
pairs to nx; non-adjacent pairs keep the native kernel.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(60))
def test_all_pairs_local_node_connectivity_match_networkx(seed):
    fg, ng, n = _pair(seed)
    for s in range(n):
        for t in range(s + 1, n):
            assert fnx.node_connectivity(fg, s, t) == nx.node_connectivity(ng, s, t)


def test_complete_graph_adjacent_local_connectivity():
    # Every pair in K_n is adjacent; local node connectivity is n - 1.
    for n in range(3, 7):
        g = fnx.complete_graph(n)
        ng = nx.complete_graph(n)
        for s in range(n):
            for t in range(s + 1, n):
                assert fnx.node_connectivity(g, s, t) == n - 1
                assert fnx.node_connectivity(g, s, t) == nx.node_connectivity(ng, s, t)


def test_global_node_connectivity_unaffected():
    for builder in (lambda lib: lib.complete_graph(5),
                    lambda lib: lib.cycle_graph(6),
                    lambda lib: lib.path_graph(5)):
        assert fnx.node_connectivity(builder(fnx)) == nx.node_connectivity(builder(nx))
