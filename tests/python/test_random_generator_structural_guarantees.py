"""Random graph generators: seed-independent structural guarantees.

Random generators are non-deterministic in their edge placement, but each
guarantees an exact structure regardless of seed:
  - gnm_random_graph(n, m): exactly n nodes and m edges;
  - barabasi_albert_graph(n, m): n nodes, m*(n-m) edges, connected;
  - watts_strogatz_graph(n, k, p): n nodes, n*k/2 edges (rewiring keeps count);
  - random_regular_graph(d, n): n nodes all of degree d, d*n/2 edges.
These are oracle-free structural invariants that hold for every seed.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(30))
def test_gnm_exact_node_and_edge_count(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    m = min(r.randint(n - 1, 2 * n), n * (n - 1) // 2)
    g = fnx.gnm_random_graph(n, m, seed=seed)
    assert g.number_of_nodes() == n
    assert g.number_of_edges() == m


@pytest.mark.parametrize("seed", range(30))
def test_barabasi_albert_structure(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    m = r.randint(1, 4)
    if n <= m:
        pytest.skip("n must exceed m")
    ba = fnx.barabasi_albert_graph(n, m, seed=seed)
    assert ba.number_of_nodes() == n
    assert ba.number_of_edges() == m * (n - m)   # each of n-m added nodes brings m edges
    assert fnx.is_connected(ba)                   # BA graphs are connected


@pytest.mark.parametrize("seed", range(30))
def test_watts_strogatz_edge_count(seed):
    r = random.Random(seed)
    n = r.randint(8, 15)
    k = 2 * r.randint(1, 3)
    if k >= n:
        pytest.skip("k must be < n")
    ws = fnx.watts_strogatz_graph(n, k, 0.3, seed=seed)
    assert ws.number_of_nodes() == n
    assert ws.number_of_edges() == n * k // 2     # rewiring preserves edge count


@pytest.mark.parametrize("seed", range(30))
def test_random_regular_graph_is_regular(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    d = r.randint(2, 4)
    if (d * n) % 2 != 0 or d >= n:
        pytest.skip("d*n must be even and d < n")
    rr = fnx.random_regular_graph(d, n, seed=seed)
    assert all(deg == d for _, deg in rr.degree())
    assert rr.number_of_edges() == d * n // 2
