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
