"""br-r37-c1-3jn5a: regression tests for dominating_set on directed graphs.

nx supports DiGraph for dominating_set (uses out-neighbors).
The Rust kernel requires undirected. The wrapper now delegates
directed input to nx.
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


def _build(cls, edges):
    g = cls()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_dominating_set_digraph_path():
    edges = [(0, 1), (1, 2)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert fnx.dominating_set(fg) == nx.dominating_set(ng)


@needs_nx
def test_dominating_set_digraph_cycle():
    edges = [(0, 1), (1, 2), (2, 0)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    assert fnx.dominating_set(fg) == nx.dominating_set(ng)


def test_dominating_set_plain_digraph_default_stays_local(monkeypatch):
    graph = _build(fnx.DiGraph, [(0, 1), (1, 2), (2, 3)])

    def fail_parity_fallback(*args, **kwargs):
        raise AssertionError("plain DiGraph dominating_set should not delegate")

    monkeypatch.setattr(fnx, "_call_networkx_for_parity", fail_parity_fallback)

    assert fnx.dominating_set(graph) == {0, 2}


@needs_nx
def test_dominating_set_multidigraph():
    edges = [(0, 1), (1, 2)]
    fg = _build(fnx.MultiDiGraph, edges)
    ng = _build(nx.MultiDiGraph, edges)
    # MultiDiGraph also delegates via is_directed() branch.
    assert fnx.dominating_set(fg) == nx.dominating_set(ng)


def test_dominating_set_undirected_unchanged():
    g = fnx.path_graph(5)
    result = fnx.dominating_set(g)
    assert isinstance(result, set)
    # On a path graph, a dominating set must cover every node.
    nodes = set(g.nodes())
    for n in nodes - result:
        # Each node not in the set must have a neighbor in the set.
        assert any(nbr in result for nbr in g.neighbors(n))
