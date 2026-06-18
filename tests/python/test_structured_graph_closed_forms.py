"""Closed-form ground-truth values for named/structured graphs.

These assert mathematically-known values with NO networkx oracle, so they
catch bugs even if fnx and nx were to share one. They also exercise
``node_connectivity`` on adjacent-rich graphs (complete and complete
bipartite), validating the br-r37-c1-cqlms fix.

br-r37-c1-dn7c2
"""

from __future__ import annotations

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("m,n", [(2, 3), (3, 3), (2, 5), (4, 2), (1, 4)])
def test_complete_bipartite_closed_forms(m, n):
    g = fnx.complete_bipartite_graph(m, n)
    assert g.number_of_nodes() == m + n
    assert g.number_of_edges() == m * n
    assert fnx.is_bipartite(g)
    # K_{m,n} vertex/edge connectivity is min(m, n).
    assert fnx.node_connectivity(g) == min(m, n)
    assert fnx.edge_connectivity(g) == min(m, n)


@pytest.mark.parametrize("d", [2, 3, 4])
def test_hypercube_closed_forms(d):
    g = fnx.hypercube_graph(d)
    assert g.number_of_nodes() == 2 ** d
    assert g.number_of_edges() == d * 2 ** (d - 1)
    assert all(deg == d for _, deg in g.degree())  # d-regular
    assert fnx.diameter(g) == d
    assert fnx.node_connectivity(g) == d


def test_petersen_closed_forms():
    p = fnx.petersen_graph()
    assert p.number_of_nodes() == 10
    assert p.number_of_edges() == 15
    assert all(d == 3 for _, d in p.degree())       # 3-regular
    assert fnx.diameter(p) == 2
    assert fnx.radius(p) == 2
    assert fnx.node_connectivity(p) == 3
    assert fnx.edge_connectivity(p) == 3
    assert not fnx.is_bipartite(p)                    # girth 5 (odd cycle)


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_complete_graph_closed_forms(n):
    g = fnx.complete_graph(n)
    assert g.number_of_edges() == n * (n - 1) // 2
    assert fnx.node_connectivity(g) == n - 1
    assert fnx.edge_connectivity(g) == n - 1
    assert fnx.diameter(g) == 1


@pytest.mark.parametrize("n", [4, 5, 6])
def test_cycle_graph_closed_forms(n):
    g = fnx.cycle_graph(n)
    assert g.number_of_edges() == n
    assert fnx.node_connectivity(g) == 2
    assert fnx.diameter(g) == n // 2
    assert fnx.is_bipartite(g) == (n % 2 == 0)
