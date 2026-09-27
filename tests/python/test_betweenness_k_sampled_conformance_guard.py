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


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("endpoints", [False, True])
@pytest.mark.parametrize("normalized", [True, False])
def test_k_zero_raises_zero_division_like_networkx(directed, endpoints, normalized):
    # nro4w.7: networkx's _rescale divides by the sample size; the native
    # sampled rescale's float 0/0 returned NaN for every node instead.
    create = fnx.DiGraph if directed else None
    G = fnx.cycle_graph(4, create_using=create)
    with pytest.raises(ZeroDivisionError):
        nx.betweenness_centrality(
            nx.cycle_graph(4, create_using=nx.DiGraph if directed else None),
            k=0, endpoints=endpoints, normalized=normalized,
        )
    with pytest.raises(ZeroDivisionError):
        fnx.betweenness_centrality(G, k=0, endpoints=endpoints, normalized=normalized)


@pytest.mark.parametrize("endpoints", [False, True])
def test_k_zero_below_two_pairs_returns_networkx_zeros(endpoints):
    # N = n (endpoints) or n - 1 < 2: networkx skips the rescale entirely.
    for n in (1, 2):
        try:
            expected = nx.betweenness_centrality(nx.path_graph(n), k=0, endpoints=endpoints)
        except ZeroDivisionError:
            with pytest.raises(ZeroDivisionError):
                fnx.betweenness_centrality(fnx.path_graph(n), k=0, endpoints=endpoints)
        else:
            assert fnx.betweenness_centrality(fnx.path_graph(n), k=0, endpoints=endpoints) == expected


def _numpy_seed(kind):
    import numpy as np

    return np.random.RandomState(4) if kind == "RandomState" else np.random.default_rng(4)


# br-r37-c1-cdf1v: networkx's wrapper for a numpy RandomState samples the k
# sources with rng.choice - an ndarray - and the native sampled route tested
# `if not sampled_nodes`, which raised "truth value of an array ... is
# ambiguous" where networkx answers. (A Generator's wrapper returns a list.)
@pytest.mark.parametrize("kind", ["RandomState", "Generator"])
@pytest.mark.parametrize("k", [1, 5])
@pytest.mark.parametrize("edge", [False, True], ids=["node", "edge"])
def test_k_sampled_betweenness_takes_numpy_seeds_like_networkx(edge, k, kind):
    fg, ng, _ = _g(9, 20)
    fn = fnx.edge_betweenness_centrality if edge else fnx.betweenness_centrality
    nf = nx.edge_betweenness_centrality if edge else nx.betweenness_centrality
    fr = fn(fg, k=k, seed=_numpy_seed(kind))
    nr = nf(ng, k=k, seed=_numpy_seed(kind))
    assert list(fr) == list(nr)
    for key in nr:
        # k=1 rescales by 1/(k-1)-style factors to NaN on both sides.
        assert fr[key] == pytest.approx(nr[key], abs=1e-12, nan_ok=True)


# ---------------------------------------------------------------------------
# br-r37-c1-quim8: a seed given without k, and weighted k-sampled calls, run
# native - equal to networkx bit for bit, and never through the Python port.
# ---------------------------------------------------------------------------


def _weighted_twins(n, directed, seed=5):
    r = random.Random(seed)
    base = nx.gnp_random_graph(n, 6.0 / n, seed=seed, directed=directed)
    edges = [(u, v, {"weight": r.choice([1, 2, 3, 0.5, 1.5])}) for u, v in base.edges()]
    graphs = []
    for lib in (fnx, nx):
        g = lib.DiGraph() if directed else lib.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(edges)
        graphs.append(g)
    return graphs


