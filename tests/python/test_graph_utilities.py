"""Tests for graph utility wrapper functions."""

from collections.abc import Mapping
import gc

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def _block_networkx_utilities(monkeypatch, *names):
    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX utility fallback should not be used")

    for name in names:
        monkeypatch.setattr(nx, name, fail_networkx)


def _normalize_attr(value):
    if isinstance(value, dict):
        return tuple(sorted((repr(key), _normalize_attr(item)) for key, item in value.items()))
    return value


def _graph_snapshot(graph):
    if graph.is_multigraph():
        edges = sorted(
            (u, v, key, _normalize_attr(dict(data)))
            for u, v, key, data in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted((u, v, _normalize_attr(dict(data))) for u, v, data in graph.edges(data=True))
    return (
        sorted((node, _normalize_attr(dict(data))) for node, data in graph.nodes(data=True)),
        edges,
    )


def _mapping_snapshot(value):
    if isinstance(value, Mapping):
        return tuple(sorted((repr(key), _mapping_snapshot(item)) for key, item in value.items()))
    return value


def _direction_utility_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.graph["name"] = "direction"
    expected.graph["name"] = "direction"
    for node, color in [("a", "red"), ("b", "blue"), ("c", "green")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)

    edge_payloads = [
        ("a", "b", 4, {"weight": 2}),
        ("b", "c", 6, {"weight": 7}),
    ]
    for source, target, key, attrs in edge_payloads:
        if graph.is_multigraph():
            graph.add_edge(source, target, key=key, **attrs)
            expected.add_edge(source, target, key=key, **attrs)
        else:
            graph.add_edge(source, target, **attrs)
            expected.add_edge(source, target, **attrs)
    return graph, expected


def _view_utility_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.graph["name"] = "view"
    expected.graph["name"] = "view"
    for node, color in [
        ("a", "red"),
        ("b", "blue"),
        ("c", "green"),
        ("d", "yellow"),
    ]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)

    edge_payloads = [
        ("a", "b", 1, {"weight": 1}),
        ("a", "b", 2, {"weight": 2}),
        ("b", "c", 1, {"weight": 3}),
        ("c", "d", 1, {"weight": 4}),
    ]
    for source, target, key, attrs in edge_payloads:
        if graph.is_multigraph():
            graph.add_edge(source, target, key=key, **attrs)
            expected.add_edge(source, target, key=key, **attrs)
        elif key == 1:
            graph.add_edge(source, target, **attrs)
            expected.add_edge(source, target, **attrs)
    return graph, expected


def _weighted_degree_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    for node in ["a", "b", "c"]:
        graph.add_node(node)
        expected.add_node(node)

    if graph.is_directed():
        edge_payloads = [
            ("a", "b", 1, {"weight": 1}),
            ("b", "a", 2, {"weight": 2}),
            ("a", "a", 3, {"weight": 4}),
            ("c", "b", 4, {}),
        ]
    else:
        edge_payloads = [
            ("a", "b", 1, {"weight": 1}),
            ("a", "a", 2, {"weight": 4}),
            ("b", "c", 3, {}),
        ]

    for source, target, key, attrs in edge_payloads:
        if graph.is_multigraph():
            graph.add_edge(source, target, key=key, **attrs)
            expected.add_edge(source, target, key=key, **attrs)
        else:
            graph.add_edge(source, target, **attrs)
            expected.add_edge(source, target, **attrs)
    return graph, expected


def _selfloop_utility_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    for node in ["a", "b", "c"]:
        graph.add_node(node)
        expected.add_node(node)

    if graph.is_multigraph():
        edge_payloads = [
            ("a", "a", "k1", {"weight": 2}),
            ("a", "a", "k2", {}),
            ("b", "b", "k3", {"color": "blue"}),
            ("a", "c", "k4", {"weight": 9}),
        ]
        for source, target, key, attrs in edge_payloads:
            graph.add_edge(source, target, key=key, **attrs)
            expected.add_edge(source, target, key=key, **attrs)
    else:
        edge_payloads = [
            ("a", "a", {"weight": 2}),
            ("b", "b", {"color": "blue"}),
            ("a", "c", {"weight": 9}),
        ]
        for source, target, attrs in edge_payloads:
            graph.add_edge(source, target, **attrs)
            expected.add_edge(source, target, **attrs)
    return graph, expected


def _isolate_utility_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_nodes_from(["a", "b", "c", "d", "e"])
    expected.add_nodes_from(["a", "b", "c", "d", "e"])

    edge_payloads = [("a", "b", 1), ("c", "a", 2)]
    for source, target, key in edge_payloads:
        if graph.is_multigraph():
            graph.add_edge(source, target, key=key)
            expected.add_edge(source, target, key=key)
        else:
            graph.add_edge(source, target)
            expected.add_edge(source, target)
    return graph, expected


def _degree_histogram_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_nodes_from(["a", "b", "c", "d"])
    expected.add_nodes_from(["a", "b", "c", "d"])

    if graph.is_multigraph():
        edge_payloads = [
            ("a", "b", "k1"),
            ("a", "b", "k2"),
            ("a", "c", "k3"),
        ]
        if graph.is_directed():
            edge_payloads.append(("c", "a", "k4"))
        for source, target, key in edge_payloads:
            graph.add_edge(source, target, key=key)
            expected.add_edge(source, target, key=key)
    else:
        edge_payloads = [("a", "b"), ("a", "c")]
        if graph.is_directed():
            edge_payloads.append(("c", "a"))
        for source, target in edge_payloads:
            graph.add_edge(source, target)
            expected.add_edge(source, target)
    return graph, expected


def _graph_helper_result_pair(fnx_cls, nx_cls, helper_name, nodes, **attrs):
    graph = fnx_cls()
    expected = nx_cls()
    getattr(nx, helper_name)(expected, nodes, **attrs)
    getattr(fnx, helper_name)(graph, nodes, **attrs)
    return graph, expected


def test_voronoi_cells_and_stoer_wagner_match_networkx():
    graph = fnx.path_graph(5)

    assert fnx.voronoi_cells(graph, [0, 4]) == nx.voronoi_cells(nx.path_graph(5), [0, 4])
    assert fnx.stoer_wagner(graph) == nx.stoer_wagner(nx.path_graph(5))


def test_dedensify_and_quotient_graph_match_networkx():
    bipartite = fnx.complete_bipartite_graph(2, 4)
    dedensified, compressors = fnx.dedensify(bipartite, 2, prefix="aux")
    dedensified_nx, compressors_nx = nx.dedensify(_to_nx(bipartite), 2, prefix="aux")

    partition = [{0, 1}, {2, 3}]
    quotient = fnx.quotient_graph(fnx.path_graph(4), partition)
    quotient_nx = nx.quotient_graph(_to_nx(fnx.path_graph(4)), partition)

    assert sorted(_to_nx(dedensified).edges()) == sorted(dedensified_nx.edges())
    assert compressors == compressors_nx
    assert sorted(_to_nx(quotient).edges()) == sorted(quotient_nx.edges())


def test_dedensify_and_quotient_graph_do_not_fallback(monkeypatch):
    bipartite = fnx.complete_bipartite_graph(2, 4)
    expected_dedensified, expected_compressors = nx.dedensify(
        _to_nx(bipartite),
        2,
        prefix="aux",
    )
    expected_dedensified_edges = sorted(expected_dedensified.edges())

    path = fnx.path_graph(4)
    partition = [{0, 1}, {2, 3}]
    expected_quotient = nx.quotient_graph(_to_nx(path), partition)
    expected_quotient_edges = sorted(expected_quotient.edges())

    _block_networkx_utilities(monkeypatch, "dedensify", "quotient_graph")

    dedensified, compressors = fnx.dedensify(bipartite, 2, prefix="aux")
    quotient = fnx.quotient_graph(path, partition)

    assert sorted(_to_nx(dedensified).edges()) == expected_dedensified_edges
    assert compressors == expected_compressors
    assert sorted(_to_nx(quotient).edges()) == expected_quotient_edges


def test_snap_aggregation_and_full_join_match_networkx():
    graph = fnx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph.nodes[node]["color"] = color

    graph_nx = nx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph_nx.nodes[node]["color"] = color

    summary = fnx.snap_aggregation(graph, ["color"])
    summary_nx = nx.snap_aggregation(graph_nx, ["color"])
    joined = fnx.full_join(fnx.path_graph(2), fnx.path_graph(2), rename=("L", "R"))
    joined_nx = nx.full_join(nx.path_graph(2), nx.path_graph(2), rename=("L", "R"))

    assert sorted(_to_nx(summary).edges()) == sorted(summary_nx.edges())
    assert sorted(_to_nx(joined).edges()) == sorted(joined_nx.edges())


def test_full_join_does_not_fallback(monkeypatch):
    expected = nx.full_join(nx.path_graph(2), nx.path_graph(2), rename=("L", "R"))
    expected_edges = sorted(expected.edges())

    _block_networkx_utilities(monkeypatch, "full_join")

    joined = fnx.full_join(fnx.path_graph(2), fnx.path_graph(2), rename=("L", "R"))

    assert sorted(_to_nx(joined).edges()) == expected_edges


