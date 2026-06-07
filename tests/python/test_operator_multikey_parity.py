"""Phase B certification: graph operators (fixed identical inputs) and
multigraph edge-key semantics — intricate merge/auto-key logic not
fully covered elsewhere. Zero divergences at certification.

(Session note: the set_edge_attributes resolve_internal_edge_key
fast-path was A/B-tested and rejected as a wash — the bottleneck is
shared per-edge node canonicalization, not key resolution.)
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _E(g):
    return sorted((repr(u), repr(v), sorted(d.items())) for u, v, d in g.edges(data=True))


def _N(g):
    return sorted((repr(n), sorted(d.items())) for n, d in g.nodes(data=True))


def _mk2(mod):
    R = random.Random(13)
    e1 = [(u, v, u) for u, v in ((R.randrange(8), R.randrange(8)) for _ in range(15)) if u != v]
    e2 = [(u, v, v * 10) for u, v in ((R.randrange(4, 12), R.randrange(4, 12)) for _ in range(15)) if u != v]
    g1, g2 = mod.Graph(), mod.Graph()
    g1.graph["name"] = "A"
    g2.graph["name"] = "B"
    g2.graph["x"] = 1
    for u, v, w in e1:
        g1.add_edge(u, v, w=w)
    for u, v, w in e2:
        g2.add_edge(u, v, w=w)
    for n in sorted(g1)[:3]:
        g1.nodes[n]["c"] = "r"
    return g1, g2


@pytest.mark.parametrize("op", ["intersection", "compose"])
def test_operator_edges_nodes_graphattr_parity(op):
    assert _E(getattr(fnx, op)(*_mk2(fnx))) == _E(getattr(nx, op)(*_mk2(nx))), (op, "E")
    assert _N(getattr(fnx, op)(*_mk2(fnx))) == _N(getattr(nx, op)(*_mk2(nx))), (op, "N")
    assert sorted(getattr(fnx, op)(*_mk2(fnx)).graph.items()) == sorted(
        getattr(nx, op)(*_mk2(nx)).graph.items()
    ), (op, "graph")


def _mk_same_nodes(mod):
    """Two graphs on an identical node set (symmetric_difference needs
    equal node sets, else both impls raise NetworkXError)."""
    R = random.Random(21)
    g1, g2 = mod.Graph(), mod.Graph()
    for n in range(10):
        g1.add_node(n)
        g2.add_node(n)
    for _ in range(14):
        u, v = R.randrange(10), R.randrange(10)
        if u != v:
            g1.add_edge(u, v)
    for _ in range(14):
        u, v = R.randrange(10), R.randrange(10)
        if u != v:
            g2.add_edge(u, v)
    return g1, g2


@pytest.mark.parametrize("op", ["difference", "symmetric_difference"])
def test_equal_node_set_operator_parity(op):
    # difference / symmetric_difference require equal node sets.
    assert _E(getattr(fnx, op)(*_mk_same_nodes(fnx))) == _E(
        getattr(nx, op)(*_mk_same_nodes(nx))
    ), op

    # unequal node sets must raise in both
    def attempt(mod):
        try:
            getattr(mod, op)(*_mk2(mod))
            return "ok"
        except nx.NetworkXError:
            return "NetworkXError"

    assert attempt(fnx) == attempt(nx) == "NetworkXError", op


def test_union_disjoint_error_and_relabeled():
    def attempt(mod):
        try:
            mod.union(*_mk2(mod))
            return "ok"
        except nx.NetworkXError:
            return "NetworkXError"

    assert attempt(fnx) == attempt(nx) == "NetworkXError"

    def mkdj(mod):
        g1, g2 = _mk2(mod)
        g2 = mod.relabel_nodes(g2, {n: n + 100 for n in g2})
        return g1, g2

    assert _E(fnx.union(*mkdj(fnx))) == _E(nx.union(*mkdj(nx)))
    assert sorted(fnx.union(*mkdj(fnx)).graph.items()) == sorted(nx.union(*mkdj(nx)).graph.items())


def test_disjoint_union_edges():
    assert sorted((repr(u), repr(v)) for u, v in fnx.disjoint_union(*_mk2(fnx)).edges()) == sorted(
        (repr(u), repr(v)) for u, v in nx.disjoint_union(*_mk2(nx)).edges()
    )


def test_multigraph_key_semantics():
    def mkm(mod):
        g = mod.MultiGraph()
        g.add_edge(0, 1)
        g.add_edge(0, 1)
        g.add_edge(0, 1, key="x", w=5)
        k = g.add_edge(0, 1)
        return g, k

    gf, kf = mkm(fnx)
    gn, kn = mkm(nx)
    assert repr(kf) == repr(kn)
    assert sorted(repr(k) for k in gf[0][1]) == sorted(repr(k) for k in gn[0][1])
    assert gf.number_of_edges(0, 1) == gn.number_of_edges(0, 1)


def test_multigraph_auto_key_after_explicit_int():
    def mkm2(mod):
        g = mod.MultiGraph()
        g.add_edge(0, 1, key=5)
        k = g.add_edge(0, 1)
        return g, k

    gf, kf = mkm2(fnx)
    gn, kn = mkm2(nx)
    assert repr(kf) == repr(kn)
    assert sorted(repr(k) for k in gf[0][1]) == sorted(repr(k) for k in gn[0][1])
