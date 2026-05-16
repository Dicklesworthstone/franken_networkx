"""br-r37-c1-n23aj: regression tests for native colliders + v_structures."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build(cls, edges):
    g = cls()
    for u, v in edges:
        g.add_edge(u, v)
    return g


def _normalize_triples(triples):
    """Normalize (p1, collider, p2) triples by sorting the parent pair so
    fnx vs nx node-iteration order doesn't affect equality."""
    return {(min(p1, p2), c, max(p1, p2)) for p1, c, p2 in triples}


@needs_nx
def test_colliders_matches_nx_on_docstring_example():
    # br-r37-c1-ax3ix: nx yields (p1, c, p2) triples where the parent
    # order depends on graph node-iteration order. fnx and nx have
    # the same node-iteration semantics (insertion-order) but the
    # node-creation timing in _build differs, so the parent pair can
    # come out swapped. Normalize the unordered parent pair before
    # comparing.
    edges = [(1, 2), (0, 4), (3, 1), (2, 4), (0, 5), (4, 5), (1, 5)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert _normalize_triples(fnx.algorithms.dag.colliders(fg)) == \
           _normalize_triples(nx.algorithms.dag.colliders(ng))


@needs_nx
def test_v_structures_matches_nx_on_docstring_example():
    # br-r37-c1-ax3ix: same parity contract as colliders.
    edges = [(1, 2), (0, 4), (3, 1), (2, 4), (0, 5), (4, 5), (1, 5)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert _normalize_triples(fnx.algorithms.dag.v_structures(fg)) == \
           _normalize_triples(nx.algorithms.dag.v_structures(ng))


def test_colliders_empty_dag():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    assert list(fnx.algorithms.dag.colliders(g)) == []


def test_colliders_two_parents():
    g = fnx.DiGraph()
    g.add_edge(0, 2)
    g.add_edge(1, 2)
    assert list(fnx.algorithms.dag.colliders(g)) == [(0, 2, 1)]


def test_v_structures_unmarried_only():
    g = fnx.DiGraph()
    g.add_edge(0, 2)
    g.add_edge(1, 2)
    # Without edge between 0 and 1, this is a v-structure.
    assert list(fnx.algorithms.dag.v_structures(g)) == [(0, 2, 1)]
    # Adding 0->1 makes them "married" — no longer a v-structure.
    g.add_edge(0, 1)
    assert list(fnx.algorithms.dag.v_structures(g)) == []


def test_colliders_rejects_undirected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.algorithms.dag.colliders(g))


def test_v_structures_rejects_undirected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.algorithms.dag.v_structures(g))


@needs_nx
def test_colliders_allows_cyclic_graphs():
    # nx docs explicitly note this — the algorithm works on cycles.
    edges = [(0, 1), (1, 0), (0, 2), (1, 2)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert list(fnx.algorithms.dag.colliders(fg)) == list(nx.algorithms.dag.colliders(ng))
