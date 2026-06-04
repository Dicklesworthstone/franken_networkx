"""Parity for the integer-relabeled Edmonds-Karp residual hot loop.

br-flowint: compute_max_flow_residual (the Edmonds-Karp core behind maximum_flow,
minimum_cut, edge_connectivity and node_connectivity) used a String-keyed residual
``HashMap<String, HashMap<String, f64>>`` and re-sorted the neighbor list
(``neighbors.sort_unstable()``) on EVERY BFS visit -- String hashing, cloning and
an O(deg log deg) re-sort per node per augmenting path. The hot loop now relabels
nodes to integers in lexicographic (string) order -- so ascending-index neighbor
iteration reproduces the original traversal order EXACTLY -- and runs the BFS on
flat ``Vec<bool>`` / ``Vec<usize>`` arrays with an ordered ``BTreeMap`` residual,
re-materializing the string residual only once at the end. Augmenting paths,
flow values, residual and min-cut are byte-identical; maximum_flow_value is now
faster than networkx and edge_connectivity's gap roughly halves.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx, directed=False):
    Gf = fnx.DiGraph() if directed else fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def test_maxflow_and_mincut_value_match_networkx():
    for seed in range(80):
        rnd = random.Random(seed)
        n = rnd.randint(4, 32)
        directed = seed % 2 == 0
        Gx = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed, directed=directed)
        for u, v in Gx.edges():
            Gx[u][v]["capacity"] = rnd.randint(1, 15)
        if Gx.number_of_nodes() < 2:
            continue
        Gf = _cp(Gx, directed=directed)
        nodes = list(Gx.nodes())
        s, t = nodes[0], nodes[-1]
        assert nx.maximum_flow_value(Gx, s, t) == fnx.maximum_flow_value(Gf, s, t), seed
        assert nx.minimum_cut_value(Gx, s, t) == fnx.minimum_cut_value(Gf, s, t), seed


def test_maxflow_value_conservation():
    rnd = random.Random(11)
    Gx = nx.gnp_random_graph(40, 0.1, seed=11, directed=True)
    for u, v in Gx.edges():
        Gx[u][v]["capacity"] = rnd.randint(1, 10)
    Gf = _cp(Gx, directed=True)
    val, flow = fnx.maximum_flow(Gf, 0, 39)
    # flow value equals net flow out of source
    out = sum(flow[0].get(w, 0) for w in flow[0])
    assert out == val
    assert val == nx.maximum_flow_value(Gx, 0, 39)


def test_edge_connectivity_matches_networkx():
    for seed in range(60):
        G = nx.gnp_random_graph(random.Random(seed).randint(5, 45), 0.12, seed=seed)
        F = _cp(G)
        assert nx.edge_connectivity(G) == fnx.edge_connectivity(F), seed


def test_node_connectivity_matches_networkx():
    for seed in range(40):
        G = nx.gnp_random_graph(random.Random(seed).randint(5, 40), 0.12, seed=seed)
        F = _cp(G)
        assert nx.node_connectivity(G) == fnx.node_connectivity(F), seed


def test_local_st_edge_connectivity():
    G = nx.gnp_random_graph(30, 0.2, seed=2)
    F = _cp(G)
    assert nx.edge_connectivity(G, 0, 15) == fnx.edge_connectivity(F, 0, 15)


def test_disconnected_edge_connectivity_zero():
    G = fnx.Graph([(0, 1), (2, 3)])
    assert fnx.edge_connectivity(G) == 0
