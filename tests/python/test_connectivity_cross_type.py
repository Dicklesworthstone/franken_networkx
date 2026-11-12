"""br-r37-c1-pf5vu: regression — connectivity / structure-test family
accepts nx graph args via boundary coercion.
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
def test_is_connected_accepts_nx_graph():
    assert fnx.is_connected(nx.path_graph(5)) is True
    assert fnx.is_connected(nx.Graph([(0, 1), (2, 3)])) is False


@needs_nx
def test_connected_components_accepts_nx_graph():
    comps = list(fnx.connected_components(nx.Graph([(0, 1), (2, 3)])))
    assert sorted([sorted(c) for c in comps]) == [[0, 1], [2, 3]]


@needs_nx
def test_number_connected_components_accepts_nx_graph():
    assert fnx.number_connected_components(nx.Graph([(0, 1), (2, 3)])) == 2


@needs_nx
def test_is_tree_accepts_nx_graph():
    assert fnx.is_tree(nx.path_graph(5)) is True
    assert fnx.is_tree(nx.cycle_graph(4)) is False


@needs_nx
def test_is_forest_accepts_nx_graph():
    assert fnx.is_forest(nx.path_graph(5)) is True
    assert fnx.is_forest(nx.Graph([(0, 1), (2, 3)])) is True


@needs_nx
def test_is_bipartite_accepts_nx_graph():
    assert fnx.is_bipartite(nx.complete_bipartite_graph(3, 3)) is True
    assert fnx.is_bipartite(nx.cycle_graph(3)) is False


@needs_nx
def test_is_directed_acyclic_graph_accepts_nx_graph():
    assert fnx.is_directed_acyclic_graph(nx.DiGraph([(0, 1), (1, 2)])) is True
    assert fnx.is_directed_acyclic_graph(nx.DiGraph([(0, 1), (1, 0)])) is False


@needs_nx
def test_no_regression_fnx_input():
    """Same-type calls still work."""
    fg = fnx.path_graph(5)
    assert fnx.is_connected(fg) is True
    assert fnx.is_tree(fg) is True
    assert fnx.is_bipartite(fg) is True
