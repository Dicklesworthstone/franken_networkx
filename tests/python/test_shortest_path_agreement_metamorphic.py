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
