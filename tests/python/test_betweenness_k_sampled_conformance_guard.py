"""Conformance scaffold for k-sampled betweenness_centrality parity.

Full (k=None) betweenness routes to the native parallel Brandes kernel (~290x vs
nx). k-sampled betweenness currently DELEGATES to nx (the kernel rejects k) — a
profiled ~1.12x gap (br-r37-c1 k-sampled-betweenness lever). This locks the
sampled-estimator parity (same sources via seed, same rescaling) so that when the
native k-sampled kernel lands, it is validated byte-for-byte against nx.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _g(seed, n):
    r = random.Random(seed)
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges += [(i, (i + step) % n) for step in (3, 7) for i in range(n) if r.random() < 0.5]
    fg = fnx.Graph(edges); fg.add_nodes_from(range(n))
    ng = nx.Graph(edges); ng.add_nodes_from(range(n))
    return fg, ng, n


@pytest.mark.parametrize("seed", [1, 7, 42, 123])
@pytest.mark.parametrize("k", [5, 10])
def test_k_sampled_betweenness_matches_nx(seed, k):
    fg, ng, n = _g(seed, 25)
    fr = fnx.betweenness_centrality(fg, k=k, seed=seed)
    nr = nx.betweenness_centrality(ng, k=k, seed=seed)
    assert set(fr) == set(nr)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


@pytest.mark.parametrize("seed", [3, 11])
def test_k_sampled_betweenness_endpoints_unnormalized(seed):
    fg, ng, n = _g(seed, 20)
    fr = fnx.betweenness_centrality(fg, k=8, seed=seed, endpoints=True, normalized=False)
    nr = nx.betweenness_centrality(ng, k=8, seed=seed, endpoints=True, normalized=False)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


@pytest.mark.parametrize("seed", [1, 7, 42])
@pytest.mark.parametrize("k", [5, 10])
def test_k_sampled_edge_betweenness_matches_nx(seed, k):
    # Same gap + same planned native k-sampling fix (br-r37-c1-8ox3z sibling):
    # edge_betweenness_centrality k-sampling also delegates to nx (~0.89x).
    fg, ng, n = _g(seed, 25)
    fr = fnx.edge_betweenness_centrality(fg, k=k, seed=seed)
    nr = nx.edge_betweenness_centrality(ng, k=k, seed=seed)
    nr = {tuple(sorted(e)): v for e, v in nr.items()}
    fr = {tuple(sorted(e)): v for e, v in fr.items()}
    assert set(fr) == set(nr)
    for e in nr:
        assert fr[e] == pytest.approx(nr[e], abs=1e-9)
