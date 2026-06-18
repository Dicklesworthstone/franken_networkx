"""BFS / DFS tree distance invariants (traversal trees <-> shortest paths).

A BFS tree from a root encodes shortest paths in an unweighted graph, so a
node's depth in bfs_tree equals its shortest-path distance from the root. A DFS
tree is also a spanning tree of the reachable component, but its depths are only
>= the shortest-path distances. These cross-check bfs_tree, dfs_tree, and
single_source_shortest_path_length:
  - bfs_tree / dfs_tree span exactly the reachable nodes and are trees (n-1 edges);
  - depth_in(bfs_tree, v) == dist(root, v);
  - depth_in(dfs_tree, v) >= dist(root, v).
Oracle-free, independent of networkx (edge parity is covered separately).

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


@pytest.mark.parametrize("seed", range(40))
def test_bfs_tree_depth_equals_distance(seed):
    g = _graph(seed)
    root = 0
    bt = fnx.bfs_tree(g, root)
    dist = fnx.single_source_shortest_path_length(g, root)
    depth = fnx.single_source_shortest_path_length(bt, root)

    # Spans exactly the reachable nodes, and is a tree.
    assert set(bt.nodes()) == set(dist.keys())
    assert bt.number_of_edges() == bt.number_of_nodes() - 1
    # BFS depth equals the graph shortest-path distance.
    for v in bt:
        assert depth[v] == dist[v]


@pytest.mark.parametrize("seed", range(40))
def test_dfs_tree_is_spanning_with_depth_geq_distance(seed):
    g = _graph(seed)
    root = 0
    dt = fnx.dfs_tree(g, root)
    dist = fnx.single_source_shortest_path_length(g, root)
    depth = fnx.single_source_shortest_path_length(dt, root)

    assert set(dt.nodes()) == set(dist.keys())
    if dt.number_of_nodes() > 0:
        assert dt.number_of_edges() == dt.number_of_nodes() - 1
    # A DFS-tree path is at least as long as the shortest path.
    for v in dt:
        assert depth[v] >= dist[v]


def test_bfs_tree_on_cycle_has_two_branches():
    # On C_6 rooted at 0, BFS reaches the antipode (node 3) at depth 3 via both
    # directions; depth equals the shortest distance (3).
    g = fnx.cycle_graph(6)
    bt = fnx.bfs_tree(g, 0)
    depth = fnx.single_source_shortest_path_length(bt, 0)
    assert depth[3] == 3
    assert max(depth.values()) == 3  # graph radius from 0 on C_6
