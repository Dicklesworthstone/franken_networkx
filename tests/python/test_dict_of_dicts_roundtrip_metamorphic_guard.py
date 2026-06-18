"""Metamorphic round-trip guard for to_dict_of_dicts / from_dict_of_dicts.

These conversions are construction-tax-heavy (from_dict_of_dicts was a ~7.8x
gap); this locks their correctness by self-consistency rather than a reference:
from_dict_of_dicts(to_dict_of_dicts(G), create_using=type(G)) reproduces G's
edges + edge attrs + node set exactly, for all 4 graph types.

Compared on endpoint+attr multisets (parallel-edge keys need not survive the
round-trip). No mocks, NO networkx — pure fnx self-consistency.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

_TYPES = [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph]


def _build(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = cls()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (g.is_directed() or u < v) and r.random() < 0.4:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


def _eattrs(g):
    def ep(u, v):
        return (u, v) if g.is_directed() else tuple(sorted((u, v), key=str))
    if g.is_multigraph():
        return sorted((ep(u, v), tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted((ep(u, v), tuple(sorted(d.items())))
                  for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(15))
def test_dict_of_dicts_roundtrip(cls, seed):
    g, n = _build(cls, seed)
    d = fnx.to_dict_of_dicts(g)
    # multigraph dicts are 3-level {u:{v:{key:attrs}}} -> need multigraph_input.
    h = fnx.from_dict_of_dicts(d, create_using=cls(),
                               multigraph_input=g.is_multigraph())

    assert sorted(h.nodes()) == sorted(g.nodes())   # incl. isolated nodes
    assert _eattrs(h) == _eattrs(g)                  # edges + attrs preserved
    assert h.number_of_edges() == g.number_of_edges()