def test_full_join_union_contract_matches_networkx_without_fallback(monkeypatch):
    left = fnx.DiGraph()
    left.graph["who"] = "left"
    left.add_node("a", color="red")
    left.add_node("b")
    left.add_edge("a", "b", weight=2)

    right = fnx.DiGraph()
    right.graph["who"] = "right"
    right.add_node("c", color="blue")
    right.add_node("d")
    right.add_edge("c", "d", weight=3)

    left_nx = nx.DiGraph()
    left_nx.graph["who"] = "left"
    left_nx.add_node("a", color="red")
    left_nx.add_node("b")
    left_nx.add_edge("a", "b", weight=2)

    right_nx = nx.DiGraph()
    right_nx.graph["who"] = "right"
    right_nx.add_node("c", color="blue")
    right_nx.add_node("d")
    right_nx.add_edge("c", "d", weight=3)

    expected = nx.full_join(left_nx, right_nx, rename=("L-", "R-"))

    overlap_left_nx = nx.Graph()
    overlap_left_nx.add_edge("x", "y")
    overlap_right_nx = nx.Graph()
    overlap_right_nx.add_edge("x", "z")
    try:
        nx.full_join(overlap_left_nx, overlap_right_nx)
    except Exception as exc:
        expected_overlap = (type(exc).__name__, str(exc))

    mixed_left_nx = nx.Graph()
    mixed_left_nx.add_edge("g0", "g1")
    mixed_right_nx = nx.MultiGraph()
    mixed_right_nx.add_edge("h0", "h1", key=1)
    try:
        nx.full_join(mixed_left_nx, mixed_right_nx)
    except Exception as exc:
        expected_mixed = (type(exc).__name__, str(exc))

    _block_networkx_utilities(monkeypatch, "full_join")

    result = fnx.full_join(left, right, rename=("L-", "R-"))

    assert dict(result.graph) == expected.graph
    assert result.is_directed() == expected.is_directed()
    assert result.is_multigraph() == expected.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected)

    overlap_left = fnx.Graph()
    overlap_left.add_edge("x", "y")
    overlap_right = fnx.Graph()
    overlap_right.add_edge("x", "z")
    with pytest.raises(Exception) as overlap_exc:
        fnx.full_join(overlap_left, overlap_right)
    assert type(overlap_exc.value).__name__ == expected_overlap[0]
    assert str(overlap_exc.value) == expected_overlap[1]

    mixed_left = fnx.Graph()
    mixed_left.add_edge("g0", "g1")
    mixed_right = fnx.MultiGraph()
    mixed_right.add_edge("h0", "h1", key=1)
    with pytest.raises(Exception) as mixed_exc:
        fnx.full_join(mixed_left, mixed_right)
    assert type(mixed_exc.value).__name__ == expected_mixed[0]
    assert str(mixed_exc.value) == expected_mixed[1]


def test_identified_nodes_and_inverse_line_graph_match_networkx():
    path = fnx.path_graph(4)
    identified = fnx.identified_nodes(path, 1, 2)
    identified_nx = nx.identified_nodes(_to_nx(path), 1, 2)

    line = fnx.line_graph(fnx.path_graph(5))
    inverse = fnx.inverse_line_graph(line)
    inverse_nx = nx.inverse_line_graph(_to_nx(line))

    assert sorted(_to_nx(identified).edges()) == sorted(identified_nx.edges())
    assert sorted(_to_nx(inverse).edges()) == sorted(inverse_nx.edges())


