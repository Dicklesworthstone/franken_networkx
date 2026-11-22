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


def _node_merge_graph(module, graph_type, side, offset=0):
    graph = getattr(module, graph_type)()
    graph.graph["source"] = side
    # Ten attributed nodes reach the native bulk constructor. Do not read
    # their dictionaries before composition: those reads materialize them
    # and can hide a merge that incorrectly depends on storage history.
    graph.add_nodes_from(
        [(offset + node, {side: node, "shared": side}) for node in range(10)]
    )
    graph.add_edge(offset + 1, offset + 2, weight=offset + 1)
    return graph


def _operator_data(graph):
    edges = (
        [(u, v, key, dict(attrs)) for u, v, key, attrs in graph.edges(keys=True, data=True)]
        if graph.is_multigraph()
        else [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)]
    )
    return (
        dict(graph.graph),
        [(node, list(attrs.items())) for node, attrs in graph.nodes(data=True)],
        edges,
    )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "left_state,right_state",
    [
        ("cold", "cold"),
        ("warm", "warm"),
        ("cold", "warm"),
        ("warm", "cold"),
        ("cold", "cleared"),
        ("cleared", "cold"),
    ],
)
def test_compose_node_attributes_ignore_storage_history(
    graph_type, left_state, right_state
):
    def run(module):
        left = _node_merge_graph(module, graph_type, "left")
        right = _node_merge_graph(module, graph_type, "right")
        for graph, state in ((left, left_state), (right, right_state)):
            if state == "warm":
                graph.nodes[0]
            elif state == "cleared":
                graph.nodes[0].clear()
        result = module.compose(left, right)
        return _operator_data(result), _operator_data(left), _operator_data(right)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("operator_name", ["compose", "union", "disjoint_union"])
@pytest.mark.parametrize("cleared_side", ["left", "right"])
def test_binary_operator_does_not_restore_cleared_node_attributes(
    graph_type, operator_name, cleared_side
):
    def run(module):
        left = _node_merge_graph(module, graph_type, "left")
        right = _node_merge_graph(module, graph_type, "right", offset=10)
        graph, node = (left, 0) if cleared_side == "left" else (right, 10)
        graph.nodes[node].clear()
        result = getattr(module, operator_name)(left, right)
        assert result.nodes[node] == {}
        return _operator_data(result), _operator_data(left), _operator_data(right)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("operator_name", ["compose", "union"])
@pytest.mark.parametrize("route", ["top_level", "operators", "algorithms", "backend"])
def test_composed_node_attributes_preserve_keys_and_sharing_across_routes(
    graph_type, operator_name, route
):
    def build(module):
        left = _node_merge_graph(module, graph_type, "left")
        target = 0 if operator_name == "compose" else 10
        right = _node_merge_graph(module, graph_type, "right", offset=target)
        left.nodes[5].clear()
        payload = ["shared"]
        right_attrs = right.nodes[target]
        right_attrs[("kind", 1)] = "nonstring key"
        right_attrs["payload"] = payload
        return left, right, target, payload, right_attrs

    expected_left, expected_right, _, _, _ = build(nx)
    expected = getattr(nx, operator_name)(expected_left, expected_right)
    left, right, target, payload, right_attrs = build(fnx)
    if route == "backend":
        result = getattr(nx, operator_name)(left, right, backend="franken_networkx")
    elif route == "operators":
        from franken_networkx import operators

        result = getattr(operators, operator_name)(left, right)
    elif route == "algorithms":
        from franken_networkx.algorithms import operators

        result = getattr(operators, operator_name)(left, right)
    else:
        result = getattr(fnx, operator_name)(left, right)

    assert type(result) is getattr(fnx, graph_type)
    assert _operator_data(result) == _operator_data(expected)
    assert _operator_data(left) == _operator_data(expected_left)
    assert _operator_data(right) == _operator_data(expected_right)
    result_attrs = result.nodes[target]
    assert result_attrs is not right_attrs
    assert result_attrs["payload"] is payload
    result_attrs["result_only"] = True
    assert "result_only" not in right_attrs
    result_attrs["payload"].append("still shared")
    assert right_attrs["payload"] == ["shared", "still shared"]


