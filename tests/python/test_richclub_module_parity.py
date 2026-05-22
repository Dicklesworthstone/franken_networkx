"""Parity coverage for the ``franken_networkx.richclub`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("rich_club_coefficient",)


def test_direct_richclub_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.richclub")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_richclub_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.richclub")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.richclub")

    assert via_algorithms is direct
    assert fnx.algorithms.richclub is direct


def test_richclub_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    expected = importlib.import_module("networkx.algorithms.richclub")

    assert set(module.__all__) == set(expected.__all__)


def test_richclub_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    expected = importlib.import_module("networkx.algorithms.richclub")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_rich_club_coefficient_values_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    fnx_graph = fnx.complete_graph(5)
    nx_graph = nx.complete_graph(5)

    assert module.rich_club_coefficient(
        fnx_graph,
        normalized=False,
    ) == nx.rich_club_coefficient(nx_graph, normalized=False)


def test_rich_club_coefficient_path_values_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    assert module.rich_club_coefficient(
        fnx_graph,
        normalized=False,
    ) == nx.rich_club_coefficient(nx_graph, normalized=False)


def test_rich_club_coefficient_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.richclub")
    graph = fnx.complete_graph(4)

    with pytest.raises(TypeError):
        module.rich_club_coefficient(graph, normalized=False, unsupported=True)
