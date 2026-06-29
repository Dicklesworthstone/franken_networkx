"""Parity guard: MultiDiGraph subgraph().copy() via the non-fresh keyed edge batch.

br-edgekeyedbatch (bt). subgraph().copy() does add_nodes_from(attrs, in subgraph node
order) THEN add_edges_from(4-tuples), so the graph is node-populated + edgeless when the
edges are added — node_count!=0 bailed the fresh keyed batch and the copy paid the per-edge
PyO3 loop (~0.46x vs nx for a MultiDiGraph). An edges-only keyed batch (every endpoint must
already be a node; one Rust extend_keyed_edges commit) brings it to ~1.1x. The copy now
materializes the view edges as a LIST so the batch dispatch (isinstance list/tuple) engages.

These assert the copy stays byte-identical to nx (node order, edge order, keys, attrs),
including isolated nodes; that a NEW node in the batch bails to per-edge correctly; that the
copy is independent of the parent; and attr-dict identity/mutation.
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
    g = mod.MultiDiGraph()
    g.add_nodes_from((i, {"nlabel": i % 5}) for i in range(n))
    for u in range(n):
        for s in range(1, 5):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(r.randint(1, 3)):
                g.add_edge(u, v, weight=(u + v + p) % 9, kind=(u * v) % 4)
    return g


@pytest.mark.parametrize("seed", range(12))
def test_subgraph_copy_byte_exact(seed):
    gn = _build(nx)
    gf = _build(fnx)
    nb = sorted(random.Random(seed).sample(range(120), 60))
    assert _sig(gn.subgraph(nb).copy()) == _sig(gf.subgraph(nb).copy())


def test_subgraph_copy_with_isolated_nodes():
    gn = _build(nx)
    gf = _build(fnx)
    nb = list(range(0, 120, 2))
    assert _sig(gn.subgraph(nb).copy()) == _sig(gf.subgraph(nb).copy())


def test_direct_node_populated_add_edges_from():
    def build(mod):
        g = mod.MultiDiGraph()
        g.add_nodes_from((i, {"a": i}) for i in range(20))
        g.add_edges_from([(i % 20, (i + 3) % 20, i % 4, {"w": i}) for i in range(40)])
        return g

    assert _sig(build(nx)) == _sig(build(fnx))


def test_new_node_in_batch_bails_to_peredge():
    def build(mod):
        g = mod.MultiDiGraph()
        g.add_nodes_from(range(10))
        g.add_edges_from(
            [(i, i + 1, 0, {"w": i}) for i in range(9)] + [(99, 100, 0, {"w": 1})]
        )
        return g

    assert _sig(build(nx)) == _sig(build(fnx))


def test_copy_attr_identity_and_mutation():
    gf = _build(fnx)
    cf = gf.subgraph(sorted(range(0, 120, 3))).copy()
    u, v, k = next(iter(cf.edges(keys=True)))
    assert cf[u][v][k] is cf[u][v][k]
    cf[u][v][k]["weight"] = 555
    assert cf[u][v][k]["weight"] == 555


def test_copy_independent_of_parent():
    gf = _build(fnx)
    before = gf.number_of_edges()
    cf = gf.subgraph(list(range(20))).copy()
    edges = list(cf.edges(keys=True))
    if edges:
        cf.remove_edge(*edges[0])
    assert gf.number_of_edges() == before
