"""Parity for the native edge materializer in `to_pandas_edgelist`.

br-tpenative: for exact simple `Graph` / `DiGraph` with the default
``nodelist=None``, `to_pandas_edgelist` now sources its edge list from the
native `_fnx.to_edgelist_simple` (which yields `(u, v, attr_dict)` tuples in
nx `G.edges()` order, reading the live Python attr dicts) instead of the
per-edge EdgeView. Multigraphs, an explicit nodelist, and subclasses / views
fall back to `G.edges(data=True)`.
"""

import copy
import random

import networkx as nx
import pandas as pd
import pytest

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


def _replace_logical_storage(graph, logical):
    graph._node = logical._node
    graph._adj = logical._adj
    if graph.is_directed():
        graph._pred = logical._pred


@pytest.mark.parametrize("class_name", ("Graph", "DiGraph"))
@pytest.mark.parametrize("shape", ("different_edges", "different_attributes", "empty"))
@pytest.mark.parametrize("module_route", (False, True), ids=("top_level", "convert_matrix"))
def test_assigned_storage_exports_the_logical_graph(class_name, shape, module_route):
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_edge("old", "edge", weight=9, stale="native")
        # Warm both the native materializer and the public edge view before
        # replacing their backing storage.
        module.to_pandas_edgelist(graph)
        list(graph.edges(data=True))
        logical = getattr(nx, class_name)()
        if shape == "different_edges":
            logical.add_edge("new", "row", weight=3, payload=[1, 2])
            logical.add_edge("row", "tail", label="second")
        elif shape == "different_attributes":
            logical.add_edge("old", "edge", weight=3, payload=[1, 2])
        _replace_logical_storage(graph, logical)
        graphs.append(graph)

    def export(module, graph):
        owner = module.convert_matrix if module_route else module
        return owner.to_pandas_edgelist(graph, source="from", target="to")

    expected = export(nx, graphs[0])
    actual = export(fnx, graphs[1])
    pd.testing.assert_frame_equal(actual, expected)
    assert "stale" not in actual.columns
    if shape != "empty":
        # A held logical row remains authoritative on the next export too;
        # do not cache a reconstructed native snapshot of the replacement.
        for graph in graphs:
            first = next(iter(graph.edges(data=True)))[2]
            first["weight"] = 17
        pd.testing.assert_frame_equal(export(fnx, graphs[1]), export(nx, graphs[0]))


@pytest.mark.parametrize("class_name", ("Graph", "DiGraph"))
def test_deepcopied_python_attributes_survive_dataframe_export(class_name):
    snapshots = []
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_edge("source", "target", weight=3, payload={"tags": ["saved"]})
        graph.graph["self"] = graph
        clone = copy.deepcopy(graph)
        frame = module.to_pandas_edgelist(clone)
        assert len(frame) == 1
        assert frame.iloc[0]["payload"] is clone["source"]["target"]["payload"]
        assert frame.iloc[0]["payload"] is not graph["source"]["target"]["payload"]
        snapshots.append(frame)
    pd.testing.assert_frame_equal(snapshots[0], snapshots[1])


@pytest.mark.parametrize("class_name", ("Graph", "DiGraph"))
def test_ordinary_graph_retains_native_export(class_name, monkeypatch):
    graph = getattr(fnx, class_name)()
    graph.add_edge("source", "target", weight=3)
    native = fnx._fnx.to_edgelist_simple
    calls = []

    def recording_native(candidate):
        calls.append(candidate)
        return native(candidate)

    monkeypatch.setattr(fnx._fnx, "to_edgelist_simple", recording_native)
    actual = fnx.to_pandas_edgelist(graph)
    assert calls == [graph]
    assert actual.to_dict("records") == [
        {"source": "source", "target": "target", "weight": 3}
    ]