def test_identified_nodes_does_not_fallback(monkeypatch):
    path = fnx.path_graph(4)
    expected = nx.identified_nodes(_to_nx(path), 1, 2, self_loops=False)
    expected_edges = sorted(expected.edges())
    expected_node_data = dict(expected.nodes[1])

    _block_networkx_utilities(monkeypatch, "identified_nodes")

    identified = fnx.identified_nodes(path, 1, 2, self_loops=False)
    identified_nx = _to_nx(identified)

    assert sorted(identified_nx.edges()) == expected_edges
    assert dict(identified_nx.nodes[1]) == expected_node_data


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("copy", [False, True])
@pytest.mark.parametrize("self_loops", [False, True])
@pytest.mark.parametrize("store_contraction_as", [None, "c", "contraction"])
def test_identified_nodes_mode_matrix_matches_networkx_without_fallback(
    monkeypatch,
    directed,
    copy,
    self_loops,
    store_contraction_as,
):
    graph = fnx.DiGraph() if directed else fnx.Graph()
    expected = nx.DiGraph() if directed else nx.Graph()
    for node, color in [(0, "zero"), (1, "one"), (2, "two"), (3, "three")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)
    edges = (
        [(0, 2, 5), (2, 1, 7), (2, 3, 11), (3, 2, 13)]
        if directed
        else [(0, 1, 10), (1, 2, 20), (2, 3, 30)]
    )
    for source, target, weight in edges:
        graph.add_edge(source, target, weight=weight)
        expected.add_edge(source, target, weight=weight)

    expected_result = nx.identified_nodes(
        expected,
        1,
        2,
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    expected_nodes = sorted((node, dict(data)) for node, data in expected_result.nodes(data=True))
    expected_edges = sorted((u, v, dict(data)) for u, v, data in expected_result.edges(data=True))

    _block_networkx_utilities(monkeypatch, "identified_nodes")

    result = fnx.identified_nodes(
        graph,
        1,
        2,
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    if not copy:
        assert result is graph
    result_nx = _to_nx(result)

    assert sorted((node, dict(data)) for node, data in result_nx.nodes(data=True)) == expected_nodes
    assert sorted((u, v, dict(data)) for u, v, data in result_nx.edges(data=True)) == expected_edges


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("copy", [False, True])
@pytest.mark.parametrize("self_loops", [False, True])
@pytest.mark.parametrize("store_contraction_as", [None, "c", "contraction"])
def test_contracted_nodes_matches_networkx_without_fallback(
    monkeypatch,
    directed,
    copy,
    self_loops,
    store_contraction_as,
):
    graph = fnx.DiGraph() if directed else fnx.Graph()
    expected = nx.DiGraph() if directed else nx.Graph()
    for node, color in [(0, "zero"), (1, "one"), (2, "two")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)
    duplicate_edges = [(0, 1, 10), (2, 1, 100)] if directed else [(0, 1, 10), (1, 2, 100)]
    for source, target, weight in duplicate_edges:
        graph.add_edge(source, target, weight=weight)
        expected.add_edge(source, target, weight=weight)

    expected_result = nx.contracted_nodes(
        expected,
        0,
        2,
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "contracted_nodes")

    result = fnx.contracted_nodes(
        graph,
        0,
        2,
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    if not copy:
        assert result is graph

    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("copy", [False, True])
@pytest.mark.parametrize("self_loops", [False, True])
@pytest.mark.parametrize("store_contraction_as", [None, "c", "contraction"])
def test_contracted_edge_matches_networkx_without_fallback(
    monkeypatch,
    directed,
    copy,
    self_loops,
    store_contraction_as,
):
    graph = fnx.DiGraph() if directed else fnx.Graph()
    expected = nx.DiGraph() if directed else nx.Graph()
    for node in range(3):
        graph.add_node(node)
        expected.add_node(node)
    for source, target, weight in [(0, 1, 10), (1, 2, 20)]:
        graph.add_edge(source, target, weight=weight)
        expected.add_edge(source, target, weight=weight)

    expected_result = nx.contracted_edge(
        expected,
        (0, 1),
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "contracted_edge", "contracted_nodes")

    result = fnx.contracted_edge(
        graph,
        (0, 1),
        copy=copy,
        self_loops=self_loops,
        store_contraction_as=store_contraction_as,
    )
    if not copy:
        assert result is graph

    assert _graph_snapshot(result) == expected_snapshot


def test_contracted_edge_rejects_missing_edge_without_fallback(monkeypatch):
    graph = fnx.path_graph(3)

    _block_networkx_utilities(monkeypatch, "contracted_edge", "contracted_nodes")

    with pytest.raises(ValueError, match="does not exist"):
        fnx.contracted_edge(graph, (0, 2))


def test_inverse_line_graph_matches_networkx_edge_cases():
    empty_inverse = fnx.inverse_line_graph(fnx.Graph())
    expected_empty_inverse = nx.inverse_line_graph(nx.Graph())
    assert sorted(_to_nx(empty_inverse).edges()) == sorted(expected_empty_inverse.edges())

    single = fnx.Graph()
    single.add_node("x")
    single_inverse = fnx.inverse_line_graph(single)
    expected_single_graph = nx.Graph()
    expected_single_graph.add_node("x")
    expected_single_inverse = nx.inverse_line_graph(expected_single_graph)
    assert sorted(_to_nx(single_inverse).edges()) == sorted(expected_single_inverse.edges())

    edgeless = fnx.Graph()
    edgeless.add_nodes_from([0, 1])
    with pytest.raises(fnx.NetworkXError, match="edgeless graph"):
        fnx.inverse_line_graph(edgeless)

    loopy = fnx.Graph()
    loopy.add_node(1)
    loopy.add_edge(0, 0)
    with pytest.raises(fnx.NetworkXError, match="no selfloops"):
        fnx.inverse_line_graph(loopy)


def test_graph_utility_wrappers_match_networkx():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2)
    graph.add_edge(1, 2, weight=3)
    graph.add_edge(2, 3, weight=4)

    expected = nx.Graph()
    expected.add_edge(0, 1, weight=2)
    expected.add_edge(1, 2, weight=3)
    expected.add_edge(2, 3, weight=4)

    assert list(fnx.nodes(graph)) == list(nx.nodes(expected))
    assert list(fnx.edges(graph)) == list(nx.edges(expected))
    assert sorted(fnx.edges(graph, [1, 2])) == sorted(nx.edges(expected, [1, 2]))
    assert list(fnx.degree(graph)) == list(nx.degree(expected))
    assert dict(fnx.degree(graph, weight="weight")) == dict(nx.degree(expected, weight="weight"))
    assert tuple(fnx.neighbors(graph, 1)) == tuple(nx.neighbors(expected, 1))


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_edges_nbunch_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = list(nx.edges(expected, ["b", "a"]))

    _block_networkx_utilities(monkeypatch, "edges")

    result = list(fnx.edges(graph, ["b", "a"]))

    assert result == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_edges_missing_scalar_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    missing_node = 9

    try:
        nx.edges(expected, missing_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "edges")

    with pytest.raises(Exception) as fnx_exc:
        fnx.edges(graph, missing_node)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_nodes_with_selfloops_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _selfloop_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = list(nx.nodes_with_selfloops(expected))

    _block_networkx_utilities(monkeypatch, "nodes_with_selfloops")

    assert list(fnx.nodes_with_selfloops(graph)) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_number_of_selfloops_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _selfloop_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.number_of_selfloops(expected)

    _block_networkx_utilities(monkeypatch, "number_of_selfloops")

    assert fnx.number_of_selfloops(graph) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
@pytest.mark.parametrize(
    ("keys", "data", "default"),
    [
        (False, False, "fallback"),
        (False, True, "fallback"),
        (False, "weight", "fallback"),
        (True, False, "fallback"),
        (True, True, "fallback"),
        (True, "weight", "fallback"),
    ],
)
def test_global_selfloop_edges_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls, keys, data, default
):
    graph, expected = _selfloop_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = list(
        nx.selfloop_edges(expected, keys=keys, data=data, default=default)
    )

    _block_networkx_utilities(monkeypatch, "selfloop_edges")

    assert (
        list(fnx.selfloop_edges(graph, keys=keys, data=data, default=default))
        == expected_result
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_is_isolate_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _isolate_utility_graph_pair(fnx_cls, nx_cls)
    expected_true = nx.is_isolate(expected, "d")
    expected_false = nx.is_isolate(expected, "a")

    _block_networkx_utilities(monkeypatch, "is_isolate")

    assert fnx.is_isolate(graph, "d") is expected_true
    assert fnx.is_isolate(graph, "a") is expected_false


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_isolates_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _isolate_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = list(nx.isolates(expected))

    _block_networkx_utilities(monkeypatch, "isolates")

    assert list(fnx.isolates(graph)) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_number_of_isolates_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _isolate_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.number_of_isolates(expected)

    _block_networkx_utilities(monkeypatch, "number_of_isolates")

    assert fnx.number_of_isolates(graph) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
@pytest.mark.parametrize("is_empty_graph", [False, True])
def test_global_is_empty_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls, is_empty_graph
):
    if is_empty_graph:
        graph = fnx_cls()
        expected = nx_cls()
    else:
        graph, expected = _isolate_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.is_empty(expected)

    _block_networkx_utilities(monkeypatch, "is_empty")

    assert fnx.is_empty(graph) is expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_density_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _degree_histogram_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.density(expected)

    _block_networkx_utilities(monkeypatch, "density")

    assert fnx.density(graph) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_degree_histogram_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _degree_histogram_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.degree_histogram(expected)

    _block_networkx_utilities(monkeypatch, "degree_histogram")

    assert fnx.degree_histogram(graph) == expected_result


@pytest.mark.parametrize(
    ("helper_name", "nodes", "attrs"),
    [
        ("add_path", [0, 1, 2], {"weight": 5, "label": "path"}),
        ("add_cycle", [0, 1, 2], {"weight": 7, "label": "cycle"}),
        ("add_star", [0, 1, 2], {"weight": 11, "label": "star"}),
        ("add_path", [], {}),
        ("add_path", [1], {}),
        ("add_path", [1, 1, 2], {}),
        ("add_cycle", [], {}),
        ("add_cycle", [1], {}),
        ("add_cycle", [1, 1, 2], {}),
        ("add_star", [], {}),
        ("add_star", [1], {}),
        ("add_star", [1, 1, 2], {}),
    ],
)
@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_helpers_match_networkx_without_fallback(
    monkeypatch, helper_name, nodes, attrs, fnx_cls, nx_cls
):
    graph, expected = _graph_helper_result_pair(
        fnx_cls,
        nx_cls,
        helper_name,
        nodes,
        **attrs,
    )
    expected_snapshot = _graph_snapshot(expected)

    _block_networkx_utilities(monkeypatch, helper_name)

    result = fnx_cls()
    getattr(fnx, helper_name)(result, nodes, **attrs)

    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_all_neighbors_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_nodes_from(["a", "b", "c", "d"])
    expected.add_nodes_from(["a", "b", "c", "d"])

    edge_payloads = [("a", "b"), ("c", "b"), ("b", "d")]
    for source, target in edge_payloads:
        graph.add_edge(source, target)
        expected.add_edge(source, target)

    expected_neighbors = list(nx.all_neighbors(expected, "b"))

    _block_networkx_utilities(monkeypatch, "all_neighbors")

    assert list(fnx.all_neighbors(graph, "b")) == expected_neighbors


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_all_neighbors_directed_duplicates_match_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_edges_from([("a", "b"), ("b", "a"), ("b", "c")])
    expected.add_edges_from([("a", "b"), ("b", "a"), ("b", "c")])

    expected_neighbors = list(nx.all_neighbors(expected, "b"))

    _block_networkx_utilities(monkeypatch, "all_neighbors")

    assert list(fnx.all_neighbors(graph, "b")) == expected_neighbors


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_neighbors_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_neighbors = list(nx.neighbors(expected, "a"))

    _block_networkx_utilities(monkeypatch, "neighbors")

    assert list(fnx.neighbors(graph, "a")) == expected_neighbors


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls", "missing_node"),
    [
        (fnx.Graph, nx.Graph, 9),
        (fnx.Graph, nx.Graph, "missing"),
        (fnx.DiGraph, nx.DiGraph, 9),
        (fnx.DiGraph, nx.DiGraph, "missing"),
        (fnx.MultiGraph, nx.MultiGraph, 9),
        (fnx.MultiGraph, nx.MultiGraph, "missing"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, 9),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "missing"),
    ],
)
def test_global_neighbors_missing_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls, missing_node
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    try:
        nx.neighbors(expected, missing_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "neighbors")

    with pytest.raises(Exception) as fnx_exc:
        list(fnx.neighbors(graph, missing_node))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_neighbors_invalid_node_type_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    invalid_node = ["a"]

    try:
        nx.neighbors(expected, invalid_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "neighbors")

    with pytest.raises(Exception) as fnx_exc:
        list(fnx.neighbors(graph, invalid_node))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_non_neighbors_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = set(nx.non_neighbors(expected, "a"))

    _block_networkx_utilities(monkeypatch, "non_neighbors")

    assert set(fnx.non_neighbors(graph, "a")) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls", "missing_node"),
    [
        (fnx.Graph, nx.Graph, 9),
        (fnx.Graph, nx.Graph, "missing"),
        (fnx.DiGraph, nx.DiGraph, 9),
        (fnx.DiGraph, nx.DiGraph, "missing"),
        (fnx.MultiGraph, nx.MultiGraph, 9),
        (fnx.MultiGraph, nx.MultiGraph, "missing"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, 9),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "missing"),
    ],
)
def test_global_non_neighbors_missing_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls, missing_node
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    try:
        set(nx.non_neighbors(expected, missing_node))
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "non_neighbors")

    with pytest.raises(Exception) as fnx_exc:
        set(fnx.non_neighbors(graph, missing_node))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_non_neighbors_invalid_node_type_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    invalid_node = ["a"]

    try:
        set(nx.non_neighbors(expected, invalid_node))
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "non_neighbors")

    with pytest.raises(Exception) as fnx_exc:
        set(fnx.non_neighbors(graph, invalid_node))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_non_edges_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_nodes_from(["a", "b", "c", "d"])
    expected.add_nodes_from(["a", "b", "c", "d"])
    graph.add_edge("a", "b")
    expected.add_edge("a", "b")
    graph.add_edge("b", "c")
    expected.add_edge("b", "c")
    if graph.is_directed():
        graph.add_edge("c", "a")
        expected.add_edge("c", "a")
    if graph.is_multigraph():
        graph.add_edge("a", "b", key="k2")
        expected.add_edge("a", "b", key="k2")

    expected_result = list(nx.non_edges(expected))

    _block_networkx_utilities(monkeypatch, "non_edges")

    assert list(fnx.non_edges(graph)) == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_global_common_neighbors_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.common_neighbors(expected, "a", "c")

    _block_networkx_utilities(monkeypatch, "common_neighbors")

    result = fnx.common_neighbors(graph, "a", "c")

    assert isinstance(result, set)
    assert result == expected_result


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_global_common_neighbors_missing_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    try:
        nx.common_neighbors(expected, "a", "missing")
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "common_neighbors")

    with pytest.raises(Exception) as fnx_exc:
        fnx.common_neighbors(graph, "a", "missing")

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_common_neighbors_directed_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    try:
        nx.common_neighbors(expected, "a", "missing")
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "common_neighbors")

    with pytest.raises(Exception) as fnx_exc:
        fnx.common_neighbors(graph, "a", "missing")

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_degree_nbunch_normalization_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_scalar = nx.degree(expected, "a")
    expected_missing_string = list(nx.degree(expected, "missing"))
    expected_missing_list = list(nx.degree(expected, ["missing"]))
    expected_subset = list(nx.degree(expected, ["a", "missing"]))

    _block_networkx_utilities(monkeypatch, "degree")

    assert fnx.degree(graph, "a") == expected_scalar
    assert list(fnx.degree(graph, "missing")) == expected_missing_string
    assert list(fnx.degree(graph, ["missing"])) == expected_missing_list
    assert list(fnx.degree(graph, ["a", "missing"])) == expected_subset


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_degree_missing_scalar_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    missing_node = 9

    try:
        nx.degree(expected, missing_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "degree")

    with pytest.raises(Exception) as fnx_exc:
        fnx.degree(graph, missing_node)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_degree_invalid_nbunch_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    invalid_nbunch = [["a"]]

    try:
        nx.degree(expected, invalid_nbunch)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "degree")

    with pytest.raises(Exception) as fnx_exc:
        list(fnx.degree(graph, invalid_nbunch))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_weighted_degree_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _weighted_degree_graph_pair(fnx_cls, nx_cls)
    expected_all = list(nx.degree(expected, weight="weight"))
    expected_scalar = nx.degree(expected, "a", weight="weight")
    expected_subset = list(nx.degree(expected, ["a", "missing"], weight="weight"))
    expected_missing_string = list(nx.degree(expected, "missing", weight="weight"))

    _block_networkx_utilities(monkeypatch, "degree")

    assert list(fnx.degree(graph, weight="weight")) == expected_all
    assert fnx.degree(graph, "a", weight="weight") == expected_scalar
    assert list(fnx.degree(graph, ["a", "missing"], weight="weight")) == expected_subset
    assert list(fnx.degree(graph, "missing", weight="weight")) == expected_missing_string


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_weighted_degree_missing_scalar_node_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _weighted_degree_graph_pair(fnx_cls, nx_cls)
    missing_node = 9

    try:
        nx.degree(expected, missing_node, weight="weight")
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "degree")

    with pytest.raises(Exception) as fnx_exc:
        fnx.degree(graph, missing_node, weight="weight")

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_weighted_degree_invalid_nbunch_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _weighted_degree_graph_pair(fnx_cls, nx_cls)
    invalid_nbunch = [["a"]]

    try:
        nx.degree(expected, invalid_nbunch, weight="weight")
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "degree")

    with pytest.raises(Exception) as fnx_exc:
        list(fnx.degree(graph, invalid_nbunch, weight="weight"))

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


