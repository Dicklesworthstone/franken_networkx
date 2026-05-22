"""Parity coverage for the ``franken_networkx.cluster`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "triangles",
    "all_triangles",
    "average_clustering",
    "clustering",
    "transitivity",
    "square_clustering",
    "generalized_degree",
)


def _build_pair():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def test_direct_cluster_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.cluster")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_cluster_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.cluster")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.cluster")

    assert via_algorithms is direct
    assert fnx.algorithms.cluster is direct


def test_cluster_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.cluster")
    expected = importlib.import_module("networkx.algorithms.cluster")

    assert set(module.__all__) == set(expected.__all__)


def test_cluster_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.cluster")
    expected = importlib.import_module("networkx.algorithms.cluster")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_cluster_functions_match_networkx():
    module = importlib.import_module("franken_networkx.cluster")
    fnx_graph, nx_graph = _build_pair()

    assert module.triangles(fnx_graph) == nx.triangles(nx_graph)
    assert list(module.all_triangles(fnx_graph)) == list(nx.all_triangles(nx_graph))
    assert module.average_clustering(fnx_graph) == nx.average_clustering(nx_graph)
    assert module.clustering(fnx_graph) == nx.clustering(nx_graph)
    assert module.transitivity(fnx_graph) == nx.transitivity(nx_graph)
    assert module.square_clustering(fnx_graph) == nx.square_clustering(nx_graph)
    assert module.generalized_degree(fnx_graph) == nx.generalized_degree(nx_graph)


def test_cluster_single_node_forms_match_networkx():
    module = importlib.import_module("franken_networkx.cluster")
    fnx_graph, nx_graph = _build_pair()

    assert module.triangles(fnx_graph, nodes=0) == nx.triangles(nx_graph, nodes=0)
    assert module.clustering(fnx_graph, nodes=0) == nx.clustering(nx_graph, nodes=0)
    assert module.square_clustering(fnx_graph, nodes=0) == nx.square_clustering(
        nx_graph, nodes=0
    )
    assert module.generalized_degree(
        fnx_graph, nodes=0
    ) == nx.generalized_degree(nx_graph, nodes=0)


def test_cluster_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.cluster")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.clustering(fnx_graph, unsupported=True)
