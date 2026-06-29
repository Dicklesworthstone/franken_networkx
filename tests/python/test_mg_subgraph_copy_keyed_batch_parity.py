"""Parity guard: MultiGraph (undirected) subgraph().copy() via the non-fresh keyed batch.

br-edgekeyedbatch (bt). Undirected sibling of the MultiDiGraph subgraph-copy batch.
subgraph().copy() does add_nodes_from(attrs, in subgraph node order) THEN
add_edges_from(4-tuples), so node_count!=0 bailed the fresh keyed batch and the copy paid
the per-edge PyO3 loop (~0.76x vs nx). An edges-only keyed batch (every endpoint must
already be a node; one Rust extend_keyed_edges commit storing edges in the GIVEN (u,v)
order so the undirected symmetric adjacency = the per-edge order) brings it to ~1.1x.

The undirected risk is edges() ORIENTATION: these assert the copy is byte-identical to nx
(edge orientation, node order, keys, attrs), including self-loops + isolated nodes, that a
NEW node bails to per-edge, that the batch matches a per-edge copy, and attr identity.
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
    edges = [
        (str(u), str(v), str(k), tuple(sorted(d.items())))
        for u, v, k, d in g.edges(keys=True, data=True)
    ]
    nodes = [(str(n), tuple(sorted(d.items()))) for n, d in g.nodes(data=True)]
    return edges, nodes


def _build(mod, n=120, seed=1):
    r = random.Random(seed)
    g = mod.MultiGraph()
    g.add_nodes_from((i, {"nlabel": i % 5}) for i in range(n))
    for u in range(n):
        for s in range(1, 5):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(r.randint(1, 3)):
                g.add_edge(u, v, weight=(u + v + p) % 9, kind=(u * v) % 4)
        if u % 6 == 0:
            g.add_edge(u, u, weight=u % 7)  # self-loop (undirected, once)
    return g


@pytest.mark.parametrize("seed", range(12))
def test_subgraph_copy_byte_exact_with_orientation(seed):
    gn = _build(nx)
    gf = _build(fnx)
    nb = sorted(random.Random(seed).sample(range(120), 60))
    assert _sig(gn.subgraph(nb).copy()) == _sig(gf.subgraph(nb).copy())


def test_subgraph_copy_isolated_and_selfloops():
    gn = _build(nx)
    gf = _build(fnx)
    nb = list(range(0, 120, 2))
    assert _sig(gn.subgraph(nb).copy()) == _sig(gf.subgraph(nb).copy())


def test_direct_node_populated_add_edges_from():
    def build(mod):
        g = mod.MultiGraph()
        g.add_nodes_from((i, {"a": i}) for i in range(20))
        g.add_edges_from([(i % 20, (i + 3) % 20, i % 4, {"w": i}) for i in range(40)])
        return g

    assert _sig(build(nx)) == _sig(build(fnx))


def test_new_node_in_batch_bails():
    def build(mod):
        g = mod.MultiGraph()
        g.add_nodes_from(range(10))
        g.add_edges_from(
            [(i, i + 1, 0, {"w": i}) for i in range(9)] + [(99, 100, 0, {"w": 1})]
        )
        return g

    assert _sig(build(nx)) == _sig(build(fnx))


def test_batch_copy_matches_peredge_copy():
    gf = _build(fnx)
    nb = sorted(random.Random(99).sample(range(120), 50))
    sub = gf.subgraph(nb)
    per = fnx.MultiGraph()
    per.add_nodes_from((n, dict(d)) for n, d in sub.nodes(data=True))
    for u, v, k, d in sub.edges(keys=True, data=True):
        per.add_edge(u, v, key=k, **d)
    assert _sig(gf.subgraph(nb).copy()) == _sig(per)


def test_copy_attr_identity_and_mutation():
    gf = _build(fnx)
    cf = gf.subgraph(sorted(range(0, 120, 3))).copy()
    u, v, k = next(iter(cf.edges(keys=True)))
    assert cf[u][v][k] is cf[u][v][k]
    cf[u][v][k]["weight"] = 555
    assert cf[u][v][k]["weight"] == 555
