"""br-r37-c1-ho3db: regression tests for SpanningTreeIterator and
ArborescenceIterator multigraph delegation.

The Rust-backed iterators handle simple graphs only. nx supports
MultiGraph (SpanningTreeIterator) and MultiDiGraph (ArborescenceIterator).
The wrappers now delegate multigraph input to nx.
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
def test_spanning_tree_iterator_multigraph_yields_results():
    g = fnx.MultiGraph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    trees = list(fnx.SpanningTreeIterator(g))
    assert len(trees) >= 1


@needs_nx
def test_arborescence_iterator_multidigraph_yields_results():
    g = fnx.MultiDiGraph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    arbs = list(fnx.ArborescenceIterator(g))
    assert len(arbs) >= 1


def test_spanning_tree_iterator_directed_still_rejected():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        list(fnx.SpanningTreeIterator(g))


def test_arborescence_iterator_undirected_still_rejected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        list(fnx.ArborescenceIterator(g))


@needs_nx
def test_spanning_tree_iterator_simple_undirected_still_native():
    g = fnx.path_graph(4)
    trees = list(fnx.SpanningTreeIterator(g))
    assert len(trees) == 1  # path graph has exactly one spanning tree


@needs_nx
def test_arborescence_iterator_simple_digraph_still_native():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    arbs = list(fnx.ArborescenceIterator(g))
    assert len(arbs) >= 1
