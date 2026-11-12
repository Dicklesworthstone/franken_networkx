"""Parity for ``max_weight_matching`` tuple direction + matching choice.

Bead br-r37-c1-kpnc8. The Rust binding's matching returned each
matched pair (u, v) in a different direction than nx ((v, u) in
nx's DFS-augmenting-path traversal order), and on graphs where
multiple equally-optimal matchings exist, selected a different
valid choice from nx's adj-iteration-driven search.

Drop-in code that compared the matching against a reference set
of (u, v) pairs broke. Both libs return correct max-weight
matchings — just not the *same* matching.

Repro: edges = [(0,1),(2,3),(4,5)]
  fnx -> {(0,1), (2,3), (4,5)}
  nx  -> {(1,0), (3,2), (5,4)}   (tuple direction reversed)

Bipartite repro:
  edges = [('a','x'),('a','y'),('b','x'),('b','z'),('c','y'),('c','z')]
  fnx -> {('a','y'),('b','x'),('c','z')}
  nx  -> {('a','x'),('b','z'),('c','y')}   (different valid matching)
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_graph(lib, edges, weighted=False, weight_attr="weight"):
    g = lib.Graph()
    for ed in edges:
        if weighted:
            u, v, w = ed
            g.add_edge(u, v, **{weight_attr: w})
        else:
            g.add_edge(*ed)
    return g


@needs_nx
def test_disjoint_edges_tuple_direction_matches_nx():
    edges = [(0, 1), (2, 3), (4, 5)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_simple_path_matching_matches_nx():
    edges = [("p", "q"), ("q", "r"), ("r", "s")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_bipartite_repro_matching_choice_matches_nx():
    """Multiple valid maximum matchings exist; fnx must pick nx's."""
    edges = [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("c", "y"), ("c", "z")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_complete_graph_k4_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_weighted_matching_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "d", 1), ("a", "d", 4)]
    g = _make_graph(fnx, edges, weighted=True)
    gx = _make_graph(nx, edges, weighted=True)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_custom_weight_attr_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "d", 1), ("a", "d", 4)]
    g = _make_graph(fnx, edges, weighted=True, weight_attr="custom_w")
    gx = _make_graph(nx, edges, weighted=True, weight_attr="custom_w")
    assert fnx.max_weight_matching(g, weight="custom_w") == nx.max_weight_matching(gx, weight="custom_w")


@needs_nx
def test_maxcardinality_kwarg_matches_nx():
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    assert fnx.max_weight_matching(g, maxcardinality=True) == nx.max_weight_matching(gx, maxcardinality=True)


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx) == set()


@needs_nx
def test_single_edge_matches_nx():
    g = fnx.Graph([(0, 1)])
    gx = nx.Graph([(0, 1)])
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_min_edge_cover_internal_consumer_unchanged():
    """min_edge_cover internally calls max_weight_matching. Verify
    that the internal tuple-direction change doesn't break the cover
    contract (cover edges should still cover every vertex)."""
    edges = [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("c", "y"), ("c", "z")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.min_edge_cover(g)
    n = nx.min_edge_cover(gx)
    # Both produce a valid edge cover; on undirected, normalise to
    # frozenset edges before comparing.
    assert set(frozenset(e) for e in f) == set(frozenset(e) for e in n)


@needs_nx
def test_is_perfect_matching_consistent_after_delegation():
    """After fnx.max_weight_matching delegates, the returned matching
    must still pass fnx.is_perfect_matching on a graph where one
    exists (regression check for matching-vs-graph round-trip)."""
    g = fnx.complete_graph(4)
    m = fnx.max_weight_matching(g)
    assert fnx.is_perfect_matching(g, m)


@needs_nx
def test_bipartite_complete_k33_matches_nx():
    g = fnx.complete_bipartite_graph(3, 3)
    gx = nx.complete_bipartite_graph(3, 3)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


# 1g0lj.1: max_weight_matching runs networkx's blossom algorithm natively
# (networkx_max_weight_matching_mate) and rebuilds networkx's result from the
# mate insertion order, so the matching AND every pair's direction match.
# min_weight_matching is networkx's body over it. The old native kernel chose
# a different optimal matching in 56 of 800 tie-heavy random graphs and a
# different pair direction in 702.

import random
import sys


def _random_graph(lib, seed, *, big=False):
    rng = random.Random(seed)
    n = rng.randint(1500, 2500) if big else rng.randint(1, 40)
    labels = list(range(n))
    if seed % 3 == 0:
        labels = [f"v{i}" for i in labels]
    if seed % 2:
        rng.shuffle(labels)
    edges = {}
    for _ in range(rng.randint(0, 4 * n)):
        u, v = rng.choice(labels), rng.choice(labels)
        if u == v and rng.random() < 0.8:
            continue
        kind = seed % 4
        if rng.random() < 0.1:
            edges[(u, v)] = None  # no weight attribute: networkx's default 1
        elif kind == 0:
            edges[(u, v)] = rng.choice([1, 1, 2, 3])
        elif kind == 1:
            edges[(u, v)] = rng.randint(-5, 30)
        elif kind == 2:
            edges[(u, v)] = rng.choice([0.5, 1.0, 1.5, 2.25])
        else:
            edges[(u, v)] = rng.random() * 10
    g = lib.Graph()
    g.add_nodes_from(labels)
    for (u, v), w in edges.items():
        g.add_edge(u, v) if w is None else g.add_edge(u, v, weight=w)
    return g


@needs_nx
@pytest.mark.parametrize("maxcardinality", [False, True])
def test_random_graphs_match_networkx_exactly(maxcardinality):
    for seed in range(400):
        expected = nx.max_weight_matching(_random_graph(nx, seed), maxcardinality=maxcardinality)
        assert fnx.max_weight_matching(_random_graph(fnx, seed), maxcardinality=maxcardinality) == expected, seed


@needs_nx
def test_min_weight_matching_matches_networkx_exactly():
    for seed in range(300):
        expected = nx.min_weight_matching(_random_graph(nx, seed))
        assert fnx.min_weight_matching(_random_graph(fnx, seed)) == expected, seed


@needs_nx
def test_large_graphs_with_deep_blossoms_match_networkx_exactly():
    for seed in range(2):
        assert fnx.max_weight_matching(_random_graph(fnx, seed, big=True)) == nx.max_weight_matching(
            _random_graph(nx, seed, big=True)
        ), seed


@needs_nx
@pytest.mark.parametrize("weights", [[2**60, 1, 2], [1, "2", 3], [1, float("nan"), 3], [1, None, 3]])
def test_weights_the_port_does_not_cover_still_match_networkx(weights):
    def build(lib):
        g = lib.Graph()
        for (u, v), w in zip([(0, 1), (1, 2), (2, 3)], weights):
            g.add_edge(u, v, weight=w)
        return g

    def outcome(lib):
        try:
            return ("ok", lib.max_weight_matching(build(lib)))
        except Exception as exc:  # noqa: BLE001 - the exception is the observation
            return ("raise", type(exc).__name__)

    assert outcome(fnx) == outcome(nx)


@needs_nx
@pytest.mark.parametrize("fn", ["max_weight_matching", "min_weight_matching"])
def test_default_path_runs_no_networkx_code(fn):
    graph = _random_graph(fnx, 5)
    root = nx.__file__.rsplit("/", 1)[0]
    seen = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_filename.startswith(root):
            seen.append(frame.f_code.co_name)

    sys.setprofile(profile)
    try:
        getattr(fnx, fn)(graph)
    finally:
        sys.setprofile(None)
    assert seen == [], seen[:10]
