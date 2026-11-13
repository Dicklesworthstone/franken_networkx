"""Backend access to connectivity decomposition, cuts and augmentation."""

import inspect

import franken_networkx as fnx
import franken_networkx.backend as fnx_backend
import networkx as nx
import pytest


_QUERIES = (
    ("is_k_edge_connected", {"k": 2}),
    ("k_edge_components", {"k": 2}),
    ("k_edge_subgraphs", {"k": 2}),
    ("k_edge_augmentation", {"k": 2}),
    ("k_components", {}),
    ("all_node_cuts", {}),
)


def _graph(shape):
    if shape == "cycle":
        return nx.cycle_graph(6)
    if shape == "path":
        return nx.path_graph(6)
    graph = nx.Graph()
    graph.add_nodes_from(range(9))
    graph.add_edges_from(nx.complete_graph(4).edges())
    graph.add_edges_from((u + 4, v + 4) for u, v in nx.complete_graph(4).edges())
    graph.add_edges_from([(3, 4), (4, 8)])
    return graph


def _warm(graph):
    nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _input(graph, route):
    if route == "native":
        result = getattr(fnx, type(graph).__name__)()
        result.graph.update(graph.graph)
        result.add_nodes_from(graph.nodes(data=True))
        if graph.is_multigraph():
            result.add_edges_from(graph.edges(keys=True, data=True))
        else:
            result.add_edges_from(graph.edges(data=True))
        return result
    if route == "warm":
        _warm(graph)
    return graph


def _materialize(name, result):
    if name == "is_k_edge_connected":
        assert type(result) is bool
        return result
    if name == "k_components":
        return {k: {frozenset(c) for c in groups} for k, groups in result.items()}
    assert inspect.isgenerator(result)
    return {frozenset(part) for part in result}


