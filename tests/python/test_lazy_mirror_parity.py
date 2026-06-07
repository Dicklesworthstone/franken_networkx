"""br-r37-c1-89kxg: lazy attr-mirror dicts — construction no longer
pre-allocates empty per-node/per-edge PyDicts; render paths materialize on
first observation. These tests lock the observable contracts."""

import copy
import pickle
import random

import networkx as nx

import franken_networkx as fnx


def test_dict_identity_stable_across_observations():
    g = fnx.Graph()
    g.add_edges_from([(i, i + 1) for i in range(20)])
    assert g[0][1] is g[0][1]
    assert g[0][1] is g[1][0]
    assert g.nodes[3] is not None
    d = g[2][3]
    d["w"] = 9
    assert g[3][2]["w"] == 9  # live shared dict


def test_views_and_data_render_empty_attrs():
    gn, gf = nx.Graph(), fnx.Graph()
    for g in (gn, gf):
        g.add_edges_from([("a", "b"), ("b", "c", {"w": 1})])
        g.add_node("iso")
    assert [(u, v, d) for u, v, d in gf.edges(data=True)] == [
        (u, v, d) for u, v, d in gn.edges(data=True)
    ]
    assert dict(gf.nodes(data=True)) == dict(gn.nodes(data=True))
    assert {n: dict(gf[n]) for n in gf} == {n: dict(gn[n]) for n in gn}


def test_copy_deepcopy_pickle_roundtrip():
    g = fnx.Graph()
    g.add_edges_from([(i, (i * 3) % 10) for i in range(15)])
    g.add_edge(0, 99, w=5)
    for clone in (g.copy(), copy.copy(g), copy.deepcopy(g), pickle.loads(pickle.dumps(g))):
        assert sorted(map(repr, clone.edges(data=True))) == sorted(map(repr, g.edges(data=True)))
        assert list(clone) == list(g)


def test_post_construction_mutation_and_kernels():
    rnd = random.Random(3)
    gn, gf = nx.Graph(), fnx.Graph()
    edges = [(rnd.randrange(30), rnd.randrange(30), {"weight": rnd.random() + 0.1}) for _ in range(80)]
    gn.add_edges_from(edges)
    gf.add_edges_from(edges)
    u, v = edges[0][0], edges[0][1]
    gf[u][v]["weight"] = 2.5
    gn[u][v]["weight"] = 2.5
    src = next(iter(gn))
    assert dict(fnx.single_source_dijkstra_path_length(gf, src)) == dict(
        nx.single_source_dijkstra_path_length(gn, src)
    )


def test_random_differential():
    rnd = random.Random(20260605)
    for trial in range(10):
        gn, gf = nx.Graph(), fnx.Graph()
        for _ in range(60):
            u, v = rnd.randrange(15), rnd.randrange(15)
            if rnd.random() < 0.5:
                gn.add_edge(u, v); gf.add_edge(u, v)
            else:
                gn.add_edge(u, v, w=rnd.random()); gf.add_edge(u, v, w=rnd.random() if False else gn[u][v]["w"])
        assert sorted(map(repr, gf.edges(data=True))) == sorted(map(repr, gn.edges(data=True))), trial
