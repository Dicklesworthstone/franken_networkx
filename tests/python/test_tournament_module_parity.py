"""Differential + golden parity for the tournament algorithm module.

A *tournament* is a directed graph in which every pair of distinct nodes
is joined by exactly one directed edge. ``networkx.algorithms.tournament``
exposes ``is_tournament``, ``score_sequence``, ``tournament_matrix``,
``hamiltonian_path``, ``is_reachable``, ``is_strongly_connected`` and the
seeded ``random_tournament`` generator. The module had no dedicated test
file.

This locks fnx against the real upstream library with:

* differential parity across random tournaments for every predicate /
  query (including exact ``hamiltonian_path`` order and all-pairs
  ``is_reachable``),
* byte-exact seeded ``random_tournament`` parity,
* hand-computed goldens (transitive vs 3-cycle tournaments),
* a validity invariant for ``hamiltonian_path``, and
* the undirected ``NetworkXNotImplemented`` contract.

br-r37-c1-udxl7
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import tournament as fnx_tournament
from networkx.algorithms import tournament as nx_tournament


def _build_tournament(seed, lib):
    """Build the same random tournament on nodes 0..n-1 from `lib`."""
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    g = lib.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.5:
                g.add_edge(u, v)
            else:
                g.add_edge(v, u)
    return g, n


# ---------------------------------------------------------------------------
# Differential parity across random tournaments.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_tournament_predicates_match_networkx(seed):
    fg, n = _build_tournament(seed, fnx)
    ng, _ = _build_tournament(seed, nx)

    assert fnx_tournament.is_tournament(fg) == nx_tournament.is_tournament(ng)
    assert list(fnx_tournament.score_sequence(fg)) == list(
        nx_tournament.score_sequence(ng)
    )
    assert fnx_tournament.is_strongly_connected(fg) == (
        nx_tournament.is_strongly_connected(ng)
    )
    assert np.array_equal(
        np.asarray(fnx_tournament.tournament_matrix(fg).todense()),
        np.asarray(nx_tournament.tournament_matrix(ng).todense()),
    )


def test_tournament_matrix_weighted_entries_match_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    edges = [
        ("a", "b", {"weight": 2}),
        ("c", "a", {"weight": 5}),
        ("b", "c", {"weight": 7}),
    ]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fnx_matrix = fnx_tournament.tournament_matrix(fg)
    nx_matrix = nx_tournament.tournament_matrix(ng)

    assert type(fnx_matrix).__name__ == type(nx_matrix).__name__
    assert fnx_matrix.dtype == nx_matrix.dtype
    assert np.array_equal(
        np.asarray(fnx_matrix.todense()),
        np.asarray(nx_matrix.todense()),
    )


@pytest.mark.parametrize("seed", range(50))
def test_hamiltonian_path_matches_networkx(seed):
    fg, n = _build_tournament(seed, fnx)
    ng, _ = _build_tournament(seed, nx)
    fpath = list(fnx_tournament.hamiltonian_path(fg))
    npath = list(nx_tournament.hamiltonian_path(ng))
    assert fpath == npath, f"seed={seed}: fnx={fpath} nx={npath}"
    # Validity invariant: a permutation of all nodes whose consecutive
    # pairs are edges (every tournament has a Hamiltonian path).
    assert len(fpath) == n
    assert set(fpath) == set(range(n))
    assert all(fg.has_edge(fpath[i], fpath[i + 1]) for i in range(n - 1))


@pytest.mark.parametrize("seed", range(40))
def test_is_reachable_matches_networkx(seed):
    fg, n = _build_tournament(seed, fnx)
    ng, _ = _build_tournament(seed, nx)
    for s in range(n):
        for t in range(n):
            assert fnx_tournament.is_reachable(fg, s, t) == (
                nx_tournament.is_reachable(ng, s, t)
            ), f"seed={seed} reach({s},{t})"


def test_is_reachable_bitset_endpoint_parity():
    labels = [("node", i) for i in range(5)]
    edges = [
        (labels[0], labels[1]),
        (labels[0], labels[2]),
        (labels[3], labels[0]),
        (labels[1], labels[2]),
        (labels[1], labels[3]),
        (labels[4], labels[1]),
        (labels[2], labels[3]),
        (labels[2], labels[4]),
        (labels[3], labels[4]),
        (labels[0], labels[4]),
    ]
    fg = fnx.DiGraph(edges)
    ng = nx.DiGraph(edges)
    probes = [
        (labels[0], labels[3]),
        (labels[3], labels[0]),
        (labels[2], ("missing", "target")),
        (("missing", "source"), labels[2]),
        (("same-missing",), ("same-missing",)),
    ]
    for source, target in probes:
        assert fnx_tournament.is_reachable(fg, source, target) == (
            nx_tournament.is_reachable(ng, source, target)
        )


# ---------------------------------------------------------------------------
# Seeded random_tournament generator parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("n", [5, 8])
def test_random_tournament_matches_networkx_byte_exact(seed, n):
    fg = fnx_tournament.random_tournament(n, seed=seed)
    ng = nx_tournament.random_tournament(n, seed=seed)
    assert sorted(map(tuple, fg.edges())) == sorted(map(tuple, ng.edges()))
    assert fnx_tournament.is_tournament(fg)


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_transitive_tournament_golden():
    # 0→1, 0→2, 1→2: a transitive tournament. Not strongly connected;
    # scores are the distinct out-degrees 0, 1, 2.
    t = fnx.DiGraph([(0, 1), (0, 2), (1, 2)])
    assert fnx_tournament.is_tournament(t)
    assert not fnx_tournament.is_strongly_connected(t)
    assert list(fnx_tournament.score_sequence(t)) == [0, 1, 2]


def test_three_cycle_tournament_golden():
    # 0→1→2→0: a 3-cycle tournament is strongly connected; every node
    # has out-degree 1.
    t = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert fnx_tournament.is_tournament(t)
    assert fnx_tournament.is_strongly_connected(t)
    assert list(fnx_tournament.score_sequence(t)) == [1, 1, 1]


def test_non_tournament_is_rejected():
    # A mutual pair (0↔1) is not a tournament; a graph missing a pair edge
    # is not a tournament either.
    assert not fnx_tournament.is_tournament(fnx.DiGraph([(0, 1), (1, 0)]))
    missing = fnx.DiGraph([(0, 1)])
    missing.add_node(2)
    assert not fnx_tournament.is_tournament(missing)


# ---------------------------------------------------------------------------
# Error contract.
# ---------------------------------------------------------------------------


def test_is_tournament_rejects_undirected_like_networkx():
    with pytest.raises(nx.NetworkXNotImplemented):
        fnx_tournament.is_tournament(fnx.Graph([(0, 1)]))
    with pytest.raises(nx.NetworkXNotImplemented):
        nx_tournament.is_tournament(nx.Graph([(0, 1)]))
