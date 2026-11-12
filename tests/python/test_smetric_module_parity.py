"""Parity coverage for the ``franken_networkx.smetric`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("s_metric",)


def test_direct_smetric_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.smetric")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_smetric_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.smetric")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.smetric")

    assert via_algorithms is direct
    assert fnx.algorithms.smetric is direct


def test_smetric_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.smetric")
    expected = importlib.import_module("networkx.algorithms.smetric")

    assert set(module.__all__) == set(expected.__all__)


def test_smetric_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.smetric")
    expected = importlib.import_module("networkx.algorithms.smetric")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_smetric_values_match_networkx():
    module = importlib.import_module("franken_networkx.smetric")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.s_metric(fnx_graph) == pytest.approx(nx.s_metric(nx_graph))


def test_smetric_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.smetric")
    graph = fnx.path_graph(4)

    with pytest.raises(TypeError):
        module.s_metric(graph, unsupported=True)
