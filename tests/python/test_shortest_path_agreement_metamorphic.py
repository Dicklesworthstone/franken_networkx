"""Oracle-free agreement tests across shortest-path algorithms.

Three independent algorithms must agree, and the distances must satisfy the
metric properties that define them — catching bugs no single-algorithm test
would surface:

- **Dijkstra == Bellman-Ford** on non-negative weights (two independent
  algorithms must produce identical distances).
- **Triangle inequality**: for every edge (v, w), |d(s,v) - d(s,w)| <= w(v,w).
- **Hop-count bound**: unweighted BFS depth <= weighted distance when every
  weight >= 1.
- **Symmetry** on undirected graphs: d(s, t) == d(t, s).

No mocks: real fnx on randomly generated weighted graphs.

br-r37-c1-cgi0s
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _random_weighted_graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.45:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


@pytest.mark.parametrize("seed", range(70))
def test_dijkstra_equals_bellman_ford(seed):
    g, n = _random_weighted_graph(seed)
    src = 0
    if g.degree(src) == 0:
        pytest.skip("isolated source")
    dij = dict(fnx.single_source_dijkstra_path_length(g, src))
    bf = dict(fnx.single_source_bellman_ford_path_length(g, src))
    assert dij == bf


@pytest.mark.parametrize("seed", range(70))
def test_triangle_inequality_and_hop_bound(seed):
    g, n = _random_weighted_graph(seed)
    src = 0
    if g.degree(src) == 0:
        pytest.skip("isolated source")
    dij = dict(fnx.single_source_dijkstra_path_length(g, src))
    for v, w, d in g.edges(data=True):
        if v in dij and w in dij:
            assert abs(dij[v] - dij[w]) <= d["weight"] + 1e-9
    hops = dict(fnx.single_source_shortest_path_length(g, src))
    for node, dist in dij.items():
        # weights >= 1, so hop count never exceeds weighted distance.
        assert hops.get(node, 0) <= dist + 1e-9


@pytest.mark.parametrize("seed", range(40))
def test_undirected_distance_symmetry(seed):
    g, n = _random_weighted_graph(seed)
    r = random.Random(seed + 1000)
    s, t = r.randrange(n), r.randrange(n)
    d_st = dict(fnx.single_source_dijkstra_path_length(g, s))
    d_ts = dict(fnx.single_source_dijkstra_path_length(g, t))
    if t in d_st:
        assert d_st[t] == d_ts[s]


@pytest.mark.parametrize("seed", range(70))
def test_dijkstra_agrees_with_floyd_warshall_and_johnson(seed):
    """The docstring claims agreement across THREE implementations.

    Only two are compared for equality — Dijkstra and Bellman-Ford. The third
    named source, unweighted BFS, supplies a BOUND rather than an equality, so
    no third algorithm ever had to produce the same distances. Floyd-Warshall
    (all-pairs, a different family entirely) and Johnson do.
    """
    g, _ = _random_weighted_graph(seed)
    src = 0
    dijkstra = dict(fnx.single_source_dijkstra_path_length(g, src))

    floyd = {
        node: dist
        for node, dist in dict(fnx.floyd_warshall(g))[src].items()
        if dist != float("inf")
    }
    assert floyd == dijkstra

    # Johnson returns paths; their weights must be the same distances.
    johnson_paths = dict(fnx.johnson(g))[src]
    johnson_lengths = {
        node: sum(g[a][b]["weight"] for a, b in zip(path, path[1:]))
        for node, path in johnson_paths.items()
    }
    assert johnson_lengths == dijkstra


def test_bellman_ford_handles_negative_weights():
    """Negative weights are what distinguishes Bellman-Ford from Dijkstra.

    The random family draws weights in 1..9, so the one capability that makes
    the two algorithms genuinely independent is never exercised.
    """
    g = fnx.DiGraph()
    g.add_edge(0, 1, weight=4)
    g.add_edge(1, 2, weight=-2)
    g.add_edge(0, 2, weight=5)

    lengths = dict(fnx.single_source_bellman_ford_path_length(g, 0))
    # 0 -> 1 -> 2 costs 2, which beats the direct edge of 5.
    assert lengths == {0: 0, 1: 4, 2: 2}


def test_negative_cycle_is_reported():
    """A negative cycle makes shortest paths undefined; it must not be answered."""
    g = fnx.DiGraph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=-3)
    g.add_edge(2, 0, weight=1)

    with pytest.raises(fnx.NetworkXUnbounded):
        fnx.single_source_bellman_ford_path_length(g, 0)
