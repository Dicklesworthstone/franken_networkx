"""Parity coverage for the ``franken_networkx.perfect_graph`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("is_perfect_graph",)


def test_direct_perfect_graph_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.perfect_graph")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_perfect_graph_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.perfect_graph")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.perfect_graph"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.perfect_graph is direct


def test_perfect_graph_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.perfect_graph")
    expected = importlib.import_module("networkx.algorithms.perfect_graph")

    assert set(module.__all__) == set(expected.__all__)


def test_is_perfect_graph_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.perfect_graph")
    expected = importlib.import_module("networkx.algorithms.perfect_graph")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_is_perfect_graph_true_case_matches_networkx():
    module = importlib.import_module("franken_networkx.perfect_graph")
    fnx_graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)

    assert module.is_perfect_graph(fnx_graph) == nx.is_perfect_graph(nx_graph)


def test_is_perfect_graph_false_case_matches_networkx():
    module = importlib.import_module("franken_networkx.perfect_graph")
    fnx_graph = fnx.cycle_graph(5)
    nx_graph = nx.cycle_graph(5)

    assert module.is_perfect_graph(fnx_graph) == nx.is_perfect_graph(nx_graph)


def test_is_perfect_graph_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.perfect_graph")
    graph = fnx.cycle_graph(4)

    with pytest.raises(TypeError):
        module.is_perfect_graph(graph, unsupported=True)
