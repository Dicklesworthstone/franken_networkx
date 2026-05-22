"""Parity for nested ``franken_networkx.algorithms.approximation`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_approximation_child_submodules_import_like_networkx():
    names = (
        "clique",
        "clustering_coefficient",
        "connectivity",
        "density",
        "distance_measures",
        "dominating_set",
        "kcomponents",
        "matching",
        "maxcut",
        "ramsey",
        "steinertree",
        "traveling_salesman",
        "treewidth",
        "vertex_cover",
    )
    for name in names:
        actual = importlib.import_module(
            f"franken_networkx.algorithms.approximation.{name}"
        )
        expected = importlib.import_module(
            f"networkx.algorithms.approximation.{name}"
        )

        assert actual is expected


def test_algorithms_approximation_from_import_exposes_child_module():
    from franken_networkx.algorithms.approximation import clique

    assert clique.large_clique_size(nx.complete_graph(3)) == 3
