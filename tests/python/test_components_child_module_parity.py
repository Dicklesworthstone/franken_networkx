"""Parity for nested ``franken_networkx.algorithms.components`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_components_child_submodules_import_like_networkx():
    names = (
        "attracting",
        "biconnected",
        "connected",
        "semiconnected",
        "strongly_connected",
        "weakly_connected",
    )
    for name in names:
        actual = importlib.import_module(
            f"franken_networkx.algorithms.components.{name}"
        )
        expected = importlib.import_module(
            f"networkx.algorithms.components.{name}"
        )

        assert actual is expected


def test_algorithms_components_from_import_exposes_child_module():
    from franken_networkx.algorithms.components import connected

    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (2, 3)])

    assert sorted(map(sorted, connected.connected_components(graph))) == [
        [0, 1],
        [2, 3],
    ]
