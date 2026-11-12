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


# br-r37-c1-wog27: the fixture above builds attributes with per-node/per-edge
# calls. The silent-attribute-drop class this bead guards has a sibling that
# only the BATCH path can reach — `add_nodes_from` / `add_edges_from` commit
# through a different collector, and multi-attr key ORDER there was a known
# defect class (an AttrMap backed by a BTreeMap alphabetises). Building the same
# fixture batch-wise costs one function and covers that route.
def _attributed_batch(lib, base=0, gname="G"):
    g = lib.Graph()
    g.add_nodes_from(
        [(n, {"tag": f"t{n}", "val": n * 10}) for n in range(base, base + 4)]
    )
    g.add_edges_from(
        [
            (u, v, {"weight": u + v, "label": f"e{u}{v}"})
            for u, v in [(base, base + 1), (base + 1, base + 2), (base + 2, base + 3)]
        ]
    )
    g.graph["gname"] = gname
    g.graph["shared"] = 1
    return g


def _attr_key_order(g):
    """Attribute key sequences — what dict equality cannot see."""
    return (
        [list(d.keys()) for _, d in g.nodes(data=True)],
        [list(d.keys()) for _, _, d in g.edges(data=True)],
        list(g.graph.keys()),
    )


@pytest.mark.parametrize("builder", [_attributed, _attributed_batch])
@pytest.mark.parametrize("name,transform", _TRANSFORMS)
def test_transform_preserves_attribute_key_order(name, transform, builder):
    """br-r37-c1-wog27: `_assert_same_attrs` compares `dict(d) == dict(d)`, which
    is blind to the ORDER of the attribute keys, to node iteration order, and —
    because `_edge_attrs` sorts the endpoints — to edge direction and edge order.
    "Attributes preserved" is exactly the property where key order silently
    flips. Every sequence below was verified equal to networkx before being
    asserted, on BOTH the per-item and batch-built fixtures.
    """
    fg = transform(fnx, builder(fnx))
    ng = transform(nx, builder(nx))
    assert _attr_key_order(fg) == _attr_key_order(ng)
    assert [str(n) for n in fg.nodes()] == [str(n) for n in ng.nodes()]
    assert [(str(u), str(v)) for u, v in fg.edges()] == [
        (str(u), str(v)) for u, v in ng.edges()
    ]


@pytest.mark.parametrize("builder", [_attributed, _attributed_batch])
def test_operators_preserve_attribute_key_order(builder):
    fa, fb = builder(fnx, 0, "A"), builder(fnx, 10, "B")
    na, nb = builder(nx, 0, "A"), builder(nx, 10, "B")
    assert _attr_key_order(fnx.union(fa, fb)) == _attr_key_order(nx.union(na, nb))
    assert _attr_key_order(fnx.disjoint_union(fa, fb)) == _attr_key_order(
        nx.disjoint_union(na, nb)
    )
    fc, fd = builder(fnx, 0, "A"), builder(fnx, 2, "B")
    nc, nd = builder(nx, 0, "A"), builder(nx, 2, "B")
    assert _attr_key_order(fnx.compose(fc, fd)) == _attr_key_order(nx.compose(nc, nd))


@pytest.mark.parametrize("builder", [_attributed, _attributed_batch])
def test_batch_built_graphs_preserve_attributes(builder):
    """The value-level assertion from test_transform_preserves_attributes, run
    against both construction routes (br-r37-c1-wog27)."""
    _assert_same_attrs(builder(fnx), builder(nx))


def test_compose_graph_attr_last_writer_wins():
    # Conflicting graph-level keys: compose resolves to the second graph's value.
    fa = fnx.Graph(); fa.graph["x"] = 1; fa.add_edge(0, 1)
    fb = fnx.Graph(); fb.graph["x"] = 2; fb.add_edge(1, 2)
    na = nx.Graph(); na.graph["x"] = 1; na.add_edge(0, 1)
    nb = nx.Graph(); nb.graph["x"] = 2; nb.add_edge(1, 2)
    assert fnx.compose(fa, fb).graph == nx.compose(na, nb).graph
