"""Regression tests for two A* defects fixed in br-r37-c1-astdir / -astie.

1. Directed correctness: the Rust ``_raw_astar_path`` kernel only has an
   undirected ``&Graph`` implementation, and the PyO3 binding fed it
   ``gr.undirected()`` even for DiGraph/MultiDiGraph — so ``astar_path`` /
   ``astar_path_length`` silently dropped edge direction and returned paths
   over non-existent (reverse) directed edges (e.g. ``[0, 4]`` when only the
   reverse edge ``4->0`` exists). dijkstra/bellman_ford always honoured
   direction. Directed graphs now delegate to networkx.

2. Undirected tie-break: among equal-f-score frontier nodes the Rust kernel
   broke ties on node identity, whereas networkx breaks ties on insertion
   order (FIFO, via ``next(counter)``). On graphs with many equal-cost paths
   (e.g. unit-weight grids) ``astar_path`` returned a different (still valid)
   shortest path than nx. The kernel now carries a monotonic counter and
   matches nx's chosen path.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _grid(mod, rows, cols, directed=False):
    g = (mod.DiGraph if directed else mod.Graph)()
    for r in range(rows):
        for c in range(cols):
            n = r * cols + c
            if c < cols - 1:
                g.add_edge(n, n + 1, weight=1)
            if r < rows - 1:
                g.add_edge(n, n + cols, weight=1)
    return g


def test_directed_astar_respects_direction_minimal():
    # Only the reverse edge 4->0 exists; 0->4 must route the long way round.
    def build(mod):
        g = mod.DiGraph()
        g.add_edge(4, 0, weight=1)
        g.add_edge(0, 1, weight=1)
        g.add_edge(1, 2, weight=1)
        g.add_edge(2, 4, weight=1)
        return g

    assert fnx.astar_path(build(fnx), 0, 4, weight="weight") == [0, 1, 2, 4]
    assert fnx.astar_path(build(fnx), 0, 4, weight="weight") == nx.astar_path(build(nx), 0, 4, weight="weight")
    assert fnx.astar_path_length(build(fnx), 0, 4, weight="weight") == nx.astar_path_length(build(nx), 0, 4, weight="weight") == 3


@pytest.mark.parametrize("rows,cols", [(3, 4), (4, 4), (5, 3)])
def test_directed_astar_matches_networkx_on_grid(rows, cols):
    gn = _grid(nx, rows, cols, directed=True)
    gf = _grid(fnx, rows, cols, directed=True)
    n = rows * cols
    for t in range(1, n):
        a = nx.astar_path(gn, 0, t, weight="weight")
        b = fnx.astar_path(gf, 0, t, weight="weight")
        assert a == b, f"directed grid {rows}x{cols} target {t}: nx={a} fnx={b}"


@pytest.mark.parametrize("rows,cols", [(4, 4), (5, 5), (3, 7)])
def test_undirected_astar_tiebreak_matches_networkx_on_grid(rows, cols):
    gn = _grid(nx, rows, cols)
    gf = _grid(fnx, rows, cols)
    n = rows * cols
    for t in range(1, n):
        a = nx.astar_path(gn, 0, t, weight="weight")
        b = fnx.astar_path(gf, 0, t, weight="weight")
        assert a == b, f"undirected grid {rows}x{cols} target {t}: nx={a} fnx={b}"


def test_multidigraph_astar_respects_direction():
    def build(mod):
        g = mod.MultiDiGraph()
        g.add_edge(2, 0, weight=1)
        g.add_edge(0, 1, weight=1)
        g.add_edge(1, 2, weight=1)
        return g

    assert fnx.astar_path(build(fnx), 0, 2, weight="weight") == nx.astar_path(build(nx), 0, 2, weight="weight") == [0, 1, 2]
