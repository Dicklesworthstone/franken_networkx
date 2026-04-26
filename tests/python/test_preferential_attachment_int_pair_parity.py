"""Parity for ``preferential_attachment`` int return type and pair order.

Bead br-r37-c1-bctxc. fnx.preferential_attachment yielded (u, v,
count) triples with two issues vs nx:

- count as float (2.0) instead of nx's int (2) — preferential
  attachment is just deg(u)*deg(v), always integer-valued.
- some pairs in reversed order vs nx (e.g. fnx ('d', 'a', 2.0)
  where nx returned ('a', 'd', 2)).

Drop-in code that asserts ``isinstance(p, int)`` or that
``(u, v, score) in result`` broke.

Fix delegates to nx for both type and pair-order parity.
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
def test_preferential_attachment_returns_int_scores():
    g = _make_str_graph(fnx)
    f = list(fnx.preferential_attachment(g))
    for u, v, score in f:
        assert isinstance(score, int), (
            f"score {score} for pair ({u}, {v}) is {type(score).__name__}, expected int"
        )


@needs_nx
def test_preferential_attachment_pair_order_matches_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.preferential_attachment(g))
    n = list(nx.preferential_attachment(gx))
    assert f == n


@needs_nx
def test_preferential_attachment_with_ebunch():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.preferential_attachment(g, [("a", "d")]))
    n = list(nx.preferential_attachment(gx, [("a", "d")]))
    assert f == n


@needs_nx
def test_preferential_attachment_int_path_graph():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.preferential_attachment(g))
    n = list(nx.preferential_attachment(gx))
    assert f == n
    for _, _, score in f:
        assert isinstance(score, int)


@needs_nx
def test_preferential_attachment_complete_graph_no_non_edges():
    """Complete graph has no non-edges — empty result."""
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = list(fnx.preferential_attachment(g))
    n = list(nx.preferential_attachment(gx))
    assert f == n == []


@needs_nx
def test_preferential_attachment_with_specific_pairs():
    """Specifying ebunch including existing edges and non-edges."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    pairs = [(0, 2), (0, 3), (1, 3)]
    f = list(fnx.preferential_attachment(g, pairs))
    n = list(nx.preferential_attachment(gx, pairs))
    assert f == n
