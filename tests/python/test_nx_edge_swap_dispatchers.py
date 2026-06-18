"""br-r37-c1-frbgb: regression — nx.double_edge_swap and
nx.connected_double_edge_swap dispatch through fnx for fnx graphs.

Two coordinated fixes:
  1. Register fnx.double_edge_swap and fnx.connected_double_edge_swap
     in backend._SUPPORTED_ALGORITHMS so the dispatcher routes the
     fnx graph through fnx's own wrapper (without it, the dispatcher
     raises NotImplementedError on these mutation-preserving fns).
  2. Teach fnx.{double_edge_swap, connected_double_edge_swap} to
     accept a pre-built ``random.Random`` instance as ``seed``,
     because nx's ``@py_random_state("seed")`` decorator has
     already wrapped the seed by the time the dispatcher hands it
     to the backend.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx
from franken_networkx import swap as fnx_swap

try:
    import networkx as nx
    from networkx.algorithms import swap as nx_swap

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _directed_swap_graph(module):
    graph = module.DiGraph()
    graph.add_edges_from(
        [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (2, 4), (4, 1)]
    )
    return graph


@needs_nx
def test_nx_double_edge_swap_on_fnx_graph_runs():
    g = fnx.cycle_graph(8)
    result = nx.algorithms.swap.double_edge_swap(g, nswap=1, max_tries=100, seed=42)
    assert result is g  # in-place mutation returns the same object
    assert g.number_of_edges() == 8  # swap preserves edge count


@needs_nx
def test_nx_connected_double_edge_swap_on_fnx_graph_runs():
    g = fnx.cycle_graph(8)
    swaps = nx.algorithms.swap.connected_double_edge_swap(g, nswap=1, seed=42)
    assert isinstance(swaps, int)
    assert swaps >= 0


@needs_nx
def test_fnx_double_edge_swap_accepts_random_instance_seed():
    """The dispatcher path passes a ``random.Random`` instance as
    seed; fnx's wrapper must handle that without crashing."""
    g = fnx.cycle_graph(8)
    fnx.double_edge_swap(g, nswap=1, max_tries=100, seed=random.Random(42))
    assert g.number_of_edges() == 8


@needs_nx
def test_fnx_connected_double_edge_swap_accepts_random_instance_seed():
    g = fnx.cycle_graph(8)
    fnx.connected_double_edge_swap(g, nswap=1, seed=random.Random(42))
    assert g.number_of_edges() == 8


@needs_nx
def test_fnx_double_edge_swap_int_seed_regression():
    """Original int-seed path must keep working (no regression from
    the Random-instance handling)."""
    g = fnx.cycle_graph(8)
    fnx.double_edge_swap(g, nswap=1, max_tries=100, seed=42)
    assert g.number_of_edges() == 8


@needs_nx
def test_backend_registers_edge_swap_helpers():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    assert "double_edge_swap" in _SUPPORTED_ALGORITHMS
    assert "connected_double_edge_swap" in _SUPPORTED_ALGORITHMS


@needs_nx
def test_swap_module_double_edge_swap_returns_original_fnx_input():
    graph = fnx.cycle_graph(8)
    expected_graph = fnx.cycle_graph(8)

    result = fnx_swap.double_edge_swap(graph, nswap=1, max_tries=100, seed=7)
    expected = fnx.double_edge_swap(expected_graph, nswap=1, max_tries=100, seed=7)

    assert result is graph
    assert expected is expected_graph
    assert sorted(result.edges()) == sorted(expected.edges())


@needs_nx
def test_swap_module_double_edge_swap_returns_original_nx_input():
    graph = nx.cycle_graph(8)
    expected_graph = nx.cycle_graph(8)

    result = fnx_swap.double_edge_swap(graph, nswap=1, max_tries=100, seed=7)
    expected = nx_swap.double_edge_swap(
        expected_graph, nswap=1, max_tries=100, seed=7
    )

    assert result is graph
    assert expected is expected_graph
    assert sorted(result.edges()) == sorted(expected.edges())


@needs_nx
def test_swap_module_directed_edge_swap_returns_original_fnx_input():
    graph = _directed_swap_graph(fnx)
    expected_graph = _directed_swap_graph(fnx)

    result = fnx_swap.directed_edge_swap(graph, nswap=1, max_tries=100, seed=3)
    expected = fnx.directed_edge_swap(
        expected_graph, nswap=1, max_tries=100, seed=3
    )

    assert result is graph
    assert expected is expected_graph
    assert sorted(result.edges()) == sorted(expected.edges())


@needs_nx
def test_swap_module_directed_edge_swap_returns_original_nx_input():
    graph = _directed_swap_graph(nx)
    expected_graph = _directed_swap_graph(nx)

    result = fnx_swap.directed_edge_swap(graph, nswap=1, max_tries=100, seed=3)
    expected = nx_swap.directed_edge_swap(
        expected_graph, nswap=1, max_tries=100, seed=3
    )

    assert result is graph
    assert expected is expected_graph
    assert sorted(result.edges()) == sorted(expected.edges())


@needs_nx
def test_algorithms_swap_alias_preserves_mutating_return_identity():
    from franken_networkx.algorithms import swap as algorithms_swap

    graph = fnx.cycle_graph(8)
    directed = _directed_swap_graph(fnx)

    result = algorithms_swap.double_edge_swap(
        graph, nswap=1, max_tries=100, seed=7
    )
    directed_result = algorithms_swap.directed_edge_swap(
        directed, nswap=1, max_tries=100, seed=3
    )

    assert result is graph
    assert directed_result is directed
