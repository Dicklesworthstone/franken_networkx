"""Parity coverage for the ``franken_networkx.regular`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("is_regular", "is_k_regular", "k_factor")


def _graph_from_edges(module, edges):
    graph = module.Graph()
    graph.add_edges_from(edges)
    return graph


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def test_direct_regular_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.regular")
    expected = importlib.import_module("networkx.algorithms.regular")

    assert set(module.__all__) == set(expected.__all__)
    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_regular_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.regular")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.regular")

    assert via_algorithms is direct
    assert fnx.algorithms.regular is direct


@pytest.mark.parametrize("name", PUBLIC_FUNCTIONS)
def test_regular_module_routes_through_top_level_fnx(monkeypatch, name):
    module = importlib.import_module("franken_networkx.regular")
    algorithms_module = importlib.import_module("franken_networkx.algorithms.regular")
    marker = object()

    def sentinel(*args, **kwargs):
        return marker, args, kwargs

    monkeypatch.setattr(fnx, name, sentinel)

    if name == "is_regular":
        expected = (marker, ("graph",), {})
        assert module.is_regular("graph") == expected
        assert algorithms_module.is_regular("graph") == expected
    elif name == "is_k_regular":
        expected = (marker, ("graph", 2), {})
        assert module.is_k_regular("graph", 2) == expected
        assert algorithms_module.is_k_regular("graph", 2) == expected
    else:
        expected = (marker, ("graph", 1), {"matching_weight": "score"})
        assert module.k_factor("graph", 1, matching_weight="score") == expected
        assert algorithms_module.k_factor("graph", 1, matching_weight="score") == expected


@pytest.mark.parametrize("name", PUBLIC_FUNCTIONS)
def test_regular_module_function_is_not_networkx_version(name):
    module = importlib.import_module("franken_networkx.regular")
    expected = importlib.import_module("networkx.algorithms.regular")

    assert getattr(module, name) is not getattr(expected, name)


def test_regular_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.regular")
    expected = importlib.import_module("networkx.algorithms.regular")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "fnx_graph,nx_graph,k",
    [
        (fnx.cycle_graph(6), nx.cycle_graph(6), 2),
        (fnx.path_graph(4), nx.path_graph(4), 2),
        (fnx.complete_graph(5), nx.complete_graph(5), 4),
        (fnx.empty_graph(3), nx.empty_graph(3), 0),
    ],
)
def test_regular_predicates_match_networkx(fnx_graph, nx_graph, k):
    module = importlib.import_module("franken_networkx.regular")

    assert module.is_regular(fnx_graph) == nx.is_regular(nx_graph)
    assert module.is_k_regular(fnx_graph, k) == nx.is_k_regular(nx_graph, k)


@pytest.mark.parametrize(
    "name,edges,k",
    [
        ("cycle4_one_factor", [(0, 1), (1, 2), (2, 3), (3, 0)], 1),
        (
            "complete4_string_labels",
            [
                ("a", "b"),
                ("a", "c"),
                ("a", "d"),
                ("b", "c"),
                ("b", "d"),
                ("c", "d"),
            ],
            2,
        ),
    ],
)
def test_k_factor_matches_networkx_graph_contract(name, edges, k):
    module = importlib.import_module("franken_networkx.regular")
    fnx_graph = _graph_from_edges(fnx, edges)
    nx_graph = _graph_from_edges(nx, edges)

    actual = module.k_factor(fnx_graph, k)
    expected = nx.k_factor(nx_graph, k)

    assert isinstance(actual, fnx.Graph), name
    assert not actual.is_directed(), name
    assert not actual.is_multigraph(), name
    assert sorted(actual.nodes()) == sorted(expected.nodes()), name
    assert _canonical_edges(actual) == _canonical_edges(expected), name
    assert module.is_k_regular(actual, k) == nx.is_k_regular(expected, k), name


def test_k_factor_impossible_degree_raises_networkx_error():
    module = importlib.import_module("franken_networkx.regular")
    fnx_graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)

    with pytest.raises(nx.NetworkXException):
        nx.k_factor(nx_graph, 3)
    with pytest.raises(nx.NetworkXException):
        module.k_factor(fnx_graph, 3)
