"""Parity for parameterized centrality variants.

Centrality functions take many flags that each select a distinct code path —
``endpoints``, ``normalized``, subset sources/targets, pagerank
``personalization``/``alpha``, katz ``alpha``/``beta``, closeness
``wf_improved``, harmonic ``nbunch``. These are less exercised than the default
forms; this pins fnx == networkx across them.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _round(d, p=5):
    return {k: (round(v, p) if isinstance(v, float) else v) for k, v in d.items()}


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, r


@pytest.mark.parametrize("seed", range(40))
def test_betweenness_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _round(fnx.betweenness_centrality(fg, endpoints=True)) == _round(
        nx.betweenness_centrality(ng, endpoints=True)
    )
    assert _round(fnx.betweenness_centrality(fg, normalized=False)) == _round(
        nx.betweenness_centrality(ng, normalized=False)
    )
    fe = {tuple(sorted(k)): round(v, 5) for k, v in fnx.edge_betweenness_centrality(fg).items()}
    ne = {tuple(sorted(k)): round(v, 5) for k, v in nx.edge_betweenness_centrality(ng).items()}
    assert fe == ne
    src, tgt = list(range(n // 2)), list(range(n // 2, n))
    assert _round(
        fnx.betweenness_centrality_subset(fg, sources=src, targets=tgt)
    ) == _round(nx.betweenness_centrality_subset(ng, sources=src, targets=tgt))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_and_katz_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    pers = {i: r.random() for i in range(n)}
    assert _round(fnx.pagerank(fg, personalization=pers)) == _round(
        nx.pagerank(ng, personalization=pers)
    )
    assert _round(fnx.pagerank(fg, alpha=0.7)) == _round(nx.pagerank(ng, alpha=0.7))
    assert _round(fnx.katz_centrality_numpy(fg, alpha=0.05, beta=0.5)) == _round(
        nx.katz_centrality_numpy(ng, alpha=0.05, beta=0.5)
    )


@pytest.mark.parametrize("seed", range(40))
def test_closeness_and_harmonic_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _round(fnx.closeness_centrality(fg, wf_improved=False)) == _round(
        nx.closeness_centrality(ng, wf_improved=False)
    )
    assert _round(fnx.harmonic_centrality(fg, nbunch=[0, 1])) == _round(
        nx.harmonic_centrality(ng, nbunch=[0, 1])
    )


@pytest.mark.parametrize("seed", range(40))
def test_each_parameter_actually_changes_the_result(seed):
    """Parity alone cannot see a parameter that BOTH libraries ignore.

    Every assertion in this file compares fnx to networkx with the same flag
    set. If a flag were dropped on the floor by both, the comparison would
    still pass — the file would be pinning the default path under a variant's
    name. Requiring each variant to differ from its default is the missing half.
    """
    fg, _, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    default_betweenness = fnx.betweenness_centrality(fg)
    assert fnx.betweenness_centrality(fg, endpoints=True) != default_betweenness
    assert fnx.betweenness_centrality(fg, normalized=False) != default_betweenness
    sources, targets = list(range(n // 2)), list(range(n // 2, n))
    assert fnx.betweenness_centrality_subset(
        fg, sources=sources, targets=targets
    ) != default_betweenness

    default_pagerank = fnx.pagerank(fg)
    assert fnx.pagerank(fg, personalization={i: r.random() for i in range(n)}) != default_pagerank
    assert fnx.pagerank(fg, alpha=0.7) != default_pagerank

    assert fnx.katz_centrality_numpy(fg, alpha=0.05, beta=0.5) != fnx.katz_centrality_numpy(fg)
    assert fnx.harmonic_centrality(fg, nbunch=[0, 1]) != fnx.harmonic_centrality(fg)


def _sparse_pair(seed):
    """Sparse enough to be disconnected, which is where wf_improved bites."""
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.18]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize("seed", range(40))
def test_wf_improved_is_exercised_where_it_is_not_the_identity(seed):
    """wf_improved=False is a NO-OP on a connected graph.

    The sweep above tests it on connected graphs only, so it compares the
    default against the default — 0 of its 38 connected draws show any
    difference. The Wasserman-Faust correction scales by the reachable
    fraction, which is 1 when everything is reachable; it only does anything
    once the graph splits.
    """
    fg, ng = _sparse_pair(seed)
    if fnx.is_connected(fg):
        pytest.skip("connected — wf_improved is the identity here")

    corrected = fnx.closeness_centrality(fg)
    uncorrected = fnx.closeness_centrality(fg, wf_improved=False)
    assert uncorrected != corrected                      # the flag now bites
    assert _round(uncorrected) == _round(nx.closeness_centrality(ng, wf_improved=False))
    assert _round(corrected) == _round(nx.closeness_centrality(ng))
