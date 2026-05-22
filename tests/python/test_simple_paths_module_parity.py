"""Parity coverage for the ``franken_networkx.simple_paths`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "all_simple_paths",
    "is_simple_path",
    "shortest_simple_paths",
    "all_simple_edge_paths",
)


def _build_pair():
    weighted_edges = [
        (0, 1, 1),
        (0, 2, 2),
        (1, 3, 1),
        (2, 3, 1),
        (1, 2, 3),
    ]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def test_direct_simple_paths_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.simple_paths")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_simple_paths_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.simple_paths")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.simple_paths")

    assert via_algorithms is direct
    assert fnx.algorithms.simple_paths is direct


def test_simple_paths_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    expected = importlib.import_module("networkx.algorithms.simple_paths")

    assert set(module.__all__) == set(expected.__all__)


def test_simple_paths_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    expected = importlib.import_module("networkx.algorithms.simple_paths")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_simple_path_generators_match_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, nx_graph = _build_pair()

    assert list(module.all_simple_paths(fnx_graph, 0, 3, cutoff=3)) == list(
        nx.all_simple_paths(nx_graph, 0, 3, cutoff=3)
    )
    assert list(module.shortest_simple_paths(fnx_graph, 0, 3)) == list(
        nx.shortest_simple_paths(nx_graph, 0, 3)
    )
    assert list(module.all_simple_edge_paths(fnx_graph, 0, 3, cutoff=3)) == list(
        nx.all_simple_edge_paths(nx_graph, 0, 3, cutoff=3)
    )


def test_is_simple_path_matches_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, nx_graph = _build_pair()

    for nodes in ([0, 1, 3], [0, 3], [0, 1, 0]):
        assert module.is_simple_path(fnx_graph, nodes) == nx.is_simple_path(
            nx_graph, nodes
        )


def test_simple_paths_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.is_simple_path(fnx_graph, [0, 1], unsupported=True)
