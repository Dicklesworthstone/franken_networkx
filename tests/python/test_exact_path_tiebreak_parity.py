"""Exact-path / traversal-tree parity with networkx (tie-breaking).

When several shortest paths tie, returning *a* valid shortest path is correct
but returning the *same* one networkx returns is a stronger property — it means
fnx reproduces nx's traversal/iteration order exactly. This pins the exact path
and tree structures (not just lengths/counts), which is where tie-break
divergences would show.

NOTE: graphs are built with identical node order in both libraries so traversal
order is comparable (an edge-list-constructed nx graph would permute iteration
order and inject a false mismatch).

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_pair(seed):
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_exact_shortest_path_parity(seed):
    fg, ng, n = _identical_pair(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    r = random.Random(seed + 5000)
    for _ in range(4):
        s, t = r.sample(range(n), 2)
        assert fnx.shortest_path(fg, s, t) == nx.shortest_path(ng, s, t)
        assert fnx.dijkstra_path(fg, s, t) == nx.dijkstra_path(ng, s, t)
        assert fnx.bidirectional_shortest_path(fg, s, t) == (
            nx.bidirectional_shortest_path(ng, s, t)
        )


@pytest.mark.parametrize("seed", range(50))
def test_exact_traversal_tree_parity(seed):
    fg, ng, n = _identical_pair(seed)
    assert sorted(fnx.bfs_tree(fg, 0).edges()) == sorted(nx.bfs_tree(ng, 0).edges())
    assert sorted(fnx.dfs_tree(fg, 0).edges()) == sorted(nx.dfs_tree(ng, 0).edges())
    assert {k: sorted(v) for k, v in fnx.bfs_successors(fg, 0)} == (
        {k: sorted(v) for k, v in nx.bfs_successors(ng, 0)}
    )
    assert fnx.single_source_shortest_path(fg, 0) == (
        nx.single_source_shortest_path(ng, 0)
    )
