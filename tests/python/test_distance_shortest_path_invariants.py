"""Oracle-free invariants for distance metrics and shortest paths.

Asserts relations that hold by definition/theorem without using networkx
as an oracle:

* diameter == max eccentricity, radius == min eccentricity
* center / periphery match their eccentricity definitions
* shortest-path lengths obey the triangle inequality
* every weighted shortest-path algorithm agrees:
  dijkstra == bellman_ford == bidirectional_dijkstra == floyd_warshall == astar

br-r37-c1-dkw4f
"""

from __future__ import annotations

import itertools
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_unweighted(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    ng = nx.Graph(g.edges())
    ng.add_nodes_from(range(n))
    return g, ng, n


def _weighted(seed, directed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                g.add_edge(u, v, weight=rng.randint(1, 9))
    return g, n


@pytest.mark.parametrize("seed", range(60))
def test_distance_metric_self_consistency(seed):
    g, ng, n = _connected_unweighted(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    ecc = fnx.eccentricity(g)
    diameter = fnx.diameter(g)
    radius = fnx.radius(g)
    assert diameter == max(ecc.values())
    assert radius == min(ecc.values())
    assert set(fnx.center(g)) == {v for v in ecc if ecc[v] == radius}
    assert set(fnx.periphery(g)) == {v for v in ecc if ecc[v] == diameter}


@pytest.mark.parametrize("seed", range(60))
def test_shortest_path_triangle_inequality(seed):
    g, ng, n = _connected_unweighted(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    spl = {k: dict(v) for k, v in fnx.all_pairs_shortest_path_length(g)}
    for a, b, c in itertools.permutations(range(n), 3):
        assert spl[a][c] <= spl[a][b] + spl[b][c]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_weighted_shortest_path_algorithms_agree(directed, seed):
    g, n = _weighted(seed, directed)
    fw = {k: dict(v) for k, v in fnx.floyd_warshall(g, weight="weight").items()}
    for s in range(min(3, n)):
        for t in range(n):
            if s == t:
                continue
            try:
                dij = fnx.dijkstra_path_length(g, s, t, weight="weight")
            except nx.NetworkXNoPath:
                continue
            assert fnx.bellman_ford_path_length(g, s, t, weight="weight") == pytest.approx(dij)
            assert fnx.bidirectional_dijkstra(g, s, t, weight="weight")[0] == pytest.approx(dij)
            assert fnx.astar_path_length(g, s, t, weight="weight") == pytest.approx(dij)
            assert fw[s][t] == pytest.approx(dij)