@pytest.fixture
def python_port_calls(monkeypatch):
    """Count the calls that reach the in-process networkx port."""
    calls = []
    for name in ("_betweenness_centrality_inproc", "_edge_betweenness_centrality_inproc"):
        original = getattr(fnx, name)

        def counting(*args, _original=original, _name=name, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(fnx, name, counting)
    return calls


@pytest.mark.parametrize("seed", [0, 3, random.Random(9)], ids=["0", "3", "Random"])
def test_seed_without_k_runs_native_and_equal(seed, python_port_calls):
    """networkx draws from seed only to sample k sources; with k=None the
    call is the full computation, native."""
    for n in (60, 450):  # 450: the parallel source arm
        fg, ng = _weighted_twins(n, directed=False)
        for kwargs in ({}, {"weight": "weight"}, {"endpoints": True}):
            assert fnx.betweenness_centrality(fg, seed=seed, **kwargs) == nx.betweenness_centrality(
                ng, seed=seed, **kwargs
            ), (n, kwargs)
        for kwargs in ({}, {"weight": "weight"}):
            assert fnx.edge_betweenness_centrality(fg, seed=seed, **kwargs) == nx.edge_betweenness_centrality(
                ng, seed=seed, **kwargs
            ), (n, kwargs)
    assert python_port_calls == []


@pytest.mark.parametrize("directed", [False, True], ids=["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "kwargs",
    [{}, {"endpoints": True}, {"normalized": False}, {"normalized": False, "endpoints": True}],
    ids=["default", "endpoints", "unnormalized", "unnormalized-endpoints"],
)
def test_weighted_k_sampled_betweenness_is_native_and_bit_exact(directed, kwargs, python_port_calls):
    for n in (60, 450):
        fg, ng = _weighted_twins(n, directed)
        for seed in (1, 4, 11):
            for k in (1, 7, n // 3):
                want = nx.betweenness_centrality(ng, k=k, seed=seed, weight="weight", **kwargs)
                got = fnx.betweenness_centrality(fg, k=k, seed=seed, weight="weight", **kwargs)
                assert list(got) == list(want)
                differ = [
                    node for node in want
                    if got[node] != want[node] and not (got[node] != got[node] and want[node] != want[node])
                ]
                assert not differ, (n, seed, k, differ[:3])
    assert python_port_calls == []


def test_weighted_k_sampled_advances_a_random_instance_as_networkx_does():
    fg, ng = _weighted_twins(80, directed=False)
    mine, theirs = random.Random(21), random.Random(21)
    for _ in range(3):
        assert fnx.betweenness_centrality(fg, k=10, seed=mine, weight="weight") == nx.betweenness_centrality(
            ng, k=10, seed=theirs, weight="weight"
        )
    assert mine.getstate() == theirs.getstate()


def test_invalid_seed_raises_networkx_error_without_k():
    fg, ng = _weighted_twins(20, directed=False)
    for fn in ("betweenness_centrality", "edge_betweenness_centrality"):
        with pytest.raises(ValueError) as expected:
            getattr(nx, fn)(ng, seed="not a seed")
        with pytest.raises(ValueError) as actual:
            getattr(fnx, fn)(fg, seed="not a seed")
        assert str(actual.value) == str(expected.value)


def test_weighted_k_sampled_with_a_negative_weight_runs_networkx(python_port_calls):
    """The native kernels take non-negative weights only; networkx's own
    Dijkstra runs on anything, so a negative weight goes to the port."""
    fg, ng = _weighted_twins(40, directed=False)
    u, v = next(iter(ng.edges()))
    for g in (fg, ng):
        g[u][v]["weight"] = -1
    assert fnx.betweenness_centrality(fg, k=10, seed=2, weight="weight") == nx.betweenness_centrality(
        ng, k=10, seed=2, weight="weight"
    )
    assert python_port_calls == ["_betweenness_centrality_inproc"]


# ---------------------------------------------------------------------------
# br-r37-c1-f0uiy: edge betweenness - k-sampled and normalized=False, weighted
# or not - runs the full edge Brandes over networkx's sample, bit for bit.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [False, True], ids=["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"], ids=["bfs", "dijkstra"])
@pytest.mark.parametrize("normalized", [True, False], ids=["normalized", "unnormalized"])
def test_edge_betweenness_sampled_and_unnormalized_are_native_and_bit_exact(
    directed, weight, normalized, python_port_calls
):
    for n in (60, 520):  # 520: past both parallel thresholds (400 / 500)
        fg, ng = _weighted_twins(n, directed)
        cases = [{}] + [{"k": k, "seed": seed} for seed in (2, 9) for k in (1, 6, n // 4, n)]
        for kwargs in cases:
            want = nx.edge_betweenness_centrality(ng, weight=weight, normalized=normalized, **kwargs)
            got = fnx.edge_betweenness_centrality(fg, weight=weight, normalized=normalized, **kwargs)
            assert list(got) == list(want), (n, kwargs)
            differ = [e for e in want if got[e] != want[e]]
            assert not differ, (n, kwargs, len(differ), differ[:3])
    assert python_port_calls == []


def test_edge_betweenness_sampled_advances_a_random_instance_as_networkx_does():
    fg, ng = _weighted_twins(80, directed=False)
    mine, theirs = random.Random(33), random.Random(33)
    for weight in (None, "weight"):
        assert fnx.edge_betweenness_centrality(fg, k=12, seed=mine, weight=weight) == nx.edge_betweenness_centrality(
            ng, k=12, seed=theirs, weight=weight
        )
    assert mine.getstate() == theirs.getstate()


def test_edge_betweenness_empty_sample_raises_as_networkx_does():
    fg, ng = _weighted_twins(10, directed=False)
    with pytest.raises(ZeroDivisionError) as expected:
        nx.edge_betweenness_centrality(ng, k=0, seed=1)
    with pytest.raises(ZeroDivisionError) as actual:
        fnx.edge_betweenness_centrality(fg, k=0, seed=1)
    assert str(actual.value) == str(expected.value)
