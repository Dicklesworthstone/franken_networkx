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


def _attributed_pair(attr_value_for_first_node):
    """Two structurally identical paths differing only in one node's colour."""
    fg = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    for graph in (fg, ng):
        for node in graph.nodes():
            graph.nodes[node]["colour"] = "red"
        graph.nodes[0]["colour"] = attr_value_for_first_node
    return fg, ng


def test_node_attr_changes_the_hash_and_matches_networkx():
    """node_attr is untested, and it is what makes the hash attribute-aware.

    The discrimination test uses four structurally DIFFERENT graphs, so it
    cannot see whether attributes reach the hash at all.
    """
    same_fg, same_ng = _attributed_pair("red")
    diff_fg, diff_ng = _attributed_pair("blue")

    # Structure alone cannot tell them apart.
    assert fnx.weisfeiler_lehman_graph_hash(same_fg) == fnx.weisfeiler_lehman_graph_hash(diff_fg)
    # With node_attr the colours reach the hash.
    hashed_same = fnx.weisfeiler_lehman_graph_hash(same_fg, node_attr="colour")
    hashed_diff = fnx.weisfeiler_lehman_graph_hash(diff_fg, node_attr="colour")
    assert hashed_same != hashed_diff
    # ...and both agree with networkx.
    assert hashed_same == nx.weisfeiler_lehman_graph_hash(same_ng, node_attr="colour")
    assert hashed_diff == nx.weisfeiler_lehman_graph_hash(diff_ng, node_attr="colour")


def test_edge_attr_changes_the_hash_and_matches_networkx():
    same_fg = fnx.Graph(); same_fg.add_edge(0, 1, kind="x"); same_fg.add_edge(1, 2, kind="x")
    diff_fg = fnx.Graph(); diff_fg.add_edge(0, 1, kind="x"); diff_fg.add_edge(1, 2, kind="y")
    same_ng = nx.Graph(); same_ng.add_edge(0, 1, kind="x"); same_ng.add_edge(1, 2, kind="x")
    diff_ng = nx.Graph(); diff_ng.add_edge(0, 1, kind="x"); diff_ng.add_edge(1, 2, kind="y")

    hashed_same = fnx.weisfeiler_lehman_graph_hash(same_fg, edge_attr="kind")
    hashed_diff = fnx.weisfeiler_lehman_graph_hash(diff_fg, edge_attr="kind")
    assert hashed_same != hashed_diff
    assert hashed_same == nx.weisfeiler_lehman_graph_hash(same_ng, edge_attr="kind")
    assert hashed_diff == nx.weisfeiler_lehman_graph_hash(diff_ng, edge_attr="kind")


def test_iterations_actually_changes_the_hash():
    """Parity at iterations=5 cannot see the parameter being ignored.

    If fnx dropped `iterations` on the floor, it would still match networkx
    wherever networkx's own default happened to agree. Requiring the hash to
    VARY with the parameter is what pins that it is read.
    """
    g = fnx.path_graph(8)
    hashes = {i: fnx.weisfeiler_lehman_graph_hash(g, iterations=i) for i in (1, 2, 3, 5)}
    assert len(set(hashes.values())) == len(hashes)


@pytest.mark.parametrize("seed", range(30))
def test_different_degree_sequences_hash_differently(seed):
    """Discrimination on the random family, not only four named graphs.

    The first WL refinement round incorporates each node's degree, so graphs
    whose degree multisets differ cannot reach the same refined labelling.
    """
    fg, _, _, _ = _graph(seed)
    other, _, _, _ = _graph((seed + 7) % 30)
    if sorted(d for _, d in fg.degree()) == sorted(d for _, d in other.degree()):
        pytest.skip("same degree sequence — nothing is claimed here")
    assert fnx.weisfeiler_lehman_graph_hash(fg) != fnx.weisfeiler_lehman_graph_hash(other)
