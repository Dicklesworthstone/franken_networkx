"""Parity coverage for the ``franken_networkx.structuralholes`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("constraint", "local_constraint", "effective_size")


def _build_pair():
    weighted_edges = [(0, 1, 2), (1, 2, 3), (2, 0, 5), (2, 3, 7)]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def test_direct_structuralholes_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.structuralholes")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_structuralholes_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.structuralholes")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.structuralholes"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.structuralholes is direct


def test_structuralholes_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    expected = importlib.import_module("networkx.algorithms.structuralholes")

    assert set(module.__all__) == set(expected.__all__)


def test_structuralholes_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    expected = importlib.import_module("networkx.algorithms.structuralholes")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_structuralholes_measures_match_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph, nx_graph = _build_pair()

    assert module.constraint(fnx_graph) == nx.constraint(nx_graph)
    assert module.constraint(fnx_graph, weight="weight") == nx.constraint(
        nx_graph, weight="weight"
    )
    assert module.local_constraint(fnx_graph, 0, 1, weight="weight") == (
        nx.local_constraint(nx_graph, 0, 1, weight="weight")
    )
    assert module.effective_size(fnx_graph) == nx.effective_size(nx_graph)
    assert module.effective_size(fnx_graph, weight="weight") == nx.effective_size(
        nx_graph, weight="weight"
    )


def test_local_constraint_digraph_missing_u_message_matches_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph = fnx.DiGraph([(0, 1)])
    nx_graph = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXError) as fnx_exc:
        module.local_constraint(fnx_graph, "missing", 1)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.local_constraint(nx_graph, "missing", 1)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("graph_factory", [fnx.Graph, fnx.DiGraph])
def test_local_constraint_missing_v_matches_networkx_zero(graph_factory):
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph = graph_factory([(0, 1)])
    nx_graph = getattr(nx, graph_factory.__name__)([(0, 1)])

    assert module.local_constraint(fnx_graph, 1, "missing") == nx.local_constraint(
        nx_graph, 1, "missing"
    )


def test_structuralholes_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.constraint(fnx_graph, unsupported=True)
