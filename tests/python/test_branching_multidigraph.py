"""br-r37-c1-s8x7z: regression tests for branching family on MultiDiGraph.

The Rust kernels for maximum/minimum_branching and maximum/minimum_spanning_arborescence
match only ``GraphRef::Directed`` (simple DiGraph) and emit a custom
"only implemented for directed graphs" error for MultiDiGraph input.
nx supports MultiDiGraph. Wrappers now delegate the multigraph case.
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
@pytest.mark.parametrize(
    "fnx_fn,nx_fn",
    [
        (fnx.maximum_branching, nx.maximum_branching),
        (fnx.minimum_branching, nx.minimum_branching),
        (fnx.maximum_spanning_arborescence, nx.maximum_spanning_arborescence),
        (fnx.minimum_spanning_arborescence, nx.minimum_spanning_arborescence),
    ],
)
def test_branching_family_accepts_multidigraph(fnx_fn, nx_fn):
    edges = [(0, 1), (1, 2)]
    fg = _build(fnx.MultiDiGraph, edges)
    ng = _build(nx.MultiDiGraph, edges)
    fr = fnx_fn(fg)
    nr = nx_fn(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes())
    # Edge sets may differ in key but should cover the same (u, v) pairs.
    f_edges = sorted((u, v) for u, v in fr.edges())
    n_edges = sorted((u, v) for u, v in nr.edges())
    assert f_edges == n_edges


@needs_nx
def test_minimum_branching_simple_digraph_still_native():
    # Sanity: the native path on simple DiGraph still works after wrapper
    # gating change.
    edges = [(0, 1), (1, 2), (2, 0)]
    fg = _build(fnx.DiGraph, edges)
    ng = _build(nx.DiGraph, edges)
    fr = fnx.minimum_branching(fg)
    nr = nx.minimum_branching(ng)
    assert sorted(fr.edges()) == sorted(nr.edges())


def test_minimum_spanning_arborescence_undirected_still_rejected():
    # Undirected rejection rule unchanged.
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="not implemented for undirected"):
        fnx.minimum_spanning_arborescence(g)
