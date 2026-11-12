"""Parity coverage for the ``franken_networkx.similarity`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "graph_edit_distance",
    "optimal_edit_paths",
    "optimize_graph_edit_distance",
    "optimize_edit_paths",
    "simrank_similarity",
    "panther_similarity",
    "panther_vector_similarity",
    "generate_random_paths",
)


def _build_path_pair(n):
    return fnx.path_graph(n), nx.path_graph(n)


def test_direct_similarity_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.similarity")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_similarity_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.similarity")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.similarity")

    assert via_algorithms is direct
    assert fnx.algorithms.similarity is direct


def test_similarity_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.similarity")
    expected = importlib.import_module("networkx.algorithms.similarity")

    assert set(module.__all__) == set(expected.__all__)


def test_similarity_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.similarity")
    expected = importlib.import_module("networkx.algorithms.similarity")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_edit_distance_wrappers_match_networkx_costs():
    module = importlib.import_module("franken_networkx.similarity")
    fnx_small, nx_small = _build_path_pair(2)
    fnx_large, nx_large = _build_path_pair(3)

    assert module.graph_edit_distance(fnx_small, fnx_large) == nx.graph_edit_distance(
        nx_small, nx_large
    )
    assert list(module.optimize_graph_edit_distance(fnx_small, fnx_large)) == list(
        nx.optimize_graph_edit_distance(nx_small, nx_large)
    )
    assert module.optimal_edit_paths(fnx_small, fnx_large)[-1] == (
        nx.optimal_edit_paths(nx_small, nx_large)[-1]
    )
    assert next(module.optimize_edit_paths(fnx_small, fnx_large))[-1] == (
        next(nx.optimize_edit_paths(nx_small, nx_large))[-1]
    )


def test_score_wrappers_match_networkx_for_seeded_cases():
    module = importlib.import_module("franken_networkx.similarity")
    fnx_graph, nx_graph = _build_path_pair(4)

    assert module.simrank_similarity(fnx_graph, source=0, target=1) == (
        nx.simrank_similarity(nx_graph, source=0, target=1)
    )
    assert module.panther_similarity(fnx_graph, 0, k=2, seed=42) == (
        nx.panther_similarity(nx_graph, 0, k=2, seed=42)
    )
    assert module.panther_vector_similarity(fnx_graph, 0, D=2, k=2, seed=42) == (
        nx.panther_vector_similarity(nx_graph, 0, D=2, k=2, seed=42)
    )


def test_generate_random_paths_wrapper_delegates_to_top_level():
    module = importlib.import_module("franken_networkx.similarity")
    fnx_graph, _ = _build_path_pair(4)

    assert list(module.generate_random_paths(fnx_graph, 2, seed=42)) == list(
        fnx.generate_random_paths(fnx_graph, 2, seed=42)
    )


def test_similarity_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.similarity")
    fnx_graph, _ = _build_path_pair(4)

    with pytest.raises(TypeError):
        module.simrank_similarity(fnx_graph, unsupported=True)
