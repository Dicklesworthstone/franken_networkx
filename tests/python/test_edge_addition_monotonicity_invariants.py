"""Oracle-free monotonicity under edge addition.

Adding an edge to a simple graph can only move certain metrics one way.
These relations need no oracle and catch metrics that respond incorrectly
to a graph modification:

* ``node_connectivity`` and ``edge_connectivity`` are non-decreasing
* triangle count is non-decreasing
* ``number_connected_components`` is non-increasing
* ``diameter`` (when both graphs are connected) is non-increasing

br-r37-c1-qtmd6
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph_and_extra_edge(seed, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    non_edges = [
        (u, v) for u in range(n) for v in range(u + 1, n) if (u, v) not in set(edges)
    ]
    if not non_edges:
        return None
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    g2 = g.copy()
    g2.add_edge(*rng.choice(non_edges))
    return g, g2, n


@pytest.mark.parametrize("seed", range(80))
def test_connectivity_non_decreasing(seed):
    res = _graph_and_extra_edge(seed)
    if res is None:
        pytest.skip("complete graph")
    g, g2, _ = res
    assert fnx.node_connectivity(g2) >= fnx.node_connectivity(g)
    assert fnx.edge_connectivity(g2) >= fnx.edge_connectivity(g)


@pytest.mark.parametrize("seed", range(80))
def test_triangles_non_decreasing_and_components_non_increasing(seed):
    res = _graph_and_extra_edge(seed)
    if res is None:
        pytest.skip("complete graph")
    g, g2, _ = res
    assert sum(fnx.triangles(g2).values()) >= sum(fnx.triangles(g).values())
    assert fnx.number_connected_components(g2) <= fnx.number_connected_components(g)


@pytest.mark.parametrize("seed", range(80))
def test_diameter_non_increasing_when_connected(seed):
    res = _graph_and_extra_edge(seed)
    if res is None:
        pytest.skip("complete graph")
    g, g2, n = res
    ng = nx.Graph(list(g.edges()))
    ng.add_nodes_from(range(n))
    ng2 = nx.Graph(list(g2.edges()))
    ng2.add_nodes_from(range(n))
    if nx.is_connected(ng) and nx.is_connected(ng2):
        assert fnx.diameter(g2) <= fnx.diameter(g)
