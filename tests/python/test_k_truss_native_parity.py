"""Parity for the native k_truss kernel + rebuild (br-r37-c1-jboes).

k_truss delegated to networkx via the heavy _fnx_to_nx conversion (~2.9x slower).
It now calls the native k_truss_rust kernel (k-truss node/edge sets computed
directly on the fnx adjacency, no conversion) and rebuilds the result subgraph in
G's own node/edge order -- byte-identical to networkx (nodes, edges, adjacency
order, node/edge/graph attributes) and at parity with networkx instead of ~3x
slower.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G, attrs=False):
    F = fnx.Graph()
    if attrs:
        F.add_nodes_from(G.nodes(data=True))
        F.add_edges_from(G.edges(data=True))
        F.graph.update(G.graph)
    else:
        F.add_nodes_from(G.nodes())
        F.add_edges_from(G.edges())
    return F


def _full(H):
    return (
        list(H.nodes(data=True)),
        list(H.edges(data=True)),
        {n: list(H[n]) for n in H},
        dict(H.graph),
    )


def test_exact_parity_including_order_and_attrs():
    for seed in range(300):
        rnd = random.Random(seed)
        m = rnd.randint(3, 55)
        g = nx.gnp_random_graph(m, rnd.uniform(0.08, 0.6), seed=seed)
        if seed % 4 == 0:
            g = nx.relabel_nodes(g, {i: f"x{i}" for i in g})
        attrs = seed % 3 == 0
        if attrs:
            g.graph["name"] = f"G{seed}"
            for n in g:
                g.nodes[n]["w"] = str(n)
            for u, v in g.edges():
                g[u][v]["weight"] = 1.25
        f = _cp(g, attrs)
        for k in [2, 3, 4, 5, 6, 7]:
            assert _full(nx.k_truss(g, k)) == _full(fnx.k_truss(f, k)), (seed, k)


def test_result_is_mutable_fnx_graph():
    G = nx.gnp_random_graph(30, 0.4, seed=1)
    F = _cp(G)
    H = fnx.k_truss(F, 3)
    assert isinstance(H, fnx.Graph)
    H.add_edge("new_a", "new_b")  # must be mutable


def test_multigraph_directed_rejected():
    for ctor in (fnx.MultiGraph, fnx.DiGraph):
        g = ctor()
        g.add_edges_from([(0, 1), (1, 2), (2, 0)])
        with pytest.raises(nx.NetworkXNotImplemented):
            fnx.k_truss(g, 3)


def test_n400_is_not_slow():
    import time

    G = nx.connected_watts_strogatz_graph(400, 8, 0.3, seed=1)
    F = _cp(G)
    fnx.k_truss(F, 4)  # warm
    t0 = time.perf_counter()
    fnx.k_truss(F, 4)
    assert time.perf_counter() - t0 < 0.05  # was ~16-22ms via double conversion
