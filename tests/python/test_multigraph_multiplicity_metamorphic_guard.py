"""Metamorphic guard: parallel-edge multiplicity is preserved through operations.

MultiGraph/MultiDiGraph handling was the single biggest source of subtle bugs in
this campaign's guard work (mixed-key sorts, keydict-vs-attrdict, "neighbor gone"
after one parallel edge removed). This pins the core invariant: the per-pair
parallel-edge *multiplicity* (and total edge count) is preserved byte-for-byte vs
networkx through copy / subgraph / to_directed / reverse / conversion.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _mg(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    fg = cls()
    ng = getattr(nx, cls.__name__)()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for _ in range(r.randint(8, 20)):
        u, v = r.randint(0, n - 1), r.randint(0, n - 1)
        w = r.randint(1, 9)
        fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    return fg, ng, n


def _multiplicity(G):
    # {frozenset_or_pair: count} of parallel edges, direction-aware for digraphs.
    counts = {}
    directed = G.is_directed()
    for u, v in G.edges(keys=False):
        key = (u, v) if directed else frozenset((u, v))
        counts[key] = counts.get(key, 0) + 1
    return counts


@pytest.mark.parametrize("cls", [fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("seed", range(15))
def test_multiplicity_matches_nx(cls, seed):
    fg, ng, n = _mg(cls, seed)
    assert fg.number_of_edges() == ng.number_of_edges()
    assert _multiplicity(fg) == _multiplicity(ng)


@pytest.mark.parametrize("cls", [fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("seed", range(10))
def test_copy_subgraph_preserve_multiplicity(cls, seed):
    fg, ng, n = _mg(cls, seed)
    assert _multiplicity(fg.copy()) == _multiplicity(ng.copy())
    sub = list(range(min(3, n)))
    assert _multiplicity(fg.subgraph(sub)) == _multiplicity(ng.subgraph(sub))


@pytest.mark.parametrize("seed", range(10))
def test_to_directed_and_reverse_multiplicity(seed):
    fg, ng, n = _mg(fnx.MultiGraph, seed)
    assert _multiplicity(fg.to_directed()) == _multiplicity(ng.to_directed())
    dg, ndg, _ = _mg(fnx.MultiDiGraph, seed + 50)
    assert _multiplicity(dg.reverse()) == _multiplicity(ndg.reverse())
