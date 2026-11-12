"""networkx interop with fnx DiGraph / MultiGraph / MultiDiGraph.

Extends the (undirected) nx-on-fnx interop test to the directed and multi graph
types: networkx functions called on fnx DiGraph/MultiGraph/MultiDiGraph match the
equivalent nx graph, and an nx graph of the matching type can be constructed from
the fnx one. Confirms the duck-typing interop holds across all four graph types.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import networkx as nx
import franken_networkx as fnx


def test_digraph_interop():
    fd = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    nd = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    assert nx.is_directed(fd) is True
    assert nx.is_strongly_connected(fd) == nx.is_strongly_connected(nd)
    assert nx.number_strongly_connected_components(fd) == (
        nx.number_strongly_connected_components(nd)
    )
    assert dict(fd.in_degree()) == dict(nd.in_degree())
    assert dict(fd.out_degree()) == dict(nd.out_degree())
    assert set(nx.pagerank(fd)) == set(nx.pagerank(nd))
    # Reconstruct an nx DiGraph from the fnx one.
    assert sorted(nx.DiGraph(fd).edges()) == sorted(nd.edges())


def test_dag_interop():
    fd = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    nd = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    assert nx.is_directed_acyclic_graph(fd) == nx.is_directed_acyclic_graph(nd)
    assert list(nx.topological_sort(fd)) == list(nx.topological_sort(nd))


def test_multigraph_interop():
    fm = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    nm = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    assert fm.is_multigraph() is True
    assert nx.number_of_edges(fm) == nx.number_of_edges(nm)
    assert dict(nx.degree(fm)) == dict(nx.degree(nm))
    assert fm.number_of_edges(0, 1) == nm.number_of_edges(0, 1) == 2
    # Reconstruct an nx MultiGraph from the fnx one.
    assert sorted(nx.MultiGraph(fm).edges()) == sorted(nm.edges())


def test_multidigraph_interop():
    fmd = fnx.MultiDiGraph([(0, 1), (0, 1), (1, 0)])
    nmd = nx.MultiDiGraph([(0, 1), (0, 1), (1, 0)])
    assert nx.is_directed(fmd) and fmd.is_multigraph()
    assert nx.number_of_edges(fmd) == nx.number_of_edges(nmd) == 3
    assert dict(fmd.in_degree()) == dict(nmd.in_degree())
