"""Parity coverage for the ``franken_networkx.moral`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest

PUBLIC_FUNCTIONS = ("moral_graph",)


def _graph_from_edges(module, edges, isolated=()):
    graph = module.DiGraph()
    graph.add_edges_from(edges)
    graph.add_nodes_from(isolated)
    return graph


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def _assert_same_graph(actual, expected):
    assert isinstance(actual, fnx.Graph)
    assert not actual.is_directed()
    assert not actual.is_multigraph()
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert _canonical_edges(actual) == _canonical_edges(expected)


def test_direct_moral_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.moral")
    expected = importlib.import_module("networkx.algorithms.moral")

    assert set(module.__all__) == set(expected.__all__)
    for name in set(expected.__all__) | set(PUBLIC_FUNCTIONS):
        assert callable(getattr(module, name))


def test_algorithms_moral_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.moral")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.moral")

    assert via_algorithms is direct
    assert fnx.algorithms.moral is direct


def test_moral_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.moral")
    expected = importlib.import_module("networkx.algorithms.moral")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: {actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    ("edges", "isolated"),
    [
        ([(0, 2), (1, 2)], ()),
        ([(0, 2), (1, 2), (2, 3), (4, 3)], (5,)),
        ([("a", "c"), ("b", "c"), ("c", "d"), ("b", "d")], ("z",)),
    ],
)
def test_moral_graph_matches_networkx_and_returns_fnx_graph(edges, isolated):
    module = importlib.import_module("franken_networkx.moral")
    fnx_graph = _graph_from_edges(fnx, edges, isolated=isolated)
    nx_graph = _graph_from_edges(nx, edges, isolated=isolated)

    actual = module.moral_graph(fnx_graph)
    expected = nx.moral_graph(nx_graph)

    _assert_same_graph(actual, expected)


def test_moral_graph_marries_all_coparents_and_preserves_skeleton():
    module = importlib.import_module("franken_networkx.moral")
    graph = fnx.DiGraph([(0, 3), (1, 3), (2, 3), (3, 4)])

    moral = module.moral_graph(graph)

    assert set(_canonical_edges(moral)) == {
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (1, 3),
        (2, 3),
        (3, 4),
    }


def test_moral_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.moral")

    with pytest.raises(TypeError):
        module.moral_graph(fnx.DiGraph([(0, 1)]), unsupported=True)
