"""Regression: MultiGraph int weighted degree over the native store.

br-r37-c1-mgwdegfs (cc): the undirected MultiGraph ``degree(weight=...)`` had no
store-backed int accumulator (unlike MultiDiGraph) — every int-weighted degree
went through a per-node ``PyList`` + ``builtins.sum`` (~0.54x nx). Added
``weighted_degree_store_int_node`` / ``native_weighted_total_degree_store_int``
(zero per-edge PyO3, gated on ``!edges_dirty``). nx's MultiDegreeView counts a
self-loop's weight TWICE, so the accumulator adds self-loop weights a second time;
integer addition is associative so the store iteration order need not match nx's
adjacency order, only the multiset of contributing weights.

These tests deliberately use the BULK builder (``add_edges_from``), which leaves
the Python edge mirror lazy and so exercises the store path.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(mod, edges, n=6):
    G = mod.MultiGraph()
    G.add_nodes_from(range(n))
    G.add_edges_from(edges)
    return G


def test_batch_built_int_weighted_degree_byte_exact():
    for seed in range(50):
        r = random.Random(seed)
        edges = [
            (r.randrange(25), r.randrange(25), {"weight": r.randint(1, 50)})
            for _ in range(80)
        ]
        Gf = _build(fnx, edges, n=25)
        Gx = _build(nx, edges, n=25)
        df = dict(Gf.degree(weight="weight"))
        dx = dict(Gx.degree(weight="weight"))
        assert df == dx, seed
        for k in dx:
            assert type(df[k]) is type(dx[k]), (seed, k)  # int stays int


def test_selfloop_weight_counted_twice():
    # Two parallel self-loops on node 0 (w=2, w=3) -> 2*(2+3)=10, plus an edge to
    # node 1 (w=5) -> 15. Node 1 just sees the single w=5 edge.
    edges = [(0, 0, {"weight": 2}), (0, 0, {"weight": 3}), (0, 1, {"weight": 5})]
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    df = dict(Gf.degree(weight="weight"))
    assert df == dict(Gx.degree(weight="weight"))
    assert df[0] == 15
    assert df[1] == 5
    assert isinstance(df[0], int)


def test_missing_weight_defaults_to_one():
    # Missing weight contributes nx's default int 1 per edge.
    edges = [(0, 1, {}), (1, 2, {"weight": 4}), (2, 2, {})]  # self-loop, no weight
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    df = dict(Gf.degree(weight="weight"))
    assert df == dict(Gx.degree(weight="weight"))
    assert df[0] == 1          # one edge, default 1
    assert df[2] == 4 + 1 * 2  # edge to 1 (w=4) + self-loop default 1 twice


def test_isolated_node_is_int_zero():
    Gf = _build(fnx, [(0, 1, {"weight": 3})], n=4)
    Gx = _build(nx, [(0, 1, {"weight": 3})], n=4)
    df = dict(Gf.degree(weight="weight"))
    assert df == dict(Gx.degree(weight="weight"))
    assert df[3] == 0 and isinstance(df[3], int)


def test_float_and_mixed_still_byte_exact():
    # The int store path must bail (-> float / PyList fallback) on non-int weights.
    for edges in (
        [(0, 1, {"weight": 1.5}), (1, 2, {"weight": 2.5}), (2, 2, {"weight": 0.5})],
        [(0, 1, {"weight": 2}), (1, 2, {"weight": 3.5}), (2, 3, {})],  # mixed
    ):
        Gf = _build(fnx, edges)
        Gx = _build(nx, edges)
        df = dict(Gf.degree(weight="weight"))
        dx = dict(Gx.degree(weight="weight"))
        assert df == dx
        for k in dx:
            assert type(df[k]) is type(dx[k]), k


def test_mutation_after_batch_stays_exact():
    edges = [(0, 1, {"weight": 2}), (1, 2, {"weight": 3}), (2, 0, {"weight": 4})]
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    Gf[0][1][0]["weight"] = 9
    Gx[0][1][0]["weight"] = 9
    assert dict(Gf.degree(weight="weight")) == dict(Gx.degree(weight="weight"))
