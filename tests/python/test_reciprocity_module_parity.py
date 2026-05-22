"""Parity coverage for the ``franken_networkx.reciprocity`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("reciprocity", "overall_reciprocity")


def test_direct_reciprocity_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.reciprocity")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_reciprocity_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.reciprocity")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.reciprocity")

    assert via_algorithms is direct
    assert fnx.algorithms.reciprocity is direct.reciprocity


def test_reciprocity_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.reciprocity")
    expected = importlib.import_module("networkx.algorithms.reciprocity")

    assert set(module.__all__) == set(expected.__all__)


def test_reciprocity_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.reciprocity")
    expected = importlib.import_module("networkx.algorithms.reciprocity")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_reciprocity_values_match_networkx():
    module = importlib.import_module("franken_networkx.reciprocity")
    fnx_graph = fnx.DiGraph()
    fnx_graph.add_edges_from([(0, 1), (1, 0), (1, 2)])
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1), (1, 0), (1, 2)])

    assert module.reciprocity(fnx_graph) == nx.reciprocity(nx_graph)
    assert module.reciprocity(fnx_graph, nodes=[0, 1, 2]) == nx.reciprocity(
        nx_graph,
        nodes=[0, 1, 2],
    )
    assert fnx.reciprocity(fnx_graph) == nx.reciprocity(nx_graph)


def test_overall_reciprocity_values_match_networkx():
    module = importlib.import_module("franken_networkx.reciprocity")
    fnx_graph = fnx.DiGraph()
    fnx_graph.add_edges_from([(0, 1), (1, 0), (1, 2)])
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1), (1, 0), (1, 2)])

    assert module.overall_reciprocity(fnx_graph) == nx.overall_reciprocity(
        nx_graph
    )


def test_reciprocity_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.reciprocity")
    graph = fnx.DiGraph([(0, 1), (1, 0)])

    with pytest.raises(TypeError):
        module.reciprocity(graph, unsupported=True)
