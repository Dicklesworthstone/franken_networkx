"""Parity for the undirected single_target_shortest_path_length routing (br-r37-c1-sptlen).

For undirected graphs the distance from every node TO target equals the distance
FROM target, so single_target_shortest_path_length now routes to the native
single_source kernel (~2.5x faster than networkx) instead of a per-node Python
reverse BFS (~6x slower). Hop counts are integers and both build the dict in
BFS-from-target order, so the result is byte-identical (value + key order).
Directed graphs use native reverse BFS while preserving NetworkX discovery order.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G, directed=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def test_parity_value_and_order():
    for seed in range(250):
        rnd = random.Random(seed)
        m = rnd.randint(1, 70)
        directed = seed % 2 == 0
        G = nx.gnp_random_graph(m, rnd.uniform(0.03, 0.45), seed=seed, directed=directed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        F = _cp(G, directed)
        for tgt in list(G)[:3]:
            for cutoff in [None, 1, 2, 3]:
                a = dict(nx.single_target_shortest_path_length(G, tgt, cutoff))
                b = fnx.single_target_shortest_path_length(F, tgt, cutoff)
                assert a == b, (seed, tgt, cutoff)
                assert list(a.keys()) == list(b.keys()), (seed, tgt, cutoff)


def test_missing_target_raises():
    F = _cp(nx.path_graph(5))
    with pytest.raises(nx.NodeNotFound):
        fnx.single_target_shortest_path_length(F, 99)


def test_directed_uses_reverse_distances():
    # Directed star inward: every leaf reaches center at distance 1.
    G = nx.DiGraph()
    G.add_edges_from([(i, 0) for i in range(1, 6)])
    F = _cp(G, directed=True)
    assert fnx.single_target_shortest_path_length(F, 0) == dict(
        nx.single_target_shortest_path_length(G, 0)
    )


def test_multidigraph_value_and_order():
    G = nx.MultiDiGraph()
    G.add_nodes_from(range(12))
    for node in range(11):
        G.add_edge(node, node + 1)
        G.add_edge(node, node + 1, key=f"p{node}")
    G.add_edges_from([(0, 5), (2, 8), (4, 8), (7, 11), (3, 10)])

    F = fnx.MultiDiGraph()
    F.add_nodes_from(G.nodes())
    for u, v, key in G.edges(keys=True):
        F.add_edge(u, v, key=key)

    for cutoff in (None, 0, 1, 2, 4):
        assert list(
            fnx.single_target_shortest_path_length(F, 11, cutoff=cutoff).items()
        ) == list(nx.single_target_shortest_path_length(G, 11, cutoff=cutoff).items())
        assert list(fnx.single_target_shortest_path(F, 11, cutoff=cutoff).items()) == list(
            nx.single_target_shortest_path(G, 11, cutoff=cutoff).items()
        )


def test_subgraphview():
    G = nx.gnp_random_graph(30, 0.2, seed=3)
    F = _cp(G)
    keep = list(range(12))
    sub = F.subgraph(keep)
    gsub = nx.subgraph(G, keep)
    assert fnx.single_target_shortest_path_length(sub, 2) == dict(
        nx.single_target_shortest_path_length(gsub, 2)
    )
