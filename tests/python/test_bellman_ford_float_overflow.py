"""Finite edge weights must keep Bellman-Ford's reachability and cycle semantics."""

from collections.abc import Iterator
import math

import networkx as nx
import pytest

import franken_networkx as fnx


GRAPH_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED_TYPES = ["DiGraph", "MultiDiGraph"]
ROUTES = ["native", "networkx_input", "backend"]


def _graph(module, graph_type, edges, *, isolates=0):
    graph = getattr(module, graph_type)()
    graph.add_weighted_edges_from(edges)
    if graph.is_multigraph():
        # Exercise the minimum-parallel-edge projection without introducing
        # an infinite input edge or changing the problem's numeric domain.
        for u, v, weight in edges:
            graph.add_edge(u, v, weight=weight)
    graph.add_nodes_from(f"isolate-{index}" for index in range(isolates))
    return graph


def _ordered_typed(value):
    if isinstance(value, Iterator):
        value = list(value)
    if isinstance(value, dict):
        return [(node, _ordered_typed(item)) for node, item in value.items()]
    if isinstance(value, (tuple, list)):
        return type(value).__name__, [_ordered_typed(item) for item in value]
    return type(value).__name__, repr(value)


def _outcome(module, name, graph, args, kwargs):
    try:
        return "return", _ordered_typed(getattr(module, name)(graph, *args, **kwargs))
    except Exception as error:
        return "raise", type(error).__name__, str(error)


def _assert_queries_match(route, graph_type, edges, *, isolates=0):
    reference = _graph(nx, graph_type, edges, isolates=isolates)
    actual = _graph(fnx if route == "native" else nx, graph_type, edges, isolates=isolates)
    module = nx if route == "backend" else fnx
    dispatch = {"backend": "franken_networkx"} if route == "backend" else {}
    weighted = {"weight": "weight", "method": "bellman-ford"}
    queries = [
        ("single_source_bellman_ford", ("s",), {}),
        ("single_source_bellman_ford_path", ("s",), {}),
        ("single_source_bellman_ford_path_length", ("s",), {}),
        ("bellman_ford_path", ("s", "t"), {}),
        ("bellman_ford_path_length", ("s", "t"), {}),
        ("single_source_bellman_ford", ("s",), {"target": "t"}),
        ("shortest_path", (), {"source": "s", **weighted}),
        ("shortest_path_length", (), {"source": "s", **weighted}),
        ("shortest_path", (), {"target": "t", **weighted}),
        ("shortest_path_length", (), {"target": "t", **weighted}),
        ("shortest_path", ("s", "t"), weighted),
        ("shortest_path_length", ("s", "t"), weighted),
        ("all_pairs_bellman_ford_path", (), {}),
        ("all_pairs_bellman_ford_path_length", (), {}),
        ("shortest_path", (), weighted),
        ("shortest_path_length", (), weighted),
    ]
    for name, args, kwargs in queries:
        expected = _outcome(nx, name, reference, args, kwargs)
        result = _outcome(module, name, actual, args, {**kwargs, **dispatch})
        assert result == expected, (name, args, kwargs, result, expected)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("route", ROUTES)
def test_positive_finite_overflow_is_not_a_reachable_distance_or_negative_cycle(
    graph_type, route
):
    edges = [("s", "a", 1e308), ("a", "b", 1e308), ("b", "t", 1)]
    reference = _graph(nx, graph_type, edges)
    # The graph is topologically connected. Bellman-Ford's strict relaxation
    # excludes +inf, unlike Dijkstra, which retains reached infinite distances.
    assert nx.single_source_bellman_ford_path_length(reference, "s") == {"s": 0, "a": 1e308}
    assert nx.dijkstra_path_length(reference, "s", "t") == math.inf
    _assert_queries_match(route, graph_type, edges)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("route", ROUTES)
def test_later_finite_alternative_discovers_each_vertex_once(graph_type, route):
    edges = [
        ("s", "a", 1e308),
        ("a", "b", 1e308),
        ("s", "c", 3),
        ("c", "b", 4),
        ("b", "t", 1),
    ]
    reference = _graph(nx, graph_type, edges)
    assert list(nx.single_source_bellman_ford_path_length(reference, "s")) == [
        "s", "a", "c", "b", "t"
    ]
    assert nx.single_source_bellman_ford(reference, "s", "t") == (8, ["s", "c", "b", "t"])
    _assert_queries_match(route, graph_type, edges)


