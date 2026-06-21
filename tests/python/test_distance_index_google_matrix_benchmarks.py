"""Benchmarks for the native-kernel routings shipped this campaign.

Each routing replaced a Python loop in the wrapper with a byte-exact native
kernel call:
  * google_matrix  — O(n) Python row-normalization loop -> google_matrix_rust
  * gutman_index   — all-pairs shortest_path_length dict + O(V^2) loop -> kernel
  * schultz_index  — same shape -> kernel

These quantify fnx vs networkx on realistic sizes so the batch can confirm the
routings beat the baseline (the wins only appear with a fresh extension that has
the routing installed — code-first).

Run: pytest tests/python/test_distance_index_google_matrix_benchmarks.py --benchmark-only
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

pytestmark = pytest.mark.benchmark


def _fnx_digraph(n, seed=7):
    g = fnx.gnp_random_graph(n, 0.06, seed, directed=True)
    return g


def _nx_digraph(n, seed=7):
    return nx.gnp_random_graph(n, 0.06, seed, directed=True)


def _fnx_conn(n, seed=11):
    # connected graph for the distance indices.
    g = fnx.Graph()
    g.add_edges_from((i, i + 1) for i in range(n - 1))
    import random
    r = random.Random(seed)
    for _ in range(n):
        g.add_edge(r.randint(0, n - 1), r.randint(0, n - 1))
    return g


def _nx_conn(n, seed=11):
    g = nx.Graph()
    g.add_edges_from((i, i + 1) for i in range(n - 1))
    import random
    r = random.Random(seed)
    for _ in range(n):
        g.add_edge(r.randint(0, n - 1), r.randint(0, n - 1))
    return g


@pytest.mark.parametrize("n", [200, 500], ids=["n=200", "n=500"])
class TestGoogleMatrix:
    def test_fnx_google_matrix(self, benchmark, n):
        g = _fnx_digraph(n)
        benchmark(lambda: fnx.google_matrix(g))

    def test_nx_google_matrix(self, benchmark, n):
        g = _nx_digraph(n)
        benchmark(lambda: nx.google_matrix(g))


@pytest.mark.parametrize("n", [150, 300], ids=["n=150", "n=300"])
class TestDistanceIndices:
    def test_fnx_gutman_index(self, benchmark, n):
        g = _fnx_conn(n)
        benchmark(lambda: fnx.gutman_index(g))

    def test_nx_gutman_index(self, benchmark, n):
        g = _nx_conn(n)
        benchmark(lambda: nx.gutman_index(g))

    def test_fnx_schultz_index(self, benchmark, n):
        g = _fnx_conn(n)
        benchmark(lambda: fnx.schultz_index(g))

    def test_nx_schultz_index(self, benchmark, n):
        g = _nx_conn(n)
        benchmark(lambda: nx.schultz_index(g))


@pytest.mark.parametrize("n", [150, 300], ids=["n=150", "n=300"])
class TestLaplacianSpectrum:
    # general dense path eigensolver n-gate: LAPACK eigvalsh for n>64 instead of
    # the 2.3-4x-slower safe-Rust eigensolver (fixed laplacian_spectrum 2.4x gap).
    def test_fnx_laplacian_spectrum(self, benchmark, n):
        g = fnx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: fnx.laplacian_spectrum(g))

    def test_nx_laplacian_spectrum(self, benchmark, n):
        g = nx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: nx.laplacian_spectrum(g))

    def test_fnx_adjacency_spectrum(self, benchmark, n):
        g = fnx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: fnx.adjacency_spectrum(g))

    def test_nx_adjacency_spectrum(self, benchmark, n):
        g = nx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: nx.adjacency_spectrum(g))

    def test_fnx_modularity_spectrum(self, benchmark, n):
        g = fnx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: fnx.modularity_spectrum(g))

    def test_nx_modularity_spectrum(self, benchmark, n):
        g = nx.gnp_random_graph(n, 0.05, 7)
        benchmark(lambda: nx.modularity_spectrum(g))


@pytest.mark.parametrize("n", [300, 800], ids=["n=300", "n=800"])
class TestGeneralizedDegree:
    # nodes=None -> native generalized_degree_rust + Counter-wrap, replacing the
    # Python _triangles_and_degree_iter loop.
    def test_fnx_generalized_degree(self, benchmark, n):
        g = _fnx_conn(n)
        benchmark(lambda: fnx.generalized_degree(g))

    def test_nx_generalized_degree(self, benchmark, n):
        g = _nx_conn(n)
        benchmark(lambda: nx.generalized_degree(g))
