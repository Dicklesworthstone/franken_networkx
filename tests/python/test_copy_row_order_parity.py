"""br-r37-c1-0ek49: G.copy() adjacency ROW ORDER must match nx's rebuild walk.

nx Graph.copy() rebuilds via ``add_edges_from((u, v, d) for u in _adj
for v in _adj[u])`` — an unordered pair enters BOTH endpoint rows at its
first u-major touch, so copies REORDER undirected adjacency rows (and
directed PRED rows) relative to the source. fnx's bulk inner clone
preserved the source rows verbatim and diverged (uniform keys too).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _rows(g):
    out = {str(n): [str(x) for x in g.adj[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {str(n): [str(x) for x in g.pred[n]] for n in g}
    return out


def _edges(g):
    return [str(e) for e in g.edges()]


@pytest.mark.parametrize("cls", CLASSES)
def test_copy_reorders_rows_like_nx_walk(cls):
    # pre-added nodes put 28 before 5/7 in node order, so the walk
    # touches (28, 5) before u=5's own row scan — nx adj[5] = [28, 7, 5].
    def build(mod):
        g = getattr(mod, cls)()
        g.add_node(28)
        g.add_node(3)
        g.add_edge(5, 7)
        g.add_edge(28, 5)
        g.add_edge(7, 3)
        g.add_edge(5, 5)
        return g

    gn, gf = build(nx).copy(), build(fnx).copy()
    assert _rows(gf) == _rows(gn)
    assert _edges(gf) == _edges(gn)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_copy_pred_rows_walk_order(cls):
    # original pred[7] = [9, 5] (edge order); the copy walk visits u=5
    # first (node order), so nx copy pred[7] = [5, 9].
    def build(mod):
        g = getattr(mod, cls)()
        g.add_nodes_from([5, 9])
        g.add_edge(9, 7)
        g.add_edge(5, 7)
        return g

    gn, gf = build(nx).copy(), build(fnx).copy()
    assert _rows(gf) == _rows(gn)
    assert [str(x) for x in gf.pred[7]] == ["5", "9"]


@pytest.mark.parametrize("cls", CLASSES)
def test_copy_of_copy_stable(cls):
    # the walk order is a fixed point: copying a copy must not reshuffle.
    def build(mod):
        g = getattr(mod, cls)()
        g.add_node(28)
        g.add_edge(5, 7)
        g.add_edge(28, 5)
        g.add_edge(5, 5)
        return g

    gn, gf = build(nx).copy().copy(), build(fnx).copy().copy()
    assert _rows(gf) == _rows(gn)


@pytest.mark.parametrize("cls", CLASSES)
def test_copy_row_order_random_corpus(cls):
    rnd = random.Random(20260605)
    for trial in range(40):
        gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
        for _ in range(rnd.randrange(1, 25)):
            r = rnd.random()
            if r < 0.15:
                x = rnd.randrange(8)
                gn.add_node(x)
                gf.add_node(x)
            elif r < 0.85:
                u, v = rnd.randrange(8), rnd.randrange(8)
                gn.add_edge(u, v)
                gf.add_edge(u, v)
            elif gn.number_of_edges():
                u, v = next(iter(gn.edges()))
                gn.remove_edge(u, v)
                gf.remove_edge(u, v)
        hn, hf = gn.copy(), gf.copy()
        assert _rows(hf) == _rows(hn), trial
        assert _edges(hf) == _edges(hn), trial
