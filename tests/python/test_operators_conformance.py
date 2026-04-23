"""Regression tests for franken_networkx-47bag.

The 5 binary graph operators (compose, union, intersection, difference,
symmetric_difference) must:

1. Return a graph of the same class as their inputs (Graph, DiGraph,
   MultiGraph, or MultiDiGraph) — upstream nx does this.
2. compose + union must preserve node and edge attributes on the output.
3. compose on multigraphs must not crash on the internal ``keys=True``
   edge-view kwarg collision that used to fire in the rust-dispatch path.
"""

import pytest

import franken_networkx as fnx
import networkx as nx


@pytest.mark.parametrize(
    "fnx_cls",
    [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph],
)
@pytest.mark.parametrize(
    "op_name",
    ["compose", "union", "intersection", "difference", "symmetric_difference"],
)
def test_binary_operator_preserves_graph_class(fnx_cls, op_name):
    """Each operator must return an instance of the input graph class."""
    g = fnx_cls()
    h = fnx_cls()
    if op_name == "union":
        # union requires disjoint node sets
        g.add_node(0)
        h.add_node(1)
    else:
        # intersection / difference / symmetric_difference need same node set
        g.add_nodes_from([0, 1])
        h.add_nodes_from([0, 1])
        if op_name == "compose":
            g.add_edge(0, 1)

    op = getattr(fnx, op_name)
    result = op(g, h)
    assert type(result) is fnx_cls, (
        f"{op_name}({fnx_cls.__name__}, {fnx_cls.__name__}) returned "
        f"{type(result).__name__}, expected {fnx_cls.__name__}"
    )


def test_compose_preserves_node_and_edge_attrs():
    g = fnx.Graph()
    g.add_node(0, color="red")
    g.add_edge(0, 1, weight=5.0, label="x")
    h = fnx.Graph()
    h.add_node(2, color="blue")
    h.add_edge(2, 3, weight=7.0)

    r = fnx.compose(g, h)
    node_attrs = {n: dict(d) for n, d in r.nodes(data=True)}
    edge_attrs = {tuple(sorted([u, v])): dict(d) for u, v, d in r.edges(data=True)}
    assert node_attrs[0] == {"color": "red"}
    assert node_attrs[2] == {"color": "blue"}
    assert edge_attrs[(0, 1)] == {"weight": 5.0, "label": "x"}
    assert edge_attrs[(2, 3)] == {"weight": 7.0}


def test_compose_overlap_H_attrs_win():
    """Upstream nx.compose rule: H's attrs override on overlap."""
    g = fnx.Graph()
    g.add_edge(0, 1, source="G", weight=1.0)
    h = fnx.Graph()
    h.add_edge(0, 1, source="H", extra="new")

    r = fnx.compose(g, h)
    assert r[0][1] == {"source": "H", "weight": 1.0, "extra": "new"}


def test_union_preserves_node_and_edge_attrs():
    g = fnx.Graph()
    g.add_node(0, color="red")
    g.add_edge(0, 1, weight=5.0)
    h = fnx.Graph()
    h.add_node(2, color="blue")
    h.add_edge(2, 3, weight=7.0)

    r = fnx.union(g, h)
    node_attrs = {n: dict(d) for n, d in r.nodes(data=True)}
    edge_attrs = {tuple(sorted([u, v])): dict(d) for u, v, d in r.edges(data=True)}
    assert node_attrs[0] == {"color": "red"}
    assert node_attrs[2] == {"color": "blue"}
    assert edge_attrs[(0, 1)] == {"weight": 5.0}
    assert edge_attrs[(2, 3)] == {"weight": 7.0}


def test_compose_on_multigraph_does_not_crash():
    """Previously raised TypeError: __call__() got unexpected 'keys' kwarg."""
    mg1 = fnx.MultiGraph()
    mg1.add_edge(0, 1, key=0, weight=1)
    mg1.add_edge(0, 1, key=1, weight=2)
    mg2 = fnx.MultiGraph()
    mg2.add_edge(1, 2, key=0, weight=3)

    r = fnx.compose(mg1, mg2)
    assert isinstance(r, fnx.MultiGraph)
    edges = sorted(r.edges(keys=True, data=True))
    assert edges == [
        (0, 1, 0, {"weight": 1}),
        (0, 1, 1, {"weight": 2}),
        (1, 2, 0, {"weight": 3}),
    ]


def test_operators_reject_mismatched_graph_classes():
    """Matching upstream nx: binary ops reject Graph + DiGraph mixtures."""
    g = fnx.Graph(); g.add_edge(0, 1)
    d = fnx.DiGraph(); d.add_edge(0, 1)

    with pytest.raises(fnx.NetworkXError):
        fnx.compose(g, d)
    with pytest.raises(fnx.NetworkXError):
        fnx.union(g, d)


@pytest.mark.parametrize("op_name", ["compose", "union"])
def test_binary_operator_matches_nx_on_mixed_attrs(op_name):
    """Differential: fnx output equals nx output for compose + union on
    a graph with mixed node and edge attribute payloads.
    """
    def build(mod):
        g = mod.Graph()
        g.add_node(0, color="red")
        g.add_node(1)
        g.add_edge(0, 1, weight=5.0, label="x")
        return g

    def build_h(mod):
        h = mod.Graph()
        h.add_node(2, color="blue")
        h.add_edge(2, 3, weight=7.0)
        return h

    def norm(graph):
        return (
            sorted((n, tuple(sorted(d.items()))) for n, d in graph.nodes(data=True)),
            sorted(
                (min(u, v), max(u, v), tuple(sorted(d.items())))
                for u, v, d in graph.edges(data=True)
            ),
        )

    r_fnx = getattr(fnx, op_name)(build(fnx), build_h(fnx))
    r_nx = getattr(nx, op_name)(build(nx), build_h(nx))
    assert norm(r_fnx) == norm(r_nx)
