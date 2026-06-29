"""Parity guard: multigraph union() routed through the keyed edges-only batch.

br-edgekeyedbatch (bt). union requires DISJOINT node sets, so G's and H's keyed edges
never collide. union previously ran two separate ``add_edges_from(view)`` calls — a view
is not a list/tuple so it skipped the native batch dispatch, and the second ran per-edge on
a non-fresh graph (~0.40x vs nx). Combining both into ONE list lets the node-populated
edgeless result hit the native keyed edges-only batch (~0.55-0.7x; still mirror-build bound,
but a real improvement).

These assert union stays byte-identical to nx (edge orientation/keys/attrs, node order, graph
attrs), including rename, self-loops, multi-attr edges, the overlapping-node error contract,
and that the result is independent of the inputs.
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
    return edges, nodes, sorted(g.graph.items())


def _mk(C, off, node_attrs=True):
    g = C()
    for i in range(off, off + 30):
        g.add_node(i, **({"col": i % 3} if node_attrs else {}))
    for u in range(off, off + 30):
        for s in range(1, 4):
            v = off + ((u - off) * 7 + s * 5) % 30
            if v == u:
                v = off + ((v - off) + 1) % 30
            for p in range(2):
                g.add_edge(u, v, weight=(u + v + p) % 9, kind=(u * v) % 4)
        if u % 5 == 0:
            g.add_edge(u, u, weight=u % 3)  # self-loop
    return g


_CLASSES = [(nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)]


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_basic(cls_n, cls_f):
    assert _sig(nx.union(_mk(cls_n, 0), _mk(cls_n, 100))) == _sig(
        fnx.union(_mk(cls_f, 0), _mk(cls_f, 100))
    )


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_no_node_attrs(cls_n, cls_f):
    assert _sig(nx.union(_mk(cls_n, 0, False), _mk(cls_n, 100, False))) == _sig(
        fnx.union(_mk(cls_f, 0, False), _mk(cls_f, 100, False))
    )


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_rename(cls_n, cls_f):
    assert _sig(nx.union(_mk(cls_n, 0), _mk(cls_n, 0), rename=("g-", "h-"))) == _sig(
        fnx.union(_mk(cls_f, 0), _mk(cls_f, 0), rename=("g-", "h-"))
    )


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_overlapping_nodes_raises(cls_n, cls_f):
    with pytest.raises(Exception):
        nx.union(_mk(cls_n, 0), _mk(cls_n, 10))
    with pytest.raises(Exception):
        fnx.union(_mk(cls_f, 0), _mk(cls_f, 10))


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_empty_operand(cls_n, cls_f):
    assert _sig(nx.union(_mk(cls_n, 0), cls_n())) == _sig(fnx.union(_mk(cls_f, 0), cls_f()))


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_union_result_independent_of_inputs(cls_n, cls_f):
    g = _mk(cls_f, 0)
    h = _mk(cls_f, 100)
    r = fnx.union(g, h)
    u, v, k = next(iter(r.edges(keys=True)))
    before = dict(g[u][v][k]) if g.has_edge(u, v) else None
    r[u][v][k]["weight"] = 99999
    r[u][v][k]["__new__"] = 1
    if before is not None:
        assert dict(g[u][v][k]) == before  # parent untouched
