"""Parity + clean-state guard for the multigraph auto-key add_edge path.

br-inedges-autokey (bt). The auto-key ``add_edge`` wrapper (key=None on a
Multi*Graph) computed the next ``new_edge_key`` by calling ``get_edge_data(u, v)``
purely to inspect the existing keydict. But ``get_edge_data`` hands out LIVE
mutable mirror attr dicts, so it marked the WHOLE graph dirty. Since that ran on
every parallel-edge add, a per-edge-built multigraph ended up permanently dirty,
forcing the ``!edges_dirty``-gated store fast paths (weighted in/out/degree, size)
off -- e.g. MultiDiGraph ``in/out/degree(weight)`` was ~0.46-0.55x vs nx.

The fix routes the new_edge_key search through ``_native_edge_key_set`` (key
objects only -- no attr materialization, no dirty mark), so the graph stays
clean. This test locks in (a) byte-identical auto-key assignment vs nx through
parallel adds, explicit/auto mixes, gaps from removals, and custom string keys,
and (b) that weighted aggregates stay byte-correct after parallel per-edge adds.
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


def _edges_signature(g):
    return sorted(
        (str(u), str(v), str(k), tuple(sorted(d.items())))
        for u, v, k, d in g.edges(keys=True, data=True)
    )


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_autokey_parallel_adds_match_nx(cls_name):
    nxg = getattr(nx, cls_name)()
    fxg = getattr(fnx, cls_name)()
    for g in (nxg, fxg):
        g.add_edge(0, 1, weight=5)
        g.add_edge(0, 1, weight=6)
        g.add_edge(0, 1, weight=7)
        g.add_edge(1, 2)
    assert _edges_signature(nxg) == _edges_signature(fxg)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_autokey_explicit_then_auto_gap_aware(cls_name):
    nxg = getattr(nx, cls_name)()
    fxg = getattr(fnx, cls_name)()
    for g in (nxg, fxg):
        g.add_edge(0, 1, key=2, weight=1)  # explicit key=2
        g.add_edge(0, 1)  # nx new_edge_key: len({2})=1 -> 1
        g.add_edge(0, 1)  # len({1,2})=2 -> 2 in set -> 3
        g.add_edge(0, 1)  # len({1,2,3})=3 -> 3 in set -> 4
    assert _edges_signature(nxg) == _edges_signature(fxg)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_autokey_after_removal_gap(cls_name):
    nxg = getattr(nx, cls_name)()
    fxg = getattr(fnx, cls_name)()
    for g in (nxg, fxg):
        g.add_edge(0, 1)
        g.add_edge(0, 1)
        g.add_edge(0, 1)  # keys 0,1,2
        g.remove_edge(0, 1, key=1)  # keys {0,2}
        g.add_edge(0, 1, weight=9)  # nx: len({0,2})=2 -> 2 in set -> 3
    assert _edges_signature(nxg) == _edges_signature(fxg)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_autokey_custom_string_keys_mixed(cls_name):
    nxg = getattr(nx, cls_name)()
    fxg = getattr(fnx, cls_name)()
    for g in (nxg, fxg):
        g.add_edge(0, 1, key="a")
        g.add_edge(0, 1)  # len({'a'})=1 -> 1 not in -> 1
        g.add_edge(0, 1, key="b")
        g.add_edge(0, 1)  # len({'a',1,'b'})=3 -> 3 not in -> 3
    assert _edges_signature(nxg) == _edges_signature(fxg)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_autokey_random_sequence_matches_nx(cls_name, seed):
    nxg = getattr(nx, cls_name)()
    fxg = getattr(fnx, cls_name)()
    for g in (nxg, fxg):
        r = random.Random(seed)
        for _ in range(50):
            u = r.randrange(4)
            v = r.randrange(4)
            roll = r.random()
            if roll < 0.6:
                if r.random() < 0.3:
                    g.add_edge(u, v, key=r.randrange(5), weight=r.randrange(9))
                else:
                    g.add_edge(u, v, weight=r.randrange(9))
            elif roll < 0.8 and g.has_edge(u, v):
                keys = list(g.get_edge_data(u, v).keys())
                g.remove_edge(u, v, key=r.choice(keys))
    assert _edges_signature(nxg) == _edges_signature(fxg)


def test_weighted_degree_correct_after_parallel_peredge_build():
    """The store fast path (engaged once the graph stays clean) must agree with
    nx's per-edge weighted-degree sum on a parallel-edge per-edge-built graph."""
    nxg = nx.MultiDiGraph()
    fxg = fnx.MultiDiGraph()
    for g in (nxg, fxg):
        g.add_nodes_from(range(60))
        for u in range(60):
            for step in range(1, 5):
                v = (u * 41 + step * 17) % 60
                if v == u:
                    v = (v + step + 3) % 60
                for parallel in range(3):  # parallel -> auto-key path
                    attrs = {}
                    if (u + v + step + parallel) % 7 != 0:
                        attrs["weight"] = (u * 7 + v * 13 + parallel) % 29 - 8
                    g.add_edge(u, v, **attrs)
    assert dict(nxg.in_degree(weight="weight")) == dict(fxg.in_degree(weight="weight"))
    assert dict(nxg.out_degree(weight="weight")) == dict(fxg.out_degree(weight="weight"))
    assert dict(nxg.degree(weight="weight")) == dict(fxg.degree(weight="weight"))
    assert nxg.size(weight="weight") == fxg.size(weight="weight")


def test_native_edge_key_set_no_dirty_side_effect():
    """_native_edge_key_set returns the public key set without materializing
    attr mirrors -- exercised here for both graph classes."""
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        g = cls()
        g.add_edge(0, 1, key="x", weight=1)
        g.add_edge(0, 1, weight=2)
        assert g._native_edge_key_set(0, 1) == {"x", 1}
        assert g._native_edge_key_set(2, 3) == set()  # no such edge
