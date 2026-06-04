"""Parity for the reimplemented small-cutoff all_simple_paths (br-r37-c1-asplocal).

all_simple_paths delegated to networkx (full fnx->nx conversion per call), 24-100x
slower than networkx for a small-cutoff query. For a non-multigraph with a small
integer cutoff it now runs networkx's exact all_simple_edge_paths DFS directly on
the fnx graph -- same G.edges(node) iteration order, so the yielded node lists and
their order are byte-identical. Large cutoff / cutoff=None / multigraph keep
delegating.
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


def test_yield_order_parity_small_cutoff():
    for seed in range(400):
        rnd = random.Random(seed)
        m = rnd.randint(2, 40)
        directed = seed % 3 == 0
        G = nx.gnp_random_graph(m, rnd.uniform(0.05, 0.3), seed=seed, directed=directed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        F = _cp(G, directed)
        ns = list(G)
        if len(ns) < 2:
            continue
        for t in [ns[-1], tuple(ns[:3])]:
            for cut in [0, 1, 2, 3]:
                assert list(nx.all_simple_paths(G, ns[0], t, cut)) == list(
                    fnx.all_simple_paths(F, ns[0], t, cut)
                ), (seed, t, cut)


def test_large_cutoff_delegates_and_matches():
    G = nx.gnp_random_graph(20, 0.2, seed=2)
    F = _cp(G)
    for cut in [4, 6, None]:
        assert list(nx.all_simple_paths(G, 0, 19, cut)) == list(
            fnx.all_simple_paths(F, 0, 19, cut)
        )


def test_source_equals_target_trivial_path():
    G = nx.path_graph(5)
    F = _cp(G)
    assert list(fnx.all_simple_paths(F, 2, 2, 2)) == list(nx.all_simple_paths(G, 2, 2, 2))


def test_missing_source_raises():
    F = _cp(nx.path_graph(5))
    with pytest.raises(nx.NodeNotFound):
        list(fnx.all_simple_paths(F, 99, 0, 2))


def test_iterable_target():
    G = nx.gnp_random_graph(15, 0.25, seed=4)
    F = _cp(G)
    assert list(fnx.all_simple_paths(F, 0, [3, 7, 11], 3)) == list(
        nx.all_simple_paths(G, 0, [3, 7, 11], 3)
    )


def test_small_cutoff_is_fast():
    import time

    G = nx.connected_watts_strogatz_graph(600, 6, 0.2, seed=1)
    F = _cp(G)
    s, t = list(G)[0], list(G)[150]
    list(fnx.all_simple_paths(F, s, t, 2))  # warm
    t0 = time.perf_counter()
    list(fnx.all_simple_paths(F, s, t, 2))
    assert time.perf_counter() - t0 < 0.003  # was ~6.8ms via full conversion
