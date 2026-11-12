"""Parity guard: multigraph compose() routed through the keyed edges-only batch.

br-edgekeyedbatch (bt). compose pre-merges G's then H's keyed edges into one deduped list
(_edge_map, H wins on overlap) and commits it. It used ``_native_add_keyed_edges_with_data``,
which predates and is slower than the keyed edges-only batch for the common int-node case
(MultiDiGraph: 45.6ms -> 28.8ms). compose now tries ``_try_add_attr_edges_from_batch`` first
and keeps ``_native_add_keyed_edges_with_data`` as the fallback for non-int graphs where the
int batch bails.

These assert compose stays byte-identical to nx (edge orientation/keys/attrs incl H-wins-on-
overlap, node order) for int AND string nodes, with overlapping nodes and edges, and that the
result is independent of the inputs.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

pytestmark = pytest.mark.skipif(nx is None, reason="networkx not installed")


def _sig(g):
    edges = [
        (str(u), str(v), str(k), tuple(sorted(d.items())))
        for u, v, k, d in g.edges(keys=True, data=True)
    ]
    nodes = [(str(n), tuple(sorted(d.items()))) for n, d in g.nodes(data=True)]
    return edges, nodes


def _build(C, off, tag):
    g = C()
    g.add_nodes_from((i, {"src": tag}) for i in range(off, off + 30))
    for u in range(off, off + 30):
        for s in range(1, 4):
            v = off + ((u - off) * 7 + s * 5) % 30
            if v == u:
                v = off + ((v - off) + 1) % 30
            for p in range(2):
                g.add_edge(u, v, weight=(u + v + p) % 9, src=tag)
        if u % 5 == 0:
            g.add_edge(u, u, weight=u % 3, src=tag)
    return g


_CLASSES = [(nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)]


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_compose_overlapping_nodes_and_edges(cls_n, cls_f):
    # off=0 and off=15 overlap on nodes 15..29 -> overlapping (u,v,key); H wins.
    rn = nx.compose(_build(cls_n, 0, "G"), _build(cls_n, 15, "H"))
    rf = fnx.compose(_build(cls_f, 0, "G"), _build(cls_f, 15, "H"))
    assert _sig(rn) == _sig(rf)


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_compose_disjoint(cls_n, cls_f):
    rn = nx.compose(_build(cls_n, 0, "G"), _build(cls_n, 100, "H"))
    rf = fnx.compose(_build(cls_f, 0, "G"), _build(cls_f, 100, "H"))
    assert _sig(rn) == _sig(rf)


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_compose_string_nodes_uses_native_fallback(cls_n, cls_f):
    gn = nx.relabel_nodes(_build(cls_n, 0, "G"), lambda x: f"n{x}")
    hn = nx.relabel_nodes(_build(cls_n, 15, "H"), lambda x: f"n{x}")
    gf = fnx.relabel_nodes(_build(cls_f, 0, "G"), lambda x: f"n{x}")
    hf = fnx.relabel_nodes(_build(cls_f, 15, "H"), lambda x: f"n{x}")
    assert _sig(nx.compose(gn, hn)) == _sig(fnx.compose(gf, hf))


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_compose_empty_operand(cls_n, cls_f):
    assert _sig(nx.compose(_build(cls_n, 0, "G"), cls_n())) == _sig(
        fnx.compose(_build(cls_f, 0, "G"), cls_f())
    )


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_compose_result_independent_of_inputs(cls_n, cls_f):
    g = _build(cls_f, 0, "G")
    h = _build(cls_f, 100, "H")
    r = fnx.compose(g, h)
    u, v, k = next(iter(r.edges(keys=True)))
    before = dict(g[u][v][k]) if g.has_edge(u, v) else None
    r[u][v][k]["weight"] = 88888
    r[u][v][k]["__x__"] = 1
    if before is not None:
        assert dict(g[u][v][k]) == before
