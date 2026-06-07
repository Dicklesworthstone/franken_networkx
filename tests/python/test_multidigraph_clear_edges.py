"""br-r37-c1-1uv81: MultiDiGraph.clear_edges() was a no-op (edges survived).

PyMultiDiGraph::clear_edges re-added nodes into the OLD inner graph without
resetting it, so every edge survived. The other three classes rebuild a
fresh inner. Parity-pin all four classes against networkx.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(mod, cls):
    g = getattr(mod, cls)()
    g.add_node("isolated", tag="keep")
    g.add_node(1, color="red")
    g.add_edge(1, 2, weight=5)
    g.add_edge(2, 3)
    if g.is_multigraph():
        g.add_edge(2, 3)  # parallel edge
    g.add_edge(3, 3)  # self-loop
    return g


@pytest.mark.parametrize("cls", CLASSES)
def test_clear_edges_removes_all_edges(cls):
    gf = _build(fnx, cls)
    gn = _build(nx, cls)
    gf.clear_edges()
    gn.clear_edges()
    assert list(gf.edges()) == list(gn.edges()) == []
    assert gf.number_of_edges() == 0


@pytest.mark.parametrize("cls", CLASSES)
def test_clear_edges_keeps_nodes_and_attrs(cls):
    gf = _build(fnx, cls)
    gn = _build(nx, cls)
    gf.clear_edges()
    gn.clear_edges()
    assert list(gf.nodes()) == list(gn.nodes())
    assert dict(gf.nodes[1]) == dict(gn.nodes[1]) == {"color": "red"}
    assert dict(gf.nodes["isolated"]) == {"tag": "keep"}


@pytest.mark.parametrize("cls", CLASSES)
def test_clear_edges_then_readd(cls):
    gf = _build(fnx, cls)
    gn = _build(nx, cls)
    gf.clear_edges()
    gn.clear_edges()
    gf.add_edge(1, 2, weight=9)
    gn.add_edge(1, 2, weight=9)
    assert list(gf.edges(data=True)) == list(gn.edges(data=True))
    if "Di" in cls:
        assert gf.in_degree(2) == gn.in_degree(2) == 1
    assert gf.degree(1) == gn.degree(1)


def test_multidigraph_clear_edges_adjacency_empty():
    gf = _build(fnx, "MultiDiGraph")
    gn = _build(nx, "MultiDiGraph")
    gf.clear_edges()
    gn.clear_edges()
    assert {n: dict(gf.adj[n]) for n in gf} == {n: dict(gn.adj[n]) for n in gn}
    assert {n: dict(gf.pred[n]) for n in gf} == {n: dict(gn.pred[n]) for n in gn}
