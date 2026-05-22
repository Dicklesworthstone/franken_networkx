"""Parity for nested ``franken_networkx.algorithms.flow`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_flow_child_submodules_import_like_networkx():
    names = (
        "boykovkolmogorov",
        "capacityscaling",
        "dinitz_alg",
        "edmondskarp",
        "gomory_hu",
        "maxflow",
        "mincost",
        "networksimplex",
        "preflowpush",
        "shortestaugmentingpath",
        "utils",
    )
    for name in names:
        actual = importlib.import_module(
            f"franken_networkx.algorithms.flow.{name}"
        )
        expected = importlib.import_module(f"networkx.algorithms.flow.{name}")

        assert actual is expected


def test_algorithms_flow_from_import_exposes_child_module():
    from franken_networkx.algorithms.flow import maxflow

    graph = nx.DiGraph()
    graph.add_edge("s", "a", capacity=3)
    graph.add_edge("a", "t", capacity=2)

    assert maxflow.maximum_flow_value(graph, "s", "t") == 2
