"""br-r37-c1-nwkg0: regression — operator/spanning-tree family accepts
nx graph args via boundary coercion."""

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
def test_complement_accepts_nx_graph():
    g = fnx.complement(nx.path_graph(5))
    assert g.number_of_edges() == 6


@needs_nx
def test_dfs_tree_accepts_nx_graph():
    g = fnx.dfs_tree(nx.path_graph(5), 0)
    assert g.is_directed() is True
    assert sorted(g.edges()) == [(0, 1), (1, 2), (2, 3), (3, 4)]


@needs_nx
def test_minimum_spanning_tree_accepts_nx_graph():
    g = fnx.minimum_spanning_tree(nx.path_graph(5))
    assert g.number_of_edges() == 4


@needs_nx
def test_maximum_spanning_tree_accepts_nx_graph():
    g = fnx.maximum_spanning_tree(nx.path_graph(5))
    assert g.number_of_edges() == 4


@needs_nx
def test_transitive_closure_accepts_nx_graph():
    g = fnx.transitive_closure(nx.DiGraph([(0, 1), (1, 2)]))
    assert sorted(g.edges()) == [(0, 1), (0, 2), (1, 2)]


@needs_nx
def test_girth_accepts_nx_graph():
    assert fnx.girth(nx.cycle_graph(4)) == 4


@needs_nx
def test_find_cycle_accepts_nx_graph():
    cycle = list(fnx.find_cycle(nx.DiGraph([(0, 1), (1, 2), (2, 0)])))
    assert len(cycle) == 3


@needs_nx
def test_triangles_accepts_nx_graph():
    g = nx.complete_graph(4)
    assert fnx.triangles(g) == {0: 3, 1: 3, 2: 3, 3: 3}


@needs_nx
def test_maximal_matching_accepts_nx_graph():
    m = list(fnx.maximal_matching(nx.path_graph(5)))
    assert len(m) == 2
