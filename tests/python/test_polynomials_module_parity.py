"""Parity coverage for the ``franken_networkx.polynomials`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("tutte_polynomial", "chromatic_polynomial")


def test_direct_polynomials_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.polynomials")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_polynomials_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.polynomials")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.polynomials")

    assert via_algorithms is direct
    assert fnx.algorithms.polynomials is direct


def test_polynomials_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.polynomials")
    expected = importlib.import_module("networkx.algorithms.polynomials")

    assert set(module.__all__) == set(expected.__all__)


def test_polynomials_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.polynomials")
    expected = importlib.import_module("networkx.algorithms.polynomials")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def _assert_result_or_missing_sympy_matches(actual_fn, expected_fn, fnx_graph, nx_graph):
    try:
        expected = expected_fn(nx_graph)
    except ModuleNotFoundError as expected_exc:
        with pytest.raises(ModuleNotFoundError, match=str(expected_exc)):
            actual_fn(fnx_graph)
    else:
        assert actual_fn(fnx_graph) == expected


def test_chromatic_polynomial_matches_networkx():
    module = importlib.import_module("franken_networkx.polynomials")
    fnx_graph = fnx.path_graph(3)
    nx_graph = nx.path_graph(3)

    _assert_result_or_missing_sympy_matches(
        module.chromatic_polynomial,
        nx.chromatic_polynomial,
        fnx_graph,
        nx_graph,
    )


def test_tutte_polynomial_matches_networkx():
    module = importlib.import_module("franken_networkx.polynomials")
    fnx_graph = fnx.path_graph(3)
    nx_graph = nx.path_graph(3)

    _assert_result_or_missing_sympy_matches(
        module.tutte_polynomial,
        nx.tutte_polynomial,
        fnx_graph,
        nx_graph,
    )


def test_polynomials_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.polynomials")
    graph = fnx.path_graph(3)

    with pytest.raises(TypeError):
        module.chromatic_polynomial(graph, unsupported=True)
