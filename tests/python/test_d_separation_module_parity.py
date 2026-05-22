"""Parity coverage for the ``franken_networkx.d_separation`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_d_separator",
    "is_minimal_d_separator",
    "find_minimal_d_separator",
)


def _build_diamond_pair():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def test_direct_d_separation_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.d_separation")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_d_separation_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.d_separation")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.d_separation")

    assert via_algorithms is direct
    assert fnx.algorithms.d_separation is direct


def test_d_separation_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    expected = importlib.import_module("networkx.algorithms.d_separation")

    assert set(module.__all__) == set(expected.__all__)


def test_d_separation_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    expected = importlib.import_module("networkx.algorithms.d_separation")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "x,y,z",
    [
        ({0}, {3}, set()),
        ({0}, {3}, {1, 2}),
        ({1}, {2}, {0}),
    ],
)
def test_is_d_separator_matches_networkx(x, y, z):
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()

    assert module.is_d_separator(fnx_graph, x, y, z) == nx.is_d_separator(
        nx_graph, x, y, z
    )


@pytest.mark.parametrize("z", [{1, 2}, {1}, set()])
def test_is_minimal_d_separator_matches_networkx(z):
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()
    x = {0}
    y = {3}

    assert module.is_minimal_d_separator(fnx_graph, x, y, z) == (
        nx.is_minimal_d_separator(nx_graph, x, y, z)
    )


def test_find_minimal_d_separator_matches_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()
    x = {0}
    y = {3}

    assert module.find_minimal_d_separator(
        fnx_graph, x, y
    ) == nx.find_minimal_d_separator(nx_graph, x, y)


def test_d_separation_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, _ = _build_diamond_pair()

    with pytest.raises(TypeError):
        module.is_d_separator(fnx_graph, {0}, {3}, set(), unsupported=True)
