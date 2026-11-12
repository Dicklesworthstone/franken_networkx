"""Parity coverage for the ``franken_networkx.wiener`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx


PUBLIC_FUNCTIONS = (
    "wiener_index",
    "schultz_index",
    "gutman_index",
    "hyper_wiener_index",
)


def test_direct_wiener_module_import_uses_fnx_wrappers():
    module = importlib.import_module("franken_networkx.wiener")

    for name in ("wiener_index", "schultz_index", "gutman_index"):
        assert getattr(module, name) is getattr(fnx, name)


def test_algorithms_wiener_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.wiener")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.wiener")

    assert via_algorithms is direct
    assert fnx.algorithms.wiener is direct


def test_wiener_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.wiener")
    expected = importlib.import_module("networkx.algorithms.wiener")

    assert set(module.__all__) == set(expected.__all__)


def test_wiener_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.wiener")
    expected = importlib.import_module("networkx.algorithms.wiener")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_wiener_module_values_match_networkx_on_path_graph():
    module = importlib.import_module("franken_networkx.wiener")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    for name in PUBLIC_FUNCTIONS:
        assert getattr(module, name)(fnx_graph) == getattr(nx, name)(nx_graph)
