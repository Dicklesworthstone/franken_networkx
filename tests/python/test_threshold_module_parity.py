"""Parity coverage for the ``franken_networkx.threshold`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest

PUBLIC_FUNCTIONS = (
    "is_threshold_graph",
    "find_threshold_graph",
    "threshold_graph",
    "find_creation_sequence",
    "find_alternating_4_cycle",
)


def _graph_from_edges(module, edges):
    graph = module.Graph()
    graph.add_edges_from(edges)
    return graph


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def _assert_same_graph(actual, expected):
    assert isinstance(actual, fnx.Graph)
    assert not actual.is_directed()
    assert not actual.is_multigraph()
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert _canonical_edges(actual) == _canonical_edges(expected)


def test_direct_threshold_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.threshold")
    expected = importlib.import_module("networkx.algorithms.threshold")

    assert set(module.__all__) == set(expected.__all__)
    for name in set(expected.__all__) | set(PUBLIC_FUNCTIONS):
        assert callable(getattr(module, name))


def test_algorithms_threshold_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.threshold")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.threshold")

    assert via_algorithms is direct
    assert fnx.algorithms.threshold is direct


def test_threshold_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.threshold")
    expected = importlib.import_module("networkx.algorithms.threshold")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: {actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "sequence",
    [
        ["d", "i", "d", "d", "i"],
        [(1, "d"), (3, "i"), (2, "d"), (0, "i")],
    ],
)
def test_threshold_graph_matches_networkx_and_returns_fnx_graph(sequence):
    module = importlib.import_module("franken_networkx.threshold")

    actual = module.threshold_graph(sequence)
    expected = nx.threshold_graph(sequence)

    _assert_same_graph(actual, expected)
    assert module.is_threshold_graph(actual) == nx.is_threshold_graph(expected)


def test_find_threshold_graph_matches_networkx_and_returns_fnx_graph():
    module = importlib.import_module("franken_networkx.threshold")
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3)]
    fnx_graph = _graph_from_edges(fnx, edges)
    nx_graph = _graph_from_edges(nx, edges)

    actual = module.find_threshold_graph(fnx_graph)
    expected = nx.find_threshold_graph(nx_graph)

    _assert_same_graph(actual, expected)
    assert module.is_threshold_graph(actual) == nx.is_threshold_graph(expected)


def test_creation_sequence_and_alternating_cycle_match_networkx():
    module = importlib.import_module("franken_networkx.threshold")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.find_creation_sequence(fnx_graph) == nx.find_creation_sequence(
        nx_graph
    )
    assert module.find_alternating_4_cycle(fnx_graph) == nx.find_alternating_4_cycle(
        nx_graph
    )


def test_threshold_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.threshold")

    with pytest.raises(TypeError):
        module.is_threshold_graph(fnx.path_graph(4), unsupported=True)
