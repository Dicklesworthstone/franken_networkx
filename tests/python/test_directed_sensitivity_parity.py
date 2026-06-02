"""Broad directed-sensitivity parity net for the recurring "undirected-only
kernel" bug class.

Four directed-semantics functions have been found returning undirected results
on DiGraphs because their Rust kernel ignored edge direction:
``astar_path`` (br-r37-c1-7e20m), ``eigenvector_centrality_numpy``
(br-r37-c1-rumht), ``constraint`` / ``effective_size`` (br-r37-c1-4bb87), and
``community.modularity`` (br-r37-c1-moddir). Each has its own focused
regression test; this harness is the broad net: it runs a battery of
direction-sensitive functions on a digraph engineered for asymmetric
reachability (so an undirected collapse changes the answer) and asserts parity
with networkx. If a future kernel change reintroduces an undirected collapse on
any of these, this trips.
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


def _asym_digraph(mod, weighted=False):
    # Strongly connected (ring) plus forward chords, so out- and in-structure
    # differ sharply and undirected != directed for every measure below.
    g = mod.DiGraph()
    n = 7
    for i in range(n):
        g.add_edge(i, (i + 1) % n)
    for j, (u, v) in enumerate([(0, 2), (2, 4), (4, 6), (1, 5), (3, 0), (5, 1)]):
        g.add_edge(u, v)
    if weighted:
        for k, (u, v) in enumerate(list(g.edges())):
            g.edges[u, v]["weight"] = float((k % 4) + 1)
    return g


def _dict_close(dn, df, tol=1e-7):
    assert set(dn) == set(df), "key set differs"
    for k in dn:
        a, b = dn[k], df[k]
        if isinstance(a, float) and not math.isfinite(a):
            assert repr(a) == repr(b)
        else:
            assert abs(a - b) <= tol, f"node {k}: nx={a} fnx={b}"


# Each entry: label -> callable(module, graph) producing a node->float dict.
_DICT_FUNCS = {
    "pagerank": lambda m, g: m.pagerank(g),
    "betweenness": lambda m, g: m.betweenness_centrality(g),
    "closeness": lambda m, g: m.closeness_centrality(g),
    "harmonic": lambda m, g: m.harmonic_centrality(g),
    "in_degree_centrality": lambda m, g: m.in_degree_centrality(g),
    "out_degree_centrality": lambda m, g: m.out_degree_centrality(g),
    "load": lambda m, g: m.load_centrality(g),
    "eigenvector_numpy": lambda m, g: m.eigenvector_centrality_numpy(g),
    "eigenvector_iter": lambda m, g: m.eigenvector_centrality(g, max_iter=5000, tol=1e-10),
    "katz_numpy": lambda m, g: m.katz_centrality_numpy(g, alpha=0.05),
    "constraint": lambda m, g: m.constraint(g),
    "effective_size": lambda m, g: m.effective_size(g),
    "clustering": lambda m, g: m.clustering(g),
}


@pytest.mark.parametrize("label", sorted(_DICT_FUNCS))
def test_directed_dict_function_parity(label):
    fn = _DICT_FUNCS[label]
    gn, gf = _asym_digraph(nx), _asym_digraph(fnx)
    _dict_close(fn(nx, gn), fn(fnx, gf))


def test_directed_hits_parity():
    gn, gf = _asym_digraph(nx), _asym_digraph(fnx)
    hn, an = nx.hits(gn, max_iter=5000)
    hf, af = fnx.hits(gf, max_iter=5000)
    _dict_close(hn, hf, tol=1e-6)
    _dict_close(an, af, tol=1e-6)


def test_directed_astar_parity():
    gn, gf = _asym_digraph(nx, weighted=True), _asym_digraph(fnx, weighted=True)
    for t in range(1, 7):
        assert fnx.astar_path(gf, 0, t, weight="weight") == nx.astar_path(gn, 0, t, weight="weight")


def test_directed_modularity_parity():
    gn, gf = _asym_digraph(nx), _asym_digraph(fnx)
    part = [{0, 1, 2, 3}, {4, 5, 6}]
    assert abs(fnx.community.modularity(gf, part) - nx.community.modularity(gn, part)) <= 1e-9


def test_directed_scalar_parity():
    gn, gf = _asym_digraph(nx), _asym_digraph(fnx)
    assert abs(nx.transitivity(gn) - fnx.transitivity(gf)) <= 1e-9
    assert abs(nx.reciprocity(gn) - fnx.reciprocity(gf)) <= 1e-9
    assert abs(nx.degree_assortativity_coefficient(gn) - fnx.degree_assortativity_coefficient(gf)) <= 1e-7
    assert nx.number_strongly_connected_components(gn) == fnx.number_strongly_connected_components(gf)
