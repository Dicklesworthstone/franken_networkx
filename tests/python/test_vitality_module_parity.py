"""Parity coverage for the ``franken_networkx.vitality`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("closeness_vitality",)


def test_direct_vitality_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.vitality")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_vitality_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.vitality")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.vitality")

    assert via_algorithms is direct
    assert fnx.algorithms.vitality is direct


def test_vitality_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.vitality")
    expected = importlib.import_module("networkx.algorithms.vitality")

    assert set(module.__all__) == set(expected.__all__)


def test_vitality_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.vitality")
    expected = importlib.import_module("networkx.algorithms.vitality")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_closeness_vitality_values_match_networkx():
    module = importlib.import_module("franken_networkx.vitality")
    fnx_graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)

    assert module.closeness_vitality(fnx_graph) == nx.closeness_vitality(nx_graph)
    assert module.closeness_vitality(fnx_graph, node=0) == pytest.approx(
        nx.closeness_vitality(nx_graph, node=0)
    )


def test_closeness_vitality_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.vitality")
    graph = fnx.cycle_graph(4)

    with pytest.raises(TypeError):
        module.closeness_vitality(graph, unsupported=True)
