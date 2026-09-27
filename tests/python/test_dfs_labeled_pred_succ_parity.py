"""Differential + golden parity for labeled DFS and BFS/DFS pred/succ maps.

Covers ``dfs_labeled_edges`` (yields ``(u, v, direction)`` where direction
is forward/reverse/nontree) and the ``bfs_predecessors`` /
``bfs_successors`` / ``dfs_successors`` / ``dfs_predecessors`` maps. None
had a dedicated test file. All are order-deterministic.

br-r37-c1-w7wwr
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_dfs_labeled_edges_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert list(fnx.dfs_labeled_edges(fg, 0)) == list(nx.dfs_labeled_edges(ng, 0))


@pytest.mark.parametrize(
    "fn", ["bfs_predecessors", "bfs_successors", "dfs_successors", "dfs_predecessors"]
)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_pred_succ_maps_match_networkx(fn, directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert dict(getattr(fnx, fn)(fg, 0)) == dict(getattr(nx, fn)(ng, 0))


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("edges", [[(0, 1), (1, 2)], []], ids=["path", "null"])
@pytest.mark.parametrize("depth_limit", [None, 1])
def test_dfs_labeled_edges_missing_source_raises_like_networkx(cls, edges, depth_limit):
    # br-r37-c1-750hp: nx yields (s, s, 'forward') and then G.neighbors(s)
    # raises NetworkXError("The node s is not in the graph." / "digraph."); fnx
    # raised KeyError from its adjacency snapshot.
    def outcome(lib):
        it = lib.dfs_labeled_edges(getattr(lib, cls)(edges), source=9, depth_limit=depth_limit)
        seen = []
        try:
            for event in it:
                seen.append(event)
        except Exception as exc:  # noqa: BLE001 - the raise is the answer
            return seen, type(exc).__name__, str(exc)
        return seen, None, None

    assert outcome(fnx) == outcome(nx)


# br-r37-c1-qnj0n: nx reads a node's row from G.neighbors when the walk
# reaches it - a LIVE row, and only the rows the walk reaches. The whole-graph
# to_dict_of_lists snapshot fnx took per call (156 ms for a depth-3 walk beside
# a 64k-node component) missed a mid-walk mutation and, on a subclass, read
# every node's row.


@pytest.mark.parametrize("directed", [False, True])
def test_dfs_labeled_edges_row_is_live_like_networkx(directed):
    def outcome(lib):
        G = (lib.DiGraph if directed else lib.Graph)([(0, 1), (1, 2), (0, 3), (3, 4)])
        walk = lib.dfs_labeled_edges(G, 0)
        seen = [next(walk), next(walk)]  # paused inside row 0, after child 1
        G.add_edge(0, 9)
        try:
            seen.extend(walk)
        except RuntimeError as exc:
            return seen, str(exc)
        return seen, None

    fnx_outcome, nx_outcome = outcome(fnx), outcome(nx)
    assert nx_outcome[1] is not None
    assert fnx_outcome == nx_outcome


@pytest.mark.parametrize("depth_limit", [None, 1, 2])
def test_dfs_labeled_edges_reads_only_reached_rows_like_networkx(depth_limit):
    def rows_read(lib):
        class Recording(lib.Graph):
            def neighbors(self, n):
                reads.append(n)
                return super().neighbors(n)

        reads = []
        G = Recording([(0, 1), (1, 2), (0, 3), (5, 6), (6, 7), (7, 5)])
        events = list(lib.dfs_labeled_edges(G, 0, depth_limit=depth_limit))
        return events, reads

    fnx_rows, nx_rows = rows_read(fnx), rows_read(nx)
    assert 5 not in nx_rows[1]
    assert fnx_rows == nx_rows


def test_goldens():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert list(fnx.dfs_labeled_edges(g, 0)) == list(nx.dfs_labeled_edges(ng, 0))
    assert dict(fnx.bfs_successors(g, 0)) == {0: [1], 1: [2]}
    assert dict(fnx.dfs_predecessors(g, 0)) == {1: 0, 2: 1}
