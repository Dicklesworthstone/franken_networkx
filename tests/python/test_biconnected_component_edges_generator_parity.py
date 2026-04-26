"""Parity for ``biconnected_component_edges`` return type.

Bead br-r37-c1-24wk3. fnx.biconnected_component_edges returned a list
(eager Rust materialisation) while nx returns a generator (lazy). Same
iter contract issue as br-r37-c1-682kr (8 traversal/path/clique
iterators) and br-r37-c1-ohxpp (edge_boundary).
"""

from __future__ import annotations

import types

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_biconnected_component_edges_returns_generator():
    G = fnx.path_graph(5)
    result = fnx.biconnected_component_edges(G)
    assert isinstance(result, types.GeneratorType)


@needs_nx
def test_biconnected_component_edges_values_match_networkx():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    fc = sorted([
        sorted([tuple(sorted(e)) for e in c])
        for c in fnx.biconnected_component_edges(G)
    ])
    nc = sorted([
        sorted([tuple(sorted(e)) for e in c])
        for c in nx.biconnected_component_edges(GX)
    ])
    assert fc == nc


@needs_nx
def test_biconnected_component_edges_triangle():
    """A triangle is one biconnected component of 3 edges."""
    G = fnx.cycle_graph(3)
    GX = nx.cycle_graph(3)
    fc = list(fnx.biconnected_component_edges(G))
    nc = list(nx.biconnected_component_edges(GX))
    assert len(fc) == len(nc) == 1
    assert len(fc[0]) == len(nc[0]) == 3


@needs_nx
def test_biconnected_component_edges_lazy_short_circuit():
    G = fnx.path_graph(20)
    gen = fnx.biconnected_component_edges(G)
    first = next(gen)
    # Each component on a path is a single bridge edge.
    assert len(first) == 1


@needs_nx
def test_biconnected_component_edges_empty_graph():
    G = fnx.Graph()
    G.add_nodes_from([0, 1, 2])
    result = list(fnx.biconnected_component_edges(G))
    nx_g = nx.Graph()
    nx_g.add_nodes_from([0, 1, 2])
    nx_result = list(nx.biconnected_component_edges(nx_g))
    assert result == nx_result == []


@needs_nx
def test_biconnected_component_edges_disconnected():
    """Two disjoint triangles."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
    GX = nx.Graph()
    GX.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
    fc = sorted([
        sorted([tuple(sorted(e)) for e in c])
        for c in fnx.biconnected_component_edges(G)
    ])
    nc = sorted([
        sorted([tuple(sorted(e)) for e in c])
        for c in nx.biconnected_component_edges(GX)
    ])
    assert fc == nc
    assert len(fc) == 2
