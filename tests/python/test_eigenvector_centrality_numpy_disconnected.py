"""br-r37-c1-mcn7h: regression tests for AmbiguousSolution on disconnected
input to eigenvector_centrality_numpy.

nx raises ``AmbiguousSolution`` when the graph is disconnected because
the numpy eigensolver returns a vector with one component arbitrary.
fnx previously returned silently. Now matches nx contract.
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


def test_disconnected_undirected_raises():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(2, 3)
    with pytest.raises(fnx.AmbiguousSolution, match="disconnected"):
        fnx.eigenvector_centrality_numpy(g)


def test_weakly_but_not_strongly_connected_digraph_raises():
    """A directed chain 0->1->2 is weakly but not strongly connected."""
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.AmbiguousSolution, match="disconnected"):
        fnx.eigenvector_centrality_numpy(g)


def test_disconnected_digraph_raises():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(2, 3)
    with pytest.raises(fnx.AmbiguousSolution, match="disconnected"):
        fnx.eigenvector_centrality_numpy(g)


def test_strongly_connected_digraph_works():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)  # makes it strongly connected
    result = fnx.eigenvector_centrality_numpy(g)
    assert set(result.keys()) == {0, 1, 2}


def test_connected_undirected_works():
    g = fnx.path_graph(5)
    result = fnx.eigenvector_centrality_numpy(g)
    assert set(result.keys()) == set(range(5))


@needs_nx
def test_matches_nx_exception_class_on_disconnected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(2, 3)
    gx = nx.Graph()
    gx.add_edge(0, 1)
    gx.add_edge(2, 3)
    # Both should raise the same exception class.
    with pytest.raises(nx.AmbiguousSolution):
        nx.eigenvector_centrality_numpy(gx)
    with pytest.raises(fnx.AmbiguousSolution):
        fnx.eigenvector_centrality_numpy(g)
