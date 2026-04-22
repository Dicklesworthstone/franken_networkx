"""Parity coverage for bfs_successors iterator contract.

Bead franken_networkx-788l: must return a generator of
(parent, [successors]) pairs in BFS discovery order, including with
depth_limit and sort_neighbors.
"""

import types

import networkx as nx
import pytest

import franken_networkx as fnx


def test_bfs_successors_returns_generator_of_pairs():
    fg = fnx.Graph()
    fg.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])
    ng = nx.Graph()
    ng.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])

    f_res = fnx.bfs_successors(fg, "a")
    n_res = nx.bfs_successors(ng, "a")
    assert isinstance(f_res, types.GeneratorType)
    assert isinstance(n_res, types.GeneratorType)

    assert list(f_res) == list(n_res)


def test_bfs_successors_path_graph_discovery_order_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert list(fnx.bfs_successors(fg, 0)) == list(nx.bfs_successors(ng, 0))


def test_bfs_successors_depth_limit_matches_networkx():
    fg = fnx.Graph()
    fg.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])
    ng = nx.Graph()
    ng.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])

    assert list(fnx.bfs_successors(fg, "a", depth_limit=1)) == list(
        nx.bfs_successors(ng, "a", depth_limit=1)
    )


def test_bfs_successors_sort_neighbors_matches_networkx():
    fg = fnx.Graph()
    fg.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])
    ng = nx.Graph()
    ng.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")])

    sorter = lambda nbrs: sorted(nbrs, reverse=True)
    assert list(fnx.bfs_successors(fg, "a", sort_neighbors=sorter)) == list(
        nx.bfs_successors(ng, "a", sort_neighbors=sorter)
    )
