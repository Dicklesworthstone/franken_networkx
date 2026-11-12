"""Correctness guard for the MultiDiGraph in_edges(data=<attr>) result cache.

br-inedges-attrcache (bt). in_edges(keys, data=<attr>) was 0.19x vs nx (per-edge
PyObject tuple materialization). A single-slot scalar-snapshot cache (keyed on
nodes_seq/edges_seq/keys/attr/default, served only while !edges_dirty, DROPPED on
mark_edges_dirty/mark_edge_dirty) makes repeat reads ~4x faster than nx.

The cache holds FROZEN scalar values, so the danger is staleness: an edge-attr edit
does not bump edges_seq. These tests assert the cache stays byte-identical to an
uncached read of the SAME graph after every kind of mutation, and matches nx.
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


def _cached(g, attr, keys, default):
    return list(g.in_edges(keys=keys, data=attr, default=default))


def _bypass(g, attr, keys, default):
    # Force the graph dirty WITHOUT changing any value (read a keydict), which drops
    # the snapshot cache, so the next read recomputes from the store/mirror in the
    # SAME iteration order. Equal to the cached read iff the cache is non-stale.
    for u, v in g.edges():
        g.get_edge_data(u, v)
        break
    return list(g.in_edges(keys=keys, data=attr, default=default))


_SHAPES = [("weight", True, 0), ("weight", False, 0), ("color", True, -1), ("missing", True, 9)]


def test_in_edges_data_attr_parity_and_repeat_hits():
    gn = _build(nx)
    gf = _build(fnx)
    for _ in range(3):  # repeat -> cache hits
        for attr, keys, default in _SHAPES:
            assert _cached(gf, attr, keys, default) == list(
                gn.in_edges(keys=keys, data=attr, default=default)
            )


def test_cache_drops_on_attr_mutation():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "weight", True, 0)  # prime
    for g in (gn, gf):
        u, v = 0, (0 * 7 + 5) % 40
        k = sorted(g.get_edge_data(u, v))[0]
        g[u][v][k]["weight"] = 999
    assert _cached(gf, "weight", True, 0) == list(gn.in_edges(keys=True, data="weight", default=0))


def test_cache_drops_on_set_edge_attributes():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "weight", False, 0)
    targets = list(gn.edges(keys=True))[:5]
    for g, m in ((gn, nx), (gf, fnx)):
        m.set_edge_attributes(g, {e: 500 for e in targets}, name="weight")
    assert _cached(gf, "weight", False, 0) == list(gn.in_edges(data="weight", default=0))


def test_cache_keys_on_structural_change():
    gn = _build(nx)
    gf = _build(fnx)
    _cached(gf, "weight", True, 0)
    for g in (gn, gf):
        g.add_edge(3, 7, weight=77)
    assert _cached(gf, "weight", True, 0) == list(gn.in_edges(keys=True, data="weight", default=0))
    for g in (gn, gf):
        u, v = 1, (1 * 7 + 5) % 40
        g.remove_edge(u, v, key=sorted(g.get_edge_data(u, v))[0])
    assert _cached(gf, "weight", True, 0) == list(gn.in_edges(keys=True, data="weight", default=0))


def test_cache_keys_on_attr_default_and_keys_flag():
    gf = _build(fnx)
    gn = _build(nx)
    _cached(gf, "weight", True, 0)  # prime weight/keys=True/default=0
    # different attr must not serve the weight snapshot
    assert _cached(gf, "color", True, -1) == list(gn.in_edges(keys=True, data="color", default=-1))
    # different default
    assert _cached(gf, "missing", True, -7) == list(
        gn.in_edges(keys=True, data="missing", default=-7)
    )
    # different keys flag
    assert _cached(gf, "weight", False, 0) == list(gn.in_edges(keys=False, data="weight", default=0))


def test_same_object_oracle_never_stale():
    """The cache must always equal an uncached read of the same graph."""
    r = random.Random(5)
    g = _build(fnx, 25, seed=5)
    fails = 0
    for step in range(60):
        op = r.random()
        _cached(g, "weight", True, 0)  # prime between ops
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
        for attr, keys, default in _SHAPES:
            if _cached(g, attr, keys, default) != _bypass(g, attr, keys, default):
                fails += 1
    assert fails == 0
