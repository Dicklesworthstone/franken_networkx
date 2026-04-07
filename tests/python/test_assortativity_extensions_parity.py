import math

import numpy as np
import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _assert_nested_dicts_close(actual, expected, tol=1e-12):
    assert set(actual) == set(expected)
    for left in expected:
        assert set(actual[left]) == set(expected[left])
        for right in expected[left]:
            assert math.isclose(actual[left][right], expected[left][right], rel_tol=tol, abs_tol=tol)


def test_degree_mixing_dict_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    _assert_nested_dicts_close(
        fnx.degree_mixing_dict(graph),
        nx.degree_mixing_dict(expected),
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
