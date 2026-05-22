"""Parity coverage for the ``franken_networkx.cuts`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "boundary_expansion",
    "conductance",
    "cut_size",
    "edge_expansion",
    "mixing_expansion",
    "node_expansion",
    "normalized_cut_size",
    "volume",
)


def _build_pair():
    weighted_edges = [(0, 1, 2), (1, 2, 3), (2, 3, 5), (3, 4, 7)]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def test_direct_cuts_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.cuts")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_cuts_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.cuts")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.cuts")

    assert via_algorithms is direct
    assert fnx.algorithms.cuts is direct


def test_cuts_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.cuts")
    expected = importlib.import_module("networkx.algorithms.cuts")

    assert set(module.__all__) == set(expected.__all__)


def test_cuts_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.cuts")
    expected = importlib.import_module("networkx.algorithms.cuts")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_cut_metrics_match_networkx():
    module = importlib.import_module("franken_networkx.cuts")
    fnx_graph, nx_graph = _build_pair()
    S = {0, 1}
    T = {2, 3, 4}

    assert module.boundary_expansion(fnx_graph, S) == nx.boundary_expansion(nx_graph, S)
    assert module.conductance(fnx_graph, S, T=T) == nx.conductance(nx_graph, S, T=T)
    assert module.cut_size(fnx_graph, S, T=T) == nx.cut_size(nx_graph, S, T=T)
    assert module.edge_expansion(fnx_graph, S, T=T) == nx.edge_expansion(
        nx_graph, S, T=T
    )
    assert module.mixing_expansion(fnx_graph, S, T=T) == nx.mixing_expansion(
        nx_graph, S, T=T
    )
    assert module.node_expansion(fnx_graph, S) == nx.node_expansion(nx_graph, S)
    assert module.normalized_cut_size(
        fnx_graph, S, T=T
    ) == nx.normalized_cut_size(nx_graph, S, T=T)
    assert module.volume(fnx_graph, S) == nx.volume(nx_graph, S)


def test_weighted_cut_metrics_match_networkx():
    module = importlib.import_module("franken_networkx.cuts")
    fnx_graph, nx_graph = _build_pair()
    S = {0, 1}
    T = {2, 3, 4}

    assert module.conductance(
        fnx_graph, S, T=T, weight="weight"
    ) == nx.conductance(nx_graph, S, T=T, weight="weight")
    assert module.cut_size(fnx_graph, S, T=T, weight="weight") == nx.cut_size(
        nx_graph, S, T=T, weight="weight"
    )
    assert module.volume(fnx_graph, S, weight="weight") == nx.volume(
        nx_graph, S, weight="weight"
    )


def test_cuts_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.cuts")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.cut_size(fnx_graph, {0, 1}, unsupported=True)
