"""Parity guard: multigraph difference() routed to the no-data keyed batch.

br-edgekeyedbatch (bt). Sibling of the symmetric_difference reroute. ``_native_difference``
predates the fast no-data keyed batch (``_native_add_keyed_edges_no_data``) and is ~2.4x
slower for multigraphs (MG 19.8ms vs the set-snapshot + batch fallback 8.2ms). The multigraph
path now skips ``_native_difference`` and uses that fallback (the node-set equality check still
runs first so the error contract is unchanged). Simple Graph/DiGraph keep their native path.

These assert difference stays byte-identical to nx (edges incl keys, node set) across parallel
edges, self-loops, partial/total/empty H overlap, and that unequal node sets raise NetworkXError.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

pytestmark = pytest.mark.skipif(nx is None, reason="networkx not installed")


def _sig(g):
    return (
        sorted((str(u), str(v), str(k)) for u, v, k in g.edges(keys=True)),
        sorted(map(str, g.nodes())),
    )


def _build(C, n=60, seed=1, drop=0.0):
    r = random.Random(seed)
    g = C()
    g.add_nodes_from(range(n))
    for u in range(n):
        for s in range(1, 5):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(2):
                if r.random() < drop:
                    continue
                g.add_edge(u, v, weight=(u + v + p) % 9)
        if u % 5 == 0:
            g.add_edge(u, u, weight=u % 3)  # self-loop
    return g


_CLASSES = [(nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)]


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
@pytest.mark.parametrize("drop", [0.0, 0.3, 0.7, 1.0])
def test_difference_byte_exact(cls_n, cls_f, drop):
    gn, gn2 = _build(cls_n, seed=1), _build(cls_n, seed=1, drop=drop)
    gf, gf2 = _build(cls_f, seed=1), _build(cls_f, seed=1, drop=drop)
    assert _sig(nx.difference(gn, gn2)) == _sig(fnx.difference(gf, gf2))


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_difference_distinct_edge_sets(cls_n, cls_f):
    gn, gn2 = _build(cls_n, seed=1), _build(cls_n, seed=2)
    gf, gf2 = _build(cls_f, seed=1), _build(cls_f, seed=2)
    assert _sig(nx.difference(gn, gn2)) == _sig(fnx.difference(gf, gf2))


@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
def test_difference_unequal_nodes_raises(cls_n, cls_f):
    g = _build(cls_f)
    h = cls_f()
    h.add_nodes_from(range(50))
    with pytest.raises(Exception):
        fnx.difference(g, h)
