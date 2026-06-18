"""Differential + metamorphic parity for the clique algorithm family.

Covers ``find_cliques`` (maximal cliques, Bron-Kerbosch),
``enumerate_all_cliques`` (every clique), ``node_clique_number``,
``number_of_cliques`` and ``make_max_clique_graph``. The family had only
scattered coverage.

This locks fnx against the real upstream networkx with:

* differential parity (order-invariant set/dict comparison) across
  random graphs,
* metamorphic invariants independent of the reference — every
  ``find_cliques`` output is an actual complete subgraph, and the largest
  ``node_clique_number`` equals the largest maximal-clique size, and
* hand-computed goldens on complete, path, and cycle graphs.

br-r37-c1-han3d
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


def _clique_set(cliques):
    return {frozenset(c) for c in cliques}


# ---------------------------------------------------------------------------
# Differential parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_find_cliques_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert _clique_set(fnx.find_cliques(fg)) == _clique_set(nx.find_cliques(ng))


@pytest.mark.parametrize("seed", range(50))
def test_enumerate_all_cliques_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert _clique_set(fnx.enumerate_all_cliques(fg)) == _clique_set(
        nx.enumerate_all_cliques(ng)
    )


@pytest.mark.parametrize("seed", range(50))
def test_node_and_number_of_cliques_match_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert fnx.node_clique_number(fg) == nx.node_clique_number(ng)
    assert fnx.number_of_cliques(fg) == nx.number_of_cliques(ng)


@pytest.mark.parametrize("seed", range(40))
def test_make_max_clique_graph_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    fm = fnx.make_max_clique_graph(fg)
    nm = nx.make_max_clique_graph(ng)
    assert fm.number_of_nodes() == nm.number_of_nodes()
    assert fm.number_of_edges() == nm.number_of_edges()


# ---------------------------------------------------------------------------
# Metamorphic invariants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_find_cliques_yields_complete_subgraphs(seed):
    fg, _, _ = _pair(seed)
    for clique in fnx.find_cliques(fg):
        members = list(clique)
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                assert fg.has_edge(members[i], members[j]), (
                    f"seed={seed}: find_cliques returned a non-clique"
                )


@pytest.mark.parametrize("seed", range(50))
def test_node_clique_number_consistent_with_max_clique(seed):
    fg, _, _ = _pair(seed)
    cliques = list(fnx.find_cliques(fg))
    if not cliques:
        pytest.skip("empty graph")
    max_clique_size = max(len(c) for c in cliques)
    assert max(fnx.node_clique_number(fg).values()) == max_clique_size


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_complete_graph_golden():
    k5 = fnx.complete_graph(5)
    cliques = list(fnx.find_cliques(k5))
    assert len(cliques) == 1
    assert set(cliques[0]) == {0, 1, 2, 3, 4}
    assert max(fnx.node_clique_number(k5).values()) == 5


def test_path_and_cycle_goldens():
    # A path's maximal cliques are its edges.
    p4 = fnx.path_graph(4)
    assert _clique_set(fnx.find_cliques(p4)) == {
        frozenset({0, 1}), frozenset({1, 2}), frozenset({2, 3})
    }
    # A 4-cycle's maximal cliques are its edges too (no triangle).
    c4 = fnx.cycle_graph(4)
    assert all(len(c) == 2 for c in fnx.find_cliques(c4))
