"""Regression: MultiDiGraph float weighted degree over the native store.

br-r37-c1-mdgwdegfs (cc): the Rust float weighted-degree fast path
(``weighted_directional_degree_float_node`` / ``weighted_total_degree_float_node``)
read every edge weight from the Python edge MIRROR (``edge_py_attrs``). That
mirror is EMPTY for graphs built with the bulk edge APIs
(``add_weighted_edges_from`` / ``add_edges_from`` commit weights straight into the
native CgseValue store and leave the mirror lazy), so the float path never engaged
on bulk-built weighted multigraphs (the common case) and they fell to the slow
per-edge ``PyList`` + ``builtins.sum`` path (~0.5-0.7x nx). The store-backed twins
read floats from the store with the SAME nx adjacency iteration order and the SAME
Neumaier compensation, so they must stay byte-exact with networkx.

These tests deliberately use the BULK builders (the prior selfloop parity test
used per-edge ``add_edge``, which materialises the mirror and so never exercised
the store path).
"""

import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(mod, edges, n=6):
    G = mod.MultiDiGraph()
    G.add_nodes_from(range(n))
    G.add_edges_from(edges)
    return G


def _float_edges(seed, n, m):
    r = random.Random(seed)
    return [
        (r.randrange(n), r.randrange(n), {"weight": r.random()}) for _ in range(m)
    ]


@pytest.mark.parametrize("view", ["degree", "in_degree", "out_degree"])
def test_batch_built_float_weighted_degree_byte_exact(view):
    # Random bulk-built float-weighted multigraphs: the store float path must be
    # byte-identical to networkx (value AND type) across many topologies,
    # including parallel edges, self-loops and isolated nodes.
    for seed in range(40):
        edges = _float_edges(seed, n=30, m=90)
        Gf = _build(fnx, edges, n=30)
        Gx = _build(nx, edges, n=30)
        df = dict(getattr(Gf, view)(weight="weight"))
        dx = dict(getattr(Gx, view)(weight="weight"))
        assert df == dx, (view, seed)
        for k in dx:
            assert type(df[k]) is type(dx[k]), (view, seed, k)
        # The fast path engages -> nodes with >=1 contributing edge are floats;
        # an edgeless direction keeps nx's int 0 (sum of an empty sequence).
        assert any(isinstance(v, float) for v in df.values())
        for k, v in df.items():
            assert isinstance(v, float) or v == 0


def test_store_float_matches_repr_of_builtin_sum():
    # Tightest exactness check: the Neumaier-compensated store sum must equal
    # CPython's builtins.sum over the same per-node weight sequence, bit-for-bit.
    edges = [
        (0, 1, {"weight": 0.1}),
        (0, 1, {"weight": 0.2}),
        (0, 2, {"weight": 0.3}),
        (1, 0, {"weight": 1e16}),
        (1, 0, {"weight": 1.0}),
        (1, 0, {"weight": -1e16}),  # catastrophic cancellation -> tests compensation
        (2, 0, {"weight": 0.7}),
    ]
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    for view in ("degree", "in_degree", "out_degree"):
        df = dict(getattr(Gf, view)(weight="weight"))
        dx = dict(getattr(Gx, view)(weight="weight"))
        assert df == dx
        for k in dx:
            assert math.copysign(1.0, df[k]) == math.copysign(1.0, dx[k]) or df[k] == dx[k]


def test_mixed_and_missing_weight_fall_back_byte_exact():
    # Non-float (int) and missing-weight edges must NOT use the float store path
    # (it bails -> exact fallback). networkx returns int default 1 and promotes
    # via builtins.sum; the result types/values must still match exactly.
    edges = [
        (0, 1, {"weight": 2}),       # int
        (1, 2, {"weight": 3.5}),     # float
        (2, 3, {}),                  # missing -> default 1 (int)
        (3, 4, {"weight": 4}),       # int
        (4, 4, {"weight": 1.5}),     # self-loop float
    ]
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    for view in ("degree", "in_degree", "out_degree"):
        df = dict(getattr(Gf, view)(weight="weight"))
        dx = dict(getattr(Gx, view)(weight="weight"))
        assert df == dx, view
        for k in dx:
            assert type(df[k]) is type(dx[k]), (view, k)


def test_mutation_after_batch_stays_exact():
    # After a per-edge mutation marks edges dirty, the mirror path takes over;
    # results must remain byte-exact (store-clean gate vs mirror).
    edges = [(0, 1, {"weight": 1.5}), (1, 2, {"weight": 2.5}), (2, 0, {"weight": 3.5})]
    Gf = _build(fnx, edges)
    Gx = _build(nx, edges)
    Gf[0][1][0]["weight"] = 9.5
    Gx[0][1][0]["weight"] = 9.5
    for view in ("degree", "in_degree", "out_degree"):
        assert dict(getattr(Gf, view)(weight="weight")) == dict(
            getattr(Gx, view)(weight="weight")
        ), view
