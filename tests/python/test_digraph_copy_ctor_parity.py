"""br-r37-c1-dgctor: DiGraph(Graph) native copy-constructor parity vs nx.

The exact-type DiGraph(Graph) constructor routes through
``digraph_absorb_graph_bidirected`` (one-pass native bidirected shallow
copy, adjacency-row edge order). These tests pin: succ/pred ROW order
(the old Python expand loop emitted u->v,v->u adjacent, diverging from
nx's from_dict_of_dicts adjacency walk), copy depth, attr kwarg, and
non-fast-path combos.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g.succ[n]) for n in g}),
        repr({n: list(g.pred[n]) for n in g}),
        repr(dict(g.graph)),
    )


def _pair(edges, nodes=()):
    gn, gf = nx.Graph(), fnx.Graph()
    for g in (gn, gf):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    return gn, gf


def test_succ_pred_row_order_matches_nx_with_selfloops():
    # the shrunk regression: self-loop after a normal edge — nx pred row
    # is [self, other]; the old expand loop produced [other, self].
    gn, gf = _pair([("s24", "s1", {"w": 1.0}), ("s24", "s24", {"w": 2.0})])
    dn, df = nx.DiGraph(gn), fnx.DiGraph(gf)
    assert _canon(dn) == _canon(df)
    assert list(df.pred["s24"]) == ["s24", "s1"]


def test_random_corpus_full_contract():
    rnd = random.Random(20260605)
    for trial in range(20):
        n = rnd.choice([0, 1, 2, 30, 120])
        labels = [f"s{rnd.randrange(50)}" for _ in range(n)]
        edges = []
        for _ in range(n * 2):
            u, v = (rnd.choice(labels), rnd.choice(labels)) if labels else ("a", "b")
            edges.append((u, v, {"w": rnd.random()}) if rnd.random() < 0.6 else (u, v))
        gn, gf = _pair(edges, nodes=labels + [f"iso{trial}"])
        assert _canon(nx.DiGraph(gn)) == _canon(fnx.DiGraph(gf)), trial


def test_int_keys_lazy_display():
    gn, gf = _pair([(i, i + 1) for i in range(30)])
    assert _canon(nx.DiGraph(gn)) == _canon(fnx.DiGraph(gf))


def test_copy_depth_shallow_and_isolated():
    gn, gf = _pair([("a", "b", {"w": [1]})])
    gf.graph["meta"] = [9]
    df = fnx.DiGraph(gf)
    assert df["a"]["b"] is not gf["a"]["b"]
    assert df["a"]["b"]["w"] is gf["a"]["b"]["w"]  # values shared (nx contract)
    assert df["a"]["b"] is not df["b"]["a"]  # directions get separate dicts
    assert df.graph is not gf.graph and df.graph["meta"] is gf.graph["meta"]
    df.add_edge("zz", "q")
    df["a"]["b"]["new"] = 1
    assert "zz" not in gf and "new" not in gf["a"]["b"]


def test_attr_kwarg_overrides_graph_dict():
    gn, gf = _pair([("a", "b")])
    gn.graph["name"] = "src"
    gf.graph["name"] = "src"
    dn = nx.DiGraph(gn, name="X", k=2)
    df = fnx.DiGraph(gf, name="X", k=2)
    assert dict(dn.graph) == dict(df.graph) == {"name": "X", "k": 2}


def test_non_fast_path_sources_still_match():
    gm_n, gm_f = nx.MultiGraph(), fnx.MultiGraph()
    for g in (gm_n, gm_f):
        g.add_edges_from([("a", "b", {"w": 1}), ("a", "b", {"w": 2})])
    assert sorted(nx.DiGraph(gm_n).edges(data=True)) == sorted(
        fnx.DiGraph(gm_f).edges(data=True)
    )
    gd_n, gd_f = nx.DiGraph([("a", "b")]), fnx.DiGraph([("a", "b")])
    assert _canon(nx.DiGraph(gd_n)) == _canon(fnx.DiGraph(gd_f))


def test_kernels_exact_after_ctor():
    rnd = random.Random(3)
    gn, gf = _pair(
        [(f"n{i}", f"n{(i * 3) % 20}", {"weight": (i % 7) + 0.5}) for i in range(60)]
    )
    dn, df = nx.DiGraph(gn), fnx.DiGraph(gf)
    src = next(iter(dn))
    assert dict(nx.single_source_dijkstra_path_length(dn, src)) == dict(
        fnx.single_source_dijkstra_path_length(df, src)
    )
    dn.remove_node(src)
    df.remove_node(src)
    assert _canon(dn) == _canon(df)
