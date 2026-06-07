"""Phase B certification (post substrate epoch d58s8): the integer-row
+ index-keyed-edges flips touched every storage path. These probes
exercise the flipped surface in ways the unit suite doesn't —
identical-op mutation sequences, round-trips after heavy mutation, and
derived-orientation surfaces (snapshot/pickle/adjacency_data) — and
must stay at zero divergence. Five exploratory sweeps found NO bugs;
this pins the highest-value shapes.
"""

import io
import pickle
import random

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("directed", [False, True])
def test_order_under_identical_mutation(directed):
    for trial in range(8):
        R = random.Random(100 + trial)
        gf = fnx.DiGraph() if directed else fnx.Graph()
        gn = nx.DiGraph() if directed else nx.Graph()
        for _ in range(R.randrange(20, 60)):
            r = R.random()
            if r < 0.5:
                u, v = R.randrange(15), R.randrange(15)
                gf.add_edge(u, v)
                gn.add_edge(u, v)
            elif r < 0.65:
                node = R.randrange(15, 25)
                gf.add_node(node)
                gn.add_node(node)
            elif r < 0.8 and len(gn) > 0:
                x = R.randrange(15)
                if x in gn:
                    gf.remove_node(x)
                    gn.remove_node(x)
            elif gn.number_of_edges() > 0:
                e = (R.randrange(15), R.randrange(15))
                if gn.has_edge(*e):
                    gf.remove_edge(*e)
                    gn.remove_edge(*e)
        assert [repr(n) for n in gf] == [repr(n) for n in gn], trial
        assert [(repr(u), repr(v)) for u, v in gf.edges()] == [
            (repr(u), repr(v)) for u, v in gn.edges()
        ], trial
        assert {repr(n): [repr(k) for k in gf[n]] for n in gf} == {
            repr(n): [repr(k) for k in gn[n]] for n in gn
        }, trial
        if directed:
            assert {repr(n): [repr(k) for k in gf.pred[n]] for n in gf} == {
                repr(n): [repr(k) for k in gn.pred[n]] for n in gn
            }, trial


@pytest.mark.parametrize("directed", [False, True])
def test_roundtrips_after_heavy_mutation(directed):
    for trial in range(8):
        R = random.Random(300 + trial)
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
        ref = sorted(
            (repr(u), repr(v), sorted(d.items())) for u, v, d in gn.edges(data=True)
        )
        pf = pickle.loads(pickle.dumps(gf))
        assert sorted(
            (repr(u), repr(v), sorted(d.items())) for u, v, d in pf.edges(data=True)
        ) == ref, ("pickle", trial)
        bF = io.BytesIO()
        fnx.write_graphml(gf, bF)
        bF.seek(0)
        rgf = fnx.read_graphml(bF)
        # graphml stringifies node ids; compare the int edge-set.
        assert sorted((int(u), int(v)) for u, v in rgf.edges()) == sorted(
            (u, v) for u, v in gn.edges()
        ), ("graphml", trial)
        assert sorted(
            (repr(u), repr(v))
            for u, v in fnx.adjacency_graph(
                fnx.adjacency_data(gf), directed=directed
            ).edges()
        ) == sorted(
            (repr(u), repr(v))
            for u, v in nx.adjacency_graph(
                nx.adjacency_data(gn), directed=directed
            ).edges()
        ), ("adjacency_data", trial)
