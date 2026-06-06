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


def test_dfs_discovery_objects_match_nx_mixed_keys():
    # br-r37-c1-wvbzw lever 2: nx traversal yields DISCOVERY objects —
    # the source as passed, every other node as its parent's
    # adjacency-ROW object (z6uka overrides for mixed hash-equal keys).
    for cls in ("DiGraph", "Graph"):
        gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
        for h in (gf, gn):
            h.add_node(28)
            h.add_edge(7, 28.0)
            h.add_edge(28.0, 5)
            h.add_edge(5, 7)
        assert [(repr(u), repr(v)) for u, v in fnx.dfs_edges(gf, 7)] == [
            (repr(u), repr(v)) for u, v in nx.dfs_edges(gn, 7)
        ], cls
        tf, tn = fnx.dfs_tree(gf, 7), nx.dfs_tree(gn, 7)
        assert [repr(n) for n in tf] == [repr(n) for n in tn], cls
        assert _canon(fnx.dfs_tree(fnx.DiGraph([(7, 28.0)]))) == _canon(
            nx.dfs_tree(nx.DiGraph([(7, 28.0)]))
        )


class TestDiscoveryObjectFamily:
    """br-r37-c1-6hpa9: nx traversal results carry DISCOVERY objects —
    the source as passed, every discovered node as its parent's
    adjacency-row object (pred rows for reverse walks)."""

    def _mixed(self, mod, directed=True):
        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
        g.add_edge(5, 7)
        g.add_edge(5, 9)
        return g

    def _rr(self, x):
        if isinstance(x, tuple):
            return tuple(self._rr(i) for i in x)
        if isinstance(x, frozenset) or isinstance(x, set):
            return sorted(self._rr(i) for i in x)
        if isinstance(x, list):
            return [self._rr(i) for i in x]
        if isinstance(x, dict):
            return {self._rr(k): self._rr(v) for k, v in x.items()}
        if hasattr(x, "nodes"):
            return [repr(n) for n in x]
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    @pytest.mark.parametrize(
        "fn",
        [
            lambda m, g: list(m.bfs_edges(g, 7)),
            lambda m, g: list(m.bfs_tree(g, 7)),
            lambda m, g: list(m.dfs_edges(g, 7)),
            lambda m, g: list(m.dfs_tree(g, 7)),
            lambda m, g: list(m.dfs_preorder_nodes(g, 7)),
            lambda m, g: list(m.dfs_postorder_nodes(g, 7)),
            lambda m, g: dict(m.bfs_predecessors(g, 7)),
            lambda m, g: dict(m.bfs_successors(g, 7)),
            lambda m, g: m.ancestors(g, 9),
            lambda m, g: m.descendants(g, 7),
        ],
    )
    def test_discovery_objects_match_nx(self, fn, directed):
        assert self._rr(fn(fnx, self._mixed(fnx, directed))) == self._rr(
            fn(nx, self._mixed(nx, directed))
        )

    def test_reverse_bfs_uses_pred_row_objects(self):
        gf, gn = self._mixed(fnx), self._mixed(nx)
        assert self._rr(list(fnx.bfs_edges(gf, 9, reverse=True))) == self._rr(
            list(nx.bfs_edges(gn, 9, reverse=True))
        )
        assert self._rr(fnx.bfs_tree(gf, 9, reverse=True)) == self._rr(
            nx.bfs_tree(gn, 9, reverse=True)
        )

    def test_uniform_keys_unchanged(self):
        e = _edges(seed=9, n=60, m=200)
        gf, gn = fnx.DiGraph(e), nx.DiGraph(e)
        assert self._rr(list(fnx.bfs_edges(gf, 0))) == self._rr(list(nx.bfs_edges(gn, 0)))
        assert self._rr(dict(fnx.bfs_successors(gf, 0))) == self._rr(
            dict(nx.bfs_successors(gn, 0))
        )
