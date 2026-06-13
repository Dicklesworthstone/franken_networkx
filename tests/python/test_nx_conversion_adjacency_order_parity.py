"""Adjacency-order parity for nx -> fnx graph conversion.

Bead br-r37-c1-k6few. ``fnx.Graph(nx_graph)`` must reproduce the source
graph's per-node adjacency *insertion order*, exactly as a native fnx
build does. Today the native build path is correct, but the conversion
constructor re-orders (sorts) per-node neighbour lists, so any
order-sensitive function (to_dict_of_lists, dfs/bfs traversals,
neighbour iteration) diverges from networkx on *converted* graphs while
agreeing on *natively-built* graphs.

Minimal repro (triangle, node 2 sees 1 before 0):
    Gx = nx.Graph(); Gx.add_edge(0, 1); Gx.add_edge(1, 2); Gx.add_edge(2, 0)
    list(nx.Graph(Gx).neighbors(2))   -> [1, 0]   (insertion order)
    list(fnx.Graph(Gx).neighbors(2))  -> [0, 1]   (sorted -- BUG)

The native-build guard below MUST stay green (it pins the correct
behaviour the conversion fix has to match). The conversion checks are
marked xfail (non-strict) and flip to xpass once the fnx-classes
verbatim-adjacency-row builder lands; remove the markers then.
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


def _triangle(lib):
    g = lib.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)
    return g


def _mixed_order(lib):
    # node 5 should see neighbours in the order edges were added: 9, 1, 7.
    g = lib.Graph()
    for u, v in [(5, 9), (1, 5), (5, 7), (9, 1), (7, 9)]:
        g.add_edge(u, v)
    return g


# --- Guards: the native fnx build path must match nx exactly. ---------------

@needs_nx
def test_native_build_preserves_adjacency_order():
    """Natively-built fnx graphs already match nx neighbour order."""
    gf = _triangle(fnx)
    gx = _triangle(nx)
    for node in gx.nodes():
        assert list(gf.neighbors(node)) == list(gx.neighbors(node)), node


@needs_nx
def test_native_build_to_dict_of_lists_matches():
    gf = _mixed_order(fnx)
    gx = _mixed_order(nx)
    assert fnx.to_dict_of_lists(gf) == nx.to_dict_of_lists(gx)


# --- The k6few bug: conversion re-orders adjacency. -------------------------

@needs_nx
@pytest.mark.xfail(
    reason="br-r37-c1-k6few: fnx.Graph(nx_graph) sorts per-node adjacency",
    strict=False,
)
def test_conversion_preserves_adjacency_order():
    gx = _triangle(nx)
    gf = fnx.Graph(gx)
    for node in gx.nodes():
        assert list(gf.neighbors(node)) == list(gx.neighbors(node)), node


@needs_nx
@pytest.mark.xfail(
    reason="br-r37-c1-k6few: conversion sort propagates to to_dict_of_lists",
    strict=False,
)
def test_conversion_to_dict_of_lists_matches():
    # Triangle reliably diverges (node 2 -> [1, 0] in nx, [0, 1] converted);
    # some neighbour orders coincidentally survive the sort, so pin the
    # triangle that does not.
    gx = _triangle(nx)
    gf = fnx.Graph(gx)
    assert fnx.to_dict_of_lists(gf) == nx.to_dict_of_lists(gx)
