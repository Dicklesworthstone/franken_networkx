"""Parity for native self-loop utilities (br-selfloopnative).

number_of_selfloops, selfloop_edges (default form) and nodes_with_selfloops walked
slow views (a per-node has_edge probe / AdjacencyView). number_of_selfloops was
~14x slower than networkx despite being a HOT internal utility (26 call sites).
They now route through the native nodes_with_selfloops_rust kernel, which returns
nodes in networkx's node-iteration order (verified). For multigraphs (where
self-loop multiplicity matters) number_of_selfloops keeps the exact edge-count
path. Results are identical to networkx (node order, counts, SubgraphView
filtering, nx-typed inputs); all three are now FASTER than networkx.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False, multi=False):
    if multi:
        F = fnx.MultiDiGraph() if directed else fnx.MultiGraph()
    else:
        F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges(keys=True) if multi else G.edges())
    return F


def test_all_three_match_networkx():
    for seed in range(120):
        rnd = random.Random(seed)
        n = rnd.randint(0, 40)
        directed = seed % 2 == 0
        multi = seed % 3 == 0
        if multi:
            G = nx.MultiDiGraph() if directed else nx.MultiGraph()
        else:
            G = nx.DiGraph() if directed else nx.Graph()
        nodes = list(range(n))
        rnd.shuffle(nodes)
        G.add_nodes_from(nodes)
        for _ in range(n):
            if n > 0:
                G.add_edge(rnd.choice(nodes), rnd.choice(nodes))
        for _ in range(rnd.randint(0, 5)):
            if n > 0:
                x = rnd.choice(nodes)
                G.add_edge(x, x)
        F = _cp(G, directed, multi)
        assert nx.number_of_selfloops(G) == fnx.number_of_selfloops(F), seed
        assert list(nx.selfloop_edges(G)) == list(fnx.selfloop_edges(F)), seed
        assert list(nx.nodes_with_selfloops(G)) == list(fnx.nodes_with_selfloops(F)), seed


def test_selfloop_edges_data_and_keys_forms():
    # br-selfloopnative2: the data/keys forms of selfloop_edges previously walked
    # the entire AdjacencyView (~180x slower than networkx). They now route the
    # node discovery through nodes_with_selfloops_rust while keeping data/key
    # materialization exact. Every (data, keys) form must match networkx.
    for seed in range(120):
        rnd = random.Random(seed)
        n = rnd.randint(0, 30)
        directed = seed % 2 == 0
        multi = seed % 3 == 0
        if multi:
            G = nx.MultiDiGraph() if directed else nx.MultiGraph()
        else:
            G = nx.DiGraph() if directed else nx.Graph()
        nodes = list(range(n))
        rnd.shuffle(nodes)
        G.add_nodes_from(nodes)
        for _ in range(n):
            if n > 0:
                G.add_edge(rnd.choice(nodes), rnd.choice(nodes), weight=rnd.random())
        for _ in range(rnd.randint(0, 5)):
            if n > 0:
                x = rnd.choice(nodes)
                G.add_edge(x, x, weight=rnd.random())
        F = _cp_data(G, directed, multi)
        variants = [
            dict(data=False),
            dict(data=True),
            dict(data="weight"),
            dict(data="weight", default=-1),
        ]
        if multi:
            variants += [
                dict(keys=True),
                dict(data=True, keys=True),
                dict(data="weight", keys=True),
            ]
        for v in variants:
            assert list(nx.selfloop_edges(G, **v)) == list(
                fnx.selfloop_edges(F, **v)
            ), (seed, v)


def _cp_data(G, directed=False, multi=False):
    if multi:
        F = fnx.MultiDiGraph() if directed else fnx.MultiGraph()
    else:
        F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges(keys=True, data=True) if multi else G.edges(data=True))
    return F


def test_subgraphview_filters_selfloops():
    G = nx.gnp_random_graph(30, 0.2, seed=1)
    for x in (0, 5, 20):
        G.add_edge(x, x)
    F = _cp(G)
    keep = [0, 1, 2, 3, 4, 5, 6]  # excludes node 20's self-loop
    assert fnx.number_of_selfloops(F.subgraph(keep)) == nx.number_of_selfloops(
        nx.subgraph(G, keep)
    )
    assert list(fnx.nodes_with_selfloops(F.subgraph(keep))) == list(
        nx.nodes_with_selfloops(nx.subgraph(G, keep))
    )


def test_nx_typed_input():
    G = nx.path_graph(6)
    G.add_edge(2, 2)
    assert fnx.number_of_selfloops(G) == 1
    assert list(fnx.nodes_with_selfloops(G)) == [2]


def test_multigraph_multiplicity():
    G = nx.MultiGraph()
    G.add_edges_from([(0, 0), (0, 0), (1, 1), (1, 2)])
    F = _cp(G, multi=True)
    # two parallel self-loops at node 0 -> count is 3 (0,0)x2 + (1,1)
    assert fnx.number_of_selfloops(F) == nx.number_of_selfloops(G) == 3
    assert list(fnx.nodes_with_selfloops(F)) == list(nx.nodes_with_selfloops(G))
