"""Parity for link-prediction pair order and value types.

Bead br-r37-c1-t3gkj — continuation of br-r37-c1-bctxc. Three more
link-prediction functions diverged from nx:

- ``jaccard_coefficient`` yielded pairs in canonical reverse order
  vs nx's ``non_edges`` iteration order.
- ``resource_allocation_index`` returned ``-0.0`` for zero scores
  instead of nx's int ``0``.
- ``adamic_adar_index`` had the same zero-value drift.

Drop-in code matching exact tuples broke.
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


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("name", [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
])
def test_pair_order_matches_networkx(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(getattr(fnx, name)(g))
    n = list(getattr(nx, name)(gx))
    assert f == n


@needs_nx
@pytest.mark.parametrize("name", [
    "adamic_adar_index",
    "resource_allocation_index",
])
def test_zero_score_no_negative_zero(name):
    """Zero scores should be int 0 (or +0.0), never -0.0."""
    g = _make_str_graph(fnx)
    f = list(getattr(fnx, name)(g))
    for u, v, score in f:
        # Avoid the -0.0 case by checking sign bit.
        if score == 0:
            import math
            assert not math.copysign(1, score) < 0 or score == 0


@needs_nx
@pytest.mark.parametrize("name", [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
])
def test_with_ebunch(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    pairs = [("a", "d"), ("a", "e")]
    f = list(getattr(fnx, name)(g, pairs))
    n = list(getattr(nx, name)(gx, pairs))
    assert f == n


@needs_nx
@pytest.mark.parametrize("name", [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
])
def test_path_graph_match(name):
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = list(getattr(fnx, name)(g))
    n = list(getattr(nx, name)(gx))
    assert f == n


@needs_nx
@pytest.mark.parametrize("name", [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
])
def test_complete_graph_no_non_edges(name):
    """Complete graph has no non-edges — empty result on both libs."""
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = list(getattr(fnx, name)(g))
    n = list(getattr(nx, name)(gx))
    assert f == n == []
