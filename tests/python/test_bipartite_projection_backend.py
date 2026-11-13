"""Backend access to bipartite projections, with original input semantics."""

from dataclasses import dataclass
from fractions import Fraction

import franken_networkx as fnx
import franken_networkx.backend as fnx_backend
import networkx as nx
import pytest


PROJECTIONS = (
    "projected_graph",
    "weighted_projected_graph",
    "collaboration_weighted_projected_graph",
    "generic_weighted_projected_graph",
    "overlap_weighted_projected_graph",
)


@dataclass(frozen=True)
class _Label:
    value: str


def _input_graph(directed=False, custom_nodes=False):
    label = _Label if custom_nodes else str
    top = [label(value) for value in ("a", "b", "c")]
    bottom = [label(value) for value in ("x", "y", "z")]
    a, b, c = top
    x, y, z = bottom
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.graph.update(title="affiliations", payload={"shared": []})
    graph.add_nodes_from((node, {"side": 0, "payload": [node]}) for node in top)
    graph.add_nodes_from((node, {"side": 1}) for node in bottom)
    graph.nodes[a][None] = "literal None attribute"
    graph.nodes[b][("field", "rank")] = 2
    edges = (
        [(a, x), (x, b), (a, y), (y, b), (b, z), (z, c), (c, x), (x, a)]
        if directed else [(a, x), (b, x), (a, y), (b, y), (b, z), (c, z)]
    )
    for index, (u, v) in enumerate(edges):
        graph.add_edge(u, v, strength=Fraction(index + 1, 2))
    return graph, top, bottom


def _warm_conversion(graph):
    nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _snapshot(graph):
    edges = (
        list(graph.edges(keys=True, data=True))
        if graph.is_multigraph() else list(graph.edges(data=True))
    )
    return (
        graph.is_directed(), graph.is_multigraph(), dict(graph.graph),
        list(graph.nodes(data=True)), edges,
    )


