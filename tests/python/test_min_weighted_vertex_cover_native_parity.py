"""Parity for the native min_weighted_vertex_cover (no fnx->nx conversion).

br-vcnative: fnx.approximation.min_weighted_vertex_cover went through the generic
_ApproximationNamespace.__getattr__ wrapper, which round-trips the graph through
_networkx_graph_for_parity (an O(n^2) fnx->nx conversion) and runs nx's pure-
Python loop over the slow fnx views -- ~28x SLOWER than networkx at n=1500. It now
calls a native Rust kernel that replicates nx's edge-order local-ratio greedy
EXACTLY: walk the integer adjacency, process pair (u, v) only when index u <= v
(networkx's by-node-position dedup + orientation, incl. self-loops), with
weight=None meaning unit weights (networkx ignores node weight attrs then).
Directed graphs (where networkx iterates directed edges) still delegate. The
result is set-identical to networkx; fnx is now ~15x FASTER than networkx and the
margin grows with n.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges(data=True))
    return F


def test_unweighted_weighted_and_none_with_attrs():
    for seed in range(150):
        rnd = random.Random(seed)
        n = rnd.randint(0, 55)
        G = nx.gnp_random_graph(n, rnd.uniform(0.03, 0.5), seed=seed)
        mode = seed % 3  # 0: no attrs; 1: weighted; 2: attrs present but weight=None
        if mode in (1, 2):
            for nd in G.nodes():
                G.nodes[nd]["weight"] = rnd.randint(1, 9)
        wk = "weight" if mode == 1 else None
        F = _cp(G)
        assert set(nx.approximation.min_weighted_vertex_cover(G, weight=wk)) == set(
            fnx.approximation.min_weighted_vertex_cover(F, weight=wk)
        ), (seed, mode)


def test_weight_none_ignores_node_weight_attrs():
    # networkx weight=None gives every node weight 1, ignoring any "weight" attr.
    G = nx.Graph([(0, 1), (1, 2), (2, 3)])
    for nd, w in zip(G.nodes(), [100, 1, 100, 1]):
        G.nodes[nd]["weight"] = w
    F = _cp(G)
    assert set(fnx.approximation.min_weighted_vertex_cover(F, weight=None)) == set(
        nx.approximation.min_weighted_vertex_cover(G, weight=None)
    )
    assert set(fnx.approximation.min_weighted_vertex_cover(F, weight="weight")) == set(
        nx.approximation.min_weighted_vertex_cover(G, weight="weight")
    )


def test_self_loops():
    for seed in range(30):
        rnd = random.Random(seed + 500)
        G = nx.gnp_random_graph(rnd.randint(3, 25), 0.2, seed=seed)
        G.add_edge(0, 0)
        G.add_edge(1, 1)
        F = _cp(G)
        cover = fnx.approximation.min_weighted_vertex_cover(F)
        assert set(cover) == set(nx.approximation.min_weighted_vertex_cover(G))
        # self-loop nodes must be covered
        assert 0 in cover and 1 in cover


def test_directed_delegates_and_matches():
    for seed in range(30):
        G = nx.gnp_random_graph(random.Random(seed).randint(4, 30), 0.15, seed=seed, directed=True)
        F = _cp(G, directed=True)
        assert set(fnx.approximation.min_weighted_vertex_cover(F)) == set(
            nx.approximation.min_weighted_vertex_cover(G)
        )


def test_result_is_a_valid_cover():
    G = nx.gnp_random_graph(60, 0.1, seed=9)
    F = _cp(G)
    cover = fnx.approximation.min_weighted_vertex_cover(F)
    assert all(u in cover or v in cover for u, v in G.edges())


def test_empty_graph():
    assert fnx.approximation.min_weighted_vertex_cover(fnx.Graph()) == set()
