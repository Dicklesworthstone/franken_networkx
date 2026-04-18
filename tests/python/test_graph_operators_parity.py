import itertools

import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _edge_records(G):
    def normalize_endpoints(u, v):
        if G.is_directed():
            return u, v
        return tuple(sorted((u, v)))

    if G.is_multigraph():
        return sorted(
            (
                *normalize_endpoints(u, v),
                key,
                data,
            )
            for u, v, key, data in G.edges(keys=True, data=True)
        )
    return sorted(
        (
            *normalize_endpoints(u, v),
            data,
        )
        for u, v, data in G.edges(data=True)
    )


def _normalize_attrs(attrs):
    return tuple(sorted((repr(key), repr(value)) for key, value in dict(attrs).items()))


def _graph_signature(G):
    return (
        tuple(sorted((repr(key), repr(value)) for key, value in dict(G.graph).items())),
        sorted((repr(node), _normalize_attrs(data)) for node, data in G.nodes(data=True)),
        sorted(
            tuple(repr(part) for part in edge[:-1]) + (_normalize_attrs(edge[-1]),)
            for edge in _edge_records(G)
        ),
    )


def _operator_graph_pair(fnx_cls, nx_cls):
    left = fnx_cls()
    right = fnx_cls()
    left_nx = nx_cls()
    right_nx = nx_cls()
    for graph, side in [(left, "left"), (left_nx, "left")]:
        graph.graph["side"] = side
        graph.add_node("a", color="red")
        graph.add_node("b")
        graph.add_node("c")
        if graph.is_multigraph():
            graph.add_edge("a", "b", key=1, weight=1)
            graph.add_edge("a", "b", key=2, weight=2)
            graph.add_edge("b", "c", key=1, weight=3)
        else:
            graph.add_edge("a", "b", weight=1)
            graph.add_edge("b", "c", weight=3)
    for graph, side in [(right, "right"), (right_nx, "right")]:
        graph.graph["side"] = side
        graph.add_node("a", size=1)
        graph.add_node("b")
        graph.add_node("d")
        if graph.is_multigraph():
            graph.add_edge("a", "b", key=1, cost=4)
            graph.add_edge("a", "b", key=3, cost=5)
            graph.add_edge("b", "d", key=1, cost=6)
        else:
            graph.add_edge("a", "b", cost=4)
            graph.add_edge("b", "d", cost=6)
    return left, right, left_nx, right_nx


def _block_networkx_operators(monkeypatch, *names):
    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX graph operator fallback should not be used")

    for name in names:
        monkeypatch.setattr(nx, name, fail_networkx)


def test_line_graph_matches_networkx_for_simple_path_without_fallback(monkeypatch):
    graph = fnx.path_graph(4)
    expected = nx.line_graph(nx.path_graph(4))

    _block_networkx_operators(monkeypatch, "line_graph")
    result = fnx.line_graph(graph)

    assert type(result).__name__ == type(expected).__name__
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_line_graph_matches_networkx_for_multigraph_and_create_using_without_fallback(monkeypatch):
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=5, capacity=2)
    graph.add_edge("b", "c", key=9, capacity=3)

    expected_input = nx.MultiGraph()
    expected_input.add_edge("a", "b", key=5, capacity=2)
    expected_input.add_edge("b", "c", key=9, capacity=3)
    expected = nx.line_graph(expected_input, create_using=nx.MultiGraph())

    _block_networkx_operators(monkeypatch, "line_graph")
    result = fnx.line_graph(graph, create_using=fnx.MultiGraph())

    assert result.is_multigraph()
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_power_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.cycle_graph(5)
    expected = nx.power(nx.cycle_graph(5), 2)

    _block_networkx_operators(monkeypatch, "power")
    result = fnx.power(graph, 2)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert sorted(result.edges(data=True)) == sorted(expected.edges(data=True))


def test_power_validation_matches_networkx_without_fallback(monkeypatch):
    expected_fractional = nx.power(nx.path_graph(4), 1.5)
    expected_errors = []
    for k in (0, -1, "2", None):
        try:
            nx.power(nx.path_graph(4), k)
        except Exception as exc:
            expected_errors.append((k, type(exc).__name__, str(exc)))

    _block_networkx_operators(monkeypatch, "power")

    fractional_result = fnx.power(fnx.path_graph(4), 1.5)
    assert _graph_signature(fractional_result) == _graph_signature(expected_fractional)

    for k, expected_type, expected_message in expected_errors:
        with pytest.raises(Exception) as fnx_exc:
            fnx.power(fnx.path_graph(4), k)
        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


