"""Parity guard: multigraph graph products use add_edge(key=...) fast path.

br-prodfast (bt). The multigraph product loops emitted each product edge via
``P.add_edges_from([(n1, n2, key, dict(attrs))])`` — a single-element list that pays the
full add_edges_from wrapper + three native batch-attempts (all bail on one tuple-node edge)
PER EDGE, over the O(E_G x E_H) product edge set (multigraph tensor_product was ~0.1x vs nx).
That list form existed only to dodge the ``key=`` kwarg collision when an edge attribute is
literally named 'key'. When no edge attr is named 'key' (and all attr keys are str), the loops
now use the direct ``P.add_edge(n1, n2, key=k, **attrs)`` (~1.67x faster); otherwise they keep
the list form.

These assert all four products stay byte-identical to nx for the no-attr fast path, the normal
attributed path, AND the 'key'-named-attr fallback, for MultiGraph and MultiDiGraph.
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


def _canon(g):
    return sorted(
        (
            str(u),
            str(v),
            str(k),
            tuple(sorted((kk, str(vv)) for kk, vv in d.items())),
        )
        for u, v, k, d in g.edges(keys=True, data=True)
    )


def _build(C, n=24, seed=1, attrs=True, keyattr=False):
    r = random.Random(seed)
    g = C()
    g.add_nodes_from((i, {"c": i % 3}) for i in range(n))
    for u in range(n):
        for s in range(1, 4):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(2):
                a = {}
                if attrs:
                    a["weight"] = (u + v + p) % 9
                if keyattr:
                    a["key"] = u  # edge attribute literally named 'key' -> list fallback
                g.add_edge(u, v, **a)
        if u % 5 == 0:
            g.add_edge(u, u, weight=u % 3)
    return g


_PRODUCTS = ["cartesian_product", "tensor_product", "strong_product", "lexicographic_product"]
_CLASSES = [(nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)]


@pytest.mark.parametrize("prod", _PRODUCTS)
@pytest.mark.parametrize("cls_n,cls_f", _CLASSES)
@pytest.mark.parametrize("attrs,keyattr", [(True, False), (False, False), (True, True)])
def test_product_byte_exact(prod, cls_n, cls_f, attrs, keyattr):
    gn = _build(cls_n, attrs=attrs, keyattr=keyattr)
    hn = _build(cls_n, n=8, seed=2, attrs=attrs, keyattr=keyattr)
    gf = _build(cls_f, attrs=attrs, keyattr=keyattr)
    hf = _build(cls_f, n=8, seed=2, attrs=attrs, keyattr=keyattr)
    rn = getattr(nx, prod)(gn, hn)
    rf = getattr(fnx, prod)(gf, hf)
    assert _canon(rn) == _canon(rf)


def test_product_result_independent_of_inputs():
    gf = _build(fnx.MultiGraph)
    hf = _build(fnx.MultiGraph, n=8, seed=2)
    r = fnx.tensor_product(gf, hf)
    # mutating a result edge's attr dict must not touch the source graphs
    u, v, k, d = next(iter(r.edges(keys=True, data=True)))
    d["weight"] = 123456
    d["__new__"] = 1
    for u2, v2, k2, d2 in gf.edges(keys=True, data=True):
        assert "__new__" not in d2
