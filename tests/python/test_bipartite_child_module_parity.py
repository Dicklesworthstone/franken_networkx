"""Parity for nested ``franken_networkx.algorithms.bipartite`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_bipartite_child_submodules_import_like_networkx():
    names = (
        "basic",
        "centrality",
        "cluster",
        "covering",
        "edgelist",
        "extendability",
        "generators",
        "link_analysis",
        "matching",
        "matrix",
        "projection",
        "redundancy",
        "spectral",
    )
    for name in names:
        actual = importlib.import_module(
            f"franken_networkx.algorithms.bipartite.{name}"
        )
        expected = importlib.import_module(
            f"networkx.algorithms.bipartite.{name}"
        )

        assert actual is expected


def test_algorithms_bipartite_from_import_exposes_child_module():
    from franken_networkx.algorithms.bipartite import basic

    graph = nx.path_graph(3)
    assert basic.is_bipartite(graph)
