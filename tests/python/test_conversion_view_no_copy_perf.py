"""to_directed / to_undirected conversion views no longer copy the parent.

Bead br-r37-c1-y2b8t.

`nx.to_directed(graph)` / `nx.to_undirected(graph)` (the module functions)
return a live view (``graph.to_directed(as_view=True)``). fnx returns a view
too, but its conversion-view classes mix in the canonical PyO3 Graph/DiGraph
base, whose ``__new__`` eagerly copied the entire parent graph into the view's
Rust storage on every construction (O(|V|+|E|)). That storage is dead weight —
``_ConversionGraphViewBase`` overrides every query method to answer through
``self._graph``. ``__new__`` now builds an empty base, so construction is O(1).
These tests pin structural parity with nx, the view-tracks-parent-mutations
contract, and that construction does not scale with parent size.
"""

from __future__ import annotations

import random
import time

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _edge_key(g, u, v):
    return (u, v) if g.is_directed() else frozenset((u, v))


@needs_nx
@pytest.mark.parametrize("conv", ["to_directed", "to_undirected"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(30)))
def test_structural_parity_with_nx(conv, directed, seed):
    rng = random.Random(seed * 41 + (3 if directed else 1))
    n = rng.randint(0, 30)
    ng = nx.DiGraph() if directed else nx.Graph()
    fg = fnx.DiGraph() if directed else fnx.Graph()
    nodes = list(range(n))
    rng.shuffle(nodes)
    for u in nodes:
        ng.add_node(u)
        fg.add_node(u)
    seen = set()
    for _ in range(rng.randint(0, n * 2)):
        if not nodes:
            break
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b:
            continue
        k = (a, b) if directed else tuple(sorted((a, b)))
        if k in seen:
            continue
        seen.add(k)
        ng.add_edge(a, b)
        fg.add_edge(a, b)
    sv = getattr(nx, conv)(ng)
    fv = getattr(fnx, conv)(fg)
    assert fv.is_directed() == sv.is_directed()
    assert fv.is_multigraph() == sv.is_multigraph()
    assert set(fv) == set(sv)
    assert fv.number_of_nodes() == sv.number_of_nodes()
    assert fv.number_of_edges() == sv.number_of_edges()
    assert {_edge_key(sv, u, v) for u, v in fv.edges()} == {
        _edge_key(sv, u, v) for u, v in sv.edges()
    }
    for u in sv:
        assert set(fv.adj[u]) == set(sv.adj[u])


@needs_nx
def test_to_directed_tracks_parent_mutations():
    f = fnx.Graph()
    f.add_edges_from([(0, 1), (1, 2), (2, 3)])
    v = fnx.to_directed(f)
    assert v.is_directed()
    assert v.number_of_edges() == 6
    f.add_edge(3, 0)
    assert v.number_of_edges() == 8
    f.remove_node(2)
    assert set(v) == {0, 1, 3}
    assert v.has_edge(3, 0) and v.has_edge(0, 3)


@needs_nx
def test_to_undirected_of_digraph():
    fd = fnx.DiGraph()
    fd.add_edges_from([(0, 1), (1, 0), (1, 2), (3, 2)])
    nd = nx.DiGraph()
    nd.add_edges_from([(0, 1), (1, 0), (1, 2), (3, 2)])
    fv = fnx.to_undirected(fd)
    sv = nx.to_undirected(nd)
    assert not fv.is_directed()
    assert {frozenset(e) for e in fv.edges()} == {frozenset(e) for e in sv.edges()}
    assert fv.number_of_edges() == sv.number_of_edges()


@needs_nx
@pytest.mark.parametrize("seed", list(range(25)))
def test_reverse_view_structural_parity(seed):
    # br-r37-c1-q131o: reverse_view had the same parent-copy bug.
    rng = random.Random(seed * 29 + 2)
    n = rng.randint(0, 30)
    ng, fg = nx.DiGraph(), fnx.DiGraph()
    nodes = list(range(n))
    rng.shuffle(nodes)
    for u in nodes:
        ng.add_node(u)
        fg.add_node(u)
    seen = set()
    for _ in range(rng.randint(0, n * 2)):
        if not nodes:
            break
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b or (a, b) in seen:
            continue
        seen.add((a, b))
        ng.add_edge(a, b)
        fg.add_edge(a, b)
    sv = nx.reverse_view(ng)
    fv = fnx.reverse_view(fg)
    assert fv.is_directed()
    assert set(fv) == set(sv)
    assert fv.number_of_edges() == sv.number_of_edges()
    assert {(u, v) for u, v in fv.edges()} == {(u, v) for u, v in sv.edges()}
    for u in sv:
        assert set(fv.succ[u]) == set(sv.succ[u])
        assert set(fv.pred[u]) == set(sv.pred[u])


@needs_nx
def test_reverse_view_tracks_parent_and_is_fast():
    f = fnx.DiGraph()
    f.add_edges_from([(0, 1), (1, 2)])
    v = fnx.reverse_view(f)
    assert sorted(v.edges()) == [(1, 0), (2, 1)]
    f.add_edge(2, 0)
    assert sorted(v.edges()) == [(0, 2), (1, 0), (2, 1)]

    big = fnx.DiGraph()
    g = nx.gnm_random_graph(8000, 32000, seed=1, directed=True)
    for u in g.nodes():
        big.add_node(u)
    for u, vv in g.edges():
        big.add_edge(u, vv)
    best = 1e9
    for _ in range(5):
        s = time.perf_counter()
        fnx.reverse_view(big)
        best = min(best, time.perf_counter() - s)
    assert best * 1000 < 5.0, f"reverse_view ctor too slow: {best * 1000:.2f}ms"


@needs_nx
def test_construction_does_not_scale_with_parent_size():
    def make(n):
        g = nx.gnm_random_graph(n, n * 4, seed=1)
        f = fnx.Graph()
        for u in g.nodes():
            f.add_node(u)
        for u, v in g.edges():
            f.add_edge(u, v)
        return f

    def ctor_ms(f):
        best = 1e9
        for _ in range(5):
            s = time.perf_counter()
            fnx.to_directed(f)
            best = min(best, time.perf_counter() - s)
        return best * 1000

    big = ctor_ms(make(8000))
    # The old O(N+E) copy was ~186ms on an 8000-node parent. An empty base
    # makes this ~microseconds. Generous bound that still fails on a regression.
    assert big < 5.0, f"to_directed ctor too slow on 8000-node parent: {big:.2f}ms"
