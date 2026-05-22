"""Parity coverage for the ``franken_networkx.mis`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("maximal_independent_set",)


def test_direct_mis_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.mis")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_mis_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.mis")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.mis")

    assert via_algorithms is direct
    assert fnx.algorithms.mis is direct


def test_mis_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.mis")
    expected = importlib.import_module("networkx.algorithms.mis")

    assert set(module.__all__) == set(expected.__all__)


def test_mis_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.mis")
    expected = importlib.import_module("networkx.algorithms.mis")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_maximal_independent_set_values_match_networkx():
    module = importlib.import_module("franken_networkx.mis")
    fnx_graph = fnx.path_graph(6)
    nx_graph = nx.path_graph(6)

    assert module.maximal_independent_set(fnx_graph, seed=7) == nx.maximal_independent_set(
        nx_graph, seed=7
    )
    assert module.maximal_independent_set(
        fnx_graph, nodes=[1], seed=3
    ) == nx.maximal_independent_set(nx_graph, nodes=[1], seed=3)


def test_maximal_independent_set_error_message_matches_networkx():
    module = importlib.import_module("franken_networkx.mis")
    graph = fnx.path_graph(3)

    with pytest.raises(nx.NetworkXUnfeasible, match=r"\{0, 1\} is not an independent"):
        module.maximal_independent_set(graph, nodes=[0, 1], seed=2)


def test_mis_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.mis")
    graph = fnx.path_graph(3)

    with pytest.raises(TypeError):
        module.maximal_independent_set(graph, unsupported=True)
