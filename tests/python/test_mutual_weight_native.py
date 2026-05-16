"""br-r37-c1-b7ejh: regression tests for native mutual_weight and
normalized_mutual_weight."""

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
    for u, v, *attrs in edges:
        if attrs:
            g.add_edge(u, v, **attrs[0])
        else:
            g.add_edge(u, v)
    return g


def test_mutual_weight_unweighted_both_directions():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 0)
    assert fnx.algorithms.structuralholes.mutual_weight(g, 0, 1) == 2


def test_mutual_weight_unweighted_one_direction():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    assert fnx.algorithms.structuralholes.mutual_weight(g, 0, 1) == 1


def test_mutual_weight_no_edges():
    g = fnx.DiGraph()
    g.add_node(0)
    g.add_node(1)
    assert fnx.algorithms.structuralholes.mutual_weight(g, 0, 1) == 0


def test_mutual_weight_with_weight_attr():
    g = fnx.DiGraph()
    g.add_edge(0, 1, weight=2.5)
    g.add_edge(1, 0, weight=1.5)
    assert fnx.algorithms.structuralholes.mutual_weight(g, 0, 1, weight="weight") == 4.0


def test_mutual_weight_missing_weight_key_treats_as_one():
    g = fnx.DiGraph()
    g.add_edge(0, 1)  # no weight attr
    assert fnx.algorithms.structuralholes.mutual_weight(g, 0, 1, weight="weight") == 1


@needs_nx
def test_mutual_weight_matches_nx():
    edges = [(0, 1, {"w": 2}), (1, 0, {"w": 3}), (0, 2, {"w": 5})]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    for u, v in [(0, 1), (0, 2), (1, 2)]:
        assert fnx.algorithms.structuralholes.mutual_weight(fg, u, v, weight="w") == (
            nx.algorithms.structuralholes.mutual_weight(ng, u, v, weight="w")
        )


def test_normalized_mutual_weight_basic():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(0, 2)
    g.add_edge(1, 0)
    # mutual_weight(0,1) = 2 (both dirs), mutual_weight(0,2) = 1
    # neighbors of 0 are {1, 2} → norm=sum gives 2+1=3
    # normalized = 2/3
    assert fnx.algorithms.structuralholes.normalized_mutual_weight(g, 0, 1) == pytest.approx(2 / 3)


def test_normalized_mutual_weight_zero_scale():
    g = fnx.DiGraph()
    g.add_node(0)
    g.add_node(1)
    # No edges → scale is 0 → return 0 (avoid division by zero)
    assert fnx.algorithms.structuralholes.normalized_mutual_weight(g, 0, 1) == 0


@needs_nx
def test_normalized_mutual_weight_matches_nx():
    edges = [(0, 1, {"w": 2}), (1, 0, {"w": 3}), (0, 2, {"w": 5}), (2, 0, {"w": 1})]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    expected = nx.algorithms.structuralholes.normalized_mutual_weight(
        ng, 0, 1, weight="w"
    )
    assert fnx.algorithms.structuralholes.normalized_mutual_weight(fg, 0, 1, weight="w") == pytest.approx(expected)


@needs_nx
def test_normalized_mutual_weight_max_norm():
    edges = [(0, 1, {"w": 2}), (0, 2, {"w": 5})]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    expected = nx.algorithms.structuralholes.normalized_mutual_weight(
        ng, 0, 1, norm=max, weight="w"
    )
    assert fnx.algorithms.structuralholes.normalized_mutual_weight(fg, 0, 1, norm=max, weight="w") == pytest.approx(
        expected
    )
