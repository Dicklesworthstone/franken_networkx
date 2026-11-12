import inspect
import math

import numpy as np
import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _assert_mapping_close(actual, expected, tol=1e-12):
    assert set(actual) == set(expected)
    for node in expected:
        assert math.isclose(actual[node], expected[node], rel_tol=tol, abs_tol=tol)


def _assert_nested_result_close(actual, expected, tol=1e-12):
    if isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            _assert_nested_result_close(actual[key], expected[key], tol=tol)
        return
    if isinstance(expected, float) and math.isnan(expected):
        assert math.isnan(actual)
        return
    assert math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)


def test_load_centrality_native_unweighted_matches_networkx():
    graph = fnx.cycle_graph(4)

    actual = fnx.load_centrality(graph)
    expected = nx.load_centrality(nx.cycle_graph(4))

    _assert_mapping_close(actual, expected)
    assert math.isclose(fnx.load_centrality(graph, v=1), expected[1], rel_tol=1e-12, abs_tol=1e-12)


def test_load_centrality_weighted_fallback_matches_networkx():
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("b", "c", weight=1.0)
    graph.add_edge("a", "c", weight=5.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge("a", "b", weight=2.0)
    expected_graph.add_edge("b", "c", weight=1.0)
    expected_graph.add_edge("a", "c", weight=5.0)

    actual = fnx.load_centrality(graph, weight="weight")
    expected = nx.load_centrality(expected_graph, weight="weight")

    _assert_mapping_close(actual, expected)


def test_load_centrality_weighted_fallback_avoids_delegation(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("b", "c", weight=1.0)
    graph.add_edge("a", "c", weight=5.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge("a", "b", weight=2.0)
    expected_graph.add_edge("b", "c", weight=1.0)
    expected_graph.add_edge("a", "c", weight=5.0)
    expected = nx.load_centrality(expected_graph, weight="weight", cutoff=3.0)

    monkeypatch.setattr(
        nx,
        "load_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.load_centrality(graph, weight="weight", cutoff=3.0)
    _assert_mapping_close(actual, expected)


def test_second_order_centrality_native_unweighted_matches_networkx():
    graph = fnx.path_graph(4)

    actual = fnx.second_order_centrality(graph)
    expected = nx.second_order_centrality(nx.path_graph(4))

    _assert_mapping_close(actual, expected)


def test_second_order_centrality_weighted_fallback_matches_networkx():
    graph = fnx.path_graph(4)
    graph[0][1]["weight"] = 2.0

    expected_graph = nx.path_graph(4)
    expected_graph[0][1]["weight"] = 2.0

    actual = fnx.second_order_centrality(graph)
    expected = nx.second_order_centrality(expected_graph)

    _assert_mapping_close(actual, expected)


def test_second_order_centrality_weighted_fallback_avoids_delegation(monkeypatch):
    graph = fnx.path_graph(4)
    graph[0][1]["weight"] = 2.0

    expected_graph = nx.path_graph(4)
    expected_graph[0][1]["weight"] = 2.0
    expected = nx.second_order_centrality(expected_graph)

    monkeypatch.setattr(
        nx,
        "second_order_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.second_order_centrality(graph)
    _assert_mapping_close(actual, expected)


def test_second_order_centrality_signature_matches_networkx():
    assert str(inspect.signature(fnx.second_order_centrality)) == str(
        inspect.signature(nx.second_order_centrality)
    )


def test_second_order_centrality_weight_knobs_match_networkx():
    actual_graph = fnx.path_graph(4)
    actual_graph[0][1]["weight"] = 2.0
    actual_graph[0][1]["alt"] = 3.0

    expected_graph = nx.path_graph(4)
    expected_graph[0][1]["weight"] = 2.0
    expected_graph[0][1]["alt"] = 3.0

    _assert_mapping_close(
        fnx.second_order_centrality(actual_graph, weight=None),
        nx.second_order_centrality(expected_graph, weight=None),
    )
    _assert_mapping_close(
        fnx.second_order_centrality(actual_graph, weight="alt"),
        nx.second_order_centrality(expected_graph, weight="alt"),
    )


def test_second_order_centrality_backend_keyword_surface_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    for backend in (None, "networkx"):
        _assert_mapping_close(
            fnx.second_order_centrality(actual_graph, backend=backend),
            nx.second_order_centrality(expected_graph, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.second_order_centrality(actual_graph, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.second_order_centrality(expected_graph, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.second_order_centrality(actual_graph, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.second_order_centrality(expected_graph, backend_kwargs={"x": 1})


@pytest.mark.parametrize(
    "name",
    ["constraint", "effective_size", "local_constraint", "dispersion"],
)
def test_structural_holes_wrappers_expose_backend_signature_matches_networkx(name):
    assert str(inspect.signature(getattr(fnx, name))) == str(inspect.signature(getattr(nx, name)))


@pytest.mark.parametrize(
    ("name", "args"),
    [
        pytest.param("constraint", (), id="constraint"),
        pytest.param("effective_size", (), id="effective_size"),
        pytest.param("local_constraint", (0, 1), id="local_constraint"),
        pytest.param("dispersion", (), id="dispersion"),
    ],
)
def test_structural_holes_wrappers_backend_keyword_surface_matches_networkx(name, args):
    actual_graph = fnx.Graph([(0, 1), (0, 2), (1, 2), (2, 3)])
    expected_graph = nx.Graph([(0, 1), (0, 2), (1, 2), (2, 3)])
    fnx_fn = getattr(fnx, name)
    nx_fn = getattr(nx, name)

    for backend in (None, "networkx"):
        _assert_nested_result_close(
            fnx_fn(actual_graph, *args, backend=backend),
            nx_fn(expected_graph, *args, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx_fn(actual_graph, *args, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx_fn(expected_graph, *args, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx_fn(actual_graph, *args, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx_fn(expected_graph, *args, backend_kwargs={"x": 1})


def test_subgraph_centrality_normalized_and_error_contract_match_networkx(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=5.0)
    graph.add_edge(1, 2, weight=7.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=5.0)
    expected_graph.add_edge(1, 2, weight=7.0)

    original_subgraph_centrality = nx.subgraph_centrality
    expected = original_subgraph_centrality(expected_graph)
    expected_normalized = original_subgraph_centrality(expected_graph, normalized=True)

    monkeypatch.setattr(
        nx,
        "subgraph_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.subgraph_centrality(graph)
    actual_normalized = fnx.subgraph_centrality(graph, normalized=True)
    _assert_mapping_close(actual, expected)
    _assert_mapping_close(actual_normalized, expected_normalized)

    actual_directed = fnx.DiGraph([(0, 1)])
    expected_directed = nx.DiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected_directed_error:
        original_subgraph_centrality(expected_directed)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual_directed_error:
        fnx.subgraph_centrality(actual_directed)
    assert str(actual_directed_error.value) == str(expected_directed_error.value)

    actual_multigraph = fnx.MultiGraph([(0, 1)])
    expected_multigraph = nx.MultiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected_multigraph_error:
        original_subgraph_centrality(expected_multigraph)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual_multigraph_error:
        fnx.subgraph_centrality(actual_multigraph)
    assert str(actual_multigraph_error.value) == str(expected_multigraph_error.value)


def test_subgraph_centrality_backend_keyword_surface_matches_networkx():
    actual_graph = fnx.path_graph(3)
    expected_graph = nx.path_graph(3)

    for backend in (None, "networkx"):
        actual = fnx.subgraph_centrality(actual_graph, backend=backend)
        expected = nx.subgraph_centrality(expected_graph, backend=backend)
        _assert_mapping_close(actual, expected)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.subgraph_centrality(actual_graph, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.subgraph_centrality(expected_graph, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.subgraph_centrality(actual_graph, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.subgraph_centrality(expected_graph, backend_kwargs={"x": 1})


def test_subgraph_centrality_exp_parity_matches_networkx():
    actual_graph = fnx.path_graph(3)
    expected_graph = nx.path_graph(3)

    _assert_mapping_close(
        fnx.subgraph_centrality_exp(actual_graph),
        nx.subgraph_centrality_exp(expected_graph),
    )

    for backend in (None, "networkx"):
        actual = fnx.subgraph_centrality_exp(actual_graph, backend=backend)
        expected = nx.subgraph_centrality_exp(expected_graph, backend=backend)
        _assert_mapping_close(actual, expected)

    with pytest.raises(AttributeError) as expected_normalized_error:
        nx.subgraph_centrality_exp(expected_graph, normalized=True)
    with pytest.raises(AttributeError) as actual_normalized_error:
        fnx.subgraph_centrality_exp(actual_graph, normalized=True)
    assert str(actual_normalized_error.value) == str(expected_normalized_error.value)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.subgraph_centrality_exp(actual_graph, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.subgraph_centrality_exp(expected_graph, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.subgraph_centrality_exp(actual_graph, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.subgraph_centrality_exp(expected_graph, backend_kwargs={"x": 1})

def test_katz_centrality_numpy_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.DiGraph()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("c", "b", weight=1.5)
    graph.add_edge("b", "c", weight=0.5)

    expected_graph = nx.DiGraph()
    expected_graph.add_edge("a", "b", weight=2.0)
    expected_graph.add_edge("c", "b", weight=1.5)
    expected_graph.add_edge("b", "c", weight=0.5)

    expected = nx.katz_centrality_numpy(
        expected_graph,
        alpha=0.1,
        beta={"c": 3.0, "a": 1.0, "b": 2.0},
        normalized=False,
        weight="weight",
    )

    monkeypatch.setattr(
        nx,
        "katz_centrality_numpy",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.katz_centrality_numpy(
        graph,
        alpha=0.1,
        beta={"c": 3.0, "a": 1.0, "b": 2.0},
        normalized=False,
        weight="weight",
    )
    _assert_mapping_close(actual, expected)


def test_katz_centrality_numpy_error_contract_matches_networkx():
    actual_graph = fnx.path_graph(3)
    expected_graph = nx.path_graph(3)

    with pytest.raises(nx.NetworkXError) as expected_beta_error:
        nx.katz_centrality_numpy(expected_graph, beta={0: 1.0})
    with pytest.raises(fnx.NetworkXError) as actual_beta_error:
        fnx.katz_centrality_numpy(actual_graph, beta={0: 1.0})
    assert str(actual_beta_error.value) == str(expected_beta_error.value)

    with pytest.raises(nx.NetworkXError) as expected_scalar_error:
        nx.katz_centrality_numpy(expected_graph, beta="x")
    with pytest.raises(fnx.NetworkXError) as actual_scalar_error:
        fnx.katz_centrality_numpy(actual_graph, beta="x")
    assert str(actual_scalar_error.value) == str(expected_scalar_error.value)

    actual_multigraph = fnx.MultiGraph([(0, 1)])
    expected_multigraph = nx.MultiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected_multigraph_error:
        nx.katz_centrality_numpy(expected_multigraph)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual_multigraph_error:
        fnx.katz_centrality_numpy(actual_multigraph)
    assert str(actual_multigraph_error.value) == str(expected_multigraph_error.value)


def test_katz_centrality_numpy_backend_keyword_surface_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    for backend in (None, "networkx"):
        actual = fnx.katz_centrality_numpy(actual_graph, backend=backend)
        expected = nx.katz_centrality_numpy(expected_graph, backend=backend)
        _assert_mapping_close(actual, expected)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.katz_centrality_numpy(actual_graph, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.katz_centrality_numpy(expected_graph, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.katz_centrality_numpy(actual_graph, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.katz_centrality_numpy(expected_graph, backend_kwargs={"x": 1})


def test_eigenvector_centrality_numpy_weight_contract_matches_networkx():
    actual_graph = fnx.Graph()
    actual_graph.add_edge(0, 1, weight=10.0)
    actual_graph.add_edge(1, 2, weight=1.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=10.0)
    expected_graph.add_edge(1, 2, weight=1.0)

    _assert_mapping_close(
        fnx.eigenvector_centrality_numpy(actual_graph),
        nx.eigenvector_centrality_numpy(expected_graph),
    )
    _assert_mapping_close(
        fnx.eigenvector_centrality_numpy(actual_graph, weight="weight"),
        nx.eigenvector_centrality_numpy(expected_graph, weight="weight"),
    )


def test_eigenvector_centrality_numpy_backend_keyword_surface_matches_networkx():
    actual_graph = fnx.path_graph(3)
    expected_graph = nx.path_graph(3)

    for backend in (None, "networkx"):
        _assert_mapping_close(
            fnx.eigenvector_centrality_numpy(actual_graph, backend=backend),
            nx.eigenvector_centrality_numpy(expected_graph, backend=backend),
        )

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.eigenvector_centrality_numpy(actual_graph, backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.eigenvector_centrality_numpy(expected_graph, backend="parallel")

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.eigenvector_centrality_numpy(actual_graph, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.eigenvector_centrality_numpy(expected_graph, backend_kwargs={"x": 1})


def test_hits_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    expected_hubs, expected_authorities = nx.hits(
        expected_graph,
        max_iter=25,
        tol=1.0e-12,
        nstart={node: float(index + 1) for index, node in enumerate(expected_graph)},
        normalized=False,
    )

    monkeypatch.setattr(
        nx,
        "hits",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual_hubs, actual_authorities = fnx.hits(
        graph,
        max_iter=25,
        tol=1.0e-12,
        nstart={node: float(index + 1) for index, node in enumerate(graph)},
        normalized=False,
    )
    _assert_mapping_close(actual_hubs, expected_hubs)
    _assert_mapping_close(actual_authorities, expected_authorities)


def test_hits_error_contract_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(nx.PowerIterationFailedConvergence) as expected_iter_error:
        nx.hits(expected_graph, max_iter=0)
    with pytest.raises(fnx.PowerIterationFailedConvergence) as actual_iter_error:
        fnx.hits(actual_graph, max_iter=0)
    assert str(actual_iter_error.value) == str(expected_iter_error.value)

    with pytest.raises(ValueError) as expected_nstart_error:
        nx.hits(expected_graph, nstart={node: index + 1 for index, node in enumerate(expected_graph)})
    with pytest.raises(ValueError) as actual_nstart_error:
        fnx.hits(actual_graph, nstart={node: index + 1 for index, node in enumerate(actual_graph)})
    assert str(actual_nstart_error.value) == str(expected_nstart_error.value)


def test_group_closeness_centrality_native_and_directed_fallback_match_networkx():
    undirected = fnx.path_graph(4)
    expected_undirected = nx.path_graph(4)
    assert math.isclose(
        fnx.group_closeness_centrality(undirected, {1}),
        nx.group_closeness_centrality(expected_undirected, {1}),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )

    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 2), (2, 3)])
    expected_directed = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert math.isclose(
        fnx.group_closeness_centrality(directed, {1}),
        nx.group_closeness_centrality(expected_directed, {1}),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_group_closeness_centrality_directed_fallback_avoids_delegation(monkeypatch):
    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 2), (2, 3)])

    expected_directed = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    expected = nx.group_closeness_centrality(expected_directed, {1})

    monkeypatch.setattr(
        nx,
        "group_closeness_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.group_closeness_centrality(directed, {1})
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def _group_closeness_live_outcome(module, owner, graph_type, variant):
    graph = getattr(owner, graph_type)()
    graph.add_weighted_edges_from([
        (0, 1, 1), (1, 2, 9), (2, 3, 1), (0, 3, 20), (3, 0, 7),
    ])
    if graph.is_multigraph():
        graph.add_edge(1, 2, key="parallel", weight=15)
    work = graph.subgraph(list(graph)) if variant == "filtered" else graph
    trace = []

    def distance(u, v, data):
        later = graph[1][2][0] if graph.is_multigraph() else graph[1][2]
        later["weight"] = 1
        attributes = list(data.values()) if graph.is_multigraph() else [data]
        for attrs in attributes:
            attrs["reads"] = attrs.get("reads", 0) + 1
        values = tuple(attrs["weight"] for attrs in attributes)
        trace.append((u, v, values))
        return min(values)

    value = module.group_closeness_centrality(work, [0], weight=distance)
    if graph.is_multigraph():
        edges = [(u, v, k, dict(d)) for u, v, k, d in graph.edges(keys=True, data=True)]
    else:
        edges = [(u, v, dict(d)) for u, v, d in graph.edges(data=True)]
    return value, trace, edges


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx", "fnx"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("variant", ["owned", "filtered"])
def test_group_closeness_keeps_live_weight_callbacks(owner, graph_type, variant):
    expected = _group_closeness_live_outcome(nx, nx, graph_type, variant)
    actual = _group_closeness_live_outcome(fnx, owner, graph_type, variant)
    assert actual == expected


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx", "fnx"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, ("cost", 0)])
def test_group_closeness_honors_literal_weight_keys(owner, graph_type, weight):
    graphs = [getattr(module, graph_type)() for module in (nx, owner)]
    for graph in graphs:
        for u, v, value in [(0, 1, 1), (1, 2, 9), (2, 3, 1), (3, 0, 20)]:
            if graph.is_multigraph():
                key = graph.add_edge(u, v)
                graph[u][v][key][weight] = value
            else:
                graph.add_edge(u, v)
                graph[u][v][weight] = value
    assert fnx.group_closeness_centrality(graphs[1], [0], weight=weight) == (
        nx.group_closeness_centrality(graphs[0], [0], weight=weight)
    )


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx", "fnx"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_group_closeness_empty_group_preserves_error(owner, graph_type):
    reference = getattr(nx, graph_type)([(0, 1), (1, 2)])
    actual = getattr(owner, graph_type)([(0, 1), (1, 2)])
    with pytest.raises(ValueError) as expected:
        nx.group_closeness_centrality(reference, [])
    with pytest.raises(ValueError) as result:
        fnx.group_closeness_centrality(actual, [])
    assert result.value.args == expected.value.args
    assert fnx.group_closeness_centrality(actual, list(actual)) == 0
    assert fnx.group_closeness_centrality(getattr(owner, graph_type)(), []) == 0


def test_group_betweenness_centrality_native_and_fallback_match_networkx():
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, normalized=True),
        nx.group_betweenness_centrality(expected_graph, {1}, normalized=True),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, normalized=False),
        nx.group_betweenness_centrality(expected_graph, {1}, normalized=False),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, endpoints=True),
        nx.group_betweenness_centrality(expected_graph, {1}, endpoints=True),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_group_betweenness_centrality_endpoints_fallback_avoids_delegation(monkeypatch):
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)
    expected = nx.group_betweenness_centrality(expected_graph, {1}, endpoints=True)

    monkeypatch.setattr(
        nx,
        "group_betweenness_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.group_betweenness_centrality(graph, {1}, endpoints=True)
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_betweenness_centrality_subset_native_matches_networkx_and_avoids_delegation(
    monkeypatch,
):
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)
    expected = nx.betweenness_centrality_subset(
        expected_graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )

    def fail(*args, **kwargs):
        raise AssertionError("delegated to networkx.betweenness_centrality_subset")

    monkeypatch.setattr(nx, "betweenness_centrality_subset", fail)
    actual = fnx.betweenness_centrality_subset(
        graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )
    _assert_mapping_close(actual, expected)


def test_betweenness_centrality_subset_backend_keyword_surface_matches_networkx():
    graph = fnx.path_graph(5)
    expected_graph = nx.path_graph(5)

    for backend in (None, "networkx"):
        actual = fnx.betweenness_centrality_subset(
            graph,
            [0],
            [4],
            backend=backend,
        )
        expected = nx.betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend=backend,
        )
        _assert_mapping_close(actual, expected)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.betweenness_centrality_subset(graph, [0], [4], backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend="parallel",
        )

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.betweenness_centrality_subset(
            graph,
            [0],
            [4],
            backend_kwargs={"x": 1},
        )
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend_kwargs={"x": 1},
        )


def test_edge_betweenness_centrality_subset_native_matches_networkx_and_avoids_delegation(
    monkeypatch,
):
    graph = fnx.cycle_graph(4)
    expected_graph = nx.cycle_graph(4)
    expected = nx.edge_betweenness_centrality_subset(
        expected_graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )

    def fail(*args, **kwargs):
        raise AssertionError(
            "delegated to networkx.edge_betweenness_centrality_subset"
        )

    monkeypatch.setattr(nx, "edge_betweenness_centrality_subset", fail)
    actual = fnx.edge_betweenness_centrality_subset(
        graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )
    _assert_mapping_close(actual, expected)


def test_edge_betweenness_centrality_subset_backend_keyword_surface_matches_networkx():
    graph = fnx.path_graph(5)
    expected_graph = nx.path_graph(5)

    for backend in (None, "networkx"):
        actual = fnx.edge_betweenness_centrality_subset(
            graph,
            [0],
            [4],
            backend=backend,
        )
        expected = nx.edge_betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend=backend,
        )
        _assert_mapping_close(actual, expected)

    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        fnx.edge_betweenness_centrality_subset(graph, [0], [4], backend="parallel")
    with pytest.raises(ImportError, match="'parallel' backend is not installed"):
        nx.edge_betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend="parallel",
        )

    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.edge_betweenness_centrality_subset(
            graph,
            [0],
            [4],
            backend_kwargs={"x": 1},
        )
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.edge_betweenness_centrality_subset(
            expected_graph,
            [0],
            [4],
            backend_kwargs={"x": 1},
        )


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight", lambda u, v, data: 1])
def test_subset_betweenness_consumes_one_shot_targets_once(algorithm, graph_class, weight):
    reference = getattr(nx, graph_class)([(0, 1), (1, 2), (2, 3)])
    graph = getattr(fnx, graph_class)([(0, 1), (1, 2), (2, 3)])

    expected = getattr(nx, algorithm)(reference, [0, 1], iter([3]), weight=weight)
    actual = getattr(fnx, algorithm)(graph, [0, 1], iter([3]), weight=weight)
    assert actual == expected


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_subset_betweenness_preserves_shared_selection_iterator(algorithm, graph_class):
    def run(library):
        graph = getattr(library, graph_class)([(0, 1), (1, 2), (2, 3)])
        selection = iter([0, 1, 2, 3])
        return getattr(library, algorithm)(graph, selection, selection)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_subset_betweenness_interleaves_lazy_sources_and_weight_changes(
    algorithm, graph_class
):
    def run(library):
        graph = getattr(library, graph_class)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 3, 1), (0, 2, 1), (2, 3, 5)])

        def sources():
            yield 0
            attrs = graph[2][3][0] if graph.is_multigraph() else graph[2][3]
            attrs["weight"] = 1
            yield 1

        return getattr(library, algorithm)(graph, sources(), [3], weight="weight")

    assert run(fnx) == run(nx)


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
def test_subset_betweenness_weight_callbacks_keep_selection_lists_live(algorithm):
    def run(library):
        graph = library.DiGraph([(0, 1), (1, 2), (2, 3)])
        sources, targets, calls = [0], [3], []

        def weight(u, v, data):
            calls.append((u, v))
            if len(calls) == 1:
                sources.append(1)
                targets[:] = [2]
            return 1

        result = getattr(library, algorithm)(graph, sources, targets, weight=weight)
        return result, calls

    assert run(fnx) == run(nx)


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
def test_subset_betweenness_empty_sources_do_not_consume_targets(algorithm):
    def targets():
        raise AssertionError("empty sources must not consume targets")
        yield 3

    reference = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    expected = getattr(nx, algorithm)(reference, [], targets())
    assert getattr(fnx, algorithm)(graph, [], targets()) == expected
    assert getattr(fnx, algorithm)(graph, [], [[3]]) == expected


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
@pytest.mark.parametrize("sources", [[99], [0, 99], [[0]]])
def test_subset_betweenness_validates_each_search_before_its_targets(algorithm, sources):
    reference = nx.DiGraph([(0, 1), (1, 2)])
    graph = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises((KeyError, TypeError)) as expected:
        getattr(nx, algorithm)(reference, sources, [[2]])
    with pytest.raises(type(expected.value)) as actual:
        getattr(fnx, algorithm)(graph, sources, [[2]])
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize(
    "algorithm", ["betweenness_centrality_subset", "edge_betweenness_centrality_subset"]
)
@pytest.mark.parametrize("sequence", [list, tuple])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_subset_betweenness_reusable_sequences_retain_native_route(
    monkeypatch, algorithm, sequence, weight
):
    reference = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    expected = getattr(nx, algorithm)(reference, [0, 1], [3], weight=weight)
    raw_name = f"_{algorithm}{'_weighted' if weight is not None else ''}_rust"
    raw = getattr(fnx, raw_name)
    calls = []

    def record(*args, **kwargs):
        calls.append(True)
        return raw(*args, **kwargs)

    monkeypatch.setattr(fnx, raw_name, record)
    result = getattr(fnx, algorithm)(graph, sequence([0, 1]), sequence([3]), weight=weight)
    assert result == expected
    assert calls == [True]


def test_communicability_betweenness_centrality_matches_networkx():
    graph = fnx.path_graph(4)

    actual = fnx.communicability_betweenness_centrality(graph)
    expected = nx.communicability_betweenness_centrality(nx.path_graph(4))

    _assert_mapping_close(actual, expected)


def test_edge_load_centrality_matches_networkx():
    graph = fnx.cycle_graph(4)
    expected = nx.edge_load_centrality(nx.cycle_graph(4))
    actual = fnx.edge_load_centrality(graph)
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_matches_networkx_without_fallback(
    monkeypatch,
):
    import franken_networkx.backend as fnx_backend

    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.0)
    graph.add_edge(1, 2, weight=3.0)
    graph.add_edge(0, 2, weight=5.0)
    graph.add_edge(2, 3, weight=1.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=2.0)
    expected_graph.add_edge(1, 2, weight=3.0)
    expected_graph.add_edge(0, 2, weight=5.0)
    expected_graph.add_edge(2, 3, weight=1.0)

    expected = nx.edge_current_flow_betweenness_centrality(
        expected_graph,
        normalized=True,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )

    for attr in ("edge_current_flow_betweenness_centrality", "is_connected", "laplacian_matrix", "relabel_nodes"):
        monkeypatch.setattr(
            nx,
            attr,
            lambda *args, _attr=attr, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"delegated to networkx.{_attr}")
            ),
        )
    monkeypatch.setattr(
        fnx_backend,
        "_fnx_to_nx",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated to backend._fnx_to_nx")),
    )

    actual = fnx.edge_current_flow_betweenness_centrality(
        graph,
        normalized=True,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_edge_current_flow_betweenness_centrality_weight_none_matches_networkx():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=10.0)
    graph.add_edge(1, 2, weight=10.0)
    graph.add_edge(0, 2, weight=1.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=10.0)
    expected_graph.add_edge(1, 2, weight=10.0)
    expected_graph.add_edge(0, 2, weight=1.0)

    actual = fnx.edge_current_flow_betweenness_centrality(graph, weight=None)
    expected = nx.edge_current_flow_betweenness_centrality(expected_graph, weight=None)
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_multigraph_matches_networkx():
    graph = fnx.MultiGraph()
    graph.add_edge(0, 1, weight=1.0)
    graph.add_edge(0, 1, weight=3.0)
    graph.add_edge(1, 2, weight=2.0)

    expected_graph = nx.MultiGraph()
    expected_graph.add_edge(0, 1, weight=1.0)
    expected_graph.add_edge(0, 1, weight=3.0)
    expected_graph.add_edge(1, 2, weight=2.0)

    actual = fnx.edge_current_flow_betweenness_centrality(graph, weight="weight")
    expected = nx.edge_current_flow_betweenness_centrality(expected_graph, weight="weight")
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_directed_error_contract_matches_networkx():
    actual_graph = fnx.DiGraph([(0, 1)])
    expected_graph = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.edge_current_flow_betweenness_centrality(expected_graph)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.edge_current_flow_betweenness_centrality(actual_graph)

    assert str(actual.value) == str(expected.value)


def test_edge_current_flow_betweenness_centrality_invalid_solver_matches_networkx():
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(KeyError) as expected:
        nx.edge_current_flow_betweenness_centrality(expected_graph, solver="bogus")
    with pytest.raises(KeyError) as actual:
        fnx.edge_current_flow_betweenness_centrality(graph, solver="bogus")

    assert actual.value.args == expected.value.args


def test_current_flow_betweenness_default_uses_native_ordered_kernel(monkeypatch):
    graph = fnx.watts_strogatz_graph(12, 4, 0.2, seed=7)
    expected_graph = nx.watts_strogatz_graph(12, 4, 0.2, seed=7)
    expected = nx.current_flow_betweenness_centrality(expected_graph)

    monkeypatch.setattr(
        fnx,
        "_flow_matrix_row",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("default path should use native ordered kernel")
        ),
    )

    actual = fnx.current_flow_betweenness_centrality(graph)
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_edge_current_flow_betweenness_default_uses_native_ordered_kernel(monkeypatch):
    graph = fnx.watts_strogatz_graph(12, 4, 0.2, seed=7)
    expected_graph = nx.watts_strogatz_graph(12, 4, 0.2, seed=7)
    expected = nx.edge_current_flow_betweenness_centrality(expected_graph)

    monkeypatch.setattr(
        fnx,
        "_flow_matrix_row",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("default path should use native ordered kernel")
        ),
    )

    actual = fnx.edge_current_flow_betweenness_centrality(graph)
    _assert_mapping_close(
        {frozenset(k): v for k, v in actual.items()},
        {frozenset(k): v for k, v in expected.items()},
        tol=1e-6,
    )


def test_current_flow_rcm_ordering_uses_native_start_without_changing_order(monkeypatch):
    if not hasattr(fnx._fnx, "current_flow_pseudo_peripheral_node_rust"):
        pytest.skip("native pseudo-peripheral route not built")

    graph = fnx.watts_strogatz_graph(18, 4, 0.2, seed=13)
    expected_ordering = list(fnx._reverse_cuthill_mckee_ordering(graph))

    monkeypatch.setattr(
        fnx,
        "_current_flow_pseudo_peripheral_node",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("current-flow RCM should use native start")
        ),
    )

    actual_ordering = fnx._current_flow_rcm_ordering(graph)
    if actual_ordering != expected_ordering:
        raise AssertionError("native-start RCM ordering changed Python RCM order")

    expected_graph = nx.watts_strogatz_graph(18, 4, 0.2, seed=13)
    expected = nx.current_flow_betweenness_centrality(expected_graph)
    actual = fnx.current_flow_betweenness_centrality(graph)
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_information_centrality_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.0)
    graph.add_edge(1, 2, weight=3.0)
    graph.add_edge(2, 3, weight=4.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=2.0)
    expected_graph.add_edge(1, 2, weight=3.0)
    expected_graph.add_edge(2, 3, weight=4.0)

    expected = nx.information_centrality(
        expected_graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )

    monkeypatch.setattr(
        nx,
        "information_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.information_centrality(
        graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_current_flow_closeness_centrality_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.0)
    graph.add_edge(1, 2, weight=3.0)
    graph.add_edge(2, 3, weight=4.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=2.0)
    expected_graph.add_edge(1, 2, weight=3.0)
    expected_graph.add_edge(2, 3, weight=4.0)

    expected = nx.current_flow_closeness_centrality(
        expected_graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )

    for attr in ("is_connected", "laplacian_matrix", "relabel_nodes"):
        monkeypatch.setattr(
            nx,
            attr,
            lambda *args, _attr=attr, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"delegated to networkx.{_attr}")
            ),
        )

    actual = fnx.current_flow_closeness_centrality(
        graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_current_flow_closeness_centrality_error_contract_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(KeyError) as expected:
        nx.current_flow_closeness_centrality(expected_graph, solver="bogus")
    with pytest.raises(KeyError) as actual:
        fnx.current_flow_closeness_centrality(actual_graph, solver="bogus")
    assert actual.value.args == expected.value.args

    actual_directed = fnx.DiGraph([(0, 1)])
    expected_directed = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.current_flow_closeness_centrality(expected_directed)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.current_flow_closeness_centrality(actual_directed)
    assert str(actual.value) == str(expected.value)

    actual_disconnected = fnx.Graph([(0, 1), (2, 3)])
    expected_disconnected = nx.Graph([(0, 1), (2, 3)])

    with pytest.raises(nx.NetworkXError) as expected:
        nx.current_flow_closeness_centrality(expected_disconnected)
    with pytest.raises(fnx.NetworkXError) as actual:
        fnx.current_flow_closeness_centrality(actual_disconnected)
    assert str(actual.value) == str(expected.value)


def test_information_centrality_error_contract_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(KeyError) as expected:
        nx.information_centrality(expected_graph, solver="bogus")
    with pytest.raises(KeyError) as actual:
        fnx.information_centrality(actual_graph, solver="bogus")
    assert actual.value.args == expected.value.args

    actual_directed = fnx.DiGraph([(0, 1)])
    expected_directed = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.information_centrality(expected_directed)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.information_centrality(actual_directed)
    assert str(actual.value) == str(expected.value)


def test_percolation_centrality_honors_attribute_and_states(monkeypatch):
    graph = fnx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        graph.nodes[node]["custom_state"] = value

    expected_graph = nx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        expected_graph.nodes[node]["custom_state"] = value

    expected_attr = nx.percolation_centrality(expected_graph, attribute="custom_state")
    states = {0: 0.1, 1: 0.3, 2: 0.7, 3: 1.0}
    expected_states = nx.percolation_centrality(expected_graph, states=states)

    def fail(*args, **kwargs):
        raise AssertionError("delegated to networkx.percolation_centrality")

    monkeypatch.setattr(nx, "percolation_centrality", fail)
    actual_attr = fnx.percolation_centrality(graph, attribute="custom_state")
    _assert_mapping_close(actual_attr, expected_attr)

    actual_states = fnx.percolation_centrality(graph, states=states)
    _assert_mapping_close(actual_states, expected_states)
