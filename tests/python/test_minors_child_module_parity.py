"""Parity for nested ``franken_networkx.algorithms.minors`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_minors_contraction_submodule_imports_like_networkx():
    actual = importlib.import_module(
        "franken_networkx.algorithms.minors.contraction"
    )
    expected = importlib.import_module("networkx.algorithms.minors.contraction")

    assert actual is expected


def test_minors_module_public_surface_matches_networkx():
    actual = importlib.import_module("franken_networkx.minors")
    expected = importlib.import_module("networkx.algorithms.minors")

    assert set(actual.__all__) == set(expected.__all__)


def test_algorithms_minors_from_import_exposes_contraction_module():
    from franken_networkx.algorithms.minors import contraction

    graph = contraction.contracted_nodes(nx.path_graph(3), 0, 1)

    assert sorted(graph.nodes()) == [0, 2]
