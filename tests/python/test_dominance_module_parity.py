"""Parity coverage for the ``franken_networkx.dominance`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("immediate_dominators", "dominance_frontiers")


def _dominance_graph_pair():
    edges = [(1, 2), (1, 3), (2, 5), (3, 4), (4, 5), (5, 6)]
    fnx_graph = fnx.DiGraph(edges)
    nx_graph = nx.DiGraph(edges)
    return fnx_graph, nx_graph


def test_direct_dominance_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.dominance")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_dominance_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.dominance")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.dominance")

    assert via_algorithms is direct
    assert fnx.algorithms.dominance is direct


def test_dominance_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.dominance")
    expected = importlib.import_module("networkx.algorithms.dominance")

    assert set(module.__all__) == set(expected.__all__)


def test_dominance_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.dominance")
    expected = importlib.import_module("networkx.algorithms.dominance")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_dominance_values_match_networkx():
    module = importlib.import_module("franken_networkx.dominance")
    fnx_graph, nx_graph = _dominance_graph_pair()

    assert module.immediate_dominators(fnx_graph, 1) == nx.immediate_dominators(
        nx_graph, 1
    )
    assert module.dominance_frontiers(fnx_graph, 1) == nx.dominance_frontiers(
        nx_graph, 1
    )


def test_dominance_start_validation_matches_networkx():
    module = importlib.import_module("franken_networkx.dominance")
    fnx_graph, _ = _dominance_graph_pair()

    with pytest.raises(nx.NetworkXError, match="start is not in G"):
        module.immediate_dominators(fnx_graph, 99)
    with pytest.raises(nx.NetworkXError, match="start is not in G"):
        module.dominance_frontiers(fnx_graph, 99)


def test_dominance_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.dominance")
    fnx_graph, _ = _dominance_graph_pair()

    with pytest.raises(TypeError):
        module.immediate_dominators(fnx_graph, 1, unsupported=True)
