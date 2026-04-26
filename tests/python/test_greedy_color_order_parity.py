"""Parity for ``greedy_color`` dict iteration order.

Bead br-r37-c1-vevfq. fnx.greedy_color returned dict keys in arbitrary
Rust internal order. nx returns them in the order the strategy
processed them (e.g. for the default 'largest_first': nodes sorted
by degree descending). Drop-in code that iterates the result broke.

Same iteration-order family. Fix delegates to nx so the order is
preserved exactly (Rust impl was for performance only; values match
between the two implementations).
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
def test_default_strategy_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_default_strategy_values_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert dict(f) == dict(n)


@needs_nx
def test_saturation_largest_first_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g, strategy="saturation_largest_first")
    n = nx.greedy_color(gx, strategy="saturation_largest_first")
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_int_path_graph_largest_first():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_complete_graph_largest_first():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_callable_strategy_still_works():
    """Custom callable strategies should still delegate to nx."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    strategy = lambda G, colors: list(G.nodes())  # noqa: E731
    f = fnx.greedy_color(g, strategy=strategy)
    n = nx.greedy_color(gx, strategy=strategy)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_empty_graph_returns_empty_dict():
    g = fnx.Graph()
    gx = nx.Graph()
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert f == n == {}
