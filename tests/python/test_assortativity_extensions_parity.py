import math
from unittest import mock

import numpy as np
import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _assert_nested_dicts_close(actual, expected, tol=1e-12):
    assert set(actual) == set(expected)
    for left in expected:
        assert set(actual[left]) == set(expected[left])
        for right in expected[left]:
            assert math.isclose(
                actual[left][right],
                expected[left][right],
                rel_tol=tol,
                abs_tol=tol,
            )


def test_mixing_dict_matches_networkx_without_delegation():
    pairs = [("red", "blue"), ("red", "blue"), ("blue", "green")]
    expected_counts = nx.mixing_dict(pairs, normalized=False)
    expected_normalized = nx.mixing_dict(pairs, normalized=True)

    with mock.patch(
        "networkx.mixing_dict",
        side_effect=AssertionError("NetworkX mixing_dict should not be used"),
    ):
        _assert_nested_dicts_close(
            fnx.mixing_dict(pairs, normalized=False),
            expected_counts,
        )
        _assert_nested_dicts_close(
            fnx.mixing_dict(pairs, normalized=True),
            expected_normalized,
        )
        assert fnx.mixing_dict([], normalized=True) == {}


def test_degree_mixing_dict_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    _assert_nested_dicts_close(
        fnx.degree_mixing_dict(graph),
        nx.degree_mixing_dict(expected),
    )


def test_degree_mixing_matrix_directed_matches_networkx_without_fallback(
    monkeypatch,
):
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    expected = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])

    wanted = nx.degree_mixing_matrix(expected)

    monkeypatch.setattr(
        nx,
        "degree_mixing_matrix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX degree_mixing_matrix fallback should not be used")
        ),
    )

    np.testing.assert_allclose(
        fnx.degree_mixing_matrix(graph),
        wanted,
    )


def test_degree_mixing_matrix_weighted_mapping_matches_networkx_without_fallback(
    monkeypatch,
):
    graph = fnx.Graph()
    expected = nx.Graph()
    for G in (graph, expected):
        G.add_edge("a", "b", weight=0.5)
        G.add_edge("b", "c", weight=1.0)
        G.add_edge("c", "a", weight=1.0)

    mapping = {0.5: 1, 1.5: 0, "unused": 2}
    wanted = nx.degree_mixing_matrix(
        expected,
        weight="weight",
        normalized=False,
        mapping=mapping,
    )

    monkeypatch.setattr(
        nx,
        "degree_mixing_matrix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX degree_mixing_matrix fallback should not be used")
        ),
    )

    np.testing.assert_allclose(
        fnx.degree_mixing_matrix(
            graph,
            weight="weight",
            normalized=False,
            mapping=mapping,
        ),
        wanted,
    )


def test_attribute_mixing_dict_and_matrix_match_networkx():
    graph = fnx.Graph()
    graph.add_nodes_from(
        [
            (0, {"color": "red"}),
            (1, {"color": "red"}),
            (2, {"color": "blue"}),
            (3, {"color": "blue"}),
        ]
    )
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])

    expected = nx.Graph()
    expected.add_nodes_from(
        [
            (0, {"color": "red"}),
            (1, {"color": "red"}),
            (2, {"color": "blue"}),
            (3, {"color": "blue"}),
        ]
    )
    expected.add_edges_from([(0, 1), (1, 2), (2, 3)])

    _assert_nested_dicts_close(
        fnx.attribute_mixing_dict(graph, "color"),
        nx.attribute_mixing_dict(expected, "color"),
    )
    np.testing.assert_allclose(
        fnx.attribute_mixing_matrix(graph, "color"),
        nx.attribute_mixing_matrix(expected, "color"),
    )


def test_attribute_assortativity_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph.nodes[node]["color"] = color
        expected.nodes[node]["color"] = color

    assert math.isclose(
        fnx.attribute_assortativity_coefficient(graph, "color"),
        nx.attribute_assortativity_coefficient(expected, "color"),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_numeric_assortativity_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)
    for node, size in [(0, 1), (1, 2), (2, 2), (3, 3)]:
        graph.nodes[node]["size"] = size
        expected.nodes[node]["size"] = size

    assert math.isclose(
        fnx.numeric_assortativity_coefficient(graph, "size"),
        nx.numeric_assortativity_coefficient(expected, "size"),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_degree_pearson_correlation_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    assert math.isclose(
        fnx.degree_pearson_correlation_coefficient(graph),
        nx.degree_pearson_correlation_coefficient(expected),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_attribute_mixing_matrix_respects_mapping():
    graph = fnx.Graph()
    graph.add_nodes_from([(0, {"kind": "a"}), (1, {"kind": "b"})])
    graph.add_edge(0, 1)

    expected = nx.Graph()
    expected.add_nodes_from([(0, {"kind": "a"}), (1, {"kind": "b"})])
    expected.add_edge(0, 1)

    mapping = {"a": 1, "b": 0, "unused": 2}
    np.testing.assert_allclose(
        fnx.attribute_mixing_matrix(graph, "kind", mapping=mapping),
        nx.attribute_mixing_matrix(expected, "kind", mapping=mapping),
    )
