"""Conformance guard for laplacian_spectrum's eigensolver n-gate.

Profiling found laplacian_spectrum 2.4x SLOWER than networkx at n=300 while
adjacency_spectrum was 15x faster — the general dense path used the safe-Rust
eigensolver (symmetric_eigvals_rust), which is 2.3-4x slower than LAPACK eigvalsh
at every measured n (and produces the same eigenvalues to 1e-8). The fix gates the
safe-Rust solver to small n and routes larger dense Laplacians to LAPACK eigvalsh.

This locks the VALUE parity vs networkx across the gate boundary (n <= 64 safe-Rust,
n > 64 LAPACK) so the perf fix cannot drift the spectrum. The spectral tests are
tolerance-based, and LAPACK eigvalsh is already the existing fallback, so the
1e-8 eigensolver difference is within contract.

No mocks: real fnx vs real networkx (numpy for comparison).
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("n", [10, 40, 64, 65, 100, 200])
def test_laplacian_spectrum_matches_nx_across_gate(n):
    fg = fnx.gnp_random_graph(n, 0.08, 7)
    ng = nx.gnp_random_graph(n, 0.08, 7)
    fv = np.sort(np.real(np.asarray(fnx.laplacian_spectrum(fg), dtype=float)))
    nv = np.sort(np.real(np.asarray(nx.laplacian_spectrum(ng), dtype=float)))
    assert fv.shape == nv.shape
    assert np.allclose(fv, nv, atol=1e-8)


@pytest.mark.parametrize("n", [40, 64, 65, 150])
def test_adjacency_spectrum_matches_nx_across_gate(n):
    # Same eigensolver gate (safe-Rust <= 64, LAPACK eigvalsh above). Spectra are
    # order-insensitive vs nx (fnx returns ascending; nx returns dgeev order), so
    # compare sorted. The swap preserves fnx's own ascending order + values.
    fg = fnx.gnp_random_graph(n, 0.08, 7)
    ng = nx.gnp_random_graph(n, 0.08, 7)
    fv = np.sort(np.real(np.asarray(fnx.adjacency_spectrum(fg), dtype=complex)))
    nv = np.sort(np.real(np.asarray(nx.adjacency_spectrum(ng), dtype=complex)))
    assert np.allclose(fv, nv, atol=1e-7)


@pytest.mark.parametrize("n", [40, 65, 150])
def test_modularity_spectrum_matches_nx_across_gate(n):
    fg = fnx.gnp_random_graph(n, 0.08, 7)
    ng = nx.gnp_random_graph(n, 0.08, 7)
    fv = np.sort(np.real(np.asarray(fnx.modularity_spectrum(fg), dtype=complex)))
    nv = np.sort(np.real(np.asarray(nx.modularity_spectrum(ng), dtype=complex)))
    assert np.allclose(fv, nv, atol=1e-7)


@pytest.mark.parametrize("n", [50, 120])
def test_weighted_laplacian_spectrum_matches_nx(n):
    import random
    r = random.Random(n)
    fg, ng = fnx.Graph(), nx.Graph()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.1:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    fv = np.sort(np.real(np.asarray(fnx.laplacian_spectrum(fg, weight="weight"), dtype=float)))
    nv = np.sort(np.real(np.asarray(nx.laplacian_spectrum(ng, weight="weight"), dtype=float)))
    assert np.allclose(fv, nv, atol=1e-8)
