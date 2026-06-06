"""br-r37-c1-u3qyn: pickle round-trip preserves adjacency structure verbatim.

nx pickles the dict structure as-is; fnx's __setstate__ rebuilt from the
u-major edge WALK (and DiGraph from a HashMap iteration — random), which
scrambled adjacency row order and dropped mixed-key display-object
overrides. State now carries explicit rows + override maps (optional
fields — old pickles still load via the legacy rebuild).
"""

import pickle
import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _rows(g):
    out = {repr(n): [repr(x) for x in g.adj[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return out


def _build(mod, cls):
    g = getattr(mod, cls)()
    g.add_nodes_from([5, 9])
    g.add_edge(9, 7, w=1)
    g.add_edge(5, 7)
    g.add_edge(7, 3)
    g.add_edge(9, 5)
    g.add_edge(3, 3)
    if g.is_multigraph():
        g.add_edge(9, 7)
    return g


@pytest.mark.parametrize("cls", CLASSES)
def test_roundtrip_preserves_rows_and_edges(cls):
    gf, gn = _build(fnx, cls), _build(nx, cls)
    pf, pn = pickle.loads(pickle.dumps(gf)), pickle.loads(pickle.dumps(gn))
    assert _rows(pf) == _rows(gf) == _rows(pn)
    assert [tuple(map(repr, e)) for e in pf.edges(data=True)] == [
        tuple(map(repr, e)) for e in pn.edges(data=True)
    ]
    assert list(pf.nodes()) == list(pn.nodes())


@pytest.mark.parametrize("cls", CLASSES)
def test_roundtrip_of_copy_keeps_walk_reordered_rows(cls):
    # copies carry walk-reordered rows that differ from edge insertion
    # order — the round-trip must keep THOSE, not re-derive.
    cf, cn = _build(fnx, cls).copy(), _build(nx, cls).copy()
    pc = pickle.loads(pickle.dumps(cf))
    assert _rows(pc) == _rows(cf) == _rows(cn)


@pytest.mark.parametrize("cls", CLASSES)
def test_roundtrip_keeps_mixed_key_display_objects(cls):
    gf = getattr(fnx, cls)()
    gn = getattr(nx, cls)()
    for g in (gf, gn):
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(5, 7)
    pf, pn = pickle.loads(pickle.dumps(gf)), pickle.loads(pickle.dumps(gn))
    assert _rows(pf) == _rows(pn)
    assert [repr(x) for x in pf[7]] == [repr(x) for x in pn[7]]


def test_roundtrip_random_mutation_corpus():
    rnd = random.Random(20260606)
    for trial in range(25):
        cls = rnd.choice(CLASSES)
        gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
        for _ in range(rnd.randrange(3, 30)):
            r = rnd.random()
            u, v = rnd.randrange(8), rnd.randrange(8)
            if r < 0.7:
                gf.add_edge(u, v)
                gn.add_edge(u, v)
            elif gn.number_of_edges():
                eu, ev = next(iter(gn.edges()))
                gf.remove_edge(eu, ev)
                gn.remove_edge(eu, ev)
        pf, pn = pickle.loads(pickle.dumps(gf)), pickle.loads(pickle.dumps(gn))
        assert _rows(pf) == _rows(pn), (trial, cls)


def test_grid_2d_native_build_pickles_exactly():
    pf = pickle.loads(pickle.dumps(fnx.grid_2d_graph(4, 4)))
    gn = nx.grid_2d_graph(4, 4)
    assert _rows(pf) == _rows(gn)
    assert [tuple(map(repr, e)) for e in pf.edges()] == [
        tuple(map(repr, e)) for e in gn.edges()
    ]
