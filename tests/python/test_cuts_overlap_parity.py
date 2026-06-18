"""Parity for the cuts module on overlapping node sets.

``cut_size(G, S, T)`` and ``normalized_cut_size`` route through native
kernels that (like ``edge_boundary``, br-r37-c1-dhi0m) compute the strict
boundary — other endpoint NOT in ``S`` — then filter by ``T``. That
undercounts S↔T crossing edges when ``S`` and ``T`` overlap. networkx
counts an edge whenever one endpoint is in ``S`` and the other in ``T``,
including edges with both endpoints in the overlap.

The fix delegates the overlapping case to nx and cascades to
``edge_expansion`` / ``mixing_expansion`` / ``conductance`` (which call
``cut_size``). Disjoint / ``T=None`` paths stay on the fast kernel.
br-r37-c1-dy93n
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_CUT_FUNCS = [
    "cut_size",
    "normalized_cut_size",
    "conductance",
    "edge_expansion",
    "mixing_expansion",
]


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
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
    return fg, ng, n


@pytest.mark.parametrize("fn", _CUT_FUNCS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_cut_functions_overlapping_sets_match_networkx(fn, directed, seed):
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 53 + 11)
    s = set(rng.sample(range(n), rng.randint(1, n - 1)))
    t = s | set(rng.sample(range(n), rng.randint(1, n - 1)))  # guaranteed overlap
    assert not s.isdisjoint(t)
    try:
        nr = getattr(nx, fn)(ng, s, t)
    except ZeroDivisionError:
        # fnx must raise the same way (degenerate volume / denominator).
        with pytest.raises(ZeroDivisionError):
            getattr(fnx, fn)(fg, s, t)
        return
    fr = getattr(fnx, fn)(fg, s, t)
    assert fr == pytest.approx(nr)


def test_cut_size_overlap_golden():
    g = fnx.path_graph(4)  # 0-1-2-3
    ng = nx.path_graph(4)
    # s={0,1,2}, t={1,2,3} overlap on {1,2}; crossing edges are
    # (0,1),(1,2),(2,3) -> 3 (strict-boundary approach wrongly gives 1).
    assert fnx.cut_size(g, {0, 1, 2}, {1, 2, 3}) == 3
    assert fnx.cut_size(g, {0, 1, 2}, {1, 2, 3}) == nx.cut_size(ng, {0, 1, 2}, {1, 2, 3})


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(20))
def test_disjoint_sets_still_match(directed, seed):
    # The common disjoint path stays on the native kernel; confirm parity.
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 7 + 2)
    s = set(rng.sample(range(n), rng.randint(1, n - 1)))
    rest = [x for x in range(n) if x not in s]
    if not rest:
        pytest.skip("no disjoint complement")
    t = set(rng.sample(rest, rng.randint(1, len(rest))))
    assert fnx.cut_size(fg, s, t) == nx.cut_size(ng, s, t)
