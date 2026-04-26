"""Parity for ``cut_size`` int/float return type.

Bead br-r37-c1-f47su. fnx.cut_size always returned a float (1.0, 2.0)
regardless of input weight type. nx.cut_size preserves int when the
result is integer (always for unweighted, and when all relevant
weights are int). Drop-in code that asserts
``isinstance(cut_size(G, S), int)`` broke.
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


@needs_nx
def test_unweighted_returns_int():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.cut_size(G, [0, 1])
    n = nx.cut_size(GX, [0, 1])
    assert f == n == 1
    assert isinstance(f, int)
    assert type(f) is type(n)


@needs_nx
def test_weighted_int_returns_int():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2)
    G.add_edge(1, 2, weight=3)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2)
    GX.add_edge(1, 2, weight=3)
    f = fnx.cut_size(G, [0], weight="weight")
    n = nx.cut_size(GX, [0], weight="weight")
    assert f == n == 2
    assert isinstance(f, int)


@needs_nx
def test_weighted_float_returns_float():
    """Float weights must stay float."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2.5)
    f = fnx.cut_size(G, [0], weight="weight")
    n = nx.cut_size(GX, [0], weight="weight")
    assert f == n == 2.5
    assert isinstance(f, float)


@needs_nx
def test_unweighted_with_S_T():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.cut_size(G, [0, 1], [2, 3])
    n = nx.cut_size(GX, [0, 1], [2, 3])
    assert type(f) is type(n)


@needs_nx
def test_zero_cut_returns_int():
    """A cut of zero edges should still be int 0, not float 0.0."""
    G = fnx.Graph()
    G.add_nodes_from([0, 1, 2])
    GX = nx.Graph()
    GX.add_nodes_from([0, 1, 2])
    f = fnx.cut_size(G, [0])
    n = nx.cut_size(GX, [0])
    assert f == n == 0
    assert isinstance(f, int)


@needs_nx
def test_selfloop_unweighted_returns_int():
    """Self-loops contribute 1 each — result is int."""
    G = fnx.Graph([(0, 0), (0, 1)])
    GX = nx.Graph([(0, 0), (0, 1)])
    f = fnx.cut_size(G, [0])
    n = nx.cut_size(GX, [0])
    assert type(f) is type(n)


@needs_nx
def test_mixed_int_float_weights_returns_float():
    """If any edge in the cut has a float weight, result is float."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2)
    G.add_edge(1, 2, weight=2.5)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2)
    GX.add_edge(1, 2, weight=2.5)
    f = fnx.cut_size(G, [0, 1], weight="weight")
    n = nx.cut_size(GX, [0, 1], weight="weight")
    assert f == n
    assert isinstance(f, float) == isinstance(n, float)
