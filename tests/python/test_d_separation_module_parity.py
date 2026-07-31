"""Parity coverage for the ``franken_networkx.d_separation`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_d_separator",
    "is_minimal_d_separator",
    "find_minimal_d_separator",
)


def _build_diamond_pair():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def _build_oracle_strongly_connected_255201798_pair():
    """Recreate behavioral-oracle input ``strongly_connected-255201798``."""
    nodes = [
        (0, {"color": "even", "value": 1}),
        (1, {"color": "odd", "value": 2}),
        (2, {"color": "even", "value": 3}),
        (3, {"color": "odd", "value": 4}),
        (4, {"color": "even", "value": 5}),
        (5, {"color": "odd", "value": 6}),
    ]
    edges = [
        (0, 1, {"capacity": 6, "color": "warm", "weight": 4}),
        (1, 2, {"capacity": 7, "color": "cool", "weight": 7}),
        (2, 3, {"capacity": 1, "color": "warm", "weight": 1}),
        (3, 4, {"capacity": 2, "color": "cool", "weight": 4}),
        (4, 5, {"capacity": 3, "color": "warm", "weight": 7}),
        (5, 0, {"capacity": 4, "color": "cool", "weight": 1}),
        (2, 1, {"capacity": 5, "color": "warm", "weight": 4}),
        (4, 1, {"capacity": 7, "color": "warm", "weight": 1}),
        (3, 0, {"capacity": 1, "color": "cool", "weight": 4}),
        (3, 5, {"capacity": 2, "color": "warm", "weight": 7}),
        (1, 3, {"capacity": 3, "color": "cool", "weight": 1}),
    ]
    fnx_graph = fnx.DiGraph(case_id="strongly_connected-255201798")
    nx_graph = nx.DiGraph(case_id="strongly_connected-255201798")
    for node, attrs in nodes:
        fnx_graph.add_node(node, **attrs)
        nx_graph.add_node(node, **attrs)
    for u, v, attrs in edges:
        fnx_graph.add_edge(u, v, **attrs)
        nx_graph.add_edge(u, v, **attrs)
    return fnx_graph, nx_graph


def test_direct_d_separation_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.d_separation")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_d_separation_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.d_separation")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.d_separation")

    assert via_algorithms is direct
    assert fnx.algorithms.d_separation is direct


def test_d_separation_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    expected = importlib.import_module("networkx.algorithms.d_separation")

    assert set(module.__all__) == set(expected.__all__)


def test_d_separation_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    expected = importlib.import_module("networkx.algorithms.d_separation")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "x,y,z",
    [
        ({0}, {3}, set()),
        ({0}, {3}, {1, 2}),
        ({1}, {2}, {0}),
    ],
)
def test_is_d_separator_matches_networkx(x, y, z):
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()

    assert module.is_d_separator(fnx_graph, x, y, z) == nx.is_d_separator(
        nx_graph, x, y, z
    )


@pytest.mark.parametrize("z", [{1, 2}, {1}, set()])
def test_is_minimal_d_separator_matches_networkx(z):
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()
    x = {0}
    y = {3}

    assert module.is_minimal_d_separator(fnx_graph, x, y, z) == (
        nx.is_minimal_d_separator(nx_graph, x, y, z)
    )


@pytest.mark.parametrize(
    "name",
    ["is_d_separator", "is_minimal_d_separator"],
)
def test_cyclic_oracle_input_raises_exact_networkx_error(name):
    """Four oracle paths formerly returned False instead of rejecting cycles."""
    module = importlib.import_module("franken_networkx.d_separation")
    nx_module = importlib.import_module("networkx.algorithms.d_separation")
    fnx_graph, nx_graph = _build_oracle_strongly_connected_255201798_pair()
    args = ({0}, {1}, {2})

    for fnx_function, nx_function in (
        (getattr(fnx, name), getattr(nx, name)),
        (getattr(module, name), getattr(nx_module, name)),
    ):
        with pytest.raises(nx.NetworkXError) as fnx_exc:
            fnx_function(fnx_graph, *args)
        with pytest.raises(nx.NetworkXError) as nx_exc:
            nx_function(nx_graph, *args)

        assert type(fnx_exc.value) is type(nx_exc.value)
        assert str(fnx_exc.value) == "graph should be directed acyclic"
        assert str(fnx_exc.value) == str(nx_exc.value)


def test_d_separator_guard_order_matches_networkx():
    undirected_fnx = fnx.Graph([(0, 1)])
    undirected_nx = nx.Graph([(0, 1)])
    cyclic_fnx = fnx.DiGraph([(0, 1), (1, 0)])
    cyclic_nx = nx.DiGraph([(0, 1), (1, 0)])

    for name in ("is_d_separator", "is_minimal_d_separator"):
        with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
            getattr(fnx, name)(undirected_fnx, {99}, {1}, set())
        with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
            getattr(nx, name)(undirected_nx, {99}, {1}, set())
        assert type(fnx_exc.value) is type(nx_exc.value)
        assert str(fnx_exc.value) == str(nx_exc.value)

    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.is_d_separator(cyclic_fnx, {99}, {1}, set())
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.is_d_separator(cyclic_nx, {99}, {1}, set())
    assert type(fnx_exc.value) is type(nx_exc.value)
    assert str(fnx_exc.value) == str(nx_exc.value)

    with pytest.raises(nx.NetworkXError) as fnx_exc:
        fnx.is_minimal_d_separator(cyclic_fnx, {99}, {1}, set())
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.is_minimal_d_separator(cyclic_nx, {99}, {1}, set())
    assert type(fnx_exc.value) is type(nx_exc.value)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_find_minimal_d_separator_matches_networkx():
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, nx_graph = _build_diamond_pair()
    x = {0}
    y = {3}

    assert module.find_minimal_d_separator(
        fnx_graph, x, y
    ) == nx.find_minimal_d_separator(nx_graph, x, y)


def test_d_separation_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.d_separation")
    fnx_graph, _ = _build_diamond_pair()

    with pytest.raises(TypeError):
        module.is_d_separator(fnx_graph, {0}, {3}, set(), unsupported=True)
