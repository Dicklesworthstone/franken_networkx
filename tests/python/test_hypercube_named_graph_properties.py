"""Closed-form properties of the hypercube and other structured named graphs.

These named graphs have exact structural fingerprints (ground-truth, independent
of networkx), complementing the earlier named-graph closed-form test:
  - hypercube Q_n: 2^n nodes, n*2^(n-1) edges, n-regular, bipartite, diameter n,
    triangle-free;
  - wheel W_n: a hub joined to a cycle of n nodes -> n+1 nodes, 2n edges;
  - grid m x k: m*k nodes, 2*m*k - m - k edges, bipartite;
  - ladder L_n: 2n nodes, 3n-2 edges.

No mocks: real fnx against textbook structure.
"""

from __future__ import annotations

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_hypercube_structure(n):
    q = fnx.hypercube_graph(n)
    assert q.number_of_nodes() == 2 ** n
    assert q.number_of_edges() == n * 2 ** (n - 1)
    assert all(d == n for _, d in q.degree())     # n-regular
    assert fnx.is_bipartite(q)                      # hypercubes are bipartite
    assert sum(fnx.triangles(q).values()) == 0      # triangle-free
    if q.number_of_nodes() > 1:
        assert fnx.diameter(q) == n                 # diameter is the dimension


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_wheel_structure(n):
    # wheel_graph(n) has n nodes: a hub joined to a rim cycle on the other n-1.
    # For n >= 4 the rim is a proper cycle of n-1 edges (n=3 degenerates to K_3).
    w = fnx.wheel_graph(n)
    assert w.number_of_nodes() == n
    assert w.number_of_edges() == 2 * (n - 1)       # (n-1) spokes + (n-1) rim


@pytest.mark.parametrize("m,k", [(2, 3), (3, 3), (2, 4), (3, 5)])
def test_grid_structure(m, k):
    g = fnx.grid_2d_graph(m, k)
    assert g.number_of_nodes() == m * k
    assert g.number_of_edges() == 2 * m * k - m - k   # horizontal + vertical
    assert fnx.is_bipartite(g)                          # grids are bipartite


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_ladder_structure(n):
    lad = fnx.ladder_graph(n)
    assert lad.number_of_nodes() == 2 * n
    assert lad.number_of_edges() == 3 * n - 2          # two rails + n rungs
    assert fnx.is_bipartite(lad)
