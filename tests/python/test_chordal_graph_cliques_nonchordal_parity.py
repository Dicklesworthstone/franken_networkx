"""Parity for ``chordal_graph_cliques`` on non-chordal input (no fallback).

nx's ``chordal_graph_cliques`` does NOT raise on every non-chordal graph:
it runs MCS per component and yields the maximal cliques it finds (e.g.
C4 -> [{0,1},{1,2},{0,2,3}]), raising NetworkXError only when the MCS
completeness check fails mid-walk. fnx now runs nx's exact algorithm
in-process (br-r37-c1-9vzvv) instead of delegating to nx, so the
no-fallback contract holds while output and raise-behaviour match
byte-for-byte.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def test_cycle4_nonchordal_returns_mcs_cliques():
    # C4 is non-chordal; nx returns MCS cliques, does not raise.
    fg = fnx.cycle_graph(4)
    ng = nx.cycle_graph(4)
    assert set(fnx.chordal_graph_cliques(fg)) == set(nx.chordal_graph_cliques(ng))


@pytest.mark.parametrize("seed", range(60))
def test_chordal_graph_cliques_matches_networkx_by_set(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 10)
    edges = [
        (u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < 0.45
    ]
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    try:
        nr = list(nx.chordal_graph_cliques(ng))
    except nx.NetworkXError as exc:
        with pytest.raises(nx.NetworkXError) as fnx_exc:
            list(fnx.chordal_graph_cliques(fg))
        assert str(fnx_exc.value) == str(exc)
        return

    fr = list(fnx.chordal_graph_cliques(fg))
    # Clique order is "arbitrary" per nx docs; compare as sets of frozensets.
    # (On non-chordal input nx's MCS yields "cliques" that are not actually
    # complete subgraphs, so we only assert byte-for-byte set parity with nx.)
    assert set(fr) == set(nr)


def test_chordal_graph_cliques_is_lazy_generator():
    it = fnx.chordal_graph_cliques(fnx.cycle_graph(4))
    assert iter(it) is iter(it)
    assert not isinstance(it, list)


def test_chordal_fast_path_still_matches():
    # A chordal graph keeps the native fast path; verify parity by set.
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)])  # chordal
    ng = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)])
    assert nx.is_chordal(ng)
    assert set(fnx.chordal_graph_cliques(g)) == set(nx.chordal_graph_cliques(ng))
