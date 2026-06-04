"""Parity for the deque-based r-ary tree edge generator.

br-treedeque: _tree_edges_local (used by full_rary_tree / balanced_tree) used a
list with pop(0) (O(n) front-shift) as its BFS frontier queue -- O(n^2) edge
generation. It now uses a deque (O(1) popleft). FIFO order is unchanged, so the
generated edge sequence (and the resulting tree) is byte-identical; full_rary_
tree(2, 300000) goes 4.3s -> 1.65s (~2.6x; the generator alone is ~41x).
"""

import networkx as nx

import franken_networkx as fnx


def test_full_rary_tree_edge_sequence_matches_networkx():
    for r in (2, 3, 4, 5):
        for n in (0, 1, 2, 3, 7, 50, 500, 3000):
            a = nx.full_rary_tree(r, n)
            b = fnx.full_rary_tree(r, n)
            assert list(a.edges()) == list(b.edges()), (r, n)
            assert sorted(a.nodes()) == sorted(b.nodes()), (r, n)


def test_balanced_tree_matches_networkx():
    for r in (2, 3):
        for h in (0, 1, 3, 5):
            a = nx.balanced_tree(r, h)
            b = fnx.balanced_tree(r, h)
            assert list(a.edges()) == list(b.edges()), (r, h)


def test_full_rary_tree_create_using_directed():
    a = nx.full_rary_tree(2, 30, create_using=nx.DiGraph)
    b = fnx.full_rary_tree(2, 30, create_using=fnx.DiGraph)
    assert list(a.edges()) == list(b.edges())
    assert a.is_directed() == b.is_directed() is True


def test_tree_structure_invariants():
    for r in (2, 3):
        for n in (1, 10, 200):
            T = fnx.full_rary_tree(r, n)
            assert T.number_of_nodes() == n
            assert T.number_of_edges() == max(0, n - 1)
            if n >= 1:
                assert fnx.is_connected(T)
                assert fnx.is_tree(T)
