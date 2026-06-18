"""Parity for nested ``franken_networkx.algorithms.minors`` imports."""

from __future__ import annotations

import importlib

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import minors as fnx_minors
from networkx.algorithms import minors as nx_minors


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


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


def _graph_shape(graph):
    return sorted(graph.nodes()), sorted(graph.edges())


@pytest.mark.parametrize(
    ("fnx_func", "nx_func", "args"),
    [
        (fnx_minors.contracted_nodes, nx_minors.contracted_nodes, (0, 1)),
        (fnx_minors.identified_nodes, nx_minors.identified_nodes, (0, 1)),
        (fnx_minors.contracted_edge, nx_minors.contracted_edge, ((0, 1),)),
    ],
)
@pytest.mark.parametrize("graph_module", [fnx, nx])
def test_minors_copy_false_preserves_in_place_return_identity(
    graph_module, fnx_func, nx_func, args
):
    graph = graph_module.path_graph(4)
    expected_graph = nx.path_graph(4)

    result = fnx_func(graph, *args, copy=False)
    expected = nx_func(expected_graph, *args, copy=False)

    assert result is graph
    assert expected is expected_graph
    assert _graph_shape(result) == _graph_shape(expected)


def test_algorithms_minors_alias_copy_false_preserves_input_identity():
    from franken_networkx.algorithms import minors as algorithms_minors

    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    result = algorithms_minors.contracted_nodes(graph, 0, 1, copy=False)
    expected = nx_minors.contracted_nodes(expected_graph, 0, 1, copy=False)

    _expect(
        result is graph,
        "franken_networkx.algorithms.minors copy=False must return input graph",
    )
    _expect(
        expected is expected_graph,
        "networkx.algorithms.minors copy=False must return input graph",
    )
    _expect(
        _graph_shape(result) == _graph_shape(expected),
        "franken_networkx.algorithms.minors contraction shape must match networkx",
    )
