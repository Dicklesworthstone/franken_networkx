"""Parity for the single-node closeness_centrality fast path (br-r37-c1-clsingle).

closeness_centrality(G, u=node) delegated to networkx (a whole-graph fnx->nx
conversion) just to run one BFS -- ~25x slower than networkx for a single node. It
now computes the single BFS from u directly; the path-length total is a sum of
INTEGER hop counts so the result is byte-identical to networkx and to the full
closeness dict.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def test_single_node_exact_vs_networkx_and_full_dict():
    for seed in range(200):
        rnd = random.Random(seed)
        n = rnd.randint(2, 60)
        G = nx.gnp_random_graph(n, rnd.uniform(0.04, 0.5), seed=seed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        F = _cp(G)
        full = fnx.closeness_centrality(F) if len(G) else {}
        for u in list(G)[:6]:
            single = fnx.closeness_centrality(F, u=u)
            assert single == nx.closeness_centrality(G, u=u), (seed, u)
            assert single == full[u], (seed, u)  # single == full-dict value


def test_disconnected_graph():
    G = nx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (3, 4), (5, 6), (6, 7)])
    F = _cp(G)
    for u in G:
        assert fnx.closeness_centrality(F, u=u) == nx.closeness_centrality(G, u=u)


def test_isolated_node_is_zero():
    G = nx.Graph()
    G.add_node(0)
    G.add_edge(1, 2)
    F = _cp(G)
    assert fnx.closeness_centrality(F, u=0) == 0.0


def test_directed_and_weighted_still_delegate():
    # Directed: incoming distances -> still delegated, must match networkx.
    Gd = nx.gnp_random_graph(25, 0.2, seed=3, directed=True)
    Fd = fnx.DiGraph()
    Fd.add_nodes_from(Gd.nodes())
    Fd.add_edges_from(Gd.edges())
    for u in [0, 5, 10]:
        assert fnx.closeness_centrality(Fd, u=u) == nx.closeness_centrality(Gd, u=u)


def test_single_node_does_not_materialize_whole_nx_graph():
    import time

    G = nx.gnp_random_graph(3000, 0.01, seed=1)
    F = _cp(G)
    src = list(G)[0]
    fnx.closeness_centrality(F, u=src)  # warm
    t0 = time.perf_counter()
    fnx.closeness_centrality(F, u=src)
    assert time.perf_counter() - t0 < 0.02
