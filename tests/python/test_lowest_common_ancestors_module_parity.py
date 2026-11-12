"""Parity coverage for the ``franken_networkx.lowest_common_ancestors`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "all_pairs_lowest_common_ancestor",
    "tree_all_pairs_lowest_common_ancestor",
    "lowest_common_ancestor",
)


def _build_dag_pair():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    fnx_graph.add_node(5)
    nx_graph.add_node(5)
    return fnx_graph, nx_graph


def _build_tree_pair():
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def test_direct_lca_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_lca_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.lowest_common_ancestors")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.lowest_common_ancestors"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.lowest_common_ancestors is direct


def test_lca_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    expected = importlib.import_module("networkx.algorithms.lowest_common_ancestors")

    assert set(module.__all__) == set(expected.__all__)


def test_lca_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    expected = importlib.import_module("networkx.algorithms.lowest_common_ancestors")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize("node1,node2,default", [(1, 2, None), (3, 5, "missing")])
def test_lowest_common_ancestor_matches_networkx(node1, node2, default):
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_dag_pair()

    assert module.lowest_common_ancestor(
        fnx_graph, node1, node2, default=default
    ) == nx.lowest_common_ancestor(nx_graph, node1, node2, default=default)


def test_all_pairs_lowest_common_ancestor_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_dag_pair()
    pairs = [(1, 2), (3, 4), (1, 4)]

    assert dict(module.all_pairs_lowest_common_ancestor(fnx_graph, pairs=pairs)) == dict(
        nx.all_pairs_lowest_common_ancestor(nx_graph, pairs=pairs)
    )


def test_tree_all_pairs_lowest_common_ancestor_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_tree_pair()
    pairs = [(3, 4), (3, 5), (1, 5)]

    assert dict(
        module.tree_all_pairs_lowest_common_ancestor(fnx_graph, root=0, pairs=pairs)
    ) == dict(nx.tree_all_pairs_lowest_common_ancestor(nx_graph, root=0, pairs=pairs))


def test_lca_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, _ = _build_dag_pair()

    with pytest.raises(TypeError):
        module.lowest_common_ancestor(fnx_graph, 1, 2, unsupported=True)
