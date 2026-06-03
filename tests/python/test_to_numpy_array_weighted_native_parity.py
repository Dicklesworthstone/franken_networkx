"""Parity for the weighted native fast path of `to_numpy_array`.

`to_numpy_array` previously only used the native Rust COO builder for the
unweighted case (`weight is None`), falling back to a pure-Python
`G._adj.items()` loop (~11x slower than nx) whenever a string `weight` key was
requested. The native COO builder now also serves the weighted case: it syncs
Python-visible edge attrs into Rust storage and scatters the f64 weights into
the pre-allocated dense matrix. Because the matrix dtype is fixed by
`np.full(..., nonedge, dtype=...)`, no native int/float dtype inference is
needed (unlike `to_scipy_sparse_array`).

These tests pin fnx to nx across the parameter matrix that exercises the
weighted native path, including a post-creation mutation (staleness guard).
"""

import random

import numpy as np
import networkx as nx

import franken_networkx as fnx


def _build_pair(n, m, seed, *, directed=False, wmode="mixed", selfloops=True):
    rnd = random.Random(seed)
    edges = []
    seen = set()
    while len(edges) < m:
        a, b = rnd.randrange(n), rnd.randrange(n)
        if a == b and (not selfloops or rnd.random() < 0.6):
            continue
        if directed:
            if (a, b) in seen:
                continue
        elif (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        edges.append((a, b))
    Gx = (nx.DiGraph if directed else nx.Graph)()
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gx.add_nodes_from(range(n))
    Gf.add_nodes_from(range(n))
    Gx.add_edges_from(edges)
    Gf.add_edges_from(edges)
    for i, (u, v) in enumerate(edges):
        if wmode == "none":
            continue
        if wmode == "all" or (wmode == "mixed" and i % 3 == 0):
            w = float(i % 7) if i % 2 == 0 else (i % 5)
            Gx[u][v]["weight"] = w
            Gf[u][v]["weight"] = w
    return Gx, Gf


def _eq(Gx, Gf, **kw):
    mx = nx.to_numpy_array(Gx, **kw)
    mf = fnx.to_numpy_array(Gf, **kw)
    return mx.dtype == mf.dtype and np.array_equal(mx, mf)


def test_weighted_undirected_default():
    Gx, Gf = _build_pair(50, 160, 11)
    assert _eq(Gx, Gf)


def test_weighted_directed_default():
    Gx, Gf = _build_pair(50, 160, 12, directed=True)
    assert _eq(Gx, Gf)


def test_param_matrix():
    for directed in (False, True):
        for wmode in ("none", "all", "mixed"):
            for dtype in (None, float, int):
                for nonedge in (0.0, -1.0, 2.0):
                    Gx, Gf = _build_pair(40, 120, 7, directed=directed, wmode=wmode)
                    assert _eq(
                        Gx, Gf, dtype=dtype, nonedge=nonedge, weight="weight"
                    ), (directed, wmode, dtype, nonedge)


def test_missing_weight_key_uses_default_one():
    # weight key absent from every edge -> nx uses default 1.
    Gx, Gf = _build_pair(40, 120, 5, wmode="mixed")
    assert _eq(Gx, Gf, weight="absent_key")


def test_self_loops_weighted():
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for u, v, w in [(0, 0, 3.0), (0, 1, 2.0), (1, 1, 5.0), (1, 2, 1.5)]:
        Gx.add_edge(u, v, weight=w)
        Gf.add_edge(u, v, weight=w)
    assert _eq(Gx, Gf)


def test_post_creation_mutation_is_not_stale():
    # The native helper reads Rust storage; a direct G[u][v][k]=v mutation must
    # be synced before the read or the matrix would be stale.
    Gx, Gf = _build_pair(30, 80, 3, wmode="mixed")
    u = list(Gf[0])[0]
    Gx[0][u]["weight"] = 99.0
    Gf[0][u]["weight"] = 99.0
    assert _eq(Gx, Gf)


def test_nodelist_subset_and_reorder():
    Gx, Gf = _build_pair(30, 80, 9, wmode="mixed")
    nodelist = [5, 3, 10, 1, 20, 0]
    assert _eq(Gx, Gf, nodelist=nodelist)


def test_multigraph_still_correct():
    Gx = nx.MultiGraph()
    Gf = fnx.MultiGraph()
    for u, v, w in [(0, 1, 2.0), (0, 1, 3.0), (1, 2, 1.0)]:
        Gx.add_edge(u, v, weight=w)
        Gf.add_edge(u, v, weight=w)
    assert _eq(Gx, Gf)
