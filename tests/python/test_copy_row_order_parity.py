"""br-r37-c1-0ek49: graph copy/deepcopy adjacency ROW ORDER parity.

nx Graph.copy() rebuilds via ``add_edges_from((u, v, d) for u in _adj
for v in _adj[u])`` — an unordered pair enters BOTH endpoint rows at its
first u-major touch, so copies REORDER undirected adjacency rows (and
directed PRED rows) relative to the source. fnx's bulk inner clone
preserved the source rows verbatim and diverged (uniform keys too).

copy.deepcopy(G) is different: nx preserves the source dict structure while
deep-copying graph/node/edge attributes.
"""

import copy
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


@pytest.mark.parametrize("cls", CLASSES)
def test_deepcopy_preserves_source_rows_like_nx(cls):
    def build(mod):
        g = getattr(mod, cls)()
        g.add_node(28)
        g.add_node(3)
        g.add_nodes_from([5, 9])
        g.add_edge(9, 7, payload=[])
        g.add_edge(5, 7)
        g.add_edge(28, 5)
        g.add_edge(7, 3)
        g.add_edge(5, 5)
        return g

    gn_src, gf_src = build(nx), build(fnx)
    gn, gf = copy.deepcopy(gn_src), copy.deepcopy(gf_src)
    assert _rows(gf) == _rows(gn)
    assert _rows(gf) == _rows(gf_src)
    assert _edges(gf) == _edges(gn)


@pytest.mark.parametrize("cls", CLASSES)
def test_deepcopy_attrs_are_independent(cls):
    def build(mod):
        g = getattr(mod, cls)()
        g.graph["payload"] = []
        g.add_node(1, payload=[])
        if g.is_multigraph():
            g.add_edge(1, 2, key="k", payload=[])
        else:
            g.add_edge(1, 2, payload=[])
        return g

    gn_src, gf_src = build(nx), build(fnx)
    gn, gf = copy.deepcopy(gn_src), copy.deepcopy(gf_src)
    assert gf.graph == gn.graph
    assert gf.nodes[1] == gn.nodes[1]
    assert gf.graph["payload"] is not gf_src.graph["payload"]
    assert gf.nodes[1]["payload"] is not gf_src.nodes[1]["payload"]
    if gf.is_multigraph():
        assert gf[1][2]["k"] == gn[1][2]["k"]
        assert gf[1][2]["k"]["payload"] is not gf_src[1][2]["k"]["payload"]
    else:
        assert gf[1][2] == gn[1][2]
        assert gf[1][2]["payload"] is not gf_src[1][2]["payload"]


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_multi_copy_cell_walk_order_adversarial(cls):
    # br-r37-c1-s0d4x: the 0ek49 fix covered Graph/DiGraph; multi-class
    # copies kept verbatim insertion-order cells where nx's copy walk
    # reorders them (u-major first-touch). Adversarial shape: mixed
    # str/int nodes, parallel keys, self-loops, dense enough that walk
    # order != insertion order.
    import random

    rnd = random.Random(5)
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    for g in (gn, gf):
        g.add_node("iso", t=1)
    for _ in range(60):
        u, v = rnd.randrange(10), rnd.randrange(10)
        gn.add_edge(u, v, w=u + v)
        gf.add_edge(u, v, w=u + v)
    assert _rows(gf.copy()) == _rows(gn.copy())
    assert _rows(gf.copy().copy()) == _rows(gn.copy().copy())


@pytest.mark.parametrize("cls", CLASSES)
def test_same_type_constructor_equals_nx(cls):
    # br-r37-c1-s0d4x: cls(G) routes to the native copy absorb; structure
    # and graph-attr semantics must equal nx's ctor exactly.
    import random

    rnd = random.Random(7)
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    for g in (gn, gf):
        g.graph["gname"] = "x"
        g.add_node("iso")
    for _ in range(40):
        u, v = rnd.randrange(9), rnd.randrange(9)
        gn.add_edge(u, v, w=u)
        gf.add_edge(u, v, w=u)
    cn, cf = getattr(nx, cls)(gn, extra=1), getattr(fnx, cls)(gf, extra=1)
    assert _rows(cf) == _rows(cn)
    assert [tuple(map(repr, e)) for e in cf.edges(data=True)] == [
        tuple(map(repr, e)) for e in cn.edges(data=True)
    ]
    assert dict(cf.graph) == dict(cn.graph) == {"gname": "x", "extra": 1}
    # independence from the source
    cf.add_edge(99, 100)
    assert 99 not in gf
