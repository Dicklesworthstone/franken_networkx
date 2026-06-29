"""Correctness guard for the MultiDiGraph edges()/out_edges() data=<attr> cache.

br-inedges-attrcache (bt). Whole-graph edges(data=<attr>) / out_edges(data=<attr>)
on a MultiDiGraph rebuilt the scalar (u, v[, key], value) tuples every call
(~0.32-0.68x vs nx). An out-major scalar-snapshot cache (edges_data_attr_cache,
keyed nodes_seq/edges_seq/keys/attr/default, served only while !edges_dirty,
DROPPED on mark_edges_dirty/mark_edge_dirty) makes repeats ~4.5-6x faster than nx.

Same staleness hazard as the in_edges cache (attr edits do not bump edges_seq), so
these tests assert the cached read always equals an uncached read of the SAME graph
after every mutation kind, matches nx, and that edges() == out_edges() (directed).
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

pytestmark = pytest.mark.skipif(nx is None, reason="networkx not installed")

_SHAPES = [("weight", True, 0), ("weight", False, 0), ("color", True, -1), ("missing", True, 9)]


def _build(mod, n=40, seed=1):
    r = random.Random(seed)
    g = mod.MultiDiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for s in range(1, 4):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(r.randint(1, 3)):
                g.add_edge(u, v, weight=(u + v + p) % 9, color=(u * v) % 5)
    return g


def _cached(g, view, attr, keys, default):
    return list(getattr(g, view)(keys=keys, data=attr, default=default))


def _bypass(g, view, attr, keys, default):
    for u, v in g.edges():
        g.get_edge_data(u, v)  # marks dirty (no value change) -> drops snapshot
        break
    return list(getattr(g, view)(keys=keys, data=attr, default=default))


@pytest.mark.parametrize("view", ["edges", "out_edges"])
def test_data_attr_parity_and_repeat_hits(view):
    gn = _build(nx)
    gf = _build(fnx)
    for _ in range(3):
        for attr, keys, default in _SHAPES:
            assert _cached(gf, view, attr, keys, default) == list(
                getattr(gn, view)(keys=keys, data=attr, default=default)
            )


def test_edges_equals_out_edges_under_cache():
    gf = _build(fnx)
    for attr, keys, default in _SHAPES:
        assert _cached(gf, "edges", attr, keys, default) == _cached(
            gf, "out_edges", attr, keys, default
        )


def test_cache_drops_on_attr_mutation():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "edges", "weight", True, 0)
    for g in (gn, gf):
        u, v = 0, (5) % 40
        k = sorted(g.get_edge_data(u, v))[0]
        g[u][v][k]["weight"] = 999
    assert _cached(gf, "edges", "weight", True, 0) == list(
        gn.edges(keys=True, data="weight", default=0)
    )


def test_cache_keys_on_structural_change():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "out_edges", "weight", True, 0)
    for g in (gn, gf):
        g.add_edge(3, 7, weight=77)
    assert _cached(gf, "out_edges", "weight", True, 0) == list(
        gn.out_edges(keys=True, data="weight", default=0)
    )
    for g in (gn, gf):
        u, v = 1, (12) % 40
        if g.has_edge(u, v):
            g.remove_edge(u, v, key=sorted(g.get_edge_data(u, v))[0])
    assert _cached(gf, "out_edges", "weight", True, 0) == list(
        gn.out_edges(keys=True, data="weight", default=0)
    )


def test_cache_keys_on_attr_default_keys_flag():
    gf = _build(fnx)
    gn = _build(nx)
    _cached(gf, "edges", "weight", True, 0)
    assert _cached(gf, "edges", "color", True, -1) == list(
        gn.edges(keys=True, data="color", default=-1)
    )
    assert _cached(gf, "edges", "missing", True, -7) == list(
        gn.edges(keys=True, data="missing", default=-7)
    )
    assert _cached(gf, "edges", "weight", False, 0) == list(
        gn.edges(keys=False, data="weight", default=0)
    )


def test_same_object_oracle_never_stale():
    r = random.Random(5)
    g = _build(fnx, 25, seed=5)
    fails = 0
    for step in range(60):
        op = r.random()
        _cached(g, "edges", "weight", True, 0)
        if op < 0.3:
            g.add_edge(r.randrange(25), r.randrange(25), weight=r.randrange(50))
        elif op < 0.55:
            u, v = r.randrange(25), r.randrange(25)
            if g.has_edge(u, v):
                g[u][v][sorted(g.get_edge_data(u, v))[0]]["weight"] = r.randrange(900)
        elif op < 0.7:
            u, v = r.randrange(25), r.randrange(25)
            if g.has_edge(u, v):
                g.remove_edge(u, v, key=sorted(g.get_edge_data(u, v))[0])
        elif op < 0.85:
            es = list(g.edges(keys=True))[:3]
            if es:
                fnx.set_edge_attributes(g, {e: r.randrange(700) for e in es}, name="weight")
        else:
            g.add_node(100 + step)
        for view in ("edges", "out_edges"):
            for attr, keys, default in _SHAPES:
                if _cached(g, view, attr, keys, default) != _bypass(g, view, attr, keys, default):
                    fails += 1
    assert fails == 0
