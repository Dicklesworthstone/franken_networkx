"""Parity coverage for the ``franken_networkx.broadcasting`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx


PUBLIC_FUNCTIONS = ("tree_broadcast_center", "tree_broadcast_time")


def test_direct_broadcasting_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.broadcasting")
    expected = importlib.import_module("networkx.algorithms.broadcasting")

    assert set(module.__all__) == set(expected.__all__)
    for name in PUBLIC_FUNCTIONS:
        assert hasattr(module, name)


def test_algorithms_broadcasting_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.broadcasting")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.broadcasting")

    assert via_algorithms is direct
    assert fnx.algorithms.broadcasting is direct


def test_broadcasting_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.broadcasting")
    expected = importlib.import_module("networkx.algorithms.broadcasting")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_broadcasting_module_values_match_networkx_on_tree():
    module = importlib.import_module("franken_networkx.broadcasting")
    fnx_graph = fnx.balanced_tree(2, 2)
    nx_graph = nx.balanced_tree(2, 2)

    assert module.tree_broadcast_center(fnx_graph) == nx.tree_broadcast_center(
        nx_graph
    )
    assert module.tree_broadcast_time(fnx_graph) == nx.tree_broadcast_time(nx_graph)
    assert module.tree_broadcast_time(fnx_graph, node=0) == nx.tree_broadcast_time(
        nx_graph, node=0
    )
