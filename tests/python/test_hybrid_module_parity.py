"""Parity coverage for the ``franken_networkx.hybrid`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest

PUBLIC_FUNCTIONS = ("is_kl_connected", "kl_connected_subgraph")


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def _assert_same_graph(actual, expected):
    assert isinstance(actual, fnx.Graph)
    assert not actual.is_directed()
    assert not actual.is_multigraph()
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert _canonical_edges(actual) == _canonical_edges(expected)


def test_direct_hybrid_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.hybrid")
    expected = importlib.import_module("networkx.algorithms.hybrid")

    assert set(module.__all__) == set(expected.__all__)
    for name in set(expected.__all__) | set(PUBLIC_FUNCTIONS):
        assert callable(getattr(module, name))


def test_algorithms_hybrid_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.hybrid")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.hybrid")

    assert via_algorithms is direct
    assert fnx.algorithms.hybrid is direct


def test_hybrid_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.hybrid")
    expected = importlib.import_module("networkx.algorithms.hybrid")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: {actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    ("fnx_graph", "nx_graph", "expected_connected"),
    [
        (fnx.cycle_graph(5), nx.cycle_graph(5), True),
        (fnx.path_graph(5), nx.path_graph(5), False),
        (fnx.complete_graph(4), nx.complete_graph(4), True),
        (fnx.barbell_graph(3, 1), nx.barbell_graph(3, 1), False),
    ],
)
@pytest.mark.parametrize("low_memory", [False, True])
def test_hybrid_kl_connected_family_matches_networkx(
    fnx_graph, nx_graph, expected_connected, low_memory
):
    module = importlib.import_module("franken_networkx.hybrid")

    actual_connected = module.is_kl_connected(
        fnx_graph, 2, 2, low_memory=low_memory
    )
    expected = nx.is_kl_connected(nx_graph, 2, 2, low_memory=low_memory)
    assert actual_connected == expected == expected_connected

    actual_subgraph = module.kl_connected_subgraph(
        fnx_graph, 2, 2, low_memory=low_memory
    )
    expected_subgraph = nx.kl_connected_subgraph(
        nx_graph, 2, 2, low_memory=low_memory
    )
    _assert_same_graph(actual_subgraph, expected_subgraph)


def test_kl_connected_subgraph_preserves_cluster_edges_and_drops_bridge():
    module = importlib.import_module("franken_networkx.hybrid")

    actual = module.kl_connected_subgraph(fnx.barbell_graph(3, 1), 2, 2)

    assert set(_canonical_edges(actual)) == {
        (0, 1),
        (0, 2),
        (1, 2),
        (4, 5),
        (4, 6),
        (5, 6),
    }


def test_hybrid_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.hybrid")

    with pytest.raises(TypeError):
        module.is_kl_connected(fnx.path_graph(3), 2, 2, unsupported=True)
