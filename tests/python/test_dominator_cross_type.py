"""br-r37-c1-1y7h1: 4 more functions accept nx graph args."""

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
def test_global_node_connectivity_nx():
    assert fnx.node_connectivity(nx.path_graph(5)) == 1


@needs_nx
def test_all_pairs_node_connectivity_nx():
    result = dict(fnx.all_pairs_node_connectivity(nx.complete_graph(4)))
    assert result[0][1] == 3


@needs_nx
def test_immediate_dominators_nx():
    assert dict(fnx.immediate_dominators(nx.DiGraph([(0, 1), (1, 2)]), 0)) == {1: 0, 2: 1}


@needs_nx
def test_dominance_frontiers_nx():
    result = dict(fnx.dominance_frontiers(nx.DiGraph([(0, 1), (1, 2)]), 0))
    assert result == {0: set(), 1: set(), 2: set()}
