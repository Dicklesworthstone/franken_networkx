"""Parity coverage for the ``franken_networkx.communicability_alg`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("communicability", "communicability_exp")


def _assert_nested_float_mapping_close(actual, expected):
    assert set(actual) == set(expected)
    for source, actual_targets in actual.items():
        expected_targets = expected[source]
        assert set(actual_targets) == set(expected_targets)
        for target, actual_value in actual_targets.items():
            assert actual_value == pytest.approx(expected_targets[target])


def test_direct_communicability_alg_import_uses_fnx_wrappers():
    module = importlib.import_module("franken_networkx.communicability_alg")

    for name in PUBLIC_FUNCTIONS:
        assert getattr(module, name) is getattr(fnx, name)


def test_algorithms_communicability_alg_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.communicability_alg")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.communicability_alg"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.communicability_alg is direct


def test_communicability_alg_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.communicability_alg")
    expected = importlib.import_module("networkx.algorithms.communicability_alg")

    assert set(module.__all__) == set(expected.__all__)


def test_communicability_alg_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.communicability_alg")
    expected = importlib.import_module("networkx.algorithms.communicability_alg")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_communicability_alg_values_match_networkx_on_path_graph():
    module = importlib.import_module("franken_networkx.communicability_alg")
    fnx_graph = fnx.path_graph(3)
    nx_graph = nx.path_graph(3)

    for name in PUBLIC_FUNCTIONS:
        _assert_nested_float_mapping_close(
            getattr(module, name)(fnx_graph),
            getattr(nx, name)(nx_graph),
        )
