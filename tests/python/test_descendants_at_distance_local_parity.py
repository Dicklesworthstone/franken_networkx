"""Parity for the local-BFS descendants_at_distance fast path (br-r37-c1-dadlocal).

The native kernel pays an O(V+E) node-index/adjacency setup even for a local
small-distance query, making descendants_at_distance 30-750x slower than networkx
for distance 1-2. It now runs networkx's exact layer BFS directly on the fnx graph,
bailing to the native kernel only when the frontier goes "global" (visited > 64).
The result is a set (order-invariant), so it stays byte-identical to networkx and
to the native kernel.
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


def test_integer_distance_parity():
    for seed in range(250):
        rnd = random.Random(seed)
        m = rnd.randint(1, 80)
        directed = seed % 3 == 0
        G = nx.gnp_random_graph(m, rnd.uniform(0.03, 0.5), seed=seed, directed=directed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        F = _cp(G, directed)
        for s in list(G)[:3]:
            for dist in [0, 1, 2, 3, 4, 6, 12]:
                assert nx.descendants_at_distance(G, s, dist) == fnx.descendants_at_distance(
                    F, s, dist
                ), (seed, s, dist)


def test_bail_path_matches_native_on_dense_far_query():
    # A high-degree graph reaches "global" quickly -> exercises the bail-to-native
    # path; the result must match networkx.
    G = nx.gnp_random_graph(300, 0.2, seed=7)
    F = _cp(G)
    for dist in [2, 3, 4, 8]:
        assert nx.descendants_at_distance(G, 0, dist) == fnx.descendants_at_distance(F, 0, dist)


def test_missing_source_raises_networkx_error():
    F = _cp(nx.path_graph(5))
    with pytest.raises(nx.NetworkXError):
        fnx.descendants_at_distance(F, 99, 2)


def test_negative_distance_empty():
    F = _cp(nx.path_graph(5))
    assert fnx.descendants_at_distance(F, 0, -3) == set()


def test_distance_one_is_neighbors_and_fast():
    import time

    G = nx.connected_watts_strogatz_graph(5000, 6, 0.2, seed=1)
    F = _cp(G)
    src = list(G)[0]
    assert fnx.descendants_at_distance(F, src, 1) == set(G[src])
    fnx.descendants_at_distance(F, src, 1)  # warm
    t0 = time.perf_counter()
    fnx.descendants_at_distance(F, src, 1)
    assert time.perf_counter() - t0 < 0.005  # was ~2.3ms via whole-graph native setup
