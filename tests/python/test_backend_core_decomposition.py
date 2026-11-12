"""Core decompositions remain available through explicit backend dispatch."""

from decimal import Decimal

import networkx as nx
import pytest

import fnx_backend_info
import franken_networkx as fnx
from franken_networkx.backend import BackendInterface, get_backend_info


_CORE_SUBGRAPHS = ("k_core", "k_shell", "k_crust", "k_corona")
_GRAPH_RESULTS = _CORE_SUBGRAPHS + ("k_truss",)
_ALGORITHMS = _GRAPH_RESULTS + ("onion_layers",)


def _core_graph(module, *, directed=False):
    graph = module.DiGraph() if directed else module.Graph()
    nodes = ["isolate", "tail", 17, "c", "a", "b", ("join", 1)]
    graph.graph.update({"name": "core fixture", "payload": ["graph"]})
    graph.graph[("graph", "key")] = {"enabled": True}
    graph.add_nodes_from(
        (node, {"rank": rank, "payload": [node]})
        for rank, node in enumerate(nodes)
    )
    edges = [
        ("b", 17), ("a", "b"), ("c", "a"), ("c", "b"),
        ("c", 17), ("a", 17), ("b", ("join", 1)),
        (("join", 1), "tail"),
    ]
    if directed:
        edges.append((17, "a"))
    for rank, (u, v) in enumerate(edges):
        graph.add_edge(u, v, weight=Decimal("1.5"), payload=[rank])
        graph[u][v][("edge", "key")] = rank
    return graph


def _kwargs(name):
    return {"k": 3} if name in ("k_corona", "k_truss") else {}


def _graph_contract(graph):
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        list(graph.graph.items()),
        [(node, list(data.items())) for node, data in graph.nodes(data=True)],
        [(u, v, list(data.items())) for u, v, data in graph.edges(data=True)],
        [(node, list(graph.adj[node])) for node in graph],
        [(node, list(graph.pred[node])) for node in graph]
        if graph.is_directed() else None,
    )


def _assert_independent_shallow_graph(actual, expected, source):
    assert actual.__networkx_backend__ == "franken_networkx"
    assert _graph_contract(actual) == _graph_contract(expected)
    assert actual.graph is not source.graph
    assert actual.graph["payload"] is source.graph["payload"]
    for node in actual:
        assert actual.nodes[node] is not source.nodes[node]
        assert actual.nodes[node]["payload"] is source.nodes[node]["payload"]
    for u, v in actual.edges():
        assert actual[u][v] is not source[u][v]
        assert actual[u][v]["payload"] is source[u][v]["payload"]

    nodes_before = list(actual)
    edges_before = list(actual.edges())
    if nodes_before:
        source.remove_node(nodes_before[0])
        assert list(actual) == nodes_before
        assert list(actual.edges()) == edges_before
    actual.add_node("result-only")
    assert "result-only" not in source


@pytest.mark.parametrize("name", _ALGORITHMS)
def test_core_decomposition_backend_is_advertised(name):
    assert name in get_backend_info()["functions"]
    assert name in fnx_backend_info.get_backend_info()["functions"]
    assert BackendInterface.can_run(name, (_core_graph(nx),), _kwargs(name))


@pytest.mark.parametrize("name", _ALGORITHMS)
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native"])
def test_explicit_core_backend_preserves_results_and_attributes(name, input_kind):
    source = _core_graph(fnx if input_kind == "native" else nx)
    expected_source = _core_graph(nx)
    if input_kind == "cached-networkx":
        # A preceding structure-only algorithm must not discard the attributes
        # requested by a graph-returning decomposition.
        nx.core_number(source, backend="franken_networkx")
    expected = getattr(nx, name)(expected_source, backend="networkx", **_kwargs(name))
    actual = getattr(nx, name)(source, backend="franken_networkx", **_kwargs(name))
    if name == "onion_layers":
        assert list(actual.items()) == list(expected.items())
    else:
        _assert_independent_shallow_graph(actual, expected, source)