def test_power_rejects_unsupported_graph_types_before_k_validation(monkeypatch):
    cases = (
        (fnx.DiGraph, nx.DiGraph, 0),
        (fnx.DiGraph, nx.DiGraph, "2"),
        (fnx.MultiGraph, nx.MultiGraph, 0),
        (fnx.MultiGraph, nx.MultiGraph, 1.5),
        (fnx.MultiDiGraph, nx.MultiDiGraph, -1),
    )

    expected_errors = []
    for fnx_cls, nx_cls, k in cases:
        graph_nx = nx_cls()
        if graph_nx.is_multigraph():
            graph_nx.add_edge("a", "b", key=1)
        else:
            graph_nx.add_edge("a", "b")
        try:
            nx.power(graph_nx, k)
        except Exception as exc:
            expected_errors.append((fnx_cls, k, type(exc).__name__, str(exc)))

    _block_networkx_operators(monkeypatch, "power")

    for fnx_cls, k, expected_type, expected_message in expected_errors:
        graph = fnx_cls()
        if graph.is_multigraph():
            graph.add_edge("a", "b", key=1)
        else:
            graph.add_edge("a", "b")
        with pytest.raises(Exception) as fnx_exc:
            fnx.power(graph, k)
        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


def test_stochastic_graph_matches_networkx_copy_and_in_place_without_fallback(monkeypatch):
    graph = fnx.MultiDiGraph()
    graph.graph["name"] = "weighted"
    graph.add_node("z", color="blue")
    graph.add_edge("a", "b", key=1, w=2.0)
    graph.add_edge("a", "c", key=4, w=6.0)
    graph.add_edge("b", "c", key=7)

    expected_input = nx.MultiDiGraph()
    expected_input.graph["name"] = "weighted"
    expected_input.add_node("z", color="blue")
    expected_input.add_edge("a", "b", key=1, w=2.0)
    expected_input.add_edge("a", "c", key=4, w=6.0)
    expected_input.add_edge("b", "c", key=7)
    expected_copy = nx.stochastic_graph(expected_input, copy=True, weight="w")

    inplace_graph = fnx.MultiDiGraph()
    inplace_graph.graph["name"] = "weighted"
    inplace_graph.add_edge("a", "b", key=1, w=2.0)
    inplace_graph.add_edge("a", "c", key=4, w=6.0)
    inplace_graph.add_edge("b", "c", key=7)

    expected_inplace = nx.MultiDiGraph()
    expected_inplace.graph["name"] = "weighted"
    expected_inplace.add_edge("a", "b", key=1, w=2.0)
    expected_inplace.add_edge("a", "c", key=4, w=6.0)
    expected_inplace.add_edge("b", "c", key=7)
    expected_same_object = nx.stochastic_graph(expected_inplace, copy=False, weight="w")

    _block_networkx_operators(monkeypatch, "stochastic_graph")
    copy_result = fnx.stochastic_graph(graph, copy=True, weight="w")
    same_object = fnx.stochastic_graph(inplace_graph, copy=False, weight="w")

    assert copy_result is not graph
    assert dict(copy_result.graph) == expected_copy.graph
    assert sorted(copy_result.nodes(data=True)) == sorted(expected_copy.nodes(data=True))
    assert _edge_records(copy_result) == _edge_records(expected_copy)
    assert same_object is inplace_graph
    assert _edge_records(same_object) == _edge_records(expected_same_object)


def test_disjoint_union_matches_networkx_for_multigraphs():
    left = fnx.MultiGraph()
    left.graph["side"] = "left"
    left.add_node("a", color="red")
    left.add_edge("a", "b", key=7, weight=2)

    right = fnx.MultiGraph()
    right.graph["side"] = "right"
    right.add_node("x", size=3)
    right.add_edge("x", "y", key=11, weight=5)

    result = fnx.disjoint_union(left, right)

    expected_left = nx.MultiGraph()
    expected_left.graph["side"] = "left"
    expected_left.add_node("a", color="red")
    expected_left.add_edge("a", "b", key=7, weight=2)
    expected_right = nx.MultiGraph()
    expected_right.graph["side"] = "right"
    expected_right.add_node("x", size=3)
    expected_right.add_edge("x", "y", key=11, weight=5)
    expected = nx.disjoint_union(expected_left, expected_right)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_disjoint_union_all_matches_networkx_and_rejects_mixed_types():
    graphs = [fnx.path_graph(3), fnx.path_graph(2), fnx.empty_graph(1)]
    expected_graphs = [nx.path_graph(3), nx.path_graph(2), nx.empty_graph(1)]

    result = fnx.disjoint_union_all(graphs)
    expected = nx.disjoint_union_all(expected_graphs)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert sorted(result.edges(data=True)) == sorted(expected.edges(data=True))

    with pytest.raises(fnx.NetworkXError, match="All graphs must be directed or undirected."):
        fnx.disjoint_union_all([fnx.Graph(), fnx.DiGraph()])


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_graph_operator_batches_match_networkx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    left, right, left_nx, right_nx = _operator_graph_pair(fnx_cls, nx_cls)
    expected = {
        "compose_all": nx.compose_all([left_nx, right_nx]),
        "union_all": nx.union_all([left_nx, right_nx], rename=("L-", "R-")),
        "intersection_all": nx.intersection_all([left_nx, right_nx]),
        "disjoint_union": nx.disjoint_union(left_nx, right_nx),
        "disjoint_union_all": nx.disjoint_union_all([left_nx, right_nx]),
    }
    expected_signatures = {name: _graph_signature(graph) for name, graph in expected.items()}

    _block_networkx_operators(
        monkeypatch,
        "compose_all",
        "union_all",
        "intersection_all",
        "disjoint_union",
        "disjoint_union_all",
    )

    actual = {
        "compose_all": fnx.compose_all([left, right]),
        "union_all": fnx.union_all([left, right], rename=("L-", "R-")),
        "intersection_all": fnx.intersection_all([left, right]),
        "disjoint_union": fnx.disjoint_union(left, right),
        "disjoint_union_all": fnx.disjoint_union_all([left, right]),
    }

    assert {name: _graph_signature(graph) for name, graph in actual.items()} == expected_signatures


