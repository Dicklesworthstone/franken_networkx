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


@pytest.mark.parametrize("seed", range(40))
def test_spanning_trees_are_subgraphs_of_the_input(seed):
    """A weight TOTAL matching networkx does not say the edges came from G.

    The existing checks are the edge count, is_tree, and the summed weight; a
    tree built from invented edges whose weights happened to total correctly
    satisfies all three.
    """
    fg, ng, n = _random_connected_weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    for tree in (fnx.minimum_spanning_tree(fg), fnx.maximum_spanning_tree(fg)):
        # It spans the input: same nodes, and every edge is one of G's.
        assert set(tree.nodes()) == set(fg.nodes())
        for u, v, data in tree.edges(data=True):
            assert fg.has_edge(u, v)
            # ...carrying G's weight, not one invented to make the total work.
            assert data["weight"] == fg.edges[u, v]["weight"]


def test_max_spanning_tree_is_strictly_heavier_on_this_family():
    """Guards `maxST >= MST`: equality would satisfy it on every draw.

    Equality is legitimate when all weights are equal, so this asserts the
    family is varied enough to separate them rather than asserting strictness
    as a universal law.
    """
    strict = 0
    considered = 0
    for seed in range(40):
        fg, _, _ = _random_connected_weighted(seed)
        if not fnx.is_connected(fg):
            continue
        considered += 1
        light = sum(d["weight"] for _, _, d in fnx.minimum_spanning_tree(fg).edges(data=True))
        heavy = sum(d["weight"] for _, _, d in fnx.maximum_spanning_tree(fg).edges(data=True))
        if heavy > light:
            strict += 1
    # Measured 35 of 35 connected draws.
    assert considered >= 20
    assert strict >= considered - 3, f"only {strict} of {considered} draws separate the two"


@pytest.mark.parametrize(
    "case",
    ["two_node_empty_sequence", "value_out_of_range", "encode_a_non_tree", "encode_two_node_tree"],
)
def test_prufer_edge_contracts_match_networkx(case):
    """The sweep draws sequences of length n-2 for n in 3..12; these are the ends."""
    def call(lib):
        if case == "two_node_empty_sequence":
            return sorted(tuple(sorted(e)) for e in lib.from_prufer_sequence([]).edges())
        if case == "value_out_of_range":
            return sorted(lib.from_prufer_sequence([9, 9]).edges())
        if case == "encode_a_non_tree":
            return list(lib.to_prufer_sequence(lib.Graph([(0, 1), (1, 2), (2, 0)])))
        return list(lib.to_prufer_sequence(lib.Graph([(0, 1)])))

    def outcome(lib):
        try:
            return ("returned", call(lib))
        except Exception as exc:  # noqa: BLE001 - the type IS the assertion
            return ("raised", type(exc).__name__)

    got, want = outcome(fnx), outcome(nx)
    assert got == want
