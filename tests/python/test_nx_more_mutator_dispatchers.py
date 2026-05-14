"""br-r37-c1-pq52x: register 5 more mutating @_dispatchable functions
in fnx's backend so nx.X(fnx_graph) no longer raises
NotImplementedError when X is mutation-preserving.

Same dispatch-gap family as br-r37-c1-frbgb / tq78w / l2j31 / 0epvo.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_directed_edge_swap_via_nx_on_fnx_digraph():
    g = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2), (2, 3), (3, 0)])
    nx.directed_edge_swap(g, nswap=1, max_tries=100, seed=42)
    assert g.number_of_edges() == 6


@needs_nx
def test_incremental_closeness_via_nx_on_fnx_graph():
    g = fnx.path_graph(5)
    res = nx.incremental_closeness_centrality(g, (0, 2))
    assert set(res.keys()) == {0, 1, 2, 3, 4}


@needs_nx
def test_recursive_simple_cycles_via_nx_on_fnx_digraph():
    g = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    cycles = nx.recursive_simple_cycles(g)
    # The 3-cycle should be the only one
    assert len(cycles) == 1
    assert set(cycles[0]) == {0, 1, 2}


@needs_nx
def test_remove_edge_attributes_via_nx_on_fnx_graph():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=2, color="red")
    nx.remove_edge_attributes(g, "color")
    assert dict(g[0][1]) == {"weight": 2}


@needs_nx
def test_remove_node_attributes_via_nx_on_fnx_graph():
    g = fnx.Graph()
    g.add_node(0, color="red")
    nx.remove_node_attributes(g, "color")
    assert dict(g.nodes[0]) == {}


@needs_nx
def test_backend_registers_five_more_mutators():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    for fname in (
        "directed_edge_swap",
        "incremental_closeness_centrality",
        "recursive_simple_cycles",
        "remove_edge_attributes",
        "remove_node_attributes",
    ):
        assert fname in _SUPPORTED_ALGORITHMS, f"{fname} missing"


@needs_nx
def test_directed_edge_swap_direct_with_random_instance_seed():
    """The dispatcher path passes a ``random.Random`` instance as seed;
    fnx.directed_edge_swap must handle that (same as
    br-r37-c1-frbgb's fix for the undirected variant)."""
    import random

    g = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2), (2, 3), (3, 0)])
    fnx.directed_edge_swap(g, nswap=1, max_tries=100, seed=random.Random(42))
    assert g.number_of_edges() == 6
