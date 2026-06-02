"""Regression: eigenvector_centrality_numpy must use the LEFT eigenvector
(in-edge convention) on directed graphs, matching networkx.

networkx solves ``eigs(M.T, ...)`` — the left eigenvector — so a node's
eigenvector centrality reflects its in-edges. fnx previously solved ``eigs(A)``
(the right / out-edge eigenvector), so eigenvector_centrality_numpy returned the
wrong values on DiGraphs, disagreeing with both nx AND fnx's own iterative
eigenvector_centrality (which already uses the in-edge convention). For
undirected graphs A is symmetric so the transpose is a no-op. (br-r37-c1-evnumdir)
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _strongly_connected_digraph(mod, n, extra):
    g = mod.DiGraph()
    for i in range(n):
        g.add_edge(i, (i + 1) % n)  # ring guarantees strong connectivity
    for u, v in extra:
        g.add_edge(u, v)
    return g


def test_directed_eigenvector_numpy_matches_networkx():
    extra = [(0, 2), (2, 0), (1, 3), (3, 1), (0, 4)]
    gn = _strongly_connected_digraph(nx, 6, extra)
    gf = _strongly_connected_digraph(fnx, 6, extra)
    en = nx.eigenvector_centrality_numpy(gn)
    ef = fnx.eigenvector_centrality_numpy(gf)
    assert set(en) == set(ef)
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9, f"node {k}: nx={en[k]} fnx={ef[k]}"


def test_directed_eigenvector_numpy_agrees_with_iterative():
    extra = [(0, 2), (2, 4), (4, 0), (1, 5)]
    gf = _strongly_connected_digraph(fnx, 6, extra)
    enum = fnx.eigenvector_centrality_numpy(gf)
    eiter = fnx.eigenvector_centrality(gf, max_iter=5000, tol=1e-12)
    for k in enum:
        assert abs(enum[k] - eiter[k]) <= 1e-6, f"node {k}: numpy={enum[k]} iter={eiter[k]}"


def test_weighted_directed_eigenvector_numpy_matches_networkx():
    def build(mod):
        g = mod.DiGraph()
        for i in range(6):
            g.add_edge(i, (i + 1) % 6, weight=float(i + 1))
        g.add_edge(0, 3, weight=2.0)
        return g
    en = nx.eigenvector_centrality_numpy(build(nx), weight="weight")
    ef = fnx.eigenvector_centrality_numpy(build(fnx), weight="weight")
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_undirected_eigenvector_numpy_unchanged(seed):
    gn = nx.gnp_random_graph(10, 0.45, seed=seed)
    gf = fnx.gnp_random_graph(10, 0.45, seed=seed)
    if not nx.is_connected(gn):
        pytest.skip("disconnected")
    en = nx.eigenvector_centrality_numpy(gn)
    ef = fnx.eigenvector_centrality_numpy(gf)
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9
