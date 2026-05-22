"""Parity for nested ``franken_networkx.algorithms.operators`` imports."""

from __future__ import annotations

import importlib

import networkx as nx


def test_algorithms_operators_child_submodules_import_like_networkx():
    for name in ("all", "binary", "product", "unary"):
        actual = importlib.import_module(
            f"franken_networkx.algorithms.operators.{name}"
        )
        expected = importlib.import_module(f"networkx.algorithms.operators.{name}")

        assert actual is expected


def test_algorithms_operators_from_import_exposes_child_module():
    from franken_networkx.algorithms.operators import product

    actual = product.cartesian_product(nx.path_graph(2), nx.path_graph(2))
    expected = nx.algorithms.operators.product.cartesian_product(
        nx.path_graph(2), nx.path_graph(2)
    )

    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert sorted(actual.edges()) == sorted(expected.edges())
