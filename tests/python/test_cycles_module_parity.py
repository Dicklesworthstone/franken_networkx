"""Parity coverage for the ``franken_networkx.cycles`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "cycle_basis",
    "simple_cycles",
    "recursive_simple_cycles",
    "find_cycle",
    "minimum_cycle_basis",
    "chordless_cycles",
    "girth",
)


def _build_undirected_pair():
    weighted_edges = [
        (0, 1, 2),
        (1, 2, 3),
        (2, 0, 4),
        (2, 3, 5),
        (3, 4, 6),
        (4, 2, 7),
    ]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def _build_directed_pair():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def _normalized_cycles(cycles):
    return sorted(tuple(sorted(cycle)) for cycle in cycles)


def test_direct_cycles_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.cycles")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_cycles_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.cycles")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.cycles")

    assert via_algorithms is direct
    assert fnx.algorithms.cycles is direct


def test_cycles_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.cycles")
    expected = importlib.import_module("networkx.algorithms.cycles")

    assert set(module.__all__) == set(expected.__all__)


def test_cycles_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.cycles")
    expected = importlib.import_module("networkx.algorithms.cycles")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_undirected_cycle_algorithms_match_networkx():
    module = importlib.import_module("franken_networkx.cycles")
    fnx_graph, nx_graph = _build_undirected_pair()

    assert _normalized_cycles(module.cycle_basis(fnx_graph)) == _normalized_cycles(
        nx.cycle_basis(nx_graph)
    )
    assert _normalized_cycles(
        module.minimum_cycle_basis(fnx_graph, weight="weight")
    ) == _normalized_cycles(nx.minimum_cycle_basis(nx_graph, weight="weight"))
    assert module.girth(fnx_graph) == nx.girth(nx_graph)


def test_directed_cycle_algorithms_match_networkx():
    module = importlib.import_module("franken_networkx.cycles")
    fnx_graph, nx_graph = _build_directed_pair()

    assert _normalized_cycles(module.simple_cycles(fnx_graph)) == _normalized_cycles(
        nx.simple_cycles(nx_graph)
    )
    assert _normalized_cycles(
        module.recursive_simple_cycles(fnx_graph)
    ) == _normalized_cycles(nx.recursive_simple_cycles(nx_graph))
    assert module.find_cycle(fnx_graph) == nx.find_cycle(nx_graph)
    assert _normalized_cycles(module.chordless_cycles(fnx_graph)) == _normalized_cycles(
        nx.chordless_cycles(nx_graph)
    )


def test_cycles_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.cycles")
    fnx_graph, _ = _build_undirected_pair()

    with pytest.raises(TypeError):
        module.girth(fnx_graph, unsupported=True)
