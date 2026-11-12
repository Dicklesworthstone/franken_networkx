"""Parity coverage for the ``franken_networkx.voronoi`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("voronoi_cells",)


def test_direct_voronoi_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.voronoi")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_voronoi_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.voronoi")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.voronoi")

    assert via_algorithms is direct
    assert fnx.algorithms.voronoi is direct


def test_voronoi_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.voronoi")
    expected = importlib.import_module("networkx.algorithms.voronoi")

    assert set(module.__all__) == set(expected.__all__)


def test_voronoi_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.voronoi")
    expected = importlib.import_module("networkx.algorithms.voronoi")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_voronoi_cells_values_match_networkx():
    module = importlib.import_module("franken_networkx.voronoi")
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    assert module.voronoi_cells(fnx_graph, {0, 4}) == nx.voronoi_cells(
        nx_graph, {0, 4}
    )


def test_voronoi_cells_weighted_values_match_networkx():
    module = importlib.import_module("franken_networkx.voronoi")
    fnx_graph = fnx.Graph()
    fnx_graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1), (0, 2, 10)])
    nx_graph = nx.Graph()
    nx_graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1), (0, 2, 10)])

    assert module.voronoi_cells(fnx_graph, {0, 2}, weight="weight") == (
        nx.voronoi_cells(nx_graph, {0, 2}, weight="weight")
    )


def test_voronoi_cells_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.voronoi")
    graph = fnx.path_graph(4)

    with pytest.raises(TypeError):
        module.voronoi_cells(graph, {0}, unsupported=True)
