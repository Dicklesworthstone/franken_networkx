"""br-r37-c1-eghxq: regression — 23 BFS/DFS/connectivity functions
accept nx graph args via boundary coercion."""

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
def test_bfs_edges_nx():
    assert list(fnx.bfs_edges(nx.path_graph(5), 0)) == [(0, 1), (1, 2), (2, 3), (3, 4)]


@needs_nx
def test_dfs_edges_nx():
    edges = list(fnx.dfs_edges(nx.path_graph(5), 0))
    assert len(edges) == 4


@needs_nx
def test_bfs_layers_nx():
    layers = list(fnx.bfs_layers(nx.path_graph(5), 0))
    assert layers == [[0], [1], [2], [3], [4]]


@needs_nx
def test_bfs_predecessors_nx():
    assert dict(fnx.bfs_predecessors(nx.path_graph(5), 0)) == {1: 0, 2: 1, 3: 2, 4: 3}


@needs_nx
def test_bfs_successors_nx():
    assert dict(fnx.bfs_successors(nx.path_graph(5), 0)) == {0: [1], 1: [2], 2: [3], 3: [4]}


@needs_nx
def test_dfs_preorder_nodes_nx():
    assert list(fnx.dfs_preorder_nodes(nx.path_graph(5), 0)) == [0, 1, 2, 3, 4]


@needs_nx
def test_dfs_postorder_nodes_nx():
    assert list(fnx.dfs_postorder_nodes(nx.path_graph(5), 0)) == [4, 3, 2, 1, 0]


@needs_nx
def test_descendants_at_distance_nx():
    assert fnx.descendants_at_distance(nx.path_graph(5), 0, 2) == {2}


@needs_nx
def test_ancestors_nx():
    assert fnx.ancestors(nx.DiGraph([(0, 1), (1, 2)]), 2) == {0, 1}


@needs_nx
def test_descendants_nx():
    assert fnx.descendants(nx.DiGraph([(0, 1), (1, 2)]), 0) == {1, 2}


@needs_nx
def test_cycle_basis_nx():
    cycles = list(fnx.cycle_basis(nx.cycle_graph(4)))
    assert len(cycles) == 1


@needs_nx
def test_strongly_connected_components_nx():
    comps = list(fnx.strongly_connected_components(nx.DiGraph([(0, 1), (1, 2), (2, 0)])))
    assert sorted([sorted(c) for c in comps]) == [[0, 1, 2]]


@needs_nx
def test_weakly_connected_components_nx():
    comps = list(fnx.weakly_connected_components(nx.DiGraph([(0, 1), (2, 3)])))
    assert len(comps) == 2


@needs_nx
def test_is_strongly_connected_nx():
    assert fnx.is_strongly_connected(nx.DiGraph([(0, 1), (1, 0)])) is True


@needs_nx
def test_is_weakly_connected_nx():
    assert fnx.is_weakly_connected(nx.DiGraph([(0, 1)])) is True


@needs_nx
def test_number_strongly_connected_components_nx():
    assert fnx.number_strongly_connected_components(nx.DiGraph([(0, 1), (1, 0), (2, 3)])) == 3


@needs_nx
def test_number_weakly_connected_components_nx():
    assert fnx.number_weakly_connected_components(nx.DiGraph([(0, 1), (2, 3)])) == 2


@needs_nx
def test_articulation_points_nx():
    assert sorted(fnx.articulation_points(nx.path_graph(5))) == [1, 2, 3]


@needs_nx
def test_bridges_nx():
    assert len(list(fnx.bridges(nx.path_graph(5)))) == 4


@needs_nx
def test_core_number_nx():
    assert fnx.core_number(nx.path_graph(5)) == {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}


@needs_nx
def test_eulerian_path_nx():
    path = list(fnx.eulerian_path(nx.path_graph(3)))
    assert len(path) == 2
