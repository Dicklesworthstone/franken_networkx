"""br-r37-c1-gtkxs: regression tests that transitive_closure preserves
node and edge attributes (parity with nx)."""

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
def test_transitive_closure_preserves_node_attributes_on_dag():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_node(0, color="red")
    ng.add_node(0, color="red")
    fg.add_node(1, color="blue")
    ng.add_node(1, color="blue")
    fg.add_edge(0, 1)
    ng.add_edge(0, 1)
    rf = fnx.transitive_closure(fg)
    rn = nx.transitive_closure(ng)
    assert dict(rf.nodes(data=True)) == dict(rn.nodes(data=True))


@needs_nx
def test_transitive_closure_preserves_edge_attributes_on_dag():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_edge(0, 1, weight=5)
    ng.add_edge(0, 1, weight=5)
    fg.add_edge(1, 2, weight=3)
    ng.add_edge(1, 2, weight=3)
    rf = fnx.transitive_closure(fg)
    rn = nx.transitive_closure(ng)
    # Check original edges keep their attributes
    assert rf[0][1] == rn[0][1]
    assert rf[1][2] == rn[1][2]


@needs_nx
def test_transitive_closure_adds_transitive_edges():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 3)]:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    rf = fnx.transitive_closure(fg)
    rn = nx.transitive_closure(ng)
    assert set(rf.edges()) == set(rn.edges())


def test_transitive_closure_no_attrs_unchanged():
    """Sanity: no-attr graph still works."""
    g = fnx.DiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
    r = fnx.transitive_closure(g)
    assert set(r.edges()) == {(0, 1), (0, 2), (1, 2)}


def _multidigraph_snapshot(graph):
    return {
        "type": type(graph).__name__,
        "graph": dict(graph.graph),
        "nodes": list(graph.nodes(data=True)),
        "edges": list(graph.edges(keys=True, data=True)),
    }


@needs_nx
def test_multidigraph_transitive_closure_matches_networkx_dag_attrs_and_order():
    fg = fnx.MultiDiGraph(name="mdag")
    ng = nx.MultiDiGraph(name="mdag")
    for graph in (fg, ng):
        graph.add_node("a", color="red")
        graph.add_node("b", color="blue")
        graph.add_node("c", color="green")
        graph.add_node("d", color="gold")
        graph.add_edge("a", "b", key="ab0", weight=1)
        graph.add_edge("a", "b", key="ab1", weight=2)
        graph.add_edge("b", "c", key="bc0", weight=3)
        graph.add_edge("a", "d", key="ad0", jump=True)
        graph.add_edge("d", "c", key="dc0", weight=4)

    assert _multidigraph_snapshot(fnx.transitive_closure(fg)) == _multidigraph_snapshot(
        nx.transitive_closure(ng)
    )


@needs_nx
def test_multidigraph_transitive_closure_matches_networkx_cycle_self_loops():
    fg = fnx.MultiDiGraph()
    ng = nx.MultiDiGraph()
    for graph in (fg, ng):
        graph.add_edge("a", "b", key=0)
        graph.add_edge("a", "b", key=1)
        graph.add_edge("b", "c", key=0)
        graph.add_edge("c", "a", key=0)

    assert _multidigraph_snapshot(fnx.transitive_closure(fg)) == _multidigraph_snapshot(
        nx.transitive_closure(ng)
    )


@needs_nx
def test_multidigraph_transitive_closure_reflexive_true_keeps_networkx_parity():
    fg = fnx.MultiDiGraph([(0, 1), (1, 2)])
    ng = nx.MultiDiGraph([(0, 1), (1, 2)])

    assert _multidigraph_snapshot(
        fnx.transitive_closure(fg, reflexive=True)
    ) == _multidigraph_snapshot(nx.transitive_closure(ng, reflexive=True))
