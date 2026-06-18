"""Attribute preservation parity for graph-returning functions.

Graph transforms (copy/subgraph/relabel/to_directed/...) and binary operators
(union/compose/disjoint_union) must carry node, edge, AND graph-level
attributes exactly the way networkx does — a fnx-side conversion that drops
attributes is a silent data-loss bug (a union graph-attr drop was a real
regression in this codebase). This pins all three attribute layers against nx.

No mocks: real fnx and real networkx on attributed graphs.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _attributed(lib, base=0, gname="G"):
    g = lib.Graph()
    for n in range(base, base + 4):
        g.add_node(n, tag=f"t{n}", val=n * 10)
    for u, v in [(base, base + 1), (base + 1, base + 2), (base + 2, base + 3)]:
        g.add_edge(u, v, weight=u + v, label=f"e{u}{v}")
    g.graph["gname"] = gname
    g.graph["shared"] = 1
    return g


def _node_attrs(g):
    return {str(n): dict(d) for n, d in g.nodes(data=True)}


def _edge_attrs(g):
    return {tuple(sorted((str(u), str(v)))): dict(d) for u, v, d in g.edges(data=True)}


def _assert_same_attrs(fg, ng):
    assert _node_attrs(fg) == _node_attrs(ng)
    assert _edge_attrs(fg) == _edge_attrs(ng)
    assert dict(fg.graph) == dict(ng.graph)


_TRANSFORMS = [
    ("copy", lambda L, g: g.copy()),
    ("subgraph", lambda L, g: g.subgraph([0, 1, 2, 3])),
    ("edge_subgraph", lambda L, g: g.edge_subgraph([(0, 1), (1, 2)])),
    ("to_directed", lambda L, g: g.to_directed()),
    ("relabel", lambda L, g: L.relabel_nodes(g, {0: "a", 1: "b"})),
    ("subgraph_copy", lambda L, g: g.subgraph([0, 1, 2]).copy()),
    ("ego_graph", lambda L, g: L.ego_graph(g, 1)),
    ("induced_subgraph", lambda L, g: L.induced_subgraph(g, [0, 1, 2])),
    ("restricted_view", lambda L, g: L.restricted_view(g, [3], [])),
]


@pytest.mark.parametrize("name,transform", _TRANSFORMS)
def test_transform_preserves_attributes(name, transform):
    fg = transform(fnx, _attributed(fnx))
    ng = transform(nx, _attributed(nx))
    _assert_same_attrs(fg, ng)


def test_union_disjoint_compose_preserve_attributes():
    fa, fb = _attributed(fnx, 0, "A"), _attributed(fnx, 10, "B")
    na, nb = _attributed(nx, 0, "A"), _attributed(nx, 10, "B")
    _assert_same_attrs(fnx.union(fa, fb), nx.union(na, nb))
    _assert_same_attrs(fnx.disjoint_union(fa, fb), nx.disjoint_union(na, nb))

    fc, fd = _attributed(fnx, 0, "A"), _attributed(fnx, 2, "B")
    nc, nd = _attributed(nx, 0, "A"), _attributed(nx, 2, "B")
    _assert_same_attrs(fnx.compose(fc, fd), nx.compose(nc, nd))


def test_compose_graph_attr_last_writer_wins():
    # Conflicting graph-level keys: compose resolves to the second graph's value.
    fa = fnx.Graph(); fa.graph["x"] = 1; fa.add_edge(0, 1)
    fb = fnx.Graph(); fb.graph["x"] = 2; fb.add_edge(1, 2)
    na = nx.Graph(); na.graph["x"] = 1; na.add_edge(0, 1)
    nb = nx.Graph(); nb.graph["x"] = 2; nb.add_edge(1, 2)
    assert fnx.compose(fa, fb).graph == nx.compose(na, nb).graph
