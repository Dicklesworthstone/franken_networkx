"""Parity coverage for the ``franken_networkx.isolate`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("is_isolate", "isolates", "number_of_isolates")


def _graph_pair_with_isolates():
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    edges = [(0, 1), (1, 2), (3, 4)]
    nodes = range(8)
    fnx_graph.add_nodes_from(nodes)
    nx_graph.add_nodes_from(nodes)
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def test_direct_isolate_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.isolate")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_isolate_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.isolate")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.isolate")

    assert via_algorithms is direct
    assert fnx.algorithms.isolate is direct


def test_isolate_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.isolate")
    expected = importlib.import_module("networkx.algorithms.isolate")

    assert set(module.__all__) == set(expected.__all__)


def test_isolate_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.isolate")
    expected = importlib.import_module("networkx.algorithms.isolate")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_isolate_values_match_networkx():
    module = importlib.import_module("franken_networkx.isolate")
    fnx_graph, nx_graph = _graph_pair_with_isolates()

    assert list(module.isolates(fnx_graph)) == list(nx.isolates(nx_graph))
    assert module.number_of_isolates(fnx_graph) == nx.number_of_isolates(nx_graph)
    for node in fnx_graph:
        assert module.is_isolate(fnx_graph, node) == nx.is_isolate(nx_graph, node)


def test_isolates_remains_lazy_like_top_level_wrapper():
    module = importlib.import_module("franken_networkx.isolate")
    fnx_graph, _ = _graph_pair_with_isolates()

    result = module.isolates(fnx_graph)

    assert iter(result) is result
    assert next(result) == 5


def test_isolate_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.isolate")
    fnx_graph, _ = _graph_pair_with_isolates()

    with pytest.raises(TypeError):
        module.number_of_isolates(fnx_graph, unsupported=True)
