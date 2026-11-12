"""Parity for value-only max-flow in edge_connectivity.

br-flowvalonly: global/local edge_connectivity computed a full minimum CUT
(string-residual round-trip + reverse-residual rebuild + reachability BFS +
partition) for each of the |D| dominating-set flows, then read only ``cut.value``
and discarded the partition. The edge-connectivity callers now use a value-only
Edmonds-Karp (``compute_max_flow_value``) -- same integer augmenting search,
returns only the flow value (== min-cut value by the max-flow/min-cut theorem),
no residual materialization / flow list / partition. Values are bit-identical to
networkx; edge_connectivity goes from ~2-3x slower (after the prior br-flowint
integer-residual commit) to FASTER-than-or-equal-to networkx. max_flow / min_cut
are unchanged (they still use compute_max_flow_residual).
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx, directed=False):
    Gf = fnx.DiGraph() if directed else fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def test_global_and_local_edge_connectivity_match_networkx():
    for seed in range(100):
        rnd = random.Random(seed)
        n = rnd.randint(4, 40)
        directed = seed % 2 == 0
        Gx = nx.gnp_random_graph(n, rnd.uniform(0.08, 0.35), seed=seed, directed=directed)
        if Gx.number_of_nodes() < 2:
            continue
        Gf = _cp(Gx, directed=directed)
        nodes = list(Gx.nodes())
        assert nx.edge_connectivity(Gx) == fnx.edge_connectivity(Gf), (seed, directed)
        assert nx.edge_connectivity(Gx, nodes[0], nodes[-1]) == fnx.edge_connectivity(
            Gf, nodes[0], nodes[-1]
        ), (seed, directed)


def test_edge_connectivity_equals_local_min_cut_value():
    # value-only flow value must equal the min-cut value (max-flow/min-cut).
    rnd = random.Random(3)
    G = nx.gnp_random_graph(40, 0.15, seed=3)
    for u, v in G.edges():
        G[u][v]["capacity"] = rnd.randint(1, 8)
    F = _cp(G)
    for s, t in [(0, 20), (1, 39), (5, 17)]:
        assert fnx.edge_connectivity(F, s, t) == nx.edge_connectivity(G, s, t)


def test_complete_graph_min_degree():
    G = fnx.Graph()
    nodes = list(range(8))
    G.add_nodes_from(nodes)
    for i in nodes:
        for j in nodes:
            if i < j:
                G.add_edge(i, j)
    assert fnx.edge_connectivity(G) == 7


def test_disconnected_zero():
    assert fnx.edge_connectivity(fnx.Graph([(0, 1), (2, 3)])) == 0


def test_max_flow_value_unchanged():
    # compute_max_flow_residual is untouched; max_flow must still match nx.
    rnd = random.Random(7)
    G = nx.gnp_random_graph(30, 0.18, seed=7, directed=True)
    for u, v in G.edges():
        G[u][v]["capacity"] = rnd.randint(1, 10)
    F = _cp(G, directed=True)
    assert nx.maximum_flow_value(G, 0, 29) == fnx.maximum_flow_value(F, 0, 29)
    assert nx.minimum_cut_value(G, 0, 29) == fnx.minimum_cut_value(F, 0, 29)


def test_missing_node_raises():
    G = _cp(nx.path_graph(4))
    try:
        fnx.edge_connectivity(G, 0, 99)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for missing node")
