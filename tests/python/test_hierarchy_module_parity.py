"""Parity coverage for the ``franken_networkx.hierarchy`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("flow_hierarchy",)


def _flow_graph_pair():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    fnx_graph = fnx.DiGraph(edges)
    nx_graph = nx.DiGraph(edges)
    return fnx_graph, nx_graph


def test_direct_hierarchy_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.hierarchy")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_hierarchy_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.hierarchy")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.hierarchy")

    assert via_algorithms is direct
    assert fnx.algorithms.hierarchy is direct


def test_hierarchy_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.hierarchy")
    expected = importlib.import_module("networkx.algorithms.hierarchy")

    assert set(module.__all__) == set(expected.__all__)


def test_hierarchy_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.hierarchy")
    expected = importlib.import_module("networkx.algorithms.hierarchy")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_flow_hierarchy_values_match_networkx():
    module = importlib.import_module("franken_networkx.hierarchy")
    fnx_graph, nx_graph = _flow_graph_pair()

    assert module.flow_hierarchy(fnx_graph) == pytest.approx(
        nx.flow_hierarchy(nx_graph)
    )


def test_flow_hierarchy_error_messages_match_networkx():
    module = importlib.import_module("franken_networkx.hierarchy")

    with pytest.raises(nx.NetworkXError, match="G must be a digraph"):
        module.flow_hierarchy(fnx.path_graph(3))
    with pytest.raises(nx.NetworkXError, match="not applicable to empty graphs"):
        module.flow_hierarchy(fnx.DiGraph())


def test_hierarchy_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.hierarchy")
    graph, _ = _flow_graph_pair()

    with pytest.raises(TypeError):
        module.flow_hierarchy(graph, unsupported=True)
