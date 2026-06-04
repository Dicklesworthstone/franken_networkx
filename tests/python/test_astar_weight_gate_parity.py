"""Parity for the gated A* weight-validation fast path (br-r37-c1-astgate).

astar_path / astar_path_length ran three O(|E|) weight scans (each re-syncing
inner -> 4x redundant sync) unconditionally on every call, even for unweighted
graphs whose native A* search is ~0.05ms. They now sync once and run the
negative/inf/nonnumeric scans only when a cheap native graph_has_edge_attr probe
says the graph carries the weight attribute. Behaviour is unchanged: an unweighted
graph never triggers those scans, and weighted graphs (incl. post-construction
mutations, seen after the single sync) still run all of them.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G, directed=False, weighted=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges(data=True) if weighted else G.edges())
    return F


def test_unweighted_exact_and_weighted_tol():
    for seed in range(200):
        rnd = random.Random(seed)
        n = rnd.randint(4, 45)
        directed = seed % 3 == 0
        weighted = seed % 2 == 0
        G = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed, directed=directed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        if weighted:
            for u, v in G.edges():
                G[u][v]["weight"] = rnd.uniform(0.5, 5)
        F = _cp(G, directed, weighted)
        ns = list(G)
        if len(ns) < 2:
            continue
        s, t = ns[0], ns[-1]
        try:
            a = nx.astar_path_length(G, s, t)
            ea = None
        except Exception as e:  # noqa: BLE001
            a, ea = None, type(e)
        try:
            b = fnx.astar_path_length(F, s, t)
            eb = None
        except Exception as e:  # noqa: BLE001
            b, eb = None, type(e)
        if ea is not None or eb is not None:
            assert ea is eb, (seed, ea, eb)
        elif weighted:
            assert abs(a - b) <= 1e-9, (seed, a, b)
        else:
            assert a == b, (seed, a, b)  # unweighted is bit-exact


def test_post_construction_weight_mutation_seen():
    # Weight added by item assignment after construction must still be honoured
    # (the single up-front sync pushes it to inner before the scans/kernel).
    F = fnx.Graph()
    F.add_nodes_from([0, 1, 2, 3])
    F.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3)])
    F[0][1]["weight"] = 1.0
    F[1][2]["weight"] = 1.0
    F[2][3]["weight"] = 1.0
    F[0][3]["weight"] = 10.0  # direct edge expensive -> path goes the long way
    G = nx.Graph()
    G.add_edges_from(
        [(0, 1, {"weight": 1.0}), (1, 2, {"weight": 1.0}), (2, 3, {"weight": 1.0}), (0, 3, {"weight": 10.0})]
    )
    assert fnx.astar_path_length(F, 0, 3) == nx.astar_path_length(G, 0, 3) == 3.0


def test_negative_and_nonnumeric_weight_delegate():
    Gn = nx.Graph()
    Gn.add_edge(0, 1, weight=-2)
    Gn.add_edge(1, 2, weight=1)
    Fn = _cp(Gn, weighted=True)
    # both should agree (nx may raise / return; fnx delegates to match)
    a = nx.astar_path_length(Gn, 0, 2)
    b = fnx.astar_path_length(Fn, 0, 2)
    assert a == b
    Gs = nx.Graph()
    Gs.add_edge(0, 1, weight="x")
    Gs.add_edge(1, 2, weight="y")
    Fs = _cp(Gs, weighted=True)
    with pytest.raises(TypeError):
        fnx.astar_path_length(Fs, 0, 2)


def test_unweighted_single_pair_is_fast():
    import time

    G = nx.connected_watts_strogatz_graph(2000, 6, 0.2, seed=1)
    F = _cp(G)
    s, t = list(G)[0], list(G)[3]
    fnx.astar_path_length(F, s, t)  # warm
    t0 = time.perf_counter()
    fnx.astar_path_length(F, s, t)
    assert time.perf_counter() - t0 < 0.05  # was ~12ms with 4x sync + 3 scans