def test_compose_undirected_edge_order_matches_networkx():
    """Edge tuple orientation/order should match nx for simple Graph output."""
    g = fnx.Graph()
    g.add_edge(0, 1, source="G")
    h = fnx.Graph()
    h.add_edge(1, 2, source="H")
    ng = nx.Graph()
    ng.add_edge(0, 1, source="G")
    nh = nx.Graph()
    nh.add_edge(1, 2, source="H")

    assert list(fnx.compose(g, h).edges(data=True)) == list(
        nx.compose(ng, nh).edges(data=True)
    )


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


# br-diffnodes: nx.difference / nx.symmetric_difference enforce that the
# two input graphs have identical node sets. fnx previously skipped this
# check and silently computed an edge-set operation over whatever nodes
# were present — diverging silently from nx on any misuse.
def test_difference_enforces_equal_node_sets():
    g = fnx.Graph()
    g.add_edges_from([(0, 1), (1, 2)])
    h = fnx.Graph()
    h.add_edges_from([(0, 1), (2, 3)])

    with pytest.raises(fnx.NetworkXError, match=r"Node sets of graphs not equal"):
        fnx.difference(g, h)


def test_symmetric_difference_enforces_equal_node_sets():
    g = fnx.Graph()
    g.add_edges_from([(0, 1), (1, 2)])
    h = fnx.Graph()
    h.add_edges_from([(0, 1), (2, 3)])

    with pytest.raises(fnx.NetworkXError, match=r"Node sets of graphs not equal"):
        fnx.symmetric_difference(g, h)


def test_difference_matches_nx_on_equal_node_set():
    """Sanity: the fix didn't break the happy path."""
    g = fnx.Graph(); g.add_nodes_from([0, 1, 2, 3]); g.add_edges_from([(0, 1), (1, 2)])
    h = fnx.Graph(); h.add_nodes_from([0, 1, 2, 3]); h.add_edges_from([(0, 1), (2, 3)])
    gn = nx.Graph(); gn.add_nodes_from([0, 1, 2, 3]); gn.add_edges_from([(0, 1), (1, 2)])
    hn = nx.Graph(); hn.add_nodes_from([0, 1, 2, 3]); hn.add_edges_from([(0, 1), (2, 3)])

    r_fnx = fnx.difference(g, h)
    r_nx = nx.difference(gn, hn)
    assert sorted(r_fnx.edges()) == sorted(r_nx.edges())
    assert sorted(r_fnx.nodes()) == sorted(r_nx.nodes())


def test_symmetric_difference_matches_nx_on_equal_node_set():
    g = fnx.Graph(); g.add_nodes_from([0, 1, 2, 3]); g.add_edges_from([(0, 1), (1, 2)])
    h = fnx.Graph(); h.add_nodes_from([0, 1, 2, 3]); h.add_edges_from([(0, 1), (2, 3)])
    gn = nx.Graph(); gn.add_nodes_from([0, 1, 2, 3]); gn.add_edges_from([(0, 1), (1, 2)])
    hn = nx.Graph(); hn.add_nodes_from([0, 1, 2, 3]); hn.add_edges_from([(0, 1), (2, 3)])

    r_fnx = fnx.symmetric_difference(g, h)
    r_nx = nx.symmetric_difference(gn, hn)
    assert sorted(r_fnx.edges()) == sorted(r_nx.edges())


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


# ---------------------------------------------------------------------------
# franken_networkx-uwa6w: ladder_graph / circular_ladder_graph edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5])
def test_ladder_graph_matches_networkx_for_small_n(n):
    fg = fnx.ladder_graph(n)
    ng = nx.ladder_graph(n)
    assert set(fg.nodes()) == set(ng.nodes())
    assert set(frozenset(e) for e in fg.edges()) == set(
        frozenset(e) for e in ng.edges()
    )


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5])
def test_circular_ladder_graph_matches_networkx_for_small_n(n):
    fg = fnx.circular_ladder_graph(n)
    ng = nx.circular_ladder_graph(n)
    assert set(fg.nodes()) == set(ng.nodes())
    assert set(frozenset(e) for e in fg.edges()) == set(
        frozenset(e) for e in ng.edges()
    )
