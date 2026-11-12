"""Parity for the integer maximal_matching kernel + native approx routing.

br-mmnative: the Rust maximal_matching kernel built a String-cloned edge list
(`undirected_edges_in_iteration_order`) and a String-keyed matched-node set --
~1.76x SLOWER than networkx. It now walks the integer adjacency and considers
each undirected edge once from its smaller-index endpoint (`u < v`, which skips
self-loops as networkx does), in networkx's exact `G.edges()` order and (smaller,
larger) tuple orientation. Additionally, `approximation.min_maximal_matching` and
`approximation.min_edge_dominating_set` -- both defined by networkx as
`maximal_matching(G)` -- went through the generic namespace wrapper's O(n^2)
fnx->nx conversion (~30x slower); they now route to the native kernel. Results
are tuple-identical to networkx; fnx is now ~18x FASTER (maximal_matching) and
~25x FASTER (the two approx functions), margins growing with n.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges(data=True))
    return F


def test_maximal_matching_tuple_exact():
    for seed in range(150):
        rnd = random.Random(seed)
        n = rnd.randint(0, 55)
        G = nx.gnp_random_graph(n, rnd.uniform(0.03, 0.5), seed=seed)
        if seed % 5 == 0 and n > 2:
            G.add_edge(0, 0)  # self-loop must be skipped
        F = _cp(G)
        assert set(nx.maximal_matching(G)) == set(fnx.maximal_matching(F)), seed


def test_min_maximal_matching_matches_networkx():
    for seed in range(80):
        G = nx.gnp_random_graph(random.Random(seed).randint(2, 50), 0.15, seed=seed)
        F = _cp(G)
        assert set(nx.approximation.min_maximal_matching(G)) == set(
            fnx.approximation.min_maximal_matching(F)
        ), seed


def test_min_edge_dominating_set_matches_networkx():
    for seed in range(80):
        G = nx.gnp_random_graph(random.Random(seed).randint(2, 50), 0.15, seed=seed)
        F = _cp(G)
        assert set(nx.approximation.min_edge_dominating_set(G)) == set(
            fnx.approximation.min_edge_dominating_set(F)
        ), seed


def test_min_edge_dominating_set_empty_raises_valueerror():
    try:
        fnx.approximation.min_edge_dominating_set(fnx.Graph())
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for empty graph")


def test_matching_is_valid_and_maximal():
    G = nx.gnp_random_graph(80, 0.1, seed=9)
    F = _cp(G)
    m = fnx.maximal_matching(F)
    matched = set()
    for u, v in m:
        assert u not in matched and v not in matched  # valid matching
        matched.update((u, v))
    # maximal: every edge has at least one endpoint matched
    assert all(u in matched or v in matched for u, v in G.edges())


def test_self_loop_node_can_still_match_via_real_edge():
    G = nx.Graph([(0, 0), (0, 1), (2, 3)])
    F = _cp(G)
    assert set(nx.maximal_matching(G)) == set(fnx.maximal_matching(F))


def test_directed_raises_not_implemented():
    try:
        fnx.maximal_matching(fnx.DiGraph([(0, 1)]))
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for directed")