@pytest.mark.parametrize("name", _CORE_SUBGRAPHS)
@pytest.mark.parametrize("precomputed", [False, True])
def test_explicit_core_backend_supports_directed_core_subgraphs(name, precomputed):
    source = _core_graph(nx, directed=True)
    expected_source = _core_graph(nx, directed=True)
    kwargs = _kwargs(name)
    if precomputed:
        kwargs["core_number"] = nx.core_number(expected_source, backend="networkx")
    expected = getattr(nx, name)(expected_source, backend="networkx", **kwargs)
    actual = getattr(nx, name)(source, backend="franken_networkx", **kwargs)
    _assert_independent_shallow_graph(actual, expected, source)


@pytest.mark.parametrize("name", _GRAPH_RESULTS)
@pytest.mark.parametrize("k", [0, 2, 4])
def test_explicit_core_backend_handles_threshold_subsets(name, k):
    source = _core_graph(nx)
    expected_source = _core_graph(nx)
    kwargs = {"k": k}
    if name in _CORE_SUBGRAPHS:
        kwargs["core_number"] = nx.core_number(expected_source, backend="networkx")
    expected = getattr(nx, name)(expected_source, backend="networkx", **kwargs)
    actual = getattr(nx, name)(source, backend="franken_networkx", **kwargs)
    _assert_independent_shallow_graph(actual, expected, source)


@pytest.mark.parametrize("name", _ALGORITHMS)
@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
def test_explicit_core_backend_preserves_multigraph_errors(name, class_name):
    source = getattr(nx, class_name)()
    source.add_edge(0, 1)
    source.add_edge(0, 1)
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        getattr(nx, name)(source, backend="networkx", **_kwargs(name))
    with pytest.raises(nx.NetworkXNotImplemented) as actual:
        getattr(nx, name)(source, backend="franken_networkx", **_kwargs(name))
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("name", ["k_truss", "onion_layers"])
def test_explicit_core_backend_preserves_directed_errors(name):
    source = _core_graph(nx, directed=True)
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        getattr(nx, name)(source, backend="networkx", **_kwargs(name))
    with pytest.raises(nx.NetworkXNotImplemented) as actual:
        getattr(nx, name)(source, backend="franken_networkx", **_kwargs(name))
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("name", _ALGORITHMS)
def test_explicit_core_backend_preserves_self_loop_errors(name):
    source = nx.Graph([(0, 1), (1, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        getattr(nx, name)(source, backend="networkx", **_kwargs(name))
    with pytest.raises(nx.NetworkXNotImplemented) as actual:
        getattr(nx, name)(source, backend="franken_networkx", **_kwargs(name))
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("name", _ALGORITHMS)
def test_explicit_core_backend_handles_empty_graphs(name):
    source = nx.Graph()
    if name in ("k_core", "k_shell", "k_crust"):
        with pytest.raises(ValueError) as expected:
            getattr(nx, name)(source, backend="networkx")
        with pytest.raises(ValueError) as actual:
            getattr(nx, name)(source, backend="franken_networkx")
        assert actual.value.args == expected.value.args
    else:
        expected = getattr(nx, name)(source, backend="networkx", **_kwargs(name))
        actual = getattr(nx, name)(source, backend="franken_networkx", **_kwargs(name))
        if name == "onion_layers":
            assert actual == expected == {}
        else:
            assert _graph_contract(actual) == _graph_contract(expected)


@pytest.mark.parametrize("native_input", [False, True], ids=["networkx", "native"])
def test_core_number_backend_preserves_self_loop_error(native_input):
    expected_source = nx.Graph([(0, 1), (1, 1)])
    source = fnx.Graph() if native_input else nx.Graph()
    source.add_edges_from([(0, 1), (1, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.core_number(expected_source, backend="networkx")
    with pytest.raises(nx.NetworkXNotImplemented) as actual:
        nx.core_number(source, backend="franken_networkx")
    assert actual.value.args == expected.value.args
