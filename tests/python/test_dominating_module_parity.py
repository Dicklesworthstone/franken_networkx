"""Parity coverage for the ``franken_networkx.dominating`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "dominating_set",
    "is_dominating_set",
    "connected_dominating_set",
    "is_connected_dominating_set",
)


def test_direct_dominating_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.dominating")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_dominating_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.dominating")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.dominating")

    assert via_algorithms is direct
    assert fnx.algorithms.dominating is direct


def test_dominating_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.dominating")
    expected = importlib.import_module("networkx.algorithms.dominating")

    assert set(module.__all__) == set(expected.__all__)


def test_dominating_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.dominating")
    expected = importlib.import_module("networkx.algorithms.dominating")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_dominating_values_match_networkx_on_path_graph():
    module = importlib.import_module("franken_networkx.dominating")
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    dominating_nodes = {0, 2, 4}
    connected_nodes = {1, 2, 3}

    assert module.dominating_set(fnx_graph, start_with=0) == nx.dominating_set(
        nx_graph, start_with=0
    )
    assert module.is_dominating_set(
        fnx_graph, dominating_nodes
    ) == nx.is_dominating_set(nx_graph, dominating_nodes)
    assert module.connected_dominating_set(
        fnx_graph
    ) == nx.connected_dominating_set(nx_graph)
    assert module.is_connected_dominating_set(
        fnx_graph, connected_nodes
    ) == nx.is_connected_dominating_set(nx_graph, connected_nodes)


def test_dominating_start_validation_matches_networkx():
    module = importlib.import_module("franken_networkx.dominating")
    graph = fnx.path_graph(3)

    with pytest.raises(nx.NetworkXError, match="node 99 is not in G"):
        module.dominating_set(graph, start_with=99)


def test_dominating_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.dominating")
    graph = fnx.path_graph(3)

    with pytest.raises(TypeError):
        module.is_dominating_set(graph, {0, 2}, unsupported=True)
