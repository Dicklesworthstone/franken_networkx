"""Parity for ``all_pairs_all_shortest_paths`` directed reachability.

The native ``all_pairs_all_shortest_paths_rust`` kernel ignored edge
direction and emitted reverse paths to unreachable targets (e.g. on
``[(0,1),(1,2),(0,2)]`` it returned ``1 -> 0`` as ``[[1, 0]]``). The
unweighted directed path now builds from the directed-correct
``single_source_all_shortest_paths`` per source. br-r37-c1-s1czw
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(pairs_iter):
    return {
        s: {t: sorted(map(tuple, paths)) for t, paths in d.items()}
        for s, d in pairs_iter
    }


def _pair(seed, directed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(60))
def test_all_pairs_all_shortest_paths_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed)
    assert _norm(fnx.all_pairs_all_shortest_paths(fg)) == _norm(
        nx.all_pairs_all_shortest_paths(ng)
    )


def test_directed_does_not_emit_reverse_paths():
    # Regression: only forward-reachable targets appear.
    fg = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])
    result = dict(fnx.all_pairs_all_shortest_paths(fg))
    # Node 2 is a sink: it reaches only itself.
    assert result[2] == {2: [[2]]}
    # Node 1 reaches 1 and 2, never 0.
    assert set(result[1]) == {1, 2}
    assert dict(fnx.all_pairs_all_shortest_paths(fg)) == {
        s: d for s, d in nx.all_pairs_all_shortest_paths(nx.DiGraph([(0, 1), (1, 2), (0, 2)]))
    }


def test_weighted_still_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in [(0, 1, 2), (1, 2, 1), (0, 2, 5)]:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    assert _norm(fnx.all_pairs_all_shortest_paths(fg, weight="weight")) == _norm(
        nx.all_pairs_all_shortest_paths(ng, weight="weight")
    )
