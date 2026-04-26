"""Parity for ``eulerian_circuit`` edge sequence / traversal direction.

Bead br-r37-c1-lim0x. Eulerian circuits are not unique, but the Rust
binding emitted edges in a different traversal direction than nx.

Repro: edges = [('a','b'),('b','c'),('c','a'),('a','d'),('d','e'),('e','a')]
  fnx -> [('a','b'),('b','c'),('c','a'),('a','d'),('d','e'),('e','a')]
  nx  -> [('a','e'),('e','d'),('d','a'),('a','c'),('c','b'),('b','a')]

Drop-in code that compared the produced edge sequence against a
reference Hierholzer traversal broke. Fix delegates ``eulerian_circuit``
to nx so the edge sequence matches its documented contract.
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


def _make_graph(lib, edges):
    g = lib.Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


def _make_digraph(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_repro_two_triangle_via_a_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d"), ("d", "e"), ("e", "a")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.eulerian_circuit(g)) == list(nx.eulerian_circuit(gx))


@needs_nx
def test_simple_4cycle_int_nodes_matches_nx():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.eulerian_circuit(g)) == list(nx.eulerian_circuit(gx))


@needs_nx
def test_with_source_kwarg_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d"), ("d", "e"), ("e", "a")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.eulerian_circuit(g, source="b")) == list(nx.eulerian_circuit(gx, source="b"))


@needs_nx
def test_directed_circuit_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    dg = _make_digraph(fnx, edges)
    dgx = _make_digraph(nx, edges)
    assert list(fnx.eulerian_circuit(dg)) == list(nx.eulerian_circuit(dgx))


@needs_nx
def test_non_eulerian_graph_raises_networkx_error():
    g = fnx.path_graph(5)
    with pytest.raises(fnx.NetworkXError, match="not Eulerian"):
        list(fnx.eulerian_circuit(g))


@needs_nx
def test_keys_kwarg_on_multigraph_matches_nx():
    """keys=True on MultiGraph yields (u, v, key) triples."""
    g = fnx.MultiGraph()
    gx = nx.MultiGraph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "a"), ("a", "b")]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    # The graph isn't Eulerian for this; pick a closed circuit graph.
    g = fnx.MultiGraph()
    gx = nx.MultiGraph()
    for u, v in [("a", "b"), ("b", "a")]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert list(fnx.eulerian_circuit(g, keys=True)) == list(nx.eulerian_circuit(gx, keys=True))


@needs_nx
def test_complete_graph_5_matches_nx():
    """K5 has all even-degree vertices -> Eulerian."""
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    assert list(fnx.eulerian_circuit(g)) == list(nx.eulerian_circuit(gx))


@needs_nx
def test_self_loop_triangle_matches_nx():
    """Self-loop contributes 2 to degree, keeping evens."""
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "a")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.eulerian_circuit(g)) == list(nx.eulerian_circuit(gx))
