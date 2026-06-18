"""Parity for the ``franken_networkx.summarization`` module path."""

from __future__ import annotations

import franken_networkx as fnx
import networkx as nx
from franken_networkx import summarization as fnx_summarization
from networkx.algorithms import summarization as nx_summarization


def _dedensify_fixture(module):
    graph = module.DiGraph()
    graph.add_nodes_from(["1", "2", "3", "4", "5", "6", "A", "B", "C"])
    graph.add_edges_from(
        [
            ("1", "C"),
            ("1", "B"),
            ("2", "C"),
            ("2", "B"),
            ("2", "A"),
            ("3", "B"),
            ("3", "A"),
            ("3", "6"),
            ("4", "C"),
            ("4", "B"),
            ("4", "A"),
            ("5", "B"),
            ("5", "A"),
            ("6", "5"),
            ("A", "6"),
        ]
    )
    return graph


def _shape(graph):
    return sorted(graph.nodes()), sorted(graph.edges())


def test_dedensify_copy_false_preserves_in_place_identity_for_fnx_input():
    graph = _dedensify_fixture(fnx)
    expected_graph = _dedensify_fixture(nx)

    result, compressors = fnx_summarization.dedensify(
        graph, threshold=2, prefix="aux", copy=False
    )
    expected, expected_compressors = nx_summarization.dedensify(
        expected_graph, threshold=2, prefix="aux", copy=False
    )

    assert result is graph
    assert expected is expected_graph
    assert compressors == expected_compressors
    assert len(compressors) == 1
    assert next(iter(compressors)).startswith("aux")
    assert _shape(result) == _shape(expected)


def test_dedensify_copy_false_preserves_in_place_identity_for_nx_input():
    graph = _dedensify_fixture(nx)
    expected_graph = _dedensify_fixture(nx)

    result, compressors = fnx_summarization.dedensify(
        graph, threshold=2, prefix="aux", copy=False
    )
    expected, expected_compressors = nx_summarization.dedensify(
        expected_graph, threshold=2, prefix="aux", copy=False
    )

    assert result is graph
    assert expected is expected_graph
    assert compressors == expected_compressors
    assert len(compressors) == 1
    assert next(iter(compressors)).startswith("aux")
    assert _shape(result) == _shape(expected)
