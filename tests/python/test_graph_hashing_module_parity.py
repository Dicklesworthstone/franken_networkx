"""Parity coverage for the ``franken_networkx.graph_hashing`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "weisfeiler_lehman_graph_hash",
    "weisfeiler_lehman_subgraph_hashes",
)


def test_direct_graph_hashing_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.graph_hashing")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_graph_hashing_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.graph_hashing")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.graph_hashing"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.graph_hashing is direct


def test_graph_hashing_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.graph_hashing")
    expected = importlib.import_module("networkx.algorithms.graph_hashing")

    assert set(module.__all__) == set(expected.__all__)


def test_graph_hashing_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.graph_hashing")
    expected = importlib.import_module("networkx.algorithms.graph_hashing")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_weisfeiler_lehman_graph_hash_matches_networkx():
    module = importlib.import_module("franken_networkx.graph_hashing")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.weisfeiler_lehman_graph_hash(
        fnx_graph,
        iterations=2,
        digest_size=8,
    ) == nx.weisfeiler_lehman_graph_hash(
        nx_graph,
        iterations=2,
        digest_size=8,
    )


def test_weisfeiler_lehman_subgraph_hashes_match_networkx():
    module = importlib.import_module("franken_networkx.graph_hashing")
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    assert module.weisfeiler_lehman_subgraph_hashes(
        fnx_graph,
        iterations=2,
        digest_size=8,
        include_initial_labels=True,
    ) == nx.weisfeiler_lehman_subgraph_hashes(
        nx_graph,
        iterations=2,
        digest_size=8,
        include_initial_labels=True,
    )


def test_graph_hashing_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.graph_hashing")
    graph = fnx.path_graph(4)

    with pytest.raises(TypeError):
        module.weisfeiler_lehman_graph_hash(graph, unsupported=True)
