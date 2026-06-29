"""Parity guard: simple-Graph edges(nbunch) dedups repeated nbunch nodes.

br-edgenbunchdedup (bt). nx's EdgeDataView builds
``nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))`` — an order-preserving
dedup — so a node repeated in nbunch has its incident edges emitted ONCE. fnx walked
the raw nbunch list, so ``G.edges([1, 1])`` on a simple undirected Graph emitted node
1's edges twice (the per-node ``seen`` set only blocks double-emission across endpoints,
not a repeated nbunch node). DiGraph/MultiGraph nbunch kernels already deduped; only the
simple-Graph path diverged.
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


def _mk(mod):
    g = mod.Graph()
    g.add_edge(0, 1, weight=10)
    g.add_edge(1, 2, weight=20)
    g.add_edge(0, 2, weight=30)
    g.add_edge(2, 3, weight=40)
    g.add_edge(3, 3, weight=50)  # self-loop
    return g


@pytest.mark.parametrize(
    "nbunch",
    [[1, 1], [1, 2, 1], [1, 1, 2, 2], [2, 2, 2], [3, 3], [0, 1, 0, 2, 1]],
)
@pytest.mark.parametrize(
    "shape",
    [
        {"data": "weight", "default": 0},
        {"data": True},
        {"data": False},
        {"data": "missing", "default": -1},
    ],
)
def test_duplicate_nbunch_matches_nx(nbunch, shape):
    gn = _mk(nx)
    gf = _mk(fnx)
    assert list(gf.edges(nbunch, **shape)) == list(gn.edges(nbunch, **shape))


def test_unique_nbunch_and_full_graph_unchanged():
    gn = _mk(nx)
    gf = _mk(fnx)
    for nbunch in ([0, 1, 2, 3], [2], None):
        assert list(gf.edges(nbunch, data="weight", default=0)) == list(
            gn.edges(nbunch, data="weight", default=0)
        )


def test_large_graph_duplicate_nbunch_parity():
    def build(mod, n=300):
        g = mod.Graph()
        g.add_nodes_from(range(n))
        r = random.Random(3)
        for u in range(n):
            for s in range(1, 6):
                v = (u * 41 + s * 17) % n
                if v == u:
                    v = (v + s + 3) % n
                g.add_edge(u, v, weight=(u + v + s) % 29 - 8)
        return g

    gn = build(nx)
    gf = build(fnx)
    base = list(range(0, 300, 3))
    dup = base + base[:60]  # repeated nodes
    assert list(gf.edges(dup, data="weight", default=0)) == list(
        gn.edges(dup, data="weight", default=0)
    )
    # length must equal the deduped (each incident edge once)
    assert len(list(gf.edges(dup, data="weight", default=0))) == len(
        list(gf.edges(base, data="weight", default=0))
    )