@pytest.mark.parametrize("name,options", _QUERIES)
@pytest.mark.parametrize("shape", ["cycle", "path", "cliques"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_resilience_queries_match_networkx(name, options, shape, route):
    graph = _graph(shape)
    expected = _materialize(name, getattr(nx, name)(graph, backend="networkx", **options))
    supplied = _input(graph.copy(), route)
    actual = _materialize(
        name, getattr(nx, name)(G=supplied, backend="franken_networkx", **options)
    )
    assert actual == expected
    assert set(supplied) == set(graph)
    assert set(supplied.edges()) == set(graph.edges())
    if name == "all_node_cuts":
        assert all(len(cut) == nx.node_connectivity(graph) for cut in actual)
        for cut in actual:
            remaining = graph.subgraph(set(graph) - cut)
            assert not nx.is_connected(remaining)
    elif name == "k_edge_augmentation":
        repaired = graph.copy()
        repaired.add_edges_from(tuple(edge) for edge in actual)
        assert nx.is_k_edge_connected(repaired, options["k"])
        assert all(not graph.has_edge(*tuple(edge)) for edge in actual)


@pytest.mark.parametrize("name", ["k_edge_components", "k_edge_subgraphs"])
@pytest.mark.parametrize("k", [1, 2, 3])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_directed_edge_decompositions(name, k, route):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(7))
    for offset in (0, 3):
        graph.add_edges_from(
            (u + offset, v + offset)
            for u in range(3) for v in range(3) if u != v
        )
    graph.add_edge(2, 3)
    expected = _materialize(name, getattr(nx, name)(graph, k, backend="networkx"))
    actual = _materialize(
        name, getattr(nx, name)(_input(graph.copy(), route), k, backend="franken_networkx")
    )
    assert actual == expected
    assert set().union(*actual) == set(graph)


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_distinguishes_edge_components_from_induced_subgraphs(route):
    graph = nx.Graph()
    for path in [(1, 2, 4, 3, 1, 4), (5, 6, 7, 8, 5, 7, 8, 6)]:
        nx.add_path(graph, path)
    supplied = _input(graph, route)
    components = _materialize(
        "k_edge_components", nx.k_edge_components(supplied, 3, backend="franken_networkx")
    )
    subgraphs = _materialize(
        "k_edge_subgraphs", nx.k_edge_subgraphs(supplied, 3, backend="franken_networkx")
    )
    assert components == {frozenset(c) for c in [{1, 4}, {2}, {3}, {5, 6, 7, 8}]}
    assert subgraphs == {frozenset(c) for c in [{1}, {2}, {3}, {4}, {5, 6, 7, 8}]}


@pytest.mark.parametrize("name", ["k_components", "all_node_cuts"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_vertex_resilience_accepts_parallel_edges(name, route):
    graph = nx.MultiGraph(nx.cycle_graph(5))
    graph.add_edge(0, 1)
    expected = _materialize(name, getattr(nx, name)(graph, backend="networkx"))
    actual = _materialize(
        name, getattr(nx, name)(_input(graph.copy(), route), backend="franken_networkx")
    )
    assert actual == expected


@pytest.mark.parametrize("name", ["k_edge_components", "k_edge_subgraphs"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_low_k_decomposition_keeps_graph_until_first_iteration(name, directed, route):
    graph = nx.DiGraph([(0, 1), (1, 0)]) if directed else nx.path_graph(2)
    supplied = _input(graph.copy(), route)
    expected = getattr(nx, name)(graph, 1, backend="networkx")
    actual = getattr(nx, name)(supplied, 1, backend="franken_networkx")
    for item in (graph, supplied):
        item.add_edges_from([(1, 2), (2, 1)])
    assert _materialize(name, actual) == _materialize(name, expected) == {frozenset({0, 1, 2})}


@pytest.mark.parametrize("name", ["k_edge_components", "k_edge_subgraphs"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_bridge_decomposition_defers_snapshot(name, route):
    graph = nx.path_graph(3)
    supplied = _input(graph.copy(), route)
    expected = getattr(nx, name)(graph, 2, backend="networkx")
    actual = getattr(nx, name)(supplied, 2, backend="franken_networkx")
    graph.add_edge(0, 2)
    supplied.add_edge(0, 2)
    assert _materialize(name, actual) == _materialize(name, expected) == {frozenset({0, 1, 2})}


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_higher_k_components_take_eager_auxiliary_snapshot(route):
    graph = nx.complete_graph(4)
    supplied = _input(graph.copy(), route)
    expected = nx.k_edge_components(graph, 3, backend="networkx")
    actual = nx.k_edge_components(supplied, 3, backend="franken_networkx")
    graph.remove_edge(0, 1)
    supplied.remove_edge(0, 1)
    assert _materialize("k_edge_components", actual) == _materialize("k_edge_components", expected)
    assert list(nx.k_edge_components(graph, 3)) != [set(range(4))]


@pytest.mark.parametrize("name", ["k_edge_components", "k_edge_subgraphs", "all_node_cuts"])
@pytest.mark.parametrize("route", ["cold", "warm"])
def test_backend_resilience_reads_changed_view_after_cached_conversion(name, route):
    graph = nx.cycle_graph(5)
    visible = {0, 1, 2, 3}
    view = nx.subgraph_view(graph, filter_node=visible.__contains__)
    if route == "warm":
        _warm(view)
    visible.add(4)
    options = {"k": 2} if name != "all_node_cuts" else {}
    expected = _materialize(name, getattr(nx, name)(view, backend="networkx", **options))
    actual = _materialize(name, getattr(nx, name)(view, backend="franken_networkx", **options))
    assert actual == expected


@pytest.mark.parametrize("k,avail,partial", [
    (1, [(0, 4, 3), (2, 4, 1)], False),
    (2, {(0, 4): 3, (2, 4): 1, (3, 4): 7}, False),
    (2, [(0, 4)], True),
])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_augmentation_candidates_and_partial_results(k, avail, partial, route):
    graph = nx.path_graph(4)
    graph.add_node(4)
    expected = list(nx.k_edge_augmentation(graph, k, avail=avail, partial=partial))
    supplied = _input(graph.copy(), route)
    actual = list(nx.k_edge_augmentation(
        supplied, k, avail=avail, partial=partial, backend="franken_networkx"
    ))
    assert actual == expected
    assert all(not graph.has_edge(u, v) for u, v in actual)


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_augmentation_starts_on_first_iteration(route):
    graph = nx.path_graph(4)
    supplied = _input(graph.copy(), route)
    actual = nx.k_edge_augmentation(supplied, 2, backend="franken_networkx")
    assert inspect.isgenerator(actual)
    supplied.add_edge(0, 3)
    assert list(actual) == []


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_node_cuts_start_on_first_iteration(route):
    graph = nx.path_graph(5)
    supplied = _input(graph.copy(), route)
    actual = nx.all_node_cuts(supplied, backend="franken_networkx")
    assert inspect.isgenerator(actual)
    supplied.add_edge(0, 4)
    assert {frozenset(cut) for cut in actual} == {
        frozenset(cut) for cut in nx.all_node_cuts(nx.cycle_graph(5))
    }


@pytest.mark.parametrize("name", ["k_components", "all_node_cuts"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_resilience_solver_callback_and_residual_reuse(name, route):
    results = []
    for backend_name in ("networkx", "franken_networkx"):
        graph = nx.cycle_graph(5)
        graph.graph["visits"] = 0
        if backend_name == "franken_networkx":
            graph = _input(graph, route)
        calls = []
        residuals = []

        def solve(auxiliary, source, target, **kwargs):
            graph.graph["visits"] += 1
            residual = kwargs.get("residual")
            calls.append((source, target, tuple(
                (key, value) for key, value in kwargs.items() if key != "residual"
            )))
            residuals.append(residual)
            return nx.algorithms.flow.edmonds_karp(auxiliary, source, target, **kwargs)

        result = _materialize(
            name, getattr(nx, name)(graph, flow_func=solve, backend=backend_name)
        )
        assert calls
        reused = [residual for residual in residuals if residual is not None]
        assert len(reused) > 1
        assert len({id(residual) for residual in reused}) < len(reused)
        if backend_name == "franken_networkx":
            copied = nx.convert_node_labels_to_integers(graph, backend=backend_name)
            assert copied.graph["visits"] == len(calls)
        results.append((result, calls))
    assert results[0] == results[1]


def test_direct_native_k_components_invokes_supplied_solver():
    graph = fnx.Graph()
    graph.add_edges_from(nx.cycle_graph(5).edges())

    def solve(*args, **kwargs):
        raise RuntimeError("selected connectivity solver")

    with pytest.raises(RuntimeError, match="selected connectivity solver"):
        fnx.k_components(graph, flow_func=solve)


@pytest.mark.parametrize("name,options", _QUERIES)
def test_backend_native_input_is_independent_of_conversion_origin(name, options):
    original = nx.path_graph(5)
    supplied = fnx_backend.backend_interface.convert_from_nx(original, name=name)
    # Live-input conversions intentionally retain the original object; use an
    # eager conversion to test the native graph's independent lifetime.
    if supplied is original:
        supplied = fnx_backend.backend_interface.convert_from_nx(original, name="pagerank")
    supplied.add_edge(0, 4)
    expected = _materialize(name, getattr(nx, name)(nx.cycle_graph(5), **options))
    actual = _materialize(name, getattr(nx, name)(supplied, backend="franken_networkx", **options))
    assert actual == expected
    assert not original.has_edge(0, 4)


@pytest.mark.parametrize("name,graph_type,options", [
    ("is_k_edge_connected", "DiGraph", {"k": 2}),
    ("is_k_edge_connected", "MultiGraph", {"k": 2}),
    ("k_edge_components", "MultiGraph", {"k": 2}),
    ("k_edge_subgraphs", "MultiDiGraph", {"k": 2}),
    ("k_edge_augmentation", "DiGraph", {"k": 2}),
    ("k_edge_augmentation", "MultiGraph", {"k": 2}),
    ("k_components", "DiGraph", {}),
    ("all_node_cuts", "DiGraph", {}),
])
def test_backend_resilience_preserves_graph_type_errors(name, graph_type, options):
    errors = []
    for backend_name in ("networkx", "franken_networkx"):
        graph = getattr(nx, graph_type)(nx.cycle_graph(5))
        with pytest.raises(nx.NetworkXNotImplemented) as caught:
            _materialize(name, getattr(nx, name)(graph, backend=backend_name, **options))
        errors.append(caught.value.args)
    assert errors[0] == errors[1]


@pytest.mark.parametrize("name", ["is_k_edge_connected", "k_edge_components", "k_edge_subgraphs"])
def test_backend_resilience_invalid_k_is_eager(name):
    graph = nx.path_graph(4)
    with pytest.raises(ValueError) as expected:
        getattr(nx, name)(graph, 0, backend="networkx")
    with pytest.raises(ValueError) as actual:
        getattr(nx, name)(graph, 0, backend="franken_networkx")
    assert actual.value.args == expected.value.args


def test_backend_augmentation_invalid_k_is_lazy():
    result = nx.k_edge_augmentation(nx.path_graph(4), 0, backend="franken_networkx")
    with pytest.raises(ValueError, match="k must be a positive integer, not 0"):
        next(result)


def test_backend_node_cuts_disconnected_graph_fails_when_advanced():
    result = nx.all_node_cuts(nx.empty_graph(3), backend="franken_networkx")
    with pytest.raises(nx.NetworkXError, match="Input graph is disconnected"):
        next(result)
