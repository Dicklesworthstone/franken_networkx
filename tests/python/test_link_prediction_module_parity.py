"""Parity coverage for the ``franken_networkx.link_prediction`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "resource_allocation_index",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
    "common_neighbor_centrality",
)


PLAIN_FUNCTIONS = (
    "resource_allocation_index",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "common_neighbor_centrality",
)


COMMUNITY_FUNCTIONS = (
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
)


def _build_pair():
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    for graph in (fnx_graph, nx_graph):
        for node in graph:
            graph.nodes[node]["community"] = node % 2
    return fnx_graph, nx_graph


def test_direct_link_prediction_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.link_prediction")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_link_prediction_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.link_prediction")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.link_prediction"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.link_prediction is direct


def test_link_prediction_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.link_prediction")
    expected = importlib.import_module("networkx.algorithms.link_prediction")

    assert set(module.__all__) == set(expected.__all__)


def test_link_prediction_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.link_prediction")
    expected = importlib.import_module("networkx.algorithms.link_prediction")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_plain_link_prediction_functions_match_networkx():
    module = importlib.import_module("franken_networkx.link_prediction")
    fnx_graph, nx_graph = _build_pair()
    ebunch = [(0, 2), (0, 3), (1, 3)]

    for name in PLAIN_FUNCTIONS:
        assert list(getattr(module, name)(fnx_graph, ebunch)) == list(
            getattr(nx, name)(nx_graph, ebunch)
        )


def test_community_link_prediction_functions_match_networkx():
    module = importlib.import_module("franken_networkx.link_prediction")
    fnx_graph, nx_graph = _build_pair()
    ebunch = [(0, 2), (0, 3), (1, 3)]

    for name in COMMUNITY_FUNCTIONS:
        assert list(getattr(module, name)(fnx_graph, ebunch)) == list(
            getattr(nx, name)(nx_graph, ebunch)
        )


def test_link_prediction_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.link_prediction")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        list(module.jaccard_coefficient(fnx_graph, unsupported=True))
