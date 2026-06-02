"""Filtered-view construction no longer copies the parent (perf + correctness).

Bead br-r37-c1-pgfd2.

`_FilteredGraphView.__new__` now builds an EMPTY Rust base instead of letting
the PyO3 ``Graph`` base eagerly copy the entire parent graph (O(|V|+|E|)) on
every ``subgraph_view`` / ``G.subgraph()`` construction. The filtered view
answers every query through ``self._graph`` + the filters, so the base is dead
weight. These tests pin: (1) structural parity with nx; (2) the view still
tracks parent mutations (the empty base must not reintroduce a stale snapshot);
(3) construction time does not scale with parent size.
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


def _build(g):
    f = fnx.Graph()
    for n in g.nodes():
        f.add_node(n)
    for u, v in g.edges():
        f.add_edge(u, v)
    return f


@needs_nx
@pytest.mark.parametrize("seed", list(range(40)))
def test_structural_parity_with_nx(seed):
    rng = random.Random(seed * 53 + 1)
    n = rng.randint(2, 30)
    g = nx.gnm_random_graph(n, rng.randint(0, n * 2), seed=seed)
    f = _build(g)
    keep = rng.sample(list(g), rng.randint(0, n))
    s = g.subgraph(keep)
    fs = f.subgraph(keep)
    assert set(fs) == set(s)
    assert fs.number_of_nodes() == s.number_of_nodes()
    assert fs.number_of_edges() == s.number_of_edges()
    assert {frozenset(e) for e in fs.edges()} == {frozenset(e) for e in s.edges()}
    for u in s:
        assert set(fs.adj[u]) == set(s.adj[u])
        assert fs.degree(u) == s.degree(u)
        assert fs.has_node(u)
    # copy materialises to the same structure
    assert {frozenset(e) for e in fs.copy().edges()} == {
        frozenset(e) for e in s.copy().edges()
    }


@needs_nx
def test_view_tracks_parent_mutations():
    # the empty base must not reintroduce a stale snapshot (br-r37-c1-fgv-has-node)
    f = fnx.Graph()
    f.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    view = f.subgraph([0, 1, 2, 3])
    assert view.has_node(2)
    assert view.number_of_edges() == 4
    f.remove_node(2)
    assert not view.has_node(2)
    assert set(view) == {0, 1, 3}
    assert view.number_of_edges() == 2  # (0,1) and (3,0) survive
    f.add_edge(1, 3)
    assert {frozenset(e) for e in view.edges()} == {
        frozenset((0, 1)), frozenset((3, 0)), frozenset((1, 3))
    }


@needs_nx
def test_construction_does_not_scale_with_parent_size():
    # building a view on a large parent must be fast (no O(N+E) copy).
    def make(n):
        g = nx.gnm_random_graph(n, n * 4, seed=1)
        return _build(g)

    def ctor_ms(f, keep):
        best = 1e9
        for _ in range(5):
            s = time.perf_counter()
            f.subgraph(keep)
            best = min(best, time.perf_counter() - s)
        return best * 1000

    small = make(500)
    big = make(8000)
    t_small = ctor_ms(small, list(range(0, 500, 5)))
    t_big = ctor_ms(big, list(range(0, 8000, 5)))
    # With the old O(N+E) copy, big/small was ~16x (140ms vs 6ms). With the
    # empty base, construction is dominated by the selected-node filter build,
    # so the ratio is far below the 16x parent-size ratio. Generous bound.
    assert t_big < 30.0, f"view ctor too slow on 8000-node parent: {t_big:.1f}ms"
