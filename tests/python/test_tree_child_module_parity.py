"""Parity for nested ``franken_networkx.algorithms.tree`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_tree_child_submodules_import_like_networkx():
    names = (
        "branchings",
        "coding",
        "decomposition",
        "distance_measures",
        "mst",
        "operations",
        "recognition",
    )
    for name in names:
        actual = importlib.import_module(
            f"franken_networkx.algorithms.tree.{name}"
        )
        expected = importlib.import_module(f"networkx.algorithms.tree.{name}")

        assert actual is expected


def test_algorithms_tree_from_import_exposes_child_module():
    from franken_networkx.algorithms.tree import recognition

    assert recognition.is_tree(nx.path_graph(3))
