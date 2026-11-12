"""Parity coverage for the ``franken_networkx.efficiency_measures`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("efficiency", "local_efficiency", "global_efficiency")


def test_direct_efficiency_measures_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.efficiency_measures")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_efficiency_measures_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.efficiency_measures")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.efficiency_measures"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.efficiency_measures is direct


def test_efficiency_measures_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.efficiency_measures")
    expected = importlib.import_module("networkx.algorithms.efficiency_measures")

    assert set(module.__all__) == set(expected.__all__)


def test_efficiency_measures_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.efficiency_measures")
    expected = importlib.import_module("networkx.algorithms.efficiency_measures")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_efficiency_measures_values_match_networkx():
    module = importlib.import_module("franken_networkx.efficiency_measures")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.efficiency(fnx_graph, 0, 3) == pytest.approx(
        nx.efficiency(nx_graph, 0, 3)
    )
    assert module.local_efficiency(fnx_graph) == pytest.approx(
        nx.local_efficiency(nx_graph)
    )
    assert module.global_efficiency(fnx_graph) == pytest.approx(
        nx.global_efficiency(nx_graph)
    )


def test_efficiency_measures_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.efficiency_measures")
    graph = fnx.path_graph(2)

    with pytest.raises(TypeError):
        module.global_efficiency(graph, unsupported=True)
