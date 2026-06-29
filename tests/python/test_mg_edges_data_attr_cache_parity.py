"""Correctness guard for the MultiGraph (undirected) edges() data=<attr> cache.

br-inedges-attrcache (bt). Whole-graph undirected MultiGraph edges(data=<attr>)
rebuilt the scalar (u, v[, key], value) tuples every call (~0.64-0.72x vs nx). A
scalar-snapshot cache (edges_data_attr_cache, keyed nodes_seq/edges_seq/keys/attr/
default, served only while !edges_dirty, DROPPED in mark_edges_dirty) makes repeats
~3.4x faster than nx. The undirected first-encounter dedup + self-loop-once ordering
happens in the build path, so the cache just stores the already-correct result.

Same staleness hazard as the directed caches (attr edits don't bump edges_seq), so
these assert the cached read equals an uncached read of the SAME graph after every
mutation, and matches nx (including self-loops).
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
    g = mod.MultiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for s in range(1, 4):
            v = (u * 7 + s * 5) % n
            if v == u:
                v = (v + s + 1) % n
            for p in range(r.randint(1, 3)):
                g.add_edge(u, v, weight=(u + v + p) % 9, color=(u * v) % 5)
        if u % 4 == 0:
            g.add_edge(u, u, weight=u % 7)  # self-loops (emitted once)
    return g


def _cached(g, attr, keys, default):
    return list(g.edges(keys=keys, data=attr, default=default))


def _bypass(g, attr, keys, default):
    for u, v in g.edges():
        g.get_edge_data(u, v)  # marks dirty without changing a value -> drops snapshot
        break
    return list(g.edges(keys=keys, data=attr, default=default))


def test_data_attr_parity_and_repeat_hits():
    gn = _build(nx)
    gf = _build(fnx)
    for _ in range(3):
        for attr, keys, default in _SHAPES:
            assert _cached(gf, attr, keys, default) == list(
                gn.edges(keys=keys, data=attr, default=default)
            )


def test_cache_drops_on_attr_mutation():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "weight", True, 0)
    for g in (gn, gf):
        u, v = 0, (5) % 40
        k = sorted(g.get_edge_data(u, v))[0]
        g[u][v][k]["weight"] = 999
    assert _cached(gf, "weight", True, 0) == list(gn.edges(keys=True, data="weight", default=0))


def test_cache_keys_on_structural_change():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "weight", True, 0)
    for g in (gn, gf):
        g.add_edge(3, 7, weight=77)
    assert _cached(gf, "weight", True, 0) == list(gn.edges(keys=True, data="weight", default=0))
    for g in (gn, gf):
        u, v = 1, (12) % 40
        if g.has_edge(u, v):
            g.remove_edge(u, v, key=sorted(g.get_edge_data(u, v))[0])
    assert _cached(gf, "weight", True, 0) == list(gn.edges(keys=True, data="weight", default=0))


def test_cache_keys_on_attr_default_keys_flag():
    gf = _build(fnx)
    gn = _build(nx)
    _cached(gf, "weight", True, 0)
    assert _cached(gf, "color", True, -1) == list(gn.edges(keys=True, data="color", default=-1))
    assert _cached(gf, "missing", True, -7) == list(
        gn.edges(keys=True, data="missing", default=-7)
    )
    assert _cached(gf, "weight", False, 0) == list(gn.edges(keys=False, data="weight", default=0))


def test_same_object_oracle_never_stale():
    r = random.Random(5)
    g = _build(fnx, 30, seed=5)
    fails = 0
    for step in range(60):
        op = r.random()
        _cached(g, "weight", True, 0)
        if op < 0.3:
            g.add_edge(r.randrange(30), r.randrange(30), weight=r.randrange(50))
        elif op < 0.55:
            u, v = r.randrange(30), r.randrange(30)
            if g.has_edge(u, v):
                g[u][v][sorted(g.get_edge_data(u, v))[0]]["weight"] = r.randrange(900)
        elif op < 0.7:
            u, v = r.randrange(30), r.randrange(30)
            if g.has_edge(u, v):
                g.remove_edge(u, v, key=sorted(g.get_edge_data(u, v))[0])
        elif op < 0.85:
            es = list(g.edges(keys=True))[:3]
            if es:
                fnx.set_edge_attributes(g, {e: r.randrange(700) for e in es}, name="weight")
        else:
            g.add_node(100 + step)
        for attr, keys, default in _SHAPES:
            if _cached(g, attr, keys, default) != _bypass(g, attr, keys, default):
                fails += 1
    assert fails == 0
