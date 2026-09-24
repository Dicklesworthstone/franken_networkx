"""Adding attributes to an EXISTING edge merges them, whatever built the graph.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.2 (existing-edge merge). fnx
keeps edge attributes in the native store and materialises the Python dicts
lazily, so an edge of a natively built graph (every generator, MultiGraph(G))
has no Python dict yet. Graph.add_edge / MultiGraph.add_edge then started a
fresh empty dict for the existing edge, hiding its stored attributes:
``karate_club_graph().add_edge(0, 1, extra=1)`` left ``G.edges[0, 1] ==
{'extra': 1}`` (networkx: ``{'weight': 4, 'extra': 1}``) and moved
``size(weight='weight')`` from 231 to 228. Everything that delegates to
add_edge (add_edges_from, add_weighted_edges_from, update) inherited it.

The "add_edges_from" provenance builds through Python dicts, so its mirrors
are already materialised — it is the control that passed before the fix; the
native provenances are the negative case.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _generator(m, cls):
    G = m.karate_club_graph()
    return G if cls == "Graph" else getattr(m, cls)(G)


def _from_python_dicts(m, cls):
    G = getattr(m, cls)()
    G.add_edges_from([(0, 1, {"weight": 4}), (1, 2, {"weight": 5})])
    return G


def _read_back(m, cls, tmp_path):
    path = tmp_path / f"{m.__name__}_{cls}.edgelist"
    nx.write_edgelist(nx.karate_club_graph(), path, data=["weight"])
    return m.read_edgelist(
        path, nodetype=int, data=[("weight", int)], create_using=getattr(m, cls)
    )


PROVENANCES = {"generator": _generator, "add_edges_from": _from_python_dicts}


def _edge(G):
    if G.is_multigraph():
        return {k: dict(d) for k, d in G[0][1].items()}
    return dict(G.edges[0, 1])


MUTATIONS = {
    "add_edge": lambda G: G.add_edge(0, 1, key=0, extra=1) if G.is_multigraph() else G.add_edge(0, 1, extra=1),
    "add_edges_from": lambda G: G.add_edges_from([(0, 1, 0, {"extra": 1})] if G.is_multigraph() else [(0, 1, {"extra": 1})]),
    "add_weighted_edges_from": lambda G: G.add_weighted_edges_from([(0, 1, 9)], weight="w2"),
    "update": lambda G: G.update(edges=[(0, 1, 0, {"extra": 1})] if G.is_multigraph() else [(0, 1, {"extra": 1})]),
    "overwrite_same_attr": lambda G: G.add_edge(0, 1, key=0, weight=7) if G.is_multigraph() else G.add_edge(0, 1, weight=7),
}


def _state(G):
    return (_edge(G), G.size(weight="weight"), sorted(G.edges(data="weight", default=None), key=repr))


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
@pytest.mark.parametrize("provenance", sorted(PROVENANCES))
def test_existing_edge_attrs_merge_like_networkx(cls, mutation, provenance):
    gnx, gfx = PROVENANCES[provenance](nx, cls), PROVENANCES[provenance](fnx, cls)
    MUTATIONS[mutation](gnx)
    MUTATIONS[mutation](gfx)
    assert _state(gfx) == _state(gnx)


@pytest.mark.parametrize("cls", CLASSES)
def test_read_edgelist_graph_merges_like_networkx(cls, tmp_path):
    gnx, gfx = _read_back(nx, cls, tmp_path), _read_back(fnx, cls, tmp_path)
    for G in (gnx, gfx):
        MUTATIONS["add_edge"](G)
    assert _state(gfx) == _state(gnx)


def test_weighted_algorithm_sees_the_merged_weight():
    """The kernels read the native store; it must agree with the view."""
    gnx, gfx = nx.karate_club_graph(), fnx.karate_club_graph()
    for G in (gnx, gfx):
        G.add_edge(0, 1, extra=1)
    assert fnx.dijkstra_path_length(gfx, 0, 33) == nx.dijkstra_path_length(gnx, 0, 33)
    assert fnx.community.modularity(gfx, [set(range(17)), set(range(17, 34))]) == pytest.approx(
        nx.community.modularity(gnx, [set(range(17)), set(range(17, 34))])
    )


GRAPHML = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="node" attr.name="club" attr.type="string"/>
  <key id="d1" for="edge" attr.name="weight" attr.type="int"/>
  <graph edgedefault="{kind}">
    <node id="0"><data key="d0">x</data></node>
    <node id="1"><data key="d0">y</data></node>
    <node id="2"><data key="d0">z</data></node>
    <edge source="0" target="1"><data key="d1">4</data></edge>
    <edge source="1" target="2"><data key="d1">5</data></edge>
  </graph>
</graphml>"""


@pytest.mark.parametrize("cls", CLASSES)
def test_node_and_edge_attrs_of_a_read_graph_survive_add_edge(cls, tmp_path):
    kind = "directed" if cls in ("DiGraph", "MultiDiGraph") else "undirected"
    path = tmp_path / "g.graphml"
    path.write_text(GRAPHML.format(kind=kind))
    graphs = []
    for m in (nx, fnx):
        G = getattr(m, cls)(m.read_graphml(path, node_type=int))
        if G.is_multigraph():
            G.add_edge(0, 1, key=0, extra=1)
        else:
            G.add_edge(0, 1, extra=1)
        G.add_edge(2, 0)
        graphs.append(G)
    gnx, gfx = graphs
    assert _edge(gfx) == _edge(gnx)
    assert dict(gfx.nodes(data=True)) == dict(gnx.nodes(data=True))
