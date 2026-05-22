"""Parity coverage for the ``franken_networkx.distance_regular`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_distance_regular",
    "is_strongly_regular",
    "intersection_array",
    "global_parameters",
)


def test_direct_distance_regular_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.distance_regular")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_distance_regular_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.distance_regular")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.distance_regular"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.distance_regular is direct


def test_distance_regular_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.distance_regular")
    expected = importlib.import_module("networkx.algorithms.distance_regular")

    assert set(module.__all__) == set(expected.__all__)


def test_distance_regular_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.distance_regular")
    expected = importlib.import_module("networkx.algorithms.distance_regular")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "fnx_graph,nx_graph",
    [
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.path_graph(4), nx.path_graph(4)),
        (fnx.complete_graph(5), nx.complete_graph(5)),
    ],
)
def test_distance_regular_predicates_match_networkx(fnx_graph, nx_graph):
    module = importlib.import_module("franken_networkx.distance_regular")

    assert module.is_distance_regular(fnx_graph) == nx.is_distance_regular(nx_graph)
    assert module.is_strongly_regular(fnx_graph) == nx.is_strongly_regular(nx_graph)


@pytest.mark.parametrize(
    "fnx_graph,nx_graph",
    [
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.complete_graph(5), nx.complete_graph(5)),
    ],
)
def test_intersection_array_and_global_parameters_match_networkx(
    fnx_graph, nx_graph
):
    module = importlib.import_module("franken_networkx.distance_regular")

    actual_b, actual_c = module.intersection_array(fnx_graph)
    expected_b, expected_c = nx.intersection_array(nx_graph)

    assert (actual_b, actual_c) == (expected_b, expected_c)
    assert list(module.global_parameters(actual_b, actual_c)) == list(
        nx.global_parameters(expected_b, expected_c)
    )


def test_distance_regular_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.distance_regular")
    graph = fnx.cycle_graph(6)

    with pytest.raises(TypeError):
        module.is_distance_regular(graph, unsupported=True)