def test_directed_conversion_helpers_match_networkx():
    graph = fnx.MultiGraph()
    graph.graph["name"] = "base"
    graph.add_node("a", color="red")
    graph.add_edge("a", "b", key=4, weight=2)

    expected = nx.MultiGraph()
    expected.graph["name"] = "base"
    expected.add_node("a", color="red")
    expected.add_edge("a", "b", key=4, weight=2)

    directed = fnx.to_directed(graph)
    directed_nx = nx.to_directed(expected)
    assert directed.is_directed()
    assert directed.is_multigraph()
    assert dict(directed.graph) == directed_nx.graph
    assert sorted(directed.nodes(data=True)) == sorted(directed_nx.nodes(data=True))
    assert sorted(directed.edges(keys=True, data=True)) == sorted(directed_nx.edges(keys=True, data=True))

    undirected = fnx.to_undirected(directed)
    undirected_nx = nx.to_undirected(directed_nx)
    assert not undirected.is_directed()
    assert undirected.is_multigraph()
    assert dict(undirected.graph) == undirected_nx.graph
    assert sorted(undirected.nodes(data=True)) == sorted(undirected_nx.nodes(data=True))
    assert sorted(undirected.edges(keys=True, data=True)) == sorted(undirected_nx.edges(keys=True, data=True))


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_is_frozen_does_not_leak_across_reclaimed_ids(fnx_cls, nx_cls):
    for _ in range(10):
        frozen_graph = fnx_cls()
        fnx.freeze(frozen_graph)
        del frozen_graph

        frozen_expected = nx_cls()
        nx.freeze(frozen_expected)
        del frozen_expected

    gc.collect()

    fresh_graph = fnx_cls()
    fresh_expected = nx_cls()

    assert fnx.is_frozen(fresh_graph) == nx.is_frozen(fresh_expected) == False


def _frozen_mutation_outcome(graph, mutation_name):
    try:
        if mutation_name == "add_node":
            graph.add_node("late")
        elif mutation_name == "add_edge":
            graph.add_edge("a", "late")
        elif mutation_name == "remove_node":
            graph.remove_node("a")
        elif mutation_name == "remove_edge":
            graph.remove_edge("a", "b")
        elif mutation_name == "clear":
            graph.clear()
        elif mutation_name == "clear_edges":
            graph.clear_edges()
        else:
            raise AssertionError(f"Unknown mutation: {mutation_name}")
    except Exception as exc:
        return type(exc).__name__, str(exc)
    return None


