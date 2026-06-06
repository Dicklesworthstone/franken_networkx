"""br-r37-c1-wvbzw: bfs_tree/dfs_tree result parity across variants.

The tree bindings no longer clone the source's RuntimePolicy decision
ledger (unbounded — one entry per recorded op), which made tree assembly
scale with the SOURCE's construction history (5.3x on identical
structures). Results must be byte-identical to nx for every variant and
independent of how the source graph was built.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        [repr(n) for n in g.nodes()],
        [tuple(map(repr, e)) for e in g.edges()],
        {repr(n): [repr(x) for x in g.adj[n]] for n in g},
        {repr(n): [repr(x) for x in g.pred[n]] for n in g},
    )


def _edges(seed=3, n=120, m=480):
    rnd = random.Random(seed)
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges += [(rnd.randrange(n), rnd.randrange(n)) for _ in range(m - n)]
    return [(u, v) for u, v in edges if u != v]


@pytest.mark.parametrize("fn", ["bfs_tree", "dfs_tree"])
@pytest.mark.parametrize("directed", [True, False])
@pytest.mark.parametrize("depth_limit", [None, 2, 5])
def test_tree_matches_networkx(fn, directed, depth_limit):
    e = _edges()
    gf = (fnx.DiGraph if directed else fnx.Graph)(e)
    gn = (nx.DiGraph if directed else nx.Graph)(e)
    tf = getattr(fnx, fn)(gf, 0, depth_limit=depth_limit)
    tn = getattr(nx, fn)(gn, 0, depth_limit=depth_limit)
    assert _canon(tf) == _canon(tn)


def test_bfs_tree_reverse_matches():
    e = _edges()
    assert _canon(fnx.bfs_tree(fnx.DiGraph(e), 0, reverse=True)) == _canon(
        nx.bfs_tree(nx.DiGraph(e), 0, reverse=True)
    )


def test_dfs_tree_forest_no_source():
    e = _edges()
    assert _canon(fnx.dfs_tree(fnx.DiGraph(e))) == _canon(nx.dfs_tree(nx.DiGraph(e)))


def test_tree_independent_of_source_build_path():
    # identical structure via two build paths (different ledger histories)
    g_native = fnx.grid_2d_graph(12, 12)
    g_ctor = fnx.Graph(list(g_native.edges()))
    assert _canon(fnx.bfs_tree(g_native, (0, 0))) == _canon(
        fnx.bfs_tree(g_ctor, (0, 0))
    )
    assert _canon(fnx.dfs_tree(g_native, (0, 0))) == _canon(
        fnx.dfs_tree(g_ctor, (0, 0))
    )


def test_tree_result_is_mutable_and_independent():
    e = _edges()
    gf = fnx.DiGraph(e)
    t = fnx.bfs_tree(gf, 0)
    t.add_edge("x", "y", w=1)
    t.nodes[0]["a"] = 1
    assert ("x", "y") in t.edges() and "x" not in gf
    assert t.nodes[0]["a"] == 1 and "a" not in gf.nodes[0]
