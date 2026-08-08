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
    # br-r37-c1-2wi7g: compare ORDER, not just structure. These assertions used
    # to sort both sides, which pins the tree's edge SET but is blind to the
    # iteration order — the exact property this module exists to verify. A
    # traversal that visited neighbours in a different order would still emit
    # the same edge set and pass a sorted comparison. Order-exact equality was
    # confirmed to hold across all 50 seeds before the assertions were
    # tightened, so this locks behaviour that already ships rather than
    # asserting an aspiration.
    fg, ng, n = _identical_pair(seed)
    assert list(fnx.bfs_tree(fg, 0).edges()) == list(nx.bfs_tree(ng, 0).edges())
    assert list(fnx.dfs_tree(fg, 0).edges()) == list(nx.dfs_tree(ng, 0).edges())
    assert [(k, list(v)) for k, v in fnx.bfs_successors(fg, 0)] == (
        [(k, list(v)) for k, v in nx.bfs_successors(ng, 0)]
    )
    assert fnx.single_source_shortest_path(fg, 0) == (
        nx.single_source_shortest_path(ng, 0)
    )


@pytest.mark.parametrize("seed", range(50))
def test_exact_traversal_edge_stream_parity(seed):
    # br-r37-c1-2wi7g: the raw edge streams were not covered at all, and they
    # are the most order-sensitive members of this family — bfs_tree/dfs_tree
    # can agree as graphs while the stream that built them differs in order.
    fg, ng, _ = _identical_pair(seed)
    assert list(fnx.bfs_edges(fg, 0)) == list(nx.bfs_edges(ng, 0))
    assert list(fnx.dfs_edges(fg, 0)) == list(nx.dfs_edges(ng, 0))
