"""Parity coverage for the ``franken_networkx.walks`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("number_of_walks",)


def test_direct_walks_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.walks")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_walks_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.walks")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.walks")

    assert via_algorithms is direct
    assert fnx.algorithms.walks is direct


def test_walks_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.walks")
    expected = importlib.import_module("networkx.algorithms.walks")

    assert set(module.__all__) == set(expected.__all__)


def test_number_of_walks_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.walks")
    expected = importlib.import_module("networkx.algorithms.walks")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_number_of_walks_values_match_networkx():
    module = importlib.import_module("franken_networkx.walks")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.number_of_walks(fnx_graph, 2) == nx.number_of_walks(nx_graph, 2)


def test_number_of_walks_directed_values_match_networkx():
    module = importlib.import_module("franken_networkx.walks")
    fnx_graph = fnx.DiGraph()
    fnx_graph.add_edges_from([(0, 1), (1, 2), (0, 2)])
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1), (1, 2), (0, 2)])

    assert module.number_of_walks(fnx_graph, 2) == nx.number_of_walks(nx_graph, 2)


def test_number_of_walks_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.walks")
    graph = fnx.path_graph(4)

    with pytest.raises(TypeError):
        module.number_of_walks(graph, 2, unsupported=True)
