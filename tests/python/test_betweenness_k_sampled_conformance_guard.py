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


@pytest.mark.parametrize("seed", [5, 17])
@pytest.mark.parametrize("k", [3, 12])
def test_k_sampled_betweenness_matches_nx_on_parallel_arm(seed, k):
    """br-r37-c1-bcsr: cover the rayon arm of the sampled kernel.

    `betweenness_centrality_sampled_generic` fans out over rayon only when
    `n >= 500 and len(sources) > 1`; every other case in this file uses n = 20-30
    and therefore only ever exercised the sequential arm. That left the parallel
    arm's call site unguarded — and it is a *separate* call site from the
    sequential one, so a wiring mistake there (e.g. passing the forward CSR where
    the reverse is expected) would have been invisible to the rest of this file
    while still being wrong for every real-sized sampled run.
    """
    fg, ng, n = _g(seed, 600)
    assert n >= 500 and k > 1, "must straddle the parallel threshold to be meaningful"
    fr = fnx.betweenness_centrality(fg, k=k, seed=seed)
    nr = nx.betweenness_centrality(ng, k=k, seed=seed)
    assert set(fr) == set(nr)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


@pytest.mark.parametrize("seed", [2, 19])
def test_k_sampled_betweenness_directed_parallel_arm(seed):
    """The case that can actually catch a reverse-CSR wiring mistake.

    Every other sampled case here is UNDIRECTED, where in-neighbours and
    out-neighbours are the same rows — so passing the forward CSR where the
    reverse belongs is invisible. Only a directed graph above the parallel
    threshold distinguishes them.
    """
    n = 600
    r = random.Random(seed)
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges += [(i, (i + step) % n) for step in (3, 7, 11) for i in range(n) if r.random() < 0.4]
    fd = fnx.DiGraph(edges); fd.add_nodes_from(range(n))
    nd = nx.DiGraph(edges); nd.add_nodes_from(range(n))
    fr = fnx.betweenness_centrality(fd, k=10, seed=seed)
    nr = nx.betweenness_centrality(nd, k=10, seed=seed)
    assert set(fr) == set(nr)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


def test_k_sampled_betweenness_endpoints_unnormalized_parallel_arm():
    """Same arm, with the endpoints/unnormalized scaling class."""
    fg, ng, n = _g(23, 700)
    fr = fnx.betweenness_centrality(fg, k=9, seed=23, endpoints=True, normalized=False)
    nr = nx.betweenness_centrality(ng, k=9, seed=23, endpoints=True, normalized=False)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


def test_full_betweenness_matches_nx_on_parallel_arm():
    """The non-sampled parallel arm, directed and undirected, above the threshold.

    The Rust-side gate proves bit-identity against the pre-CSR kernel; this proves
    the whole public route agrees with live NetworkX at a size that actually fans
    out over rayon.
    """
    fg, ng, _ = _g(31, 600)
    for kwargs in ({}, {"normalized": False}, {"endpoints": True}):
        fr = fnx.betweenness_centrality(fg, **kwargs)
        nr = nx.betweenness_centrality(ng, **kwargs)
        for node in nr:
            assert fr[node] == pytest.approx(nr[node], abs=1e-9)

    edges = [(i, (i + 1) % 550) for i in range(550)]
    edges += [(i, (i + 5) % 550) for i in range(0, 550, 3)]
    fd = fnx.DiGraph(edges); fd.add_nodes_from(range(550))
    nd = nx.DiGraph(edges); nd.add_nodes_from(range(550))
    fr = fnx.betweenness_centrality(fd)
    nr = nx.betweenness_centrality(nd)
    for node in nr:
        assert fr[node] == pytest.approx(nr[node], abs=1e-9)


def test_k_sampled_betweenness_uses_native_route(monkeypatch):
    fg, ng, n = _g(99, 30)

    def fail_networkx_parity(*args, **kwargs):
        raise AssertionError("k-sampled betweenness must not delegate to NetworkX")

    monkeypatch.setattr(fnx, "_call_networkx_for_parity", fail_networkx_parity)
    fr = fnx.betweenness_centrality(fg, k=6, seed=123)
    nr = nx.betweenness_centrality(ng, k=6, seed=123)
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


@pytest.mark.parametrize("normalized", [True, False])
def test_k_sampled_edge_betweenness_uses_native_route(monkeypatch, normalized):
    fg, ng, n = _g(111, 30)

    def fail_networkx_parity(*args, **kwargs):
        raise AssertionError("k-sampled edge betweenness must not delegate to NetworkX")

    monkeypatch.setattr(fnx, "_call_networkx_for_parity", fail_networkx_parity)
    fr = fnx.edge_betweenness_centrality(
        fg, k=7, seed=321, normalized=normalized
    )
    nr = nx.edge_betweenness_centrality(
        ng, k=7, seed=321, normalized=normalized
    )
    nr = {tuple(sorted(e)): v for e, v in nr.items()}
    fr = {tuple(sorted(e)): v for e, v in fr.items()}
    assert set(fr) == set(nr)
    for e in nr:
        assert fr[e] == pytest.approx(nr[e], abs=1e-9)
