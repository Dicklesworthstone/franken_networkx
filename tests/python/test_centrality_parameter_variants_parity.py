"""Differential parity for less-tested centrality parameter combinations.

Default-parameter centrality is covered elsewhere; this exercises the
non-default knobs that are a common source of subtle bugs: ``endpoints``,
``weight``, ``normalized``, ``distance`` and ``wf_improved``.

br-r37-c1-2pzqb
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_weighted(seed, directed):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < 0.5:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    ok = nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
    return (fg, ng) if ok else None


def _close(a, b, tol=1e-7):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol, rel=1e-6)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_betweenness_parameter_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair
    _close(fnx.betweenness_centrality(fg, endpoints=True),
           nx.betweenness_centrality(ng, endpoints=True))
    _close(fnx.betweenness_centrality(fg, weight="weight"),
           nx.betweenness_centrality(ng, weight="weight"))
    _close(fnx.betweenness_centrality(fg, normalized=False),
           nx.betweenness_centrality(ng, normalized=False))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_closeness_parameter_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair
    _close(fnx.closeness_centrality(fg, distance="weight"),
           nx.closeness_centrality(ng, distance="weight"))
    _close(fnx.closeness_centrality(fg, wf_improved=False),
           nx.closeness_centrality(ng, wf_improved=False))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_edge_betweenness_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair

    def _norm(d):
        return {(tuple(sorted(k)) if not directed else k): v for k, v in d.items()}

    _close(_norm(fnx.edge_betweenness_centrality(fg)),
           _norm(nx.edge_betweenness_centrality(ng)))
    _close(_norm(fnx.edge_betweenness_centrality(fg, weight="weight")),
           _norm(nx.edge_betweenness_centrality(ng, weight="weight")))
