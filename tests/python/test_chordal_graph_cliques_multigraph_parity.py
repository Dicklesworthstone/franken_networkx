"""Parity for ``chordal_graph_cliques`` on MultiGraph inputs.

Bead br-r37-c1-xd6xi. fnx.chordal_graph_cliques raised
NetworkXNotImplemented for MultiGraph inputs, but nx accepts them
and returns the maximal cliques of the underlying simple graph
(parallel edges collapsed). The fnx comment claimed nx had a
@not_implemented_for guard but it actually doesn't.

Also fixes the pre-existing test failures
test_clustering_cliques.py::TestChordalGraphCliquesParity::
test_matches_networkx_without_fallback[MultiGraph-...] which were
asserting the very contract this fix establishes.

Repro:
  mg = MultiGraph([(0,1),(1,2),(2,0),(2,3)])
  fnx (pre-fix) -> NetworkXNotImplemented "not implemented for multigraph type"
  nx            -> [frozenset({0,1,2}), frozenset({2,3})]
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
def test_multigraph_triangle_with_pendant_matches_nx():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    mg = fnx.MultiGraph()
    mgx = nx.MultiGraph()
    for u, v in edges:
        mg.add_edge(u, v)
        mgx.add_edge(u, v)
    f = sorted(sorted(c) for c in fnx.chordal_graph_cliques(mg))
    n = sorted(sorted(c) for c in nx.chordal_graph_cliques(mgx, backend="networkx"))
    assert f == n


@needs_nx
def test_multigraph_with_parallel_edges_raises_not_chordal_matching_nx():
    """nx's chordal-detection treats a multigraph with parallel edges
    as not-chordal (because the parallel edge creates a 2-cycle).
    fnx must match by raising the same NetworkXError."""
    mg = fnx.MultiGraph()
    for u, v in [(0, 1), (0, 1), (1, 2), (2, 0), (2, 3)]:
        mg.add_edge(u, v)
    with pytest.raises(fnx.NetworkXError, match="not chordal"):
        list(fnx.chordal_graph_cliques(mg))


@needs_nx
def test_multigraph_cycle4_matches_nx():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    mg = fnx.MultiGraph()
    mgx = nx.MultiGraph()
    for u, v in edges:
        mg.add_edge(u, v)
        mgx.add_edge(u, v)
    f = sorted(sorted(c) for c in fnx.chordal_graph_cliques(mg))
    n = sorted(sorted(c) for c in nx.chordal_graph_cliques(mgx, backend="networkx"))
    assert f == n


@needs_nx
def test_multigraph_returns_generator_of_frozenset():
    """Result is a generator yielding frozenset objects."""
    mg = fnx.MultiGraph([(0, 1), (1, 2), (2, 0)])
    result = fnx.chordal_graph_cliques(mg)
    cliques = list(result)
    assert all(isinstance(c, frozenset) for c in cliques)


@needs_nx
def test_simple_graph_path_unchanged():
    """Non-multigraph case unchanged from prior behaviour."""
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in edges:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    f = sorted(sorted(c) for c in fnx.chordal_graph_cliques(g))
    n = sorted(sorted(c) for c in nx.chordal_graph_cliques(gx, backend="networkx"))
    assert f == n


@needs_nx
def test_directed_input_still_raises():
    """DiGraph rejection preserved (genuine algorithmic constraint)."""
    dg = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        list(fnx.chordal_graph_cliques(dg))


@needs_nx
def test_multidigraph_input_raises_directed_error():
    """MultiDiGraph hits the directed guard before the multigraph
    projection."""
    mdg = fnx.MultiDiGraph([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        list(fnx.chordal_graph_cliques(mdg))


@needs_nx
def test_self_loop_raises_networkx_error():
    """Self-loops are rejected by nx; our wrapper propagates that."""
    g = fnx.Graph()
    g.add_edge("a", "a")
    with pytest.raises(fnx.NetworkXError):
        list(fnx.chordal_graph_cliques(g))


@needs_nx
def test_empty_multigraph_returns_empty():
    mg = fnx.MultiGraph()
    mgx = nx.MultiGraph()
    f = list(fnx.chordal_graph_cliques(mg))
    n = list(nx.chordal_graph_cliques(mgx, backend="networkx"))
    assert f == n == []


@needs_nx
def test_node_attrs_preserved_on_multigraph_projection():
    """The MultiGraph -> Graph projection should preserve node attrs
    so any nx-equivalent algorithm seeing the same view yields the
    same cliques."""
    mg = fnx.MultiGraph()
    mg.add_node(0, color="red")
    mg.add_node(1, color="blue")
    mg.add_edge(0, 1)
    mg.add_edge(0, 1)  # parallel
    cliques = list(fnx.chordal_graph_cliques(mg))
    assert len(cliques) == 1
    assert cliques[0] == frozenset({0, 1})