def test_union_all_rename_iterables_match_networkx_without_fallback(monkeypatch):
    def build_graphs(lib):
        left = lib.Graph()
        left.graph["label"] = "left"
        left.add_node("a", color="red")
        left.add_node("b")
        left.add_edge("a", "b", weight=1)

        right = lib.Graph()
        right.graph["label"] = "right"
        right.add_node("a", color="blue")
        right.add_node("b")
        right.add_edge("a", "b", weight=2)
        return [left, right]

    rename_factories = (
        lambda: ("L-",),
        lambda: iter(["L-"]),
        lambda: (f"{index}-" for index in itertools.count()),
    )

    expected = []
    for make_rename in rename_factories:
        expected.append(
            _graph_signature(nx.union_all(build_graphs(nx), rename=make_rename()))
        )

    _block_networkx_operators(monkeypatch, "union_all")

    actual = []
    for make_rename in rename_factories:
        actual.append(
            _graph_signature(fnx.union_all(build_graphs(fnx), rename=make_rename()))
        )

    assert actual == expected


def test_graph_operator_empty_errors_without_fallback(monkeypatch):
    _block_networkx_operators(
        monkeypatch,
        "compose_all",
        "union_all",
        "intersection_all",
        "disjoint_union_all",
    )

    for operator in (fnx.compose_all, fnx.union_all, fnx.intersection_all, fnx.disjoint_union_all):
        with pytest.raises(ValueError):
            operator([])


@pytest.mark.parametrize("operator_name", ["compose_all", "union_all"])
def test_graph_operator_batch_validation_matches_networkx_without_fallback(
    monkeypatch, operator_name
):
    cases = (
        ((fnx.Graph, fnx.DiGraph), (nx.Graph, nx.DiGraph)),
        ((fnx.Graph, fnx.MultiGraph), (nx.Graph, nx.MultiGraph)),
        ((fnx.MultiGraph, fnx.DiGraph), (nx.MultiGraph, nx.DiGraph)),
        ((fnx.DiGraph, fnx.MultiDiGraph), (nx.DiGraph, nx.MultiDiGraph)),
    )

    expected_errors = []
    operator_nx = getattr(nx, operator_name)
    for (fnx_left_cls, fnx_right_cls), (nx_left_cls, nx_right_cls) in cases:
        left_nx = nx_left_cls()
        right_nx = nx_right_cls()
        if left_nx.is_multigraph():
            left_nx.add_edge("a", "b", key=1)
        else:
            left_nx.add_edge("a", "b")
        if right_nx.is_multigraph():
            right_nx.add_edge("c", "d", key=1)
        else:
            right_nx.add_edge("c", "d")
        try:
            if operator_name == "union_all":
                operator_nx([left_nx, right_nx], rename=("L-", "R-"))
            else:
                operator_nx([left_nx, right_nx])
        except Exception as exc:
            expected_errors.append(((fnx_left_cls, fnx_right_cls), type(exc).__name__, str(exc)))

    _block_networkx_operators(monkeypatch, operator_name)

    operator_fnx = getattr(fnx, operator_name)
    for (fnx_left_cls, fnx_right_cls), expected_type, expected_message in expected_errors:
        left = fnx_left_cls()
        right = fnx_right_cls()
        if left.is_multigraph():
            left.add_edge("a", "b", key=1)
        else:
            left.add_edge("a", "b")
        if right.is_multigraph():
            right.add_edge("c", "d", key=1)
        else:
            right.add_edge("c", "d")

        with pytest.raises(Exception) as fnx_exc:
            if operator_name == "union_all":
                operator_fnx([left, right], rename=("L-", "R-"))
            else:
                operator_fnx([left, right])

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


def test_make_max_clique_graph_create_using_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

    expected_input = nx.Graph()
    expected_input.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    expected = nx.make_max_clique_graph(expected_input, create_using=nx.MultiGraph())

    _block_networkx_operators(monkeypatch, "make_max_clique_graph")
    result = fnx.make_max_clique_graph(graph, create_using=fnx.MultiGraph())

    assert result.is_multigraph()
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)