@pytest.mark.parametrize("graph_type", DIRECTED_TYPES)
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("positive_cycle", [False, True])
def test_negative_infinity_ties_keep_first_paths_without_false_cycles(
    graph_type, route, positive_cycle
):
    edges = [
        ("s", "a", -1e308),
        ("a", "b", -1e308),
        ("a", "c", -1e308),
        ("b", "t", 3),
        ("c", "t", 2),
    ]
    if positive_cycle:
        edges.append(("t", "b", 1))
    reference = _graph(nx, graph_type, edges)
    assert nx.single_source_bellman_ford(reference, "s", "t") == (
        -math.inf, ["s", "a", "b", "t"]
    )
    _assert_queries_match(route, graph_type, edges)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("weight", [-1, -1e308])
def test_recent_negative_cycles_are_detected_with_many_unrelated_nodes(
    graph_type, route, weight
):
    edges = [("s", "a", weight), ("a", "t", 2)]
    if graph_type in DIRECTED_TYPES:
        edges.append(("a", "s", 0))
    reference = _graph(nx, graph_type, edges, isolates=32)
    with pytest.raises(nx.NetworkXUnbounded, match="Negative cycle detected"):
        nx.single_source_bellman_ford_path_length(reference, "s")
    _assert_queries_match(route, graph_type, edges, isolates=32)


@pytest.mark.parametrize("graph_type", DIRECTED_TYPES)
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("rounding", ["overflow", "finite", "alternate_predecessor"])
def test_cyclic_selected_parents_keep_lengths_and_search_complete_predecessors(
    graph_type, route, rounding
):
    if rounding == "overflow":
        edges = [("s", "a", 0), ("a", "b", -1e308), ("b", "t", -1e308), ("t", "a", 0)]
    elif rounding == "finite":
        edges = [("s", "a", 1), ("a", "b", -1e308), ("b", "t", 1e308), ("t", "a", -0.5)]
    else:
        # The first selected parents contain a cycle, but pred[a]'s second
        # entry provides a valid source-rooted path. A cycle guard must ask
        # the complete predecessor search, rather than report no path itself.
        edges = [
            ("s", "a", 1), ("s", "x", 0), ("a", "b", -1e308),
            ("x", "y", 0), ("b", "t", 1e308), ("y", "z", 0),
            ("t", "a", -0.5), ("z", "a", -0.5),
        ]
    reference = _graph(nx, graph_type, edges)
    lengths = nx.single_source_bellman_ford_path_length(reference, "s")
    assert lengths["t"] == (-math.inf if rounding == "overflow" else 0.0)
    if rounding == "alternate_predecessor":
        assert nx.bellman_ford_path(reference, "s", "t") == ["s", "x", "y", "z", "a", "b", "t"]
    else:
        with pytest.raises(StopIteration):
            nx.bellman_ford_path(reference, "s", "t")
    _assert_queries_match(route, graph_type, edges)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_weight_mutation_changes_overflow_reachability(graph_type):
    edges = [("s", "a", 1e308), ("a", "b", 1), ("b", "t", 1)]
    actual = _graph(fnx, graph_type, edges)
    reference = _graph(nx, graph_type, edges)
    for weight in (1, 1e308, 1):
        for graph in (actual, reference):
            attrs = graph["a"]["b"]
            rows = attrs.values() if graph.is_multigraph() else [attrs]
            for row in rows:
                row["weight"] = weight
        assert _outcome(fnx, "single_source_bellman_ford_path_length", actual, ("s",), {}) == _outcome(
            nx, "single_source_bellman_ford_path_length", reference, ("s",), {}
        )


@pytest.mark.parametrize("graph_type", DIRECTED_TYPES)
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("source_change", [-1.0, -1e-308])
def test_rounded_source_improvements_preserve_each_descendants_numeric_type(
    graph_type, route, source_change
):
    edges = [
        ("s", "a", 1), ("a", "b", -1e308), ("b", "t", 1e308),
        ("t", "a", source_change), ("a", "u", 2), ("u", "v", 2),
    ]
    reference = _graph(nx, graph_type, edges)
    expected_distances, expected_paths = nx.single_source_bellman_ford(reference, "a")
    assert expected_distances["a"] == source_change
    assert type(expected_distances["a"]) is float
    assert expected_paths["a"] == ["a"]
    # A tiny source improvement rounds away on the integer branches. A larger
    # improvement changes their distances and changes their types to float.
    descendant_type = float if source_change == -1.0 else int
    assert type(expected_distances["u"]) is descendant_type
    assert type(expected_distances["v"]) is descendant_type

    actual = _graph(fnx if route == "native" else nx, graph_type, edges)
    module = nx if route == "backend" else fnx
    kwargs = {"backend": "franken_networkx"} if route == "backend" else {}
    result = module.single_source_bellman_ford(actual, "a", **kwargs)
    assert _ordered_typed(result) == _ordered_typed((expected_distances, expected_paths))
