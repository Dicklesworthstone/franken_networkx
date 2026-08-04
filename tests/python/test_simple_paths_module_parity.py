"""Parity coverage for the ``franken_networkx.simple_paths`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "all_simple_paths",
    "is_simple_path",
    "shortest_simple_paths",
    "all_simple_edge_paths",
)


def _build_pair():
    weighted_edges = [
        (0, 1, 1),
        (0, 2, 2),
        (1, 3, 1),
        (2, 3, 1),
        (1, 2, 3),
    ]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def _build_oracle_connected_255201293_pair():
    """Recreate behavioral-oracle input ``connected-255201293`` exactly."""
    nodes = [
        ("n0", {"color": "even", "value": 1}),
        ("n1", {"color": "odd", "value": 2}),
        ("n2", {"color": "even", "value": 3}),
        ("n3", {"color": "odd", "value": 4}),
        ("n4", {"color": "even", "value": 5}),
        ("n5", {"color": "odd", "value": 6}),
        ("n6", {"color": "even", "value": 7}),
    ]
    edges = [
        ("n0", "n1", {"capacity": 5, "color": "warm", "weight": 3}),
        ("n1", "n2", {"capacity": 6, "color": "cool", "weight": 6}),
        ("n2", "n3", {"capacity": 7, "color": "warm", "weight": 9}),
        ("n3", "n4", {"capacity": 1, "color": "cool", "weight": 3}),
        ("n4", "n5", {"capacity": 2, "color": "warm", "weight": 6}),
        ("n5", "n6", {"capacity": 3, "color": "cool", "weight": 9}),
        ("n4", "n1", {"capacity": 4, "color": "warm", "weight": 3}),
        ("n3", "n0", {"capacity": 5, "color": "cool", "weight": 6}),
        ("n6", "n3", {"capacity": 6, "color": "warm", "weight": 9}),
        ("n2", "n5", {"capacity": 1, "color": "warm", "weight": 6}),
        ("n0", "n4", {"capacity": 2, "color": "cool", "weight": 9}),
    ]
    fnx_graph = fnx.Graph(case_id="connected-255201293")
    nx_graph = nx.Graph(case_id="connected-255201293")
    for node, attrs in nodes:
        fnx_graph.add_node(node, **attrs)
        nx_graph.add_node(node, **attrs)
    for u, v, attrs in edges:
        fnx_graph.add_edge(u, v, **attrs)
        nx_graph.add_edge(u, v, **attrs)
    return fnx_graph, nx_graph


def test_direct_simple_paths_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.simple_paths")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_simple_paths_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.simple_paths")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.simple_paths")

    assert via_algorithms is direct
    assert fnx.algorithms.simple_paths is direct


def test_simple_paths_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    expected = importlib.import_module("networkx.algorithms.simple_paths")

    assert set(module.__all__) == set(expected.__all__)


def test_simple_paths_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    expected = importlib.import_module("networkx.algorithms.simple_paths")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_simple_path_generators_match_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, nx_graph = _build_pair()

    assert list(module.all_simple_paths(fnx_graph, 0, 3, cutoff=3)) == list(
        nx.all_simple_paths(nx_graph, 0, 3, cutoff=3)
    )
    assert list(module.shortest_simple_paths(fnx_graph, 0, 3)) == list(
        nx.shortest_simple_paths(nx_graph, 0, 3)
    )
    assert list(module.all_simple_edge_paths(fnx_graph, 0, 3, cutoff=3)) == list(
        nx.all_simple_edge_paths(nx_graph, 0, 3, cutoff=3)
    )


def test_is_simple_path_matches_networkx():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, nx_graph = _build_pair()

    for nodes in ([0, 1, 3], [0, 3], [0, 1, 0]):
        assert module.is_simple_path(fnx_graph, nodes) == nx.is_simple_path(
            nx_graph, nodes
        )


def test_is_simple_path_accepts_exact_oracle_node_set():
    """Both generated-oracle identities formerly raised in FNX."""
    fnx_graph, nx_graph = _build_oracle_connected_255201293_pair()
    nodes = {"n0", "n1", "n2"}
    module = importlib.import_module("franken_networkx.simple_paths")

    assert fnx.is_simple_path(fnx_graph, nodes) == nx.is_simple_path(
        nx_graph, nodes
    )
    assert module.is_simple_path(fnx_graph, nodes) == (
        nx.algorithms.simple_paths.is_simple_path(nx_graph, nodes)
    )


@pytest.mark.parametrize(
    "nodes",
    [
        frozenset((0, 1, 3)),
        {0: "ignored", 1: "ignored", 3: "ignored"},
        range(4),
    ],
)
def test_is_simple_path_sized_iterable_matches_networkx(nodes):
    fnx_graph, nx_graph = _build_pair()

    assert fnx.is_simple_path(fnx_graph, nodes) == nx.is_simple_path(
        nx_graph, nodes
    )


def test_is_simple_path_singleton_set_preserves_networkx_type_error():
    fnx_graph, nx_graph = _build_pair()

    with pytest.raises(TypeError) as fnx_exc:
        fnx.is_simple_path(fnx_graph, {0})
    with pytest.raises(TypeError) as nx_exc:
        nx.is_simple_path(nx_graph, {0})

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_simple_paths_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.simple_paths")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.is_simple_path(fnx_graph, [0, 1], unsupported=True)
