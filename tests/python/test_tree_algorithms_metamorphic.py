"""Tree algorithms: Prüfer bijection + spanning-tree invariants + nx parity.

Trees obey strong structural laws: the Prüfer sequence is a bijection with
labelled trees (encode→decode→encode is the identity), a spanning tree of an
n-node graph has exactly n-1 edges and is acyclic/connected, and the maximum
spanning tree weighs at least as much as the minimum. Checking the laws plus
networkx parity catches construction and weighting bugs.

No mocks: real fnx and real networkx on random trees and weighted graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(40))
def test_prufer_roundtrip_and_parity(seed):
    r = random.Random(seed)
    n = r.randint(3, 12)
    seq = [r.randrange(n) for _ in range(n - 2)]

    t = fnx.from_prufer_sequence(seq)
    nt = nx.from_prufer_sequence(seq)
    # Structure parity with networkx.
    assert sorted(tuple(sorted(e)) for e in t.edges()) == (
        sorted(tuple(sorted(e)) for e in nt.edges())
    )
    # It is a tree with n-1 edges.
    assert fnx.is_tree(t)
    assert t.number_of_edges() == n - 1
    # Bijection: encoding the decoded tree returns the original sequence.
    assert list(fnx.to_prufer_sequence(t)) == seq


def _random_connected_weighted(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_spanning_tree_invariants_and_parity(seed):
    fg, ng, n = _random_connected_weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    mst = fnx.minimum_spanning_tree(fg)
    assert mst.number_of_edges() == n - 1
    assert fnx.is_tree(mst)

    mst_w = sum(d["weight"] for _, _, d in mst.edges(data=True))
    nx_mst_w = sum(
        d["weight"] for _, _, d in nx.minimum_spanning_tree(ng).edges(data=True)
    )
    assert mst_w == nx_mst_w  # minimality (weight is the invariant, not edge set)

    maxst = fnx.maximum_spanning_tree(fg)
    maxst_w = sum(d["weight"] for _, _, d in maxst.edges(data=True))
    assert maxst_w >= mst_w  # max spanning tree weighs at least as much
    assert maxst_w == sum(
        d["weight"] for _, _, d in nx.maximum_spanning_tree(ng).edges(data=True)
    )
