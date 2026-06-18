"""Oracle-free traversal / ordering invariants.

* ``topological_sort`` and ``lexicographical_topological_sort`` place the
  tail of every edge before its head
* ``bipartite.color`` is a proper 2-colouring of a bipartite graph
* a BFS tree rooted at ``r`` records, for each node, its true unweighted
  shortest-path distance from ``r`` (BFS shortest-path property)

br-r37-c1-hfj5a
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fnx_bip


def _random_dag(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # u < v keeps it acyclic
            if rng.random() < p:
                g.add_edge(u, v)
    return g


@pytest.mark.parametrize("seed", range(60))
def test_topological_orders_respect_every_edge(seed):
    g = _random_dag(seed)
    for order in (
        list(fnx.topological_sort(g)),
        list(fnx.lexicographical_topological_sort(g)),
    ):
        pos = {node: i for i, node in enumerate(order)}
        assert len(order) == g.number_of_nodes()
        assert all(pos[u] < pos[v] for u, v in g.edges())


@pytest.mark.parametrize("seed", range(60))
def test_bipartite_color_is_proper(seed):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    top = list(range(n // 2))
    bot = list(range(n // 2, n))
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in top:
        for v in bot:
            if rng.random() < 0.4:
                g.add_edge(u, v)
    if not fnx.is_bipartite(g):
        pytest.skip("not bipartite")
    color = fnx_bip.color(g)
    assert all(color[u] != color[v] for u, v in g.edges())


@pytest.mark.parametrize("seed", range(60))
def test_bfs_tree_encodes_shortest_path_distances(seed):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.4:
                g.add_edge(u, v)
    tree = nx.Graph(list(fnx.bfs_tree(g, 0).edges()))
    tree.add_node(0)
    dist = fnx.single_source_shortest_path_length(g, 0)
    for node in dist:
        if node == 0:
            continue
        assert nx.shortest_path_length(tree, 0, node) == dist[node]
