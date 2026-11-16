"""Parity coverage for the ``franken_networkx.covering`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("min_edge_cover", "is_edge_cover")


def test_direct_covering_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.covering")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_covering_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.covering")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.covering")

    assert via_algorithms is direct
    assert fnx.algorithms.covering is direct


def test_covering_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.covering")
    expected = importlib.import_module("networkx.algorithms.covering")

    assert set(module.__all__) == set(expected.__all__)


def test_covering_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.covering")
    expected = importlib.import_module("networkx.algorithms.covering")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_covering_values_match_networkx_on_path_graph():
    module = importlib.import_module("franken_networkx.covering")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    actual_cover = module.min_edge_cover(fnx_graph)
    expected_cover = nx.min_edge_cover(nx_graph)

    assert actual_cover == expected_cover
    assert module.is_edge_cover(fnx_graph, actual_cover)
    assert module.is_edge_cover(fnx_graph, {(0, 1)}) == nx.is_edge_cover(
        nx_graph, {(0, 1)}
    )


def test_covering_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.covering")
    graph = fnx.path_graph(2)

    with pytest.raises(TypeError):
        module.is_edge_cover(graph, {(0, 1)}, unsupported=True)


def _call_min_edge_cover(graph, matcher, route):
    if route == "backend":
        return nx.min_edge_cover(
            graph, matching_algorithm=matcher, backend="franken_networkx"
        )
    if route == "module":
        return importlib.import_module(
            "franken_networkx.covering"
        ).min_edge_cover(graph, matching_algorithm=matcher)
    return fnx.min_edge_cover(graph, matching_algorithm=matcher)


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
def test_min_edge_cover_empty_graph_does_not_call_matcher(route):
    graph = nx.Graph()
    calls = []

    def unexpected_matcher(received):
        calls.append(received)
        raise AssertionError("an empty graph must not invoke its matcher")

    assert nx.min_edge_cover(
        graph, unexpected_matcher, backend="networkx"
    ) == set()
    assert _call_min_edge_cover(graph, unexpected_matcher, route) == set()
    assert calls == []


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
@pytest.mark.parametrize("class_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_min_edge_cover_empty_graph_still_validates_graph_type(route, class_name):
    graph = getattr(nx, class_name)()
    calls = []

    def unexpected_matcher(received):
        calls.append(received)
        return set()

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.min_edge_cover(graph, unexpected_matcher, backend="networkx")
    with pytest.raises(nx.NetworkXNotImplemented) as actual:
        _call_min_edge_cover(graph, unexpected_matcher, route)
    assert str(actual.value) == str(expected.value)
    assert calls == []


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
def test_min_edge_cover_extends_and_returns_the_matcher_set(route):
    graph = nx.path_graph(3)
    matching = {(0, 1)}
    expected_matching = {(0, 1)}

    expected = nx.min_edge_cover(
        nx.path_graph(3),
        lambda graph: expected_matching,
        backend="networkx",
    )
    actual = _call_min_edge_cover(graph, lambda graph: matching, route)

    assert expected is expected_matching
    assert actual is matching
    assert matching == expected == {(0, 1), (1, 2)}


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
def test_min_edge_cover_completes_from_public_adjacency(route):
    class AdjacencyGraph(nx.Graph):
        def __getitem__(self, node):
            row = super().__getitem__(node)
            if node == 2:
                return {neighbor: row[neighbor] for neighbor in (1, 0)}
            return row

    graph = AdjacencyGraph([(0, 1), (0, 2), (1, 2)])
    expected_graph = AdjacencyGraph([(0, 1), (0, 2), (1, 2)])
    # The two public providers intentionally have different orders.
    assert list(graph.neighbors(2)) == [0, 1]
    assert list(graph[2]) == [1, 0]

    expected = nx.min_edge_cover(
        expected_graph, lambda graph: {(0, 1)}, backend="networkx"
    )
    actual = _call_min_edge_cover(graph, lambda graph: {(0, 1)}, route)

    assert actual == expected == {(0, 1), (1, 2)}


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
def test_min_edge_cover_uses_graph_iteration_after_matcher_changes_node_reader(route):
    def build():
        graph = nx.path_graph(3)

        def matcher(received):
            assert received is graph
            graph.nodes = lambda: ()
            return {(0, 1)}

        return graph, matcher

    graph, matcher = build()
    expected_graph, expected_matcher = build()
    expected = nx.min_edge_cover(
        expected_graph, expected_matcher, backend="networkx"
    )
    actual = _call_min_edge_cover(graph, matcher, route)

    assert actual == expected == {(0, 1), (1, 2)}
    assert list(graph) == [0, 1, 2]
    assert graph.nodes() == ()


@pytest.mark.parametrize("route", ["top-level", "module", "backend"])
def test_min_edge_cover_rejects_iterator_only_adjacency(route):
    class IteratorAdjacency(nx.Graph):
        def __getitem__(self, node):
            row = super().__getitem__(node)
            return iter(row) if node == 2 else row

    expected_graph = IteratorAdjacency([(0, 1), (1, 2)])
    graph = IteratorAdjacency([(0, 1), (1, 2)])
    with pytest.raises(ValueError, match="cannot return an arbitrary item from an iterator"):
        nx.min_edge_cover(
            expected_graph, lambda graph: {(0, 1)}, backend="networkx"
        )
    with pytest.raises(ValueError, match="cannot return an arbitrary item from an iterator"):
        _call_min_edge_cover(graph, lambda graph: {(0, 1)}, route)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("keyword", [False, True])
@pytest.mark.parametrize("as_dict", [False, True])
def test_min_edge_cover_backend_observes_matcher_topology_changes(
    cached, keyword, as_dict, monkeypatch
):
    def build():
        graph = nx.path_graph(4)
        calls = []
        matching = (
            {0: 1, 1: 0, 2: 3, 3: 2}
            if as_dict else {(0, 1), (2, 3)}
        )

        def matcher(received):
            calls.append(received is graph)
            # Change the caller through the closure so a detached backend
            # conversion would omit this new node from its completion step.
            graph.add_edge(3, 4)
            return matching

        return graph, matcher, calls, matching

    source, matcher, calls, matching = build()
    expected_source, expected_matcher, expected_calls, _ = build()
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    if cached:
        nx.relabel_nodes(source, {}, backend="franken_networkx")
        assert source.__networkx_cache__["backends"]["franken_networkx"]

    expected = nx.min_edge_cover(
        expected_source, expected_matcher, backend="networkx"
    )
    if keyword:
        actual = nx.min_edge_cover(
            source, matching_algorithm=matcher, backend="franken_networkx"
        )
    else:
        actual = nx.min_edge_cover(
            source, matcher, backend="franken_networkx"
        )

    ordinary_cover = {(0, 1), (2, 3), (3, 4)}
    want = (
        ordinary_cover | {(1, 0), (3, 2), (4, 3)}
        if as_dict else ordinary_cover
    )
    assert actual == expected == want
    assert calls == expected_calls == [True]
    assert list(source.edges) == list(expected_source.edges)
    assert nx.is_edge_cover(source, actual, backend="networkx")
    assert not source.__networkx_cache__.get("backends")
    if not as_dict:
        assert actual is matching


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("error_type", [ValueError, nx.NetworkXNotImplemented])
def test_min_edge_cover_backend_preserves_matcher_error_and_clears_caches(
    cached, error_type, monkeypatch
):
    source = nx.path_graph(4)
    source[0][1]["weight"] = 1
    failure = error_type("matcher refused the graph")
    calls = []
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    if cached:
        nx.relabel_nodes(source, {}, backend="franken_networkx")
        assert source.__networkx_cache__["backends"]["franken_networkx"]

    def matcher(received):
        assert received is source
        calls.append(True)
        # A nested backend call can install a new conversion while this
        # callback runs. An in-place attribute write does not clear it.
        nx.relabel_nodes(source, {}, backend="franken_networkx")
        assert source.__networkx_cache__["backends"]["franken_networkx"]
        source[0][1]["weight"] = 9
        raise failure

    with pytest.raises(error_type, match="^matcher refused the graph$") as caught:
        nx.min_edge_cover(
            source, matching_algorithm=matcher, backend="franken_networkx"
        )

    assert caught.value is failure
    assert calls == [True]
    assert source[0][1]["weight"] == 9
    assert not source.__networkx_cache__.get("backends")
