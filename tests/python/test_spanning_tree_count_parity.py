"""Spanning-tree enumeration: count parity, Cayley golden, MST optimality.

Covers ``number_of_spanning_trees`` (Kirchhoff's theorem), the MST
optimality invariant, and ``random_spanning_tree`` validity. None had a
dedicated test file.

br-r37-c1-uvvqy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, weighted=False, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(3, 7)
    fg = fnx.Graph()
    fg.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                if weighted:
                    fg.add_edge(u, v, weight=rng.randint(1, 5))
                else:
                    fg.add_edge(u, v)
    ng = nx.Graph()
    ng.add_nodes_from(range(n))
    ng.add_edges_from((u, v, d) for u, v, d in fg.edges(data=True))
    return fg, ng, n


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_number_of_spanning_trees_matches_networkx(weighted, seed):
    fg, ng, _ = _connected(seed, weighted=weighted)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    kwargs = {"weight": "weight"} if weighted else {}
    assert fnx.number_of_spanning_trees(fg, **kwargs) == pytest.approx(
        nx.number_of_spanning_trees(ng, **kwargs), rel=1e-6
    )


@pytest.mark.parametrize("n", range(2, 8))
def test_cayley_formula_golden(n):
    # Kirchhoff/Cayley: the complete graph K_n has exactly n^(n-2) spanning trees.
    assert round(fnx.number_of_spanning_trees(fnx.complete_graph(n))) == n ** (n - 2)


@pytest.mark.parametrize("seed", range(40))
def test_mst_is_optimal_and_is_a_tree(seed):
    fg, ng, n = _connected(seed, weighted=True, p=0.55)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    mst = fnx.minimum_spanning_tree(fg, weight="weight")
    mst_weight = sum(d["weight"] for _, _, d in mst.edges(data=True))
    assert mst.number_of_edges() == n - 1
    assert nx.is_tree(nx.Graph(mst.edges()))
    # No spanning tree can weigh less than the MST.
    for k in range(3):
        rt = fnx.random_spanning_tree(fg, weight="weight", seed=seed * 10 + k)
        assert nx.is_tree(nx.Graph(rt.edges()))
        assert rt.number_of_edges() == n - 1
        assert mst_weight <= sum(fg[u][v]["weight"] for u, v in rt.edges()) + 1e-9
