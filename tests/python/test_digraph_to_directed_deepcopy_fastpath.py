"""Regression: DiGraph.to_directed() deep-copy fast path.

br-r37-c1-dgtodir (cc): DiGraph was the only graph type whose to_directed() had
no native fast path (Graph / MultiGraph / MultiDiGraph all route to
_native_to_directed_deepcopy). It rebuilt via a per-arc Python add_edges_from loop
AND was wrapped by _materialize_attrs_before_convert, whose post-conversion probe
walks result.edges(data=True) and forces an O(E) mirror materialisation of the
copy. Net: ~0.58x nx.

An already-directed DiGraph's to_directed() is a full deep copy into the same
class, so the fast path routes to copy.deepcopy (native deep copy, preserves store
edge attrs + deep-copies graph attrs) AHEAD of the materialize wrapper. These
tests lock byte-exactness with networkx and the attr-survival the wrapper guarded.
"""

import copy
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _estrict(a, b):
    ea = {(u, v): d for u, v, d in a.edges(data=True)}
    eb = {(u, v): d for u, v, d in b.edges(data=True)}
    return (
        dict(a.nodes(data=True)) == dict(b.nodes(data=True))
        and a.graph == b.graph
        and ea == eb
        and list(a.nodes) == list(b.nodes)
        and list(a.edges) == list(b.edges)
        and a.is_directed() == b.is_directed()
        and a.is_multigraph() == b.is_multigraph()
    )


def test_to_directed_byte_exact_vs_networkx():
    for seed in range(60):
        r = random.Random(seed)
        nn = r.randint(0, 25)
        nodes = [(i, {"w": r.random(), "tag": [i]}) for i in range(nn)]
        edges = (
            [
                (r.randrange(nn), r.randrange(nn), {"weight": r.random(), "lst": [r.randint(0, 3)]})
                for _ in range(r.randint(0, 70))
            ]
            if nn
            else []
        )
        gf, gx = fnx.DiGraph(), nx.DiGraph()
        gf.graph["m"] = {"k": [seed]}
        gx.graph["m"] = {"k": [seed]}
        gf.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gx.add_nodes_from([(n, copy.deepcopy(d)) for n, d in nodes])
        gf.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        gx.add_edges_from([(u, v, copy.deepcopy(d)) for u, v, d in edges])
        assert _estrict(gf.to_directed(), gx.to_directed()), seed


def test_batch_built_edge_attrs_survive():
    # The bug _materialize_attrs_before_convert guards: batch-built graphs keep
    # edge attrs in the native store with a lazy mirror. The deepcopy fast path
    # must preserve them.
    gf, gx = fnx.DiGraph(), nx.DiGraph()
    gf.add_nodes_from(range(5))
    gx.add_nodes_from(range(5))
    gf.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    gx.add_weighted_edges_from([(0, 1, 2.5), (1, 2, 3.5)])
    rf, rx = gf.to_directed(), gx.to_directed()
    assert _estrict(rf, rx)
    assert {(u, v): d for u, v, d in rf.edges(data=True)} == {
        (0, 1): {"weight": 2.5},
        (1, 2): {"weight": 3.5},
    }


def test_result_independent_from_source():
    gf = fnx.DiGraph()
    gf.graph["m"] = ["orig"]
    gf.add_node(0, tag=["n0"])
    gf.add_edge(1, 2, lst=["e12"])
    r = gf.to_directed()
    gf.graph["m"].append("MUT")
    gf.nodes[0]["tag"].append("MUT")
    gf[1][2]["lst"].append("MUT")
    gf.add_edge(9, 8)
    assert "MUT" not in r.graph["m"]
    assert "MUT" not in r.nodes[0]["tag"]
    assert "MUT" not in r[1][2]["lst"]
    assert 9 not in r


def test_as_view_still_returns_view():
    gf = fnx.DiGraph([(0, 1, {"weight": 1.0})])
    v = gf.to_directed(as_view=True)
    assert v.is_directed()
    assert list(v.edges(data=True)) == [(0, 1, {"weight": 1.0})]


def test_subclass_falls_through():
    class Sub(fnx.DiGraph):
        pass

    s = Sub()
    s.add_edge(0, 1, weight=2.0)
    r = s.to_directed()
    # to_directed_class() default is DiGraph, so result is a plain DiGraph
    assert {(u, v): d for u, v, d in r.edges(data=True)} == {(0, 1): {"weight": 2.0}}


def test_empty_graph():
    assert _estrict(fnx.DiGraph().to_directed(), nx.DiGraph().to_directed())
