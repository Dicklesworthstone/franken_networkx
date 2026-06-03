"""Parity for the native edge materializer in `to_pandas_edgelist`.

br-tpenative: for exact simple `Graph` / `DiGraph` with the default
``nodelist=None``, `to_pandas_edgelist` now sources its edge list from the
native `_fnx.to_edgelist_simple` (which yields `(u, v, attr_dict)` tuples in
nx `G.edges()` order, reading the live Python attr dicts) instead of the
per-edge EdgeView. Multigraphs, an explicit nodelist, and subclasses / views
fall back to `G.edges(data=True)`.
"""

import random

import networkx as nx
import pandas as pd

import franken_networkx as fnx


def _build_pair(n, m, seed, *, directed=False, attrs=True):
    rnd = random.Random(seed)
    edges, seen = [], set()
    while len(edges) < m:
        a, b = rnd.randrange(n), rnd.randrange(n)
        if a == b:
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
    if attrs:
        for i, (u, v) in enumerate(edges):
            if i % 3 == 0:
                Gx[u][v]["weight"] = 1.0 + (i % 5)
                Gf[u][v]["weight"] = 1.0 + (i % 5)
            if i % 4 == 0:
                Gx[u][v]["label"] = f"x{i}"
                Gf[u][v]["label"] = f"x{i}"
    return Gx, Gf


def _eq(dx, dn):
    if sorted(dx.columns) != sorted(dn.columns):
        return False
    cols = sorted(dx.columns)
    return dx[cols].reset_index(drop=True).equals(dn[cols].reset_index(drop=True))


def test_simple_graph_parity():
    for directed in (False, True):
        for attrs in (True, False):
            Gx, Gf = _build_pair(60, 200, 11, directed=directed, attrs=attrs)
            assert _eq(nx.to_pandas_edgelist(Gx), fnx.to_pandas_edgelist(Gf))


def test_custom_source_target_columns():
    Gx, Gf = _build_pair(50, 150, 12)
    assert _eq(
        nx.to_pandas_edgelist(Gx, source="from", target="to"),
        fnx.to_pandas_edgelist(Gf, source="from", target="to"),
    )


def test_singleton_and_tiny():
    for n, m, d in [(1, 0, False), (2, 1, False), (3, 2, True)]:
        Gx, Gf = _build_pair(n, m, 100 + n, directed=d)
        assert _eq(nx.to_pandas_edgelist(Gx), fnx.to_pandas_edgelist(Gf))


def test_source_name_is_attr_raises_like_nx():
    Gx = nx.Graph([(0, 1)])
    Gf = fnx.Graph([(0, 1)])
    Gx[0][1]["source"] = 5
    Gf[0][1]["source"] = 5
    for G in (Gx, Gf):
        try:
            (nx if G is Gx else fnx).to_pandas_edgelist(G)
        except (nx.NetworkXError, fnx.NetworkXError):
            pass
        else:  # pragma: no cover
            raise AssertionError("expected NetworkXError when source name is an attr")


def test_explicit_nodelist_still_works():
    Gx, Gf = _build_pair(40, 120, 9)
    nl = [0, 1, 2, 3, 4, 5]
    assert _eq(
        nx.to_pandas_edgelist(Gx, nodelist=nl),
        fnx.to_pandas_edgelist(Gf, nodelist=nl),
    )


def test_multigraph_falls_back():
    MGx = nx.MultiGraph()
    MGf = fnx.MultiGraph()
    for u, v, d in [(0, 1, {}), (0, 1, {"w": 2}), (1, 2, {"w": 3})]:
        MGx.add_edge(u, v, **d)
        MGf.add_edge(u, v, **d)
    assert _eq(nx.to_pandas_edgelist(MGx), fnx.to_pandas_edgelist(MGf))
