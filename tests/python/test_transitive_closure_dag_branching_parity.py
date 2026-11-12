"""Differential + golden parity for ``transitive_closure_dag`` / ``dag_to_branching``.

``transitive_closure_dag(G)`` adds an edge ``(u, v)`` for every pair where
``v`` is reachable from ``u`` in a DAG; ``dag_to_branching(G)`` expands a
DAG into a branching (forest of out-trees) whose nodes carry a ``source``
attribute. Neither had a dedicated test file.

br-r37-c1-h1fyk
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_dag(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # u < v keeps it acyclic
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("seed", range(50))
def test_transitive_closure_dag_matches_networkx(seed):
    fg, ng = _random_dag(seed)
    assert sorted(fnx.transitive_closure_dag(fg).edges()) == sorted(
        nx.transitive_closure_dag(ng).edges()
    )


def test_transitive_closure_dag_golden():
    g = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert sorted(fnx.transitive_closure_dag(g).edges()) == [
        (0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)
    ]


def test_transitive_closure_dag_cyclic_raises_like_networkx():
    fg = fnx.DiGraph([(0, 1), (1, 0)])
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.NetworkXUnfeasible):
        fnx.transitive_closure_dag(fg)
    with pytest.raises(nx.NetworkXUnfeasible):
        nx.transitive_closure_dag(ng)


@pytest.mark.parametrize("seed", range(40))
def test_dag_to_branching_is_valid_branching(seed):
    fg, ng = _random_dag(seed)
    fb = fnx.dag_to_branching(fg)
    nb = nx.dag_to_branching(ng)
    # Same shape, a valid branching, and every node records its source.
    assert fb.number_of_nodes() == nb.number_of_nodes()
    assert fb.number_of_edges() == nb.number_of_edges()
    assert nx.is_branching(fb)
    assert all("source" in d for _, d in fb.nodes(data=True))


def test_dag_to_branching_cyclic_raises_like_networkx():
    # dag_to_branching raises HasACycle (NOT NetworkXUnfeasible, unlike
    # transitive_closure_dag) — both libraries agree on the exact type.
    fg = fnx.DiGraph([(0, 1), (1, 0)])
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.HasACycle):
        fnx.dag_to_branching(fg)
    with pytest.raises(nx.HasACycle):
        nx.dag_to_branching(ng)
