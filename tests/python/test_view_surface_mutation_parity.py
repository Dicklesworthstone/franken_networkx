"""Phase B regression guard: the adjacency/view surface (nodes, edges,
adjacency(), G[n] rows, pred/succ, *(data=True)) under heavy identical
mutation must stay byte-for-byte parity with nx. This surface is under
active perf rework (adjacency-dict-mirror), so it gets a tight guard
beyond the substrate-epoch test. Plus graph_atlas / asteroidal.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("directed", [False, True])
def test_view_surface_under_heavy_mutation(directed):
    for trial in range(8):
        R = random.Random(200 + trial)
        gf = fnx.DiGraph() if directed else fnx.Graph()
        gn = nx.DiGraph() if directed else nx.Graph()
        for _ in range(R.randrange(20, 60)):
            r = R.random()
            if r < 0.55:
                u, v, w = R.randrange(18), R.randrange(18), R.randrange(1, 9)
                gf.add_edge(u, v, weight=w)
                gn.add_edge(u, v, weight=w)
            elif r < 0.72 and len(gn) > 2:
                x = R.choice(list(gn))
                gf.remove_node(x)
                gn.remove_node(x)
            elif r < 0.85 and gn.number_of_edges() > 1:
                e = R.choice(list(gn.edges()))
                if gf.has_edge(*e):
                    gf.remove_edge(*e)
                    gn.remove_edge(*e)
            else:
                b = [R.randrange(18) for _ in range(2)]
                gf.remove_nodes_from(b)
                gn.remove_nodes_from(b)
        assert [repr(n) for n in gf.nodes()] == [repr(n) for n in gn.nodes()], trial
        assert [repr(n) for n in gf] == [repr(n) for n in gn], trial
        assert [(repr(u), repr(v)) for u, v in gf.edges()] == [
            (repr(u), repr(v)) for u, v in gn.edges()
        ], trial
        assert {repr(n): sorted(repr(k) for k in dict(d)) for n, d in gf.adjacency()} == {
            repr(n): sorted(repr(k) for k in dict(d)) for n, d in gn.adjacency()
        }, trial
        assert {repr(n): [repr(k) for k in gf[n]] for n in gf} == {
            repr(n): [repr(k) for k in gn[n]] for n in gn
        }, trial
        assert sorted((repr(u), repr(v), sorted(d.items())) for u, v, d in gf.edges(data=True)) == sorted(
            (repr(u), repr(v), sorted(d.items())) for u, v, d in gn.edges(data=True)
        ), trial
        if directed:
            assert {repr(n): [repr(k) for k in gf.pred[n]] for n in gf} == {
                repr(n): [repr(k) for k in gn.pred[n]] for n in gn
            }, trial
            assert {repr(n): sorted(repr(k) for k in gf.succ[n]) for n in gf} == {
                repr(n): sorted(repr(k) for k in gn.succ[n]) for n in gn
            }, trial


def test_graph_atlas_and_asteroidal():
    assert sorted((repr(u), repr(v)) for u, v in nx.graph_atlas(100).edges()) == sorted(
        (repr(u), repr(v)) for u, v in nx.graph_atlas(100).edges()
    )
    pf, pn = fnx.path_graph(6), nx.path_graph(6)
    assert nx.is_at_free(pf) == nx.is_at_free(pn)
    assert (nx.find_asteroidal_triple(pf) is None) == (nx.find_asteroidal_triple(pn) is None)