@pytest.mark.parametrize("name", PROJECTIONS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("custom_nodes", [False, True])
@pytest.mark.parametrize("prewarm", [False, True])
@pytest.mark.parametrize("keyword_arguments", [False, True])
def test_backend_projection_preserves_graph_and_node_metadata(
    name, directed, custom_nodes, prewarm, keyword_arguments
):
    graph, top, _ = _input_graph(directed, custom_nodes)
    if prewarm:
        _warm_conversion(graph)
    # These writes deliberately leave any earlier backend conversion stale.
    graph.graph["title"] = "updated affiliations"
    graph.nodes[top[0]]["side"] = "updated node"
    projection = getattr(nx.bipartite, name)
    expected = projection(graph, top, backend="networkx")
    if keyword_arguments:
        actual = projection(B=graph, nodes=top, backend="franken_networkx")
    else:
        actual = projection(graph, top, backend="franken_networkx")
    assert isinstance(actual, fnx.DiGraph if directed else fnx.Graph)
    assert _snapshot(actual) == _snapshot(expected)
    assert actual.graph["payload"] is graph.graph["payload"]
    assert actual.nodes[top[0]]["payload"] is graph.nodes[top[0]]["payload"]


@pytest.mark.parametrize(
    "name,options",
    [
        ("projected_graph", {"multigraph": True}),
        ("weighted_projected_graph", {"ratio": True}),
        ("overlap_weighted_projected_graph", {"jaccard": False}),
    ],
)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("prewarm", [False, True])
def test_backend_projection_options_match_networkx(name, options, directed, prewarm):
    graph, top, _ = _input_graph(directed, custom_nodes=True)
    if prewarm:
        _warm_conversion(graph)
    projection = getattr(nx.bipartite, name)
    expected = projection(graph, top, backend="networkx", **options)
    actual = projection(graph, top, backend="franken_networkx", **options)
    assert _snapshot(actual) == _snapshot(expected)
    if options.get("multigraph"):
        assert isinstance(actual, fnx.MultiDiGraph if directed else fnx.MultiGraph)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("prewarm", [False, True])
@pytest.mark.parametrize("keyword_arguments", [False, True])
def test_backend_projection_callback_receives_original_weighted_graph(
    directed, prewarm, keyword_arguments
):
    outcomes = []
    for backend_name in ("networkx", "franken_networkx"):
        graph, top, _ = _input_graph(directed, custom_nodes=True)
        graph.graph["callback_calls"] = 0
        if prewarm and backend_name == "franken_networkx":
            _warm_conversion(graph)
        visits = []

        def weight_function(received, u, v, graph=graph, visits=visits):
            assert received is graph
            visits.append((u, v))
            received.graph["callback_calls"] += 1
            predecessors = received.pred[v] if directed else received[v]
            return sum(
                (received[u][neighbor]["strength"]
                 for neighbor in set(received[u]) & set(predecessors)),
                Fraction(0),
            )

        projection = nx.bipartite.generic_weighted_projected_graph
        if keyword_arguments:
            result = projection(
                B=graph, nodes=top, weight_function=weight_function, backend=backend_name
            )
        else:
            result = projection(graph, top, weight_function, backend=backend_name)
        assert visits
        assert graph.graph["callback_calls"] == len(visits)
        assert all(type(data["weight"]) is Fraction for _, _, data in result.edges(data=True))
        if backend_name == "franken_networkx":
            # A later conversion must observe the callback's direct writes.
            copied = nx.convert_node_labels_to_integers(graph, backend=backend_name)
            assert copied.graph["callback_calls"] == len(visits)
        outcomes.append((_snapshot(result), visits))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", PROJECTIONS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("prewarm", [False, True])
def test_backend_projection_observes_live_filtered_graph(name, directed, prewarm):
    graph, top, _ = _input_graph(directed)
    graph.add_edge(top[0], "hidden")
    graph.add_edge("hidden", top[2])
    state = {"include_hidden": False}
    view = nx.subgraph_view(
        graph, filter_node=lambda node: node != "hidden" or state["include_hidden"]
    )
    if prewarm:
        _warm_conversion(view)
    state["include_hidden"] = True
    projection = getattr(nx.bipartite, name)
    expected = projection(view, top, backend="networkx")
    actual = projection(view, top, backend="franken_networkx")
    assert actual.has_edge(top[0], top[2])
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("name", PROJECTIONS)
@pytest.mark.parametrize("kind", ["multigraph", "multidigraph", "missing_node"])
def test_backend_projection_errors_match_networkx(name, kind):
    if kind == "missing_node":
        graph, top, _ = _input_graph()
        top.append("absent")
    else:
        graph = nx.MultiDiGraph() if kind == "multidigraph" else nx.MultiGraph()
        graph.add_edges_from([("a", "x"), ("b", "x")])
        top = ["a", "b"]
    projection = getattr(nx.bipartite, name)
    with pytest.raises(Exception) as expected:
        projection(graph, top, backend="networkx")
    with pytest.raises(type(expected.value)) as actual:
        projection(graph, top, backend="franken_networkx")
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("ratio", [False, True])
def test_backend_weighted_projection_rejects_invalid_partition(ratio):
    graph, _, _ = _input_graph()
    nodes = list(graph)
    with pytest.raises(nx.NetworkXAlgorithmError) as expected:
        nx.bipartite.weighted_projected_graph(graph, nodes, ratio, backend="networkx")
    with pytest.raises(nx.NetworkXAlgorithmError) as actual:
        nx.bipartite.weighted_projected_graph(
            graph, nodes, ratio, backend="franken_networkx"
        )
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("name", PROJECTIONS)
@pytest.mark.parametrize("directed", [False, True])
def test_backend_projection_keeps_explicit_native_graph(name, directed):
    original, top, bottom = _input_graph(directed)
    graph = fnx_backend.BackendInterface.convert_from_nx(
        original, preserve_all_attrs=True, name=name
    )
    graph.add_edge(top[0], bottom[2], strength=7)
    oracle_graph = original.copy()
    oracle_graph.add_edge(top[0], bottom[2], strength=7)
    projection = getattr(nx.bipartite, name)
    expected = projection(oracle_graph, top, backend="networkx")
    actual = projection(graph, top, backend="franken_networkx")
    assert actual.has_edge(top[0], top[2])
    assert not original.has_edge(top[0], bottom[2])
    assert _snapshot(actual) == _snapshot(expected)
