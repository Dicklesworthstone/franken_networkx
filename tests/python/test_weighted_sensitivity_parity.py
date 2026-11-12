"""Weighted-sensitivity parity net for the "kernel silently ignores weight"
bug class.

``community.modularity`` was found returning the *unweighted* result on
weighted graphs because the Rust ``_raw_modularity`` kernel ignored the
``weight`` kwarg (br-r37-c1-nim1v, now delegated). A kernel that drops the
weight parameter passes any test that only uses uniform/trivial weights. This
harness runs weight-sensitive functions on a graph with **highly non-uniform**
weights (so the weighted answer differs sharply from the unweighted one) and:

  1. asserts the weighted result matches networkx, and
  2. asserts the weighted result actually *differs* from the unweighted result
     (``_DIFFERS`` cases) — so a regression that started ignoring ``weight``
     would be caught rather than silently passing.
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


def _wgraph(mod, key="weight"):
    g = mod.Graph()
    edges = [(0, 1, 1.0), (1, 2, 10.0), (2, 3, 1.0), (3, 0, 10.0), (0, 2, 1.0),
             (2, 4, 10.0), (4, 5, 1.0), (5, 3, 10.0), (1, 4, 5.0), (0, 4, 2.0)]
    for u, v, w in edges:
        g.add_edge(u, v, **{key: w})
    return g


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, 6) if math.isfinite(x) else repr(x)
    return x


def _close(a, b, tol=1e-6):
    if isinstance(a, dict):
        assert set(a) == set(b)
        return all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, float):
        return abs(a - b) <= tol
    return a == b


# label -> (weighted_call(mod, G), unweighted_call(mod, G))
# weighted_call uses the weight; unweighted_call is the same function without it.
_WEIGHTED = {
    "betweenness": (lambda m, g: m.betweenness_centrality(g, weight="weight"),
                    lambda m, g: m.betweenness_centrality(g)),
    "closeness": (lambda m, g: m.closeness_centrality(g, distance="weight"),
                  lambda m, g: m.closeness_centrality(g)),
    "harmonic": (lambda m, g: m.harmonic_centrality(g, distance="weight"),
                 lambda m, g: m.harmonic_centrality(g)),
    "clustering": (lambda m, g: m.clustering(g, weight="weight"),
                   lambda m, g: m.clustering(g)),
    "pagerank": (lambda m, g: m.pagerank(g, weight="weight"),
                 lambda m, g: m.pagerank(g, weight=None)),
    "eigenvector_numpy": (lambda m, g: m.eigenvector_centrality_numpy(g, weight="weight"),
                          lambda m, g: m.eigenvector_centrality_numpy(g, weight=None)),
    "dijkstra": (lambda m, g: dict(m.single_source_dijkstra_path_length(g, 0, weight="weight")),
                 lambda m, g: dict(m.single_source_dijkstra_path_length(g, 0, weight=None))),
    "eccentricity": (lambda m, g: m.eccentricity(g, weight="weight"),
                     lambda m, g: m.eccentricity(g)),
    "avg_shortest_path": (lambda m, g: round(m.average_shortest_path_length(g, weight="weight"), 6),
                          lambda m, g: round(m.average_shortest_path_length(g), 6)),
    "wiener": (lambda m, g: round(m.wiener_index(g, weight="weight"), 6),
               lambda m, g: round(m.wiener_index(g), 6)),
}


@pytest.mark.parametrize("label", sorted(_WEIGHTED))
def test_weighted_matches_networkx(label):
    wfn, _ = _WEIGHTED[label]
    gn, gf = _wgraph(nx), _wgraph(fnx)
    assert _close(_norm(wfn(nx, gn)), _norm(wfn(fnx, gf))), label


@pytest.mark.parametrize("label", sorted(_WEIGHTED))
def test_weighted_actually_uses_weight(label):
    # The non-uniform weights must change the answer vs unweighted; otherwise
    # this harness couldn't catch a "weight ignored" regression.
    wfn, ufn = _WEIGHTED[label]
    gf = _wgraph(fnx)
    assert not _close(_norm(wfn(fnx, gf)), _norm(ufn(fnx, gf))), (
        f"{label}: weighted result equals unweighted — test is vacuous"
    )


def test_mst_uses_weight_and_matches_networkx():
    gn, gf = _wgraph(nx), _wgraph(fnx)
    wn = round(sum(d["weight"] for *_, d in nx.minimum_spanning_edges(gn, data=True)), 6)
    wf = round(sum(d["weight"] for *_, d in fnx.minimum_spanning_edges(gf, data=True)), 6)
    assert wf == wn


def test_custom_weight_key_matches_networkx():
    gn, gf = _wgraph(nx, key="cost"), _wgraph(fnx, key="cost")
    assert _close(
        _norm(dict(nx.single_source_dijkstra_path_length(gn, 0, weight="cost"))),
        _norm(dict(fnx.single_source_dijkstra_path_length(gf, 0, weight="cost"))),
    )
    assert _close(_norm(nx.pagerank(gn, weight="cost")), _norm(fnx.pagerank(gf, weight="cost")))


def test_multidigraph_dijkstra_path_length_parallel_min_matches_networkx():
    def build(mod):
        graph = mod.MultiDiGraph()
        graph.add_nodes_from(range(5))
        graph.add_edge(0, 1, key="slow", weight=9)
        graph.add_edge(0, 1, key="fast", weight=2)
        graph.add_edge(1, 4, key="tail", weight=2)
        graph.add_edge(0, 2, key="float", weight=1.5)
        graph.add_edge(2, 4, key="bad-tail", weight=10)
        graph.add_edge(0, 4, key="direct", weight=20)
        return graph

    expected = nx.dijkstra_path_length(build(nx), 0, 4, weight="weight")
    actual = fnx.dijkstra_path_length(build(fnx), 0, 4, weight="weight")
    assert type(actual) is type(expected)
    assert actual == expected


def test_multidigraph_dijkstra_path_length_missing_weight_default_matches_networkx():
    def build(mod):
        graph = mod.MultiDiGraph()
        graph.add_nodes_from(range(4))
        graph.add_edge(0, 1, key="missing")
        graph.add_edge(0, 1, key="weighted", weight=5)
        graph.add_edge(1, 3, key="tail")
        graph.add_edge(0, 3, key="direct", weight=7)
        return graph

    expected = nx.dijkstra_path_length(build(nx), 0, 3, weight="weight")
    actual = fnx.dijkstra_path_length(build(fnx), 0, 3, weight="weight")
    assert type(actual) is type(expected)
    assert actual == expected
