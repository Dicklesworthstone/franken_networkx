"""Weisfeiler-Lehman graph hash: defining invariants + networkx parity.

The WL graph hash has two defining properties, both oracle-free:
  - **Isomorphism invariance**: relabeling the nodes does NOT change the hash
    (isomorphic graphs hash equal).
  - **Discrimination**: structurally different graphs hash differently (a
    necessary, though not sufficient, isomorphism test).
This checks both, plus exact parity with networkx for the graph hash, subgraph
hashes, and the iterations parameter.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, r


@pytest.mark.parametrize("seed", range(30))
def test_wl_hash_parity_and_isomorphism_invariance(seed):
    fg, ng, n, r = _graph(seed)
    h = fnx.weisfeiler_lehman_graph_hash(fg)
    assert h == nx.weisfeiler_lehman_graph_hash(ng)

    # Relabeling (a node permutation) must not change the hash.
    perm = list(range(n))
    r.shuffle(perm)
    relabeled = fnx.relabel_nodes(fg, {i: perm[i] for i in range(n)})
    assert fnx.weisfeiler_lehman_graph_hash(relabeled) == h

    # Subgraph hashes and the iterations parameter match networkx too.
    assert fnx.weisfeiler_lehman_subgraph_hashes(fg) == (
        nx.weisfeiler_lehman_subgraph_hashes(ng)
    )
    assert fnx.weisfeiler_lehman_graph_hash(fg, iterations=5) == (
        nx.weisfeiler_lehman_graph_hash(ng, iterations=5)
    )


def test_wl_hash_discriminates_distinct_structures():
    hashes = {
        name: fnx.weisfeiler_lehman_graph_hash(builder())
        for name, builder in [
            ("path", lambda: fnx.path_graph(5)),
            ("cycle", lambda: fnx.cycle_graph(5)),
            ("star", lambda: fnx.star_graph(4)),
            ("complete", lambda: fnx.complete_graph(5)),
        ]
    }
    # All four 5-node structures hash differently.
    assert len(set(hashes.values())) == 4


def test_wl_hash_equal_for_isomorphic_relabelings():
    g1 = fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    g2 = fnx.Graph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
    assert fnx.weisfeiler_lehman_graph_hash(g1) == (
        fnx.weisfeiler_lehman_graph_hash(g2)
    )
