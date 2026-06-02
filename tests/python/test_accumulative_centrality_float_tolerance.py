"""Float-tolerance contract for accumulative centralities at the Python API.

NetworkX accumulates these centralities by summing many floating-point terms in
a specific traversal order (e.g. ``harmonic_centrality`` does
``centrality[u] += 1 / d`` iterating sources in node order; Brandes betweenness
sums dependency contributions in BFS-stack order). franken_networkx's Rust
kernels are numerically equivalent but accumulate in their own order, so the
results agree with networkx only up to floating-point round-off (~1e-15 here),
NOT bit-for-bit. This is by design and matches the project's conformance
contract, which compares centrality scores with a 1e-12 absolute tolerance
(1e-9 for HITS) — see ``centrality_score_tolerance`` in fnx-conformance.

``degree_centrality`` is the exception: its single reciprocal-multiply was
made bit-exact (it does ``s = 1/(n-1); d*s`` like nx), so it is asserted
exactly here as a guard against that fix regressing.

This test documents the policy (so an exact-float probe doesn't re-file ~1e-16
"bugs") and guards the tolerance bound at the public Python boundary — distinct
from the Rust-fixture conformance harness. A regression that pushed a kernel
past 1e-12 would trip it.
"""

import networkx as nx
import franken_networkx as fnx

import pytest

_TOL = 1e-12


def _build(mod, weighted=False):
    g = mod.Graph()
    edges = []
    for i in range(20):
        edges.append((i, (i + 1) % 20))
        edges.append((i, (i + 3) % 20))
        if i % 2 == 0:
            edges.append((i, (i + 7) % 20))
    for j, (u, v) in enumerate(edges):
        if u == v:
            continue
        if weighted:
            g.add_edge(u, v, weight=1.0 + ((j * 7) % 11) / 3.0)
        else:
            g.add_edge(u, v)
    return g


_UNWEIGHTED = [
    ("betweenness", lambda m, g: m.betweenness_centrality(g)),
    ("betweenness_unnormalized", lambda m, g: m.betweenness_centrality(g, normalized=False)),
    ("harmonic", lambda m, g: m.harmonic_centrality(g)),
    ("closeness", lambda m, g: m.closeness_centrality(g)),
    ("closeness_wf_false", lambda m, g: m.closeness_centrality(g, wf_improved=False)),
    ("load", lambda m, g: m.load_centrality(g)),
    ("eigenvector", lambda m, g: m.eigenvector_centrality(g, max_iter=3000, tol=1e-12)),
]

_WEIGHTED = [
    ("betweenness_w", lambda m, g: m.betweenness_centrality(g, weight="weight")),
    ("closeness_distance", lambda m, g: m.closeness_centrality(g, distance="weight")),
]


def _assert_close(label, dn, df):
    assert set(dn) == set(df), f"{label}: key set differs"
    worst = max((abs(dn[k] - df[k]) for k in dn), default=0.0)
    assert worst <= _TOL, f"{label}: max abs diff {worst:.3e} exceeds tolerance {_TOL:.0e}"


@pytest.mark.parametrize("label,fn", _UNWEIGHTED, ids=[c[0] for c in _UNWEIGHTED])
def test_unweighted_centrality_within_tolerance(label, fn):
    _assert_close(label, fn(nx, _build(nx)), fn(fnx, _build(fnx)))


@pytest.mark.parametrize("label,fn", _WEIGHTED, ids=[c[0] for c in _WEIGHTED])
def test_weighted_centrality_within_tolerance(label, fn):
    _assert_close(label, fn(nx, _build(nx, weighted=True)), fn(fnx, _build(fnx, weighted=True)))


def test_edge_betweenness_within_tolerance():
    gn, gf = _build(nx), _build(fnx)
    dn = {tuple(sorted(k)): v for k, v in nx.edge_betweenness_centrality(gn).items()}
    df = {tuple(sorted(k)): v for k, v in fnx.edge_betweenness_centrality(gf).items()}
    _assert_close("edge_betweenness", dn, df)


def test_degree_centrality_is_bit_exact():
    # degree_centrality was deliberately made bit-exact (s = 1/(n-1); d*s).
    gn, gf = _build(nx), _build(fnx)
    assert fnx.degree_centrality(gf) == nx.degree_centrality(gn)
