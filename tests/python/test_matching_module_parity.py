"""Parity coverage for the ``franken_networkx.matching`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_matching",
    "is_maximal_matching",
    "is_perfect_matching",
    "max_weight_matching",
    "min_weight_matching",
    "maximal_matching",
)


def _build_pair():
    weighted_edges = [
        (0, 1, 5),
        (1, 2, 6),
        (2, 3, 5),
        (0, 3, 1),
    ]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def _normalized_edges(edges):
    return {frozenset(edge) for edge in edges}


def test_direct_matching_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.matching")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_matching_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.matching")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.matching")

    assert via_algorithms is direct
    assert fnx.algorithms.matching is direct


def test_matching_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.matching")
    expected = importlib.import_module("networkx.algorithms.matching")

    assert set(module.__all__) == set(expected.__all__)


def test_matching_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    expected = importlib.import_module("networkx.algorithms.matching")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_matching_predicates_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, nx_graph = _build_pair()
    matching = {(0, 1), (2, 3)}

    assert module.is_matching(fnx_graph, matching) == nx.is_matching(
        nx_graph, matching
    )
    assert module.is_maximal_matching(fnx_graph, matching) == nx.is_maximal_matching(
        nx_graph, matching
    )
    assert module.is_perfect_matching(fnx_graph, matching) == nx.is_perfect_matching(
        nx_graph, matching
    )


def test_matching_constructors_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, nx_graph = _build_pair()

    assert _normalized_edges(module.max_weight_matching(fnx_graph)) == _normalized_edges(
        nx.max_weight_matching(nx_graph)
    )
    assert _normalized_edges(module.min_weight_matching(fnx_graph)) == _normalized_edges(
        nx.min_weight_matching(nx_graph)
    )
    assert _normalized_edges(module.maximal_matching(fnx_graph)) == _normalized_edges(
        nx.maximal_matching(nx_graph)
    )


def test_matching_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.maximal_matching(fnx_graph, unsupported=True)
