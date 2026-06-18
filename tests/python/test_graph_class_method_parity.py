"""Core Graph/DiGraph class method parity with networkx.

The graph classes are the foundation every algorithm builds on — view access
(nodes/edges/adj/degree), data access (attributes), mutation (add/remove/update),
and subgraph views must match networkx semantics exactly, including that
subgraph() returns a live view.

No mocks: real fnx and real networkx, operated in lock-step.
"""

from __future__ import annotations

import networkx as nx
import franken_networkx as fnx


def _setup(lib):
    g = lib.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3)])
    g.add_node(5, color="red")
    g.nodes[0]["x"] = 1
    g[0][1]["w"] = 9
    return g


def _edges(g):
    return sorted(tuple(sorted((u, v))) for u, v in g.edges())


def test_views_and_data_access():
    fg, ng = _setup(fnx), _setup(nx)
    assert sorted(fg.nodes()) == sorted(ng.nodes())
    assert _edges(fg) == _edges(ng)
    assert {n: dict(d) for n, d in fg.nodes(data=True)} == (
        {n: dict(d) for n, d in ng.nodes(data=True)}
    )
    assert {tuple(sorted((u, v))): dict(d) for u, v, d in fg.edges(data=True)} == (
        {tuple(sorted((u, v))): dict(d) for u, v, d in ng.edges(data=True)}
    )
    assert dict(fg.degree()) == dict(ng.degree())
    assert {n: sorted(fg[n]) for n in fg} == {n: sorted(ng[n]) for n in ng}
    assert sorted(fg.neighbors(1)) == sorted(ng.neighbors(1))
    assert fg.get_edge_data(0, 1) == ng.get_edge_data(0, 1)
    assert (fg.order(), fg.size()) == (ng.order(), ng.size())
    assert fg.size(weight="w") == ng.size(weight="w")
    assert sorted(fg.nbunch_iter([0, 1, 99])) == sorted(ng.nbunch_iter([0, 1, 99]))


def test_mutation_lockstep():
    fg, ng = _setup(fnx), _setup(nx)

    def mutate(g):
        g.remove_node(5)
        g.remove_edge(0, 1)
        g.add_edge(3, 4)
        g.update(edges=[(4, 5)], nodes=[6])
        g.remove_nodes_from([6])
        return _edges(g), sorted(g.nodes())

    assert mutate(fg) == mutate(ng)


def test_subgraph_is_live_view():
    fg, ng = _setup(fnx), _setup(nx)
    fsv, nsv = fg.subgraph([0, 1, 2]), ng.subgraph([0, 1, 2])
    assert _edges(fsv) == _edges(nsv)
    # Mutating the parent is reflected in the subgraph view.
    fg.add_edge(0, 2)
    ng.add_edge(0, 2)
    assert _edges(fsv) == _edges(nsv)


def test_digraph_directional_views():
    fd = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    nd = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    assert dict(fd.in_degree()) == dict(nd.in_degree())
    assert dict(fd.out_degree()) == dict(nd.out_degree())
    assert {n: sorted(fd.successors(n)) for n in fd} == (
        {n: sorted(nd.successors(n)) for n in nd}
    )
    assert {n: sorted(fd.predecessors(n)) for n in fd} == (
        {n: sorted(nd.predecessors(n)) for n in nd}
    )
    assert _edges(fd.reverse()) == _edges(nd.reverse())
    assert sorted(fd.reverse().edges()) == sorted(nd.reverse().edges())
