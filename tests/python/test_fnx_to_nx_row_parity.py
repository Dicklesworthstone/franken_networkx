"""br-r37-c1-w7nn3: _fnx_to_nx must reproduce the source's adjacency
structure verbatim — row ORDER (directed pred rows followed the
succ-major emission walk, poisoning every delegated directed algorithm
sensitive to pred iteration: bidirectional searches returned the WRONG
tie-break path) and row OBJECTS (z6uka display overrides for mixed
hash-equal keys).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _rows(g):
    out = {repr(n): [repr(x) for x in g.adj[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return out


@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_rows_match_native_nx(cls):
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (gf, gn):
        g.add_node(28)
        g.add_edge("s", "a")
        g.add_edge("s", "b")
        g.add_edge("b", "t")
        g.add_edge("a", "t")
        g.add_edge(7, 28.0)
        if g.is_multigraph():
            g.add_edge("s", "a", w=9)
    assert _rows(_fnx_to_nx(gf)) == _rows(gn)


@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_random_corpus(cls):
    rnd = random.Random(17)
    for trial in range(15):
        gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
        for _ in range(rnd.randrange(2, 50)):
            u, v = rnd.randrange(12), rnd.randrange(12)
            gf.add_edge(u, v, w=u)
            gn.add_edge(u, v, w=u)
        assert _rows(_fnx_to_nx(gf)) == _rows(gn), trial


def test_succ_pred_datadict_sharing_survives_alignment():
    gf = fnx.DiGraph()
    gf.add_edge("s", "a", w=1)
    gf.add_edge("b", "a", w=2)
    conv = _fnx_to_nx(gf)
    conv.succ["s"]["a"]["w"] = 99
    assert conv.pred["a"]["s"]["w"] == 99
    gu = fnx.Graph()
    gu.add_edge("s", "a", w=1)
    convu = _fnx_to_nx(gu)
    convu.adj["s"]["a"]["w"] = 99
    assert convu.adj["a"]["s"]["w"] == 99


def test_delegated_bidirectional_tie_break_no_longer_poisoned():
    gf, gn = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gn):
        g.add_edge("s", "a")
        g.add_edge("s", "b")
        g.add_edge("b", "t")
        g.add_edge("a", "t")
    assert nx.bidirectional_shortest_path(
        _fnx_to_nx(gf), "s", "t"
    ) == nx.bidirectional_shortest_path(gn, "s", "t")