@pytest.mark.parametrize(
    "mutation_name",
    [
        "add_node",
        "add_edge",
        "remove_node",
        "remove_edge",
        "clear",
        "clear_edges",
    ],
)
@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_freeze_mutation_errors_match_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls, mutation_name
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    fnx.freeze(graph)
    nx.freeze(expected)
    expected_is_frozen = nx.is_frozen(expected)
    expected_outcome = _frozen_mutation_outcome(expected, mutation_name)

    _block_networkx_utilities(monkeypatch, "freeze", "is_frozen")

    assert fnx.is_frozen(graph) == expected_is_frozen
    assert _frozen_mutation_outcome(graph, mutation_name) == expected_outcome


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_is_frozen_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    graph.graph["phase"] = "after"
    expected.graph["phase"] = "after"
    graph.nodes["a"]["shade"] = "scarlet"
    expected.nodes["a"]["shade"] = "scarlet"

    if graph.is_multigraph():
        graph.add_edge("c", "a", key="late", weight=11)
        expected.add_edge("c", "a", key="late", weight=11)
    else:
        graph.add_edge("c", "a", weight=11)
        expected.add_edge("c", "a", weight=11)

    assert dict(result.graph) == expected_result.graph
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_support_to_directed_as_view_like_networkx(fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.to_directed(as_view=True)
    expected_result = expected.to_directed(as_view=True)

    assert type(result).__name__ == type(expected_result).__name__
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert result.graph is graph.graph
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)

    graph.graph["phase"] = "live"
    expected.graph["phase"] = "live"
    graph.nodes["a"]["shade"] = "scarlet"
    expected.nodes["a"]["shade"] = "scarlet"
    if graph.is_multigraph():
        graph.add_edge("c", "a", key="late", weight=11)
        expected.add_edge("c", "a", key="late", weight=11)
    else:
        graph.add_edge("c", "a", weight=11)
        expected.add_edge("c", "a", weight=11)

    assert dict(result.graph) == dict(expected_result.graph)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)

    with pytest.raises(Exception) as fnx_exc:
        result.add_edge("x", "y")
    with pytest.raises(Exception) as nx_exc:
        expected_result.add_edge("x", "y")
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)

    result_explicit_copy = graph.to_directed(as_view=False)
    expected_explicit_copy = expected.to_directed(as_view=False)

    assert type(result_explicit_copy).__name__ == type(expected_explicit_copy).__name__
    assert _graph_snapshot(result_explicit_copy) == _graph_snapshot(expected_explicit_copy)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_exposes_predecessor_and_successor_queries_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    assert result.has_successor("a", "b") == expected_result.has_successor("a", "b")
    assert result.has_predecessor("b", "a") == expected_result.has_predecessor("b", "a")
    assert result.has_successor("a", "missing") == expected_result.has_successor(
        "a", "missing"
    )
    assert result.has_successor("missing", "a") == expected_result.has_successor(
        "missing", "a"
    )
    assert result.has_predecessor("a", "missing") == expected_result.has_predecessor(
        "a", "missing"
    )
    assert result.has_predecessor("missing", "a") == expected_result.has_predecessor(
        "missing", "a"
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_directed_graph_classes_expose_predecessor_and_successor_queries(
    fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    assert graph.has_successor("a", "b") == expected.has_successor("a", "b")
    assert graph.has_successor("b", "a") == expected.has_successor("b", "a")
    assert graph.has_successor("a", "missing") == expected.has_successor("a", "missing")
    assert graph.has_successor("missing", "a") == expected.has_successor("missing", "a")
    assert graph.has_predecessor("b", "a") == expected.has_predecessor("b", "a")
    assert graph.has_predecessor("a", "b") == expected.has_predecessor("a", "b")
    assert graph.has_predecessor("a", "missing") == expected.has_predecessor(
        "a", "missing"
    )
    assert graph.has_predecessor("missing", "a") == expected.has_predecessor(
        "missing", "a"
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_directed_graph_classes_expose_in_and_out_edges(fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    assert list(graph.out_edges()) == list(expected.out_edges())
    assert list(graph.out_edges(["a"], data=True)) == list(expected.out_edges(["a"], data=True))
    assert list(graph.out_edges(data="weight", default="NA")) == list(
        expected.out_edges(data="weight", default="NA")
    )

    assert list(graph.in_edges()) == list(expected.in_edges())
    assert list(graph.in_edges(["b"], data=True)) == list(expected.in_edges(["b"], data=True))
    assert list(graph.in_edges(data="weight", default="NA")) == list(
        expected.in_edges(data="weight", default="NA")
    )

    if graph.is_multigraph():
        assert list(graph.out_edges(keys=True)) == list(expected.out_edges(keys=True))
        assert list(graph.out_edges(keys=True, data=True)) == list(
            expected.out_edges(keys=True, data=True)
        )
        assert list(graph.out_edges(keys=True, data="weight", default="NA")) == list(
            expected.out_edges(keys=True, data="weight", default="NA")
        )

        assert list(graph.in_edges(keys=True)) == list(expected.in_edges(keys=True))
        assert list(graph.in_edges(keys=True, data=True)) == list(
            expected.in_edges(keys=True, data=True)
        )
        assert list(graph.in_edges(keys=True, data="weight", default="NA")) == list(
            expected.in_edges(keys=True, data="weight", default="NA")
        )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_graph_classes_edges_accept_nbunch_data_and_default_keywords(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    assert list(graph.edges(["a"], data=True)) == list(expected.edges(["a"], data=True))
    assert list(graph.edges(nbunch=["a"], data="weight", default="NA")) == list(
        expected.edges(nbunch=["a"], data="weight", default="NA")
    )
    assert list(graph.edges(["a"], data="missing", default="NA")) == list(
        expected.edges(["a"], data="missing", default="NA")
    )

    if graph.is_multigraph():
        assert list(graph.edges(["a"], keys=True, data=True)) == list(
            expected.edges(["a"], keys=True, data=True)
        )
        assert list(graph.edges(nbunch=["a"], keys=True, data="weight", default="NA")) == list(
            expected.edges(nbunch=["a"], keys=True, data="weight", default="NA")
        )


def test_multigraph_edges_support_attribute_name_data_retrieval():
    graph, expected = _view_utility_graph_pair(fnx.MultiGraph, nx.MultiGraph)

    assert list(graph.edges(data="weight")) == list(expected.edges(data="weight"))
    assert list(graph.edges(data="weight", default="NA")) == list(
        expected.edges(data="weight", default="NA")
    )
    assert list(graph.edges(["a"], data="weight", default="NA")) == list(
        expected.edges(["a"], data="weight", default="NA")
    )
    assert list(graph.edges(keys=True, data="weight", default="NA")) == list(
        expected.edges(keys=True, data="weight", default="NA")
    )
    assert list(graph.edges(["a"], keys=True, data="weight", default="NA")) == list(
        expected.edges(["a"], keys=True, data="weight", default="NA")
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_node_views_support_attribute_name_data_retrieval(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    assert list(graph.nodes(data="color")) == list(expected.nodes(data="color"))
    assert list(graph.nodes(data="color", default="gray")) == list(
        expected.nodes(data="color", default="gray")
    )
    assert list(graph.nodes("color", "gray")) == list(expected.nodes("color", "gray"))
    assert list(graph.nodes(data="missing", default="NA")) == list(
        expected.nodes(data="missing", default="NA")
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls", "missing_node"),
    [
        (fnx.Graph, nx.Graph, "missing"),
        (fnx.Graph, nx.Graph, 9),
        (fnx.MultiGraph, nx.MultiGraph, "missing"),
        (fnx.MultiGraph, nx.MultiGraph, 9),
    ],
)
def test_undirected_graph_classes_neighbors_preserve_missing_node_errors(
    fnx_cls, nx_cls, missing_node
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    try:
        expected.neighbors(missing_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)
    else:
        raise AssertionError("expected NetworkX neighbors() to fail for a missing node")

    with pytest.raises(Exception) as fnx_exc:
        graph.neighbors(missing_node)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls", "method_name", "missing_node"),
    [
        (fnx.DiGraph, nx.DiGraph, "neighbors", "missing"),
        (fnx.DiGraph, nx.DiGraph, "neighbors", 9),
        (fnx.DiGraph, nx.DiGraph, "successors", "missing"),
        (fnx.DiGraph, nx.DiGraph, "successors", 9),
        (fnx.DiGraph, nx.DiGraph, "predecessors", "missing"),
        (fnx.DiGraph, nx.DiGraph, "predecessors", 9),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "neighbors", "missing"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "neighbors", 9),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "successors", "missing"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "successors", 9),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "predecessors", "missing"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "predecessors", 9),
    ],
)
def test_directed_graph_classes_neighbors_preserve_missing_node_errors(
    fnx_cls, nx_cls, method_name, missing_node
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    try:
        getattr(expected, method_name)(missing_node)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)
    else:
        raise AssertionError(f"expected NetworkX {method_name}() to fail for a missing node")

    with pytest.raises(Exception) as fnx_exc:
        getattr(graph, method_name)(missing_node)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_expose_nbunch_iter_like_networkx(fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    assert list(graph.nbunch_iter()) == list(expected.nbunch_iter())
    assert list(graph.nbunch_iter("a")) == list(expected.nbunch_iter("a"))
    assert list(graph.nbunch_iter("missing")) == list(expected.nbunch_iter("missing"))
    assert list(graph.nbunch_iter(["a", "missing"])) == list(
        expected.nbunch_iter(["a", "missing"])
    )

    with pytest.raises(Exception) as fnx_exc:
        list(graph.nbunch_iter(9))
    with pytest.raises(Exception) as nx_exc:
        list(expected.nbunch_iter(9))
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)

    with pytest.raises(Exception) as fnx_exc:
        list(graph.nbunch_iter([[]]))
    with pytest.raises(Exception) as nx_exc:
        list(expected.nbunch_iter([[]]))
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_simple_graph_classes_support_number_of_edges_endpoint_queries(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()

    for target in (graph, expected):
        target.add_edge("a", "b")
        target.add_edge("b", "c")

    assert graph.number_of_edges() == expected.number_of_edges()
    assert graph.number_of_edges("a") == expected.number_of_edges("a")
    assert graph.number_of_edges("a", "b") == expected.number_of_edges("a", "b")
    assert graph.number_of_edges("a", "missing") == expected.number_of_edges("a", "missing")

    with pytest.raises(Exception) as fnx_exc:
        graph.number_of_edges("missing")
    with pytest.raises(Exception) as nx_exc:
        expected.number_of_edges("missing")
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_expose_class_factories_like_networkx(fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    assert graph.to_directed_class() is (
        fnx.MultiDiGraph if graph.is_multigraph() else fnx.DiGraph
    )
    assert graph.to_undirected_class() is (
        fnx.MultiGraph if graph.is_multigraph() else fnx.Graph
    )
    assert graph.to_directed_class().__name__ == expected.to_directed_class().__name__
    assert graph.to_undirected_class().__name__ == expected.to_undirected_class().__name__


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_expose_dict_factories_and_multigraph_key_helpers_like_networkx(
    fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    factory_names = [
        "adjlist_inner_dict_factory",
        "adjlist_outer_dict_factory",
        "edge_attr_dict_factory",
        "graph_attr_dict_factory",
        "node_attr_dict_factory",
        "node_dict_factory",
    ]

    for name in factory_names:
        factory = getattr(graph, name)
        expected_factory = getattr(expected, name)
        assert factory is dict
        assert factory().__class__ is dict
        assert factory.__name__ == expected_factory.__name__

    if graph.is_multigraph():
        assert graph.edge_key_dict_factory is dict
        assert graph.edge_key_dict_factory().__class__ is dict
        assert (
            graph.edge_key_dict_factory.__name__
            == expected.edge_key_dict_factory.__name__
        )
        helper_graph = fnx_cls()
        helper_expected = nx_cls()
        assert helper_graph.new_edge_key("missing", "pair") == helper_expected.new_edge_key(
            "missing", "pair"
        )

        helper_graph.add_edge("a", "b", key="k1")
        helper_expected.add_edge("a", "b", key="k1")
        assert helper_graph.new_edge_key("a", "b") == helper_expected.new_edge_key("a", "b") == 1

        helper_graph.add_edge("a", "b", key=1)
        helper_expected.add_edge("a", "b", key=1)
        assert helper_graph.new_edge_key("a", "b") == helper_expected.new_edge_key("a", "b")


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_support_copy_as_view_like_networkx(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.copy(as_view=True)
    expected_result = expected.copy(as_view=True)

    assert type(result).__name__ == type(expected_result).__name__
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert result.graph is graph.graph
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)

    graph.graph["mode"] = "live"
    expected.graph["mode"] = "live"
    graph.nodes["a"]["color"] = "purple"
    expected.nodes["a"]["color"] = "purple"
    if graph.is_multigraph():
        graph.add_edge("d", "a", key=9, weight=9)
        expected.add_edge("d", "a", key=9, weight=9)
    else:
        graph.add_edge("d", "a", weight=9)
        expected.add_edge("d", "a", weight=9)

    assert _graph_snapshot(result) == _graph_snapshot(expected_result)
    assert dict(result.graph) == dict(expected_result.graph)

    with pytest.raises(Exception) as fnx_exc:
        result.add_edge("x", "y")
    with pytest.raises(Exception) as nx_exc:
        expected_result.add_edge("x", "y")
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)

    result_copy = result.copy()
    expected_copy = expected_result.copy()

    assert type(result_copy).__name__ == type(expected_copy).__name__
    assert result_copy.is_directed() == expected_copy.is_directed()
    assert result_copy.is_multigraph() == expected_copy.is_multigraph()
    assert _graph_snapshot(result_copy) == _graph_snapshot(expected_copy)

    result_explicit_copy = graph.copy(as_view=False)
    expected_explicit_copy = expected.copy(as_view=False)

    assert type(result_explicit_copy).__name__ == type(expected_explicit_copy).__name__
    assert _graph_snapshot(result_explicit_copy) == _graph_snapshot(expected_explicit_copy)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_exposes_callable_in_and_out_degree_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    assert list(result.in_degree()) == list(expected_result.in_degree())
    assert result.in_degree("b") == expected_result.in_degree("b")
    assert result.in_degree("b", weight="weight") == expected_result.in_degree(
        "b", weight="weight"
    )
    assert list(result.in_degree(["b", "missing"])) == list(
        expected_result.in_degree(["b", "missing"])
    )
    assert list(result.in_degree("missing")) == list(expected_result.in_degree("missing"))

    assert list(result.out_degree()) == list(expected_result.out_degree())
    assert result.out_degree("a") == expected_result.out_degree("a")
    assert result.out_degree("a", weight="weight") == expected_result.out_degree(
        "a", weight="weight"
    )
    assert list(result.out_degree(["a", "missing"])) == list(
        expected_result.out_degree(["a", "missing"])
    )
    assert list(result.out_degree("missing")) == list(
        expected_result.out_degree("missing")
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_size_preserve_networkx_return_types(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    assert graph.size() == expected.size()
    assert type(graph.size()).__name__ == type(expected.size()).__name__
    assert graph.size(weight="weight") == expected.size(weight="weight")
    assert type(graph.size(weight="weight")).__name__ == type(
        expected.size(weight="weight")
    ).__name__


@pytest.mark.parametrize(
    ("builder_name", "fnx_builder", "nx_builder", "fnx_cls", "nx_cls"),
    [
        ("to_directed", fnx.to_directed, nx.to_directed, fnx.Graph, nx.Graph),
        ("to_undirected", fnx.to_undirected, nx.to_undirected, fnx.DiGraph, nx.DiGraph),
        (
            "subgraph_view",
            lambda graph: fnx.subgraph_view(graph, filter_node=lambda node: node != "d"),
            lambda graph: nx.subgraph_view(graph, filter_node=lambda node: node != "d"),
            fnx.Graph,
            nx.Graph,
        ),
        (
            "restricted_view",
            lambda graph: fnx.restricted_view(graph, [], []),
            lambda graph: nx.restricted_view(graph, [], []),
            fnx.Graph,
            nx.Graph,
        ),
    ],
)
def test_common_live_views_size_preserve_networkx_return_types(
    builder_name, fnx_builder, nx_builder, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    result = fnx_builder(graph)
    expected_result = nx_builder(expected)

    assert result.size() == expected_result.size(), builder_name
    assert type(result.size()).__name__ == type(expected_result.size()).__name__, builder_name
    assert result.size(weight="weight") == expected_result.size(weight="weight"), builder_name
    assert type(result.size(weight="weight")).__name__ == type(
        expected_result.size(weight="weight")
    ).__name__, builder_name


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_simple_graph_classes_adjacency_preserve_networkx_mapping_contract(
    fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    assert [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in graph.adjacency()
    ] == [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in expected.adjacency()
    ]


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_classes_adjacency_preserve_networkx_mapping_contract(
    fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    assert [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in graph.adjacency()
    ] == [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in expected.adjacency()
    ]


@pytest.mark.parametrize(
    ("builder_name", "fnx_builder", "nx_builder", "fnx_cls", "nx_cls"),
    [
        ("to_directed", fnx.to_directed, nx.to_directed, fnx.Graph, nx.Graph),
        ("to_directed", fnx.to_directed, nx.to_directed, fnx.MultiGraph, nx.MultiGraph),
        ("to_undirected", fnx.to_undirected, nx.to_undirected, fnx.DiGraph, nx.DiGraph),
        (
            "to_undirected",
            fnx.to_undirected,
            nx.to_undirected,
            fnx.MultiDiGraph,
            nx.MultiDiGraph,
        ),
    ],
)
def test_conversion_live_views_preserve_adjacency_mapping_contract_without_fallback(
    monkeypatch, builder_name, fnx_builder, nx_builder, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    _block_networkx_utilities(monkeypatch, "to_directed", "to_undirected")

    result = fnx_builder(graph)
    expected_result = nx_builder(expected)

    assert [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in result.adjacency()
    ] == [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in expected_result.adjacency()
    ], builder_name


@pytest.mark.parametrize(
    ("builder_name", "fnx_builder", "nx_builder", "fnx_cls", "nx_cls"),
    [
        ("to_directed", fnx.to_directed, nx.to_directed, fnx.Graph, nx.Graph),
        ("to_directed", fnx.to_directed, nx.to_directed, fnx.MultiGraph, nx.MultiGraph),
        ("to_undirected", fnx.to_undirected, nx.to_undirected, fnx.DiGraph, nx.DiGraph),
        (
            "to_undirected",
            fnx.to_undirected,
            nx.to_undirected,
            fnx.MultiDiGraph,
            nx.MultiDiGraph,
        ),
    ],
)
def test_conversion_live_views_reject_update_while_frozen_without_fallback(
    monkeypatch, builder_name, fnx_builder, nx_builder, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    _block_networkx_utilities(monkeypatch, "to_directed", "to_undirected")

    result = fnx_builder(graph)
    expected_result = nx_builder(expected)

    with pytest.raises(Exception) as fnx_exc:
        result.update([])
    with pytest.raises(Exception) as nx_exc:
        expected_result.update([])

    assert builder_name in {"to_directed", "to_undirected"}
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_conversion_live_views_expose_class_factories_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    directed_expected = nx.to_directed(expected)
    undirected_expected = nx.to_undirected(expected)

    _block_networkx_utilities(monkeypatch, "to_directed", "to_undirected")

    directed_result = fnx.to_directed(graph)
    undirected_result = fnx.to_undirected(graph)

    expected_directed_class = fnx.MultiDiGraph if graph.is_multigraph() else fnx.DiGraph
    expected_undirected_class = fnx.MultiGraph if graph.is_multigraph() else fnx.Graph

    assert directed_result.to_directed_class() is expected_directed_class
    assert directed_result.to_undirected_class() is expected_undirected_class
    assert undirected_result.to_directed_class() is expected_directed_class
    assert undirected_result.to_undirected_class() is expected_undirected_class

    assert (
        directed_result.to_directed_class().__name__
        == directed_expected.to_directed_class().__name__
    )
    assert (
        directed_result.to_undirected_class().__name__
        == directed_expected.to_undirected_class().__name__
    )
    assert (
        undirected_result.to_directed_class().__name__
        == undirected_expected.to_directed_class().__name__
    )
    assert (
        undirected_result.to_undirected_class().__name__
        == undirected_expected.to_undirected_class().__name__
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_conversion_live_views_expose_dict_factories_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    directed_expected = nx.to_directed(expected)
    undirected_expected = nx.to_undirected(expected)

    _block_networkx_utilities(monkeypatch, "to_directed", "to_undirected")

    directed_result = fnx.to_directed(graph)
    undirected_result = fnx.to_undirected(graph)

    factory_names = [
        "adjlist_inner_dict_factory",
        "adjlist_outer_dict_factory",
        "edge_attr_dict_factory",
        "graph_attr_dict_factory",
        "node_attr_dict_factory",
        "node_dict_factory",
    ]

    for name in factory_names:
        directed_factory = getattr(directed_result, name)
        undirected_factory = getattr(undirected_result, name)

        assert directed_factory is dict
        assert undirected_factory is dict
        assert directed_factory().__class__ is dict
        assert undirected_factory().__class__ is dict

        assert directed_factory.__name__ == getattr(directed_expected, name).__name__
        assert undirected_factory.__name__ == getattr(undirected_expected, name).__name__


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_directed_reverse_copy_contract_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_directed(expected)

    _block_networkx_utilities(monkeypatch, "to_directed")

    result = fnx.to_directed(graph)

    reverse_view = result.reverse(copy=False)
    reverse_copy = result.reverse(copy=True)
    expected_reverse_view = expected_result.reverse(copy=False)
    expected_reverse_copy = expected_result.reverse(copy=True)
    expected_reverse_copy_snapshot = _graph_snapshot(expected_reverse_copy)

    assert reverse_view.is_directed() == expected_reverse_view.is_directed()
    assert reverse_view.is_multigraph() == expected_reverse_view.is_multigraph()
    assert fnx.is_frozen(reverse_view) == nx.is_frozen(expected_reverse_view)
    assert _graph_snapshot(reverse_view) == _graph_snapshot(expected_reverse_view)

    assert type(reverse_copy).__name__ == type(expected_reverse_copy).__name__
    assert reverse_copy.is_directed() == expected_reverse_copy.is_directed()
    assert reverse_copy.is_multigraph() == expected_reverse_copy.is_multigraph()
    assert fnx.is_frozen(reverse_copy) == nx.is_frozen(expected_reverse_copy)
    assert _graph_snapshot(reverse_copy) == expected_reverse_copy_snapshot

    if graph.is_multigraph():
        graph.add_edge("c", "a", key="late", weight=11)
        expected.add_edge("c", "a", key="late", weight=11)
    else:
        graph.add_edge("c", "a", weight=11)
        expected.add_edge("c", "a", weight=11)

    assert _graph_snapshot(reverse_view) == _graph_snapshot(expected_reverse_view)
    assert _graph_snapshot(reverse_copy) == expected_reverse_copy_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_undirected(expected)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "to_undirected")

    result = fnx.to_undirected(graph)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_is_frozen_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_undirected(expected)

    _block_networkx_utilities(monkeypatch, "to_undirected")

    result = fnx.to_undirected(graph)

    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.to_undirected(expected)

    _block_networkx_utilities(monkeypatch, "to_undirected")

    result = fnx.to_undirected(graph)

    graph.graph["phase"] = "after"
    expected.graph["phase"] = "after"
    graph.nodes["b"]["shade"] = "violet"
    expected.nodes["b"]["shade"] = "violet"

    if graph.is_multigraph():
        graph.add_edge("c", "a", key="late", weight=11)
        expected.add_edge("c", "a", key="late", weight=11)
    else:
        graph.add_edge("c", "a", weight=11)
        expected.add_edge("c", "a", weight=11)

    assert dict(result.graph) == expected_result.graph
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_support_to_undirected_as_view_like_networkx(fnx_cls, nx_cls):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.to_undirected(as_view=True)
    expected_result = expected.to_undirected(as_view=True)

    assert type(result).__name__ == type(expected_result).__name__
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert result.graph is graph.graph
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)

    graph.graph["phase"] = "live"
    expected.graph["phase"] = "live"
    graph.nodes["a"]["shade"] = "scarlet"
    expected.nodes["a"]["shade"] = "scarlet"
    if graph.is_multigraph():
        graph.add_edge("c", "a", key="late", weight=11)
        expected.add_edge("c", "a", key="late", weight=11)
    else:
        graph.add_edge("c", "a", weight=11)
        expected.add_edge("c", "a", weight=11)

    assert dict(result.graph) == dict(expected_result.graph)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)

    with pytest.raises(Exception) as fnx_exc:
        result.add_edge("x", "y")
    with pytest.raises(Exception) as nx_exc:
        expected_result.add_edge("x", "y")
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)

    result_explicit_copy = graph.to_undirected(as_view=False)
    expected_explicit_copy = expected.to_undirected(as_view=False)

    assert type(result_explicit_copy).__name__ == type(expected_explicit_copy).__name__
    assert _graph_snapshot(result_explicit_copy) == _graph_snapshot(expected_explicit_copy)

    if not graph.is_directed():
        with pytest.raises(Exception) as fnx_reciprocal_exc:
            graph.to_undirected(reciprocal=False)
        with pytest.raises(Exception) as nx_reciprocal_exc:
            expected.to_undirected(reciprocal=False)
        assert type(fnx_reciprocal_exc.value).__name__ == type(
            nx_reciprocal_exc.value
        ).__name__
        assert str(fnx_reciprocal_exc.value) == str(nx_reciprocal_exc.value)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_directed_graph_classes_support_to_undirected_reciprocal_keyword_like_networkx(
    fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    graph.graph["name"] = "reciprocal"
    expected.graph["name"] = "reciprocal"
    for node, color in [("a", "red"), ("b", "blue"), ("c", "green")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)

    if graph.is_multigraph():
        graph.add_edge("a", "b", key="shared", weight="ab")
        graph.add_edge("b", "a", key="shared", weight="ba")
        graph.add_edge("a", "b", key="solo", weight="solo")
        graph.add_edge("b", "c", key="tail", weight="tail")
        expected.add_edge("a", "b", key="shared", weight="ab")
        expected.add_edge("b", "a", key="shared", weight="ba")
        expected.add_edge("a", "b", key="solo", weight="solo")
        expected.add_edge("b", "c", key="tail", weight="tail")
    else:
        graph.add_edge("a", "b", weight="ab")
        graph.add_edge("b", "a", weight="ba")
        graph.add_edge("b", "c", weight="tail")
        expected.add_edge("a", "b", weight="ab")
        expected.add_edge("b", "a", weight="ba")
        expected.add_edge("b", "c", weight="tail")

    result_default = graph.to_undirected(reciprocal=False)
    expected_default = expected.to_undirected(reciprocal=False)
    assert type(result_default).__name__ == type(expected_default).__name__
    assert _graph_snapshot(result_default) == _graph_snapshot(expected_default)

    result_reciprocal = graph.to_undirected(reciprocal=True)
    expected_reciprocal = expected.to_undirected(reciprocal=True)
    assert type(result_reciprocal).__name__ == type(expected_reciprocal).__name__
    assert _graph_snapshot(result_reciprocal) == _graph_snapshot(expected_reciprocal)

    result_view = graph.to_undirected(reciprocal=True, as_view=True)
    expected_view = expected.to_undirected(reciprocal=True, as_view=True)
    assert type(result_view).__name__ == type(expected_view).__name__
    assert result_view.graph is graph.graph
    assert _graph_snapshot(result_view) == _graph_snapshot(expected_view)
    assert fnx.is_frozen(result_view) == nx.is_frozen(expected_view)
    assert _graph_snapshot(result_view) != _graph_snapshot(result_reciprocal)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_reciprocal_edge_attrs_match_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_node("a")
    graph.add_node("b")
    expected.add_node("a")
    expected.add_node("b")

    if graph.is_multigraph():
        graph.add_edge("b", "a", key="shared", weight="ba")
        graph.add_edge("a", "b", key="shared", weight="ab")
        expected.add_edge("b", "a", key="shared", weight="ba")
        expected.add_edge("a", "b", key="shared", weight="ab")
    else:
        graph.add_edge("b", "a", weight="ba")
        graph.add_edge("a", "b", weight="ab")
        expected.add_edge("b", "a", weight="ba")
        expected.add_edge("a", "b", weight="ab")

    expected_result = nx.to_undirected(expected)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "to_undirected")

    result = fnx.to_undirected(graph)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("view_fnx", "view_nx", "fnx_cls", "nx_cls", "networkx_name"),
    [
        (fnx.to_directed, nx.to_directed, fnx.Graph, nx.Graph, "to_directed"),
        (fnx.to_directed, nx.to_directed, fnx.MultiGraph, nx.MultiGraph, "to_directed"),
        (fnx.to_undirected, nx.to_undirected, fnx.DiGraph, nx.DiGraph, "to_undirected"),
        (
            fnx.to_undirected,
            nx.to_undirected,
            fnx.MultiDiGraph,
            nx.MultiDiGraph,
            "to_undirected",
        ),
    ],
)
def test_conversion_live_views_expose_callable_degree_without_fallback(
    monkeypatch, view_fnx, view_nx, fnx_cls, nx_cls, networkx_name
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = view_nx(expected)

    _block_networkx_utilities(monkeypatch, networkx_name)

    result = view_fnx(graph)

    assert list(result.degree()) == list(expected_result.degree())
    assert result.degree("b") == expected_result.degree("b")
    assert result.degree("b", weight="weight") == expected_result.degree(
        "b", weight="weight"
    )
    assert list(result.degree(["b", "missing"])) == list(
        expected_result.degree(["b", "missing"])
    )
    assert list(result.degree("missing")) == list(expected_result.degree("missing"))


def test_reverse_helper_matches_networkx():
    digraph = fnx.MultiDiGraph()
    digraph.graph["kind"] = "digraph"
    digraph.add_edge("u", "v", key=9, capacity=4)

    expected = nx.MultiDiGraph()
    expected.graph["kind"] = "digraph"
    expected.add_edge("u", "v", key=9, capacity=4)

    reversed_graph = fnx.reverse(digraph)
    reversed_nx = nx.reverse(expected)
    assert dict(reversed_graph.graph) == reversed_nx.graph
    assert sorted(reversed_graph.edges(keys=True, data=True)) == sorted(reversed_nx.edges(keys=True, data=True))


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_reverse_undirected_error_matches_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)

    try:
        nx.reverse(expected)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, "reverse")

    with pytest.raises(Exception) as fnx_exc:
        fnx.reverse(graph)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
@pytest.mark.parametrize("copy", [False, True])
def test_reverse_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls, copy):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse(expected, copy=copy)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "reverse")

    result = fnx.reverse(graph, copy=copy)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_copy_false_is_frozen_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _direction_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse(expected, copy=False)

    _block_networkx_utilities(monkeypatch, "reverse")

    result = fnx.reverse(graph, copy=False)

    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_copy_false_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    if graph.is_multigraph():
        graph.add_edge("a", "b", key="k", weight=1)
        expected.add_edge("a", "b", key="k", weight=1)
    else:
        graph.add_edge("a", "b", weight=1)
        expected.add_edge("a", "b", weight=1)

    expected_result = nx.reverse(expected, copy=False)

    _block_networkx_utilities(monkeypatch, "reverse")

    result = fnx.reverse(graph, copy=False)

    if graph.is_multigraph():
        graph.add_edge("c", "a", key="j", weight=2)
        expected.add_edge("c", "a", key="j", weight=2)
    else:
        graph.add_edge("c", "a", weight=2)
        expected.add_edge("c", "a", weight=2)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize("utility_name", ["subgraph", "induced_subgraph"])
@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_induced_subgraph_helpers_match_networkx_without_fallback(
    monkeypatch, utility_name, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = getattr(nx, utility_name)(expected, ["a", "b", "c"])
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, utility_name)

    result = getattr(fnx, utility_name)(graph, ["a", "b", "c"])

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize("utility_name", ["subgraph", "induced_subgraph"])
@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_induced_subgraph_helpers_track_mutations_like_networkx_without_fallback(
    monkeypatch, utility_name, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = getattr(nx, utility_name)(expected, ["a", "b", "c"])

    _block_networkx_utilities(monkeypatch, utility_name)

    result = getattr(fnx, utility_name)(graph, ["a", "b", "c"])

    if graph.is_multigraph():
        graph.add_edge("a", "c", key=7, weight=9)
        expected.add_edge("a", "c", key=7, weight=9)
    else:
        graph.add_edge("a", "c", weight=9)
        expected.add_edge("a", "c", weight=9)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_subgraph_tracks_graph_attr_mutations_like_networkx(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    graph.graph["mode"] = "orig"
    expected.graph["mode"] = "orig"

    result = graph.subgraph(["a", "b", "c"])
    expected_result = expected.subgraph(["a", "b", "c"])

    assert type(result).__name__ == type(expected_result).__name__
    assert dict(result.graph) == dict(expected_result.graph)
    assert result.graph is graph.graph

    graph.graph["mode"] = "updated"
    expected.graph["mode"] = "updated"

    assert dict(result.graph) == dict(expected_result.graph)
    assert result.graph["mode"] == "updated"
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_subgraph_tracks_node_attr_mutations_like_networkx(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.subgraph(["a", "b", "c"])
    expected_result = expected.subgraph(["a", "b", "c"])

    assert type(result.nodes).__name__ == type(expected_result.nodes).__name__

    graph.nodes["a"]["color"] = "black"
    expected.nodes["a"]["color"] = "black"
    graph.nodes["b"]["score"] = 7
    expected.nodes["b"]["score"] = 7

    assert dict(result.nodes["a"]) == dict(expected_result.nodes["a"])
    assert dict(result.nodes["b"]) == dict(expected_result.nodes["b"])
    assert list(result.nodes(data=True)) == list(expected_result.nodes(data=True))
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_subgraph_tracks_parent_node_removals_like_networkx(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.subgraph(["a", "b", "c"])
    expected_result = expected.subgraph(["a", "b", "c"])

    graph.remove_node("a")
    expected.remove_node("a")

    assert "a" not in result
    assert "a" not in expected_result
    assert result.has_node("a") == expected_result.has_node("a")
    assert list(result.nodes(data=True)) == list(expected_result.nodes(data=True))
    assert result.number_of_nodes() == expected_result.number_of_nodes()
    assert result.number_of_edges() == expected_result.number_of_edges()
    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_classes_subgraph_tracks_edge_mutations_like_networkx(fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)

    result = graph.subgraph(["a", "b", "c"])
    expected_result = expected.subgraph(["a", "b", "c"])

    if graph.is_multigraph():
        graph["a"]["b"][1]["weight"] = 9
        expected["a"]["b"][1]["weight"] = 9
        graph.add_edge("a", "c", key=7, weight=11)
        expected.add_edge("a", "c", key=7, weight=11)
    else:
        graph["a"]["b"]["weight"] = 9
        expected["a"]["b"]["weight"] = 9
        graph.add_edge("a", "c", weight=11)
        expected.add_edge("a", "c", weight=11)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert fnx.is_frozen(result) == nx.is_frozen(expected_result)
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize("utility_name", ["subgraph", "induced_subgraph"])
def test_induced_subgraph_helpers_missing_node_error_match_networkx_without_fallback(
    monkeypatch, utility_name
):
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    try:
        getattr(nx, utility_name)(expected, 9)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    _block_networkx_utilities(monkeypatch, utility_name)

    with pytest.raises(Exception) as fnx_exc:
        getattr(fnx, utility_name)(graph, 9)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_edge_subgraph_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    if graph.is_multigraph():
        selected_edges = [("a", "b", 1), ("b", "c", 1)]
    else:
        selected_edges = [("a", "b"), ("b", "c")]
    expected_result = nx.edge_subgraph(expected, selected_edges)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "edge_subgraph")

    result = fnx.edge_subgraph(graph, selected_edges)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edge_subgraph_requires_keyed_edge_tuples(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.add_edge("a", "b", key="k1", weight=1)
    expected.add_edge("a", "b", key="k1", weight=1)

    with pytest.raises(Exception) as fnx_exc:
        graph.edge_subgraph([("a", "b")])
    with pytest.raises(Exception) as nx_exc:
        expected.edge_subgraph([("a", "b")])

    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_edge_subgraph_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    for node, color in [("a", "red"), ("b", "blue"), ("c", "green")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)

    if graph.is_multigraph():
        selected_edges = [("a", "c", 7)]
        expected_result = nx.edge_subgraph(expected, selected_edges)
        result_builder = lambda target: target.add_edge("a", "c", key=7, weight=9)
        edge_snapshot = lambda g: sorted(g.edges(keys=True, data=True))
    else:
        selected_edges = [("a", "c")]
        expected_result = nx.edge_subgraph(expected, selected_edges)
        result_builder = lambda target: target.add_edge("a", "c", weight=9)
        edge_snapshot = lambda g: sorted(g.edges(data=True))

    _block_networkx_utilities(monkeypatch, "edge_subgraph")

    result = fnx.edge_subgraph(graph, selected_edges)

    graph.nodes["a"]["color"] = "black"
    expected.nodes["a"]["color"] = "black"
    result_builder(graph)
    result_builder(expected)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert sorted(result.nodes(data=True)) == sorted(expected_result.nodes(data=True))
    assert edge_snapshot(result) == edge_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_subgraph_view_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    filter_node = lambda node: node != "d"
    if graph.is_multigraph():
        filter_edge = lambda u, v, key: key != 2 and (u, v) != ("b", "c")
    else:
        filter_edge = lambda u, v: (u, v) != ("b", "c")
    expected_result = nx.subgraph_view(
        expected,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "subgraph_view")

    result = fnx.subgraph_view(
        graph,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_subgraph_view_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    filter_node = lambda node: node != "d"
    if graph.is_multigraph():
        filter_edge = lambda u, v, key: key != 2 and (u, v) != ("b", "c")
        add_edge = lambda target: target.add_edge("a", "c", key=7, weight=9)
    else:
        filter_edge = lambda u, v: (u, v) != ("b", "c")
        add_edge = lambda target: target.add_edge("a", "c", weight=9)

    expected_result = nx.subgraph_view(
        expected,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )

    _block_networkx_utilities(monkeypatch, "subgraph_view")

    result = fnx.subgraph_view(
        graph,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )

    add_edge(graph)
    add_edge(expected)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph = fnx_cls()
    expected = nx_cls()
    if graph.is_multigraph():
        graph.add_edge("a", "b", key="k", weight=1)
        expected.add_edge("a", "b", key="k", weight=1)
    else:
        graph.add_edge("a", "b", weight=1)
        expected.add_edge("a", "b", weight=1)

    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    if graph.is_multigraph():
        graph.add_edge("c", "a", key="j", weight=2)
        expected.add_edge("c", "a", key="j", weight=2)
    else:
        graph.add_edge("c", "a", weight=2)
        expected.add_edge("c", "a", weight=2)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_restricted_view_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    if graph.is_multigraph():
        edges_to_remove = [("a", "b", 2)]
    else:
        edges_to_remove = [("b", "c")]
    expected_result = nx.restricted_view(expected, ["d"], edges_to_remove)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "restricted_view")

    result = fnx.restricted_view(graph, ["d"], edges_to_remove)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_restricted_view_tracks_mutations_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    if graph.is_multigraph():
        edges_to_remove = [("a", "b", 2)]
        add_edge = lambda target: target.add_edge("a", "c", key=7, weight=9)
    else:
        edges_to_remove = [("b", "c")]
        add_edge = lambda target: target.add_edge("a", "c", weight=9)

    expected_result = nx.restricted_view(expected, ["d"], edges_to_remove)

    _block_networkx_utilities(monkeypatch, "restricted_view")

    result = fnx.restricted_view(graph, ["d"], edges_to_remove)

    add_edge(graph)
    add_edge(expected)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_matches_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)
    expected_snapshot = _graph_snapshot(expected_result)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert _graph_snapshot(result) == expected_snapshot


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_succ_and_pred_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert _mapping_snapshot(result.succ) == _mapping_snapshot(expected_result.succ)
    assert _mapping_snapshot(result.pred) == _mapping_snapshot(expected_result.pred)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_class_factories_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)
    expected_directed_class = fnx.MultiDiGraph if graph.is_multigraph() else fnx.DiGraph
    expected_undirected_class = fnx.MultiGraph if graph.is_multigraph() else fnx.Graph

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert result.to_directed_class() is expected_directed_class
    assert result.to_undirected_class() is expected_undirected_class
    assert result.to_directed_class().__name__ == expected_result.to_directed_class().__name__
    assert (
        result.to_undirected_class().__name__
        == expected_result.to_undirected_class().__name__
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_dict_factories_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    factory_names = [
        "adjlist_inner_dict_factory",
        "adjlist_outer_dict_factory",
        "edge_attr_dict_factory",
        "graph_attr_dict_factory",
        "node_attr_dict_factory",
        "node_dict_factory",
    ]

    for name in factory_names:
        factory = getattr(result, name)
        expected_factory = getattr(expected_result, name)
        assert factory is dict
        assert factory().__class__ is dict
        assert factory.__name__ == expected_factory.__name__


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_query_helpers_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert result.has_node("a") == expected_result.has_node("a")
    assert result.has_node("z") == expected_result.has_node("z")
    assert result.get_edge_data("b", "a") == expected_result.get_edge_data("b", "a")
    assert result.get_edge_data("a", "b") == expected_result.get_edge_data("a", "b")

    if graph.is_multigraph():
        assert result.get_edge_data("b", "a", key=1) == expected_result.get_edge_data(
            "b", "a", key=1
        )
        assert result.get_edge_data("a", "b", key=99, default="missing") == (
            expected_result.get_edge_data("a", "b", key=99, default="missing")
        )
    else:
        assert result.get_edge_data("a", "b", default="missing") == expected_result.get_edge_data(
            "a", "b", default="missing"
        )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_size_helpers_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert result.number_of_nodes() == expected_result.number_of_nodes()
    assert result.order() == expected_result.order()
    assert result.size() == expected_result.size()
    assert type(result.size()).__name__ == type(expected_result.size()).__name__
    assert result.size(weight="weight") == expected_result.size(weight="weight")
    assert type(result.size(weight="weight")).__name__ == type(
        expected_result.size(weight="weight")
    ).__name__


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_adjacency_iteration_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert [
        (node, _mapping_snapshot(neighbors)) for node, neighbors in result.adjacency()
    ] == [
        (node, _mapping_snapshot(neighbors))
        for node, neighbors in expected_result.adjacency()
    ]


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_exposes_edge_and_degree_apis_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)

    assert list(result.out_edges()) == list(expected_result.out_edges())
    assert list(result.out_edges(["b"], data=True)) == list(
        expected_result.out_edges(["b"], data=True)
    )
    assert list(result.in_edges(data=True)) == list(expected_result.in_edges(data=True))
    assert list(result.in_edges(["b"], data=True)) == list(
        expected_result.in_edges(["b"], data=True)
    )
    if graph.is_multigraph():
        assert list(result.out_edges(keys=True, data=True)) == list(
            expected_result.out_edges(keys=True, data=True)
        )
        assert list(result.in_edges(keys=True, data=True)) == list(
            expected_result.in_edges(keys=True, data=True)
        )

    assert list(result.degree()) == list(expected_result.degree())
    assert result.degree("b") == expected_result.degree("b")
    assert result.degree("b", weight="weight") == expected_result.degree(
        "b", weight="weight"
    )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_supports_subgraph_and_copy_like_networkx_without_fallback(
    monkeypatch, fnx_cls, nx_cls
):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    expected_result = nx.reverse_view(expected)

    _block_networkx_utilities(monkeypatch, "reverse_view")

    result = fnx.reverse_view(graph)
    result_subgraph = result.subgraph(["a", "b", "z"])
    expected_subgraph = expected_result.subgraph(["a", "b", "z"])

    assert result_subgraph.is_directed() == expected_subgraph.is_directed()
    assert result_subgraph.is_multigraph() == expected_subgraph.is_multigraph()
    assert _graph_snapshot(result_subgraph) == _graph_snapshot(expected_subgraph)

    if graph.is_multigraph():
        graph.add_edge("b", "a", key=7, weight=5)
        expected.add_edge("b", "a", key=7, weight=5)
    else:
        graph.add_edge("b", "a", weight=5)
        expected.add_edge("b", "a", weight=5)

    assert _graph_snapshot(result_subgraph) == _graph_snapshot(expected_subgraph)

    result_copy = result.copy()
    expected_copy = expected_result.copy()

    assert type(result_copy).__name__ == type(expected_copy).__name__
    assert result_copy.is_directed() == expected_copy.is_directed()
    assert result_copy.is_multigraph() == expected_copy.is_multigraph()
    assert _graph_snapshot(result_copy) == _graph_snapshot(expected_copy)

    result_subgraph_copy = result_subgraph.copy()
    expected_subgraph_copy = expected_subgraph.copy()

    assert type(result_subgraph_copy).__name__ == type(expected_subgraph_copy).__name__
    assert result_subgraph_copy.is_directed() == expected_subgraph_copy.is_directed()
    assert result_subgraph_copy.is_multigraph() == expected_subgraph_copy.is_multigraph()
    assert _graph_snapshot(result_subgraph_copy) == _graph_snapshot(expected_subgraph_copy)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_supports_edge_subgraph_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph, expected = _view_utility_graph_pair(fnx_cls, nx_cls)
    if graph.is_multigraph():
        selected_edges = [("b", "a", 1)]
    else:
        selected_edges = [("b", "a")]
    expected_result = nx.reverse_view(expected).edge_subgraph(selected_edges)

    _block_networkx_utilities(monkeypatch, "reverse_view", "edge_subgraph")

    result = fnx.reverse_view(graph).edge_subgraph(selected_edges)

    assert result.is_directed() == expected_result.is_directed()
    assert result.is_multigraph() == expected_result.is_multigraph()
    assert result.frozen == expected_result.frozen
    assert _graph_snapshot(result) == _graph_snapshot(expected_result)
