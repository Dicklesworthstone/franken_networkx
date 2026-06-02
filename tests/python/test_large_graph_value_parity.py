"""Large-graph value parity for core algorithms.

The per-feature parity suites overwhelmingly use tiny graphs (≤ ~10 nodes).
Some divergences only appear at scale: tie-breaking among many equal candidates,
accumulation round-off that grows with the number of summed terms (and could
exceed the 1e-12 centrality tolerance), integer overflow in counts, or an
O(N^2)/O(E*N) complexity cliff that would time the test out. This harness runs
the core algorithms on deterministically-built ~400-600 node graphs (identical
on both libraries — no RNG divergence) and asserts value parity with networkx
at the conformance tolerance (exact for integer-valued results).
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _build(n, deg, directed=False, weighted=False):
    cls_n = nx.DiGraph if directed else nx.Graph
    cls_f = fnx.DiGraph if directed else fnx.Graph
    gn, gf = cls_n(), cls_f()
    for i in range(n):
        for k in range(1, deg + 1):
            j = (i * 7 + k * k) % n
            if i == j:
                continue
            if weighted:
                w = 1.0 + ((i * k) % 13) / 2.0
                gn.add_edge(i, j, weight=w)
                gf.add_edge(i, j, weight=w)
            else:
                gn.add_edge(i, j)
                gf.add_edge(i, j)
    return gn, gf


def _assert_dict_close(dn, df, tol):
    assert set(dn) == set(df), "key set differs"
    if tol == 0:
        assert dn == df
        return
    worst = max((abs(dn[k] - df[k]) for k in dn), default=0.0)
    assert worst <= tol, f"max abs diff {worst:.3e} > tol {tol:.0e}"


# (label, build_args, nx_fn, fnx_fn, tol)
_FLOAT_DICT_CASES = [
    ("pagerank", (500, 6), lambda g: nx.pagerank(g), lambda g: fnx.pagerank(g), 1e-9),
    ("pagerank_weighted", (500, 6, False, True), lambda g: nx.pagerank(g, weight="weight"), lambda g: fnx.pagerank(g, weight="weight"), 1e-9),
    ("pagerank_directed", (500, 6, True), lambda g: nx.pagerank(g), lambda g: fnx.pagerank(g), 1e-9),
    ("betweenness", (300, 5), lambda g: nx.betweenness_centrality(g), lambda g: fnx.betweenness_centrality(g), 1e-9),
    ("closeness", (500, 6), lambda g: nx.closeness_centrality(g), lambda g: fnx.closeness_centrality(g), 1e-9),
    ("harmonic", (500, 6), lambda g: nx.harmonic_centrality(g), lambda g: fnx.harmonic_centrality(g), 1e-9),
    ("clustering", (500, 6), lambda g: nx.clustering(g), lambda g: fnx.clustering(g), 1e-12),
    ("square_clustering", (400, 5), lambda g: nx.square_clustering(g), lambda g: fnx.square_clustering(g), 1e-9),
    ("degree_centrality", (500, 6), lambda g: nx.degree_centrality(g), lambda g: fnx.degree_centrality(g), 1e-12),
    ("eigenvector_numpy", (500, 6), lambda g: nx.eigenvector_centrality_numpy(g), lambda g: fnx.eigenvector_centrality_numpy(g), 1e-6),
    ("katz_numpy", (400, 5), lambda g: nx.katz_centrality_numpy(g), lambda g: fnx.katz_centrality_numpy(g), 1e-6),
    ("load_centrality", (300, 5), lambda g: nx.load_centrality(g), lambda g: fnx.load_centrality(g), 1e-9),
]

_INT_DICT_CASES = [
    ("triangles", (500, 6), lambda g: nx.triangles(g), lambda g: fnx.triangles(g)),
    ("core_number", (500, 6), lambda g: nx.core_number(g), lambda g: fnx.core_number(g)),
]


@pytest.mark.parametrize("label,args,fn_n,fn_f,tol", _FLOAT_DICT_CASES, ids=[c[0] for c in _FLOAT_DICT_CASES])
def test_large_float_centrality_parity(label, args, fn_n, fn_f, tol):
    gn, gf = _build(*args)
    _assert_dict_close(fn_n(gn), fn_f(gf), tol)


@pytest.mark.parametrize("label,args,fn_n,fn_f", _INT_DICT_CASES, ids=[c[0] for c in _INT_DICT_CASES])
def test_large_int_dict_parity(label, args, fn_n, fn_f):
    gn, gf = _build(*args)
    _assert_dict_close(fn_n(gn), fn_f(gf), 0)


def test_large_scalar_parity():
    gn, gf = _build(500, 6)
    assert abs(nx.transitivity(gn) - fnx.transitivity(gf)) <= 1e-12
    assert abs(nx.average_clustering(gn) - fnx.average_clustering(gf)) <= 1e-12
    assert nx.number_connected_components(gn) == fnx.number_connected_components(gf)
    dgn, dgf = _build(500, 6, directed=True)
    assert nx.number_strongly_connected_components(dgn) == fnx.number_strongly_connected_components(dgf)


def test_large_all_pairs_dijkstra_parity():
    gn, gf = _build(300, 5, weighted=True)
    an = {s: dict(d) for s, d in nx.all_pairs_dijkstra_path_length(gn, weight="weight")}
    af = {s: dict(d) for s, d in fnx.all_pairs_dijkstra_path_length(gf, weight="weight")}
    assert set(an) == set(af)
    for s in an:
        assert an[s] == af[s], f"source {s} distances differ"
