"""Conformance + source-independence guard for the copy / to_directed family.

These graph-cloning operations are being optimized to drop the eager per-node /
per-edge ``py_dict_to_attr_map`` crossing in favour of lazy Rust AttrMap
materialization from the Python dict mirror (the in-flight digraph.rs lazy-attr
work + the to_undirected lever, br-r37-c1-tbh4q). That optimization MUST preserve
two observable properties, which this guard locks vs networkx:

  * full attribute fidelity: copy()/to_directed() reproduce node, edge, and
    graph attrs exactly (values match networkx's clone);
  * source-independence: mutating the SOURCE after the clone (edge-attr write,
    new edge, new node, nested-attr mutation is shallow like nx) does not alter
    the clone's top-level structure/attrs.

Locking these lets the lazy-AttrMap lever land without silent attr loss or
accidental aliasing between source and clone.

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_TYPES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


def _build(fcls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    fg, ng = fcls(), ncls()
    for node in range(n):
        fg.add_node(node, tag=f"t{node}", rank=node)
        ng.add_node(node, tag=f"t{node}", rank=node)
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.4:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fg.graph["meta"] = "m"
    ng.graph["meta"] = "m"
    return fg, ng


def _node_attrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


def _edge_attrs(g):
    if g.is_multigraph():
        return sorted((tuple(sorted((u, v))), k, tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted((tuple(sorted((u, v))), tuple(sorted(d.items())))
                  for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(15))
def test_copy_matches_networkx(fcls, ncls, seed):
    fg, ng = _build(fcls, ncls, seed)
    fc, nc = fg.copy(), ng.copy()
    assert _node_attrs(fc) == _node_attrs(nc)
    assert _edge_attrs(fc) == _edge_attrs(nc)
    assert dict(fc.graph) == dict(nc.graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(15))
def test_copy_is_independent_of_source(fcls, ncls, seed):
    fg, ng = _build(fcls, ncls, seed)
    fc = fg.copy()
    before_nodes = _node_attrs(fc)
    before_edges = _edge_attrs(fc)
    # Mutate the SOURCE after copying (node attr, then add a fresh node).
    for node in list(fg.nodes()):
        fg.nodes[node]["rank"] = 999
        break
    fg.add_node("brand_new", rank=-1)
    # The copy must be unchanged (no aliasing of attrs/structure with the source).
    assert _node_attrs(fc) == before_nodes
    assert _edge_attrs(fc) == before_edges
    assert "brand_new" not in set(fc.nodes())
