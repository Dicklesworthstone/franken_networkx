"""Parity for ``dijkstra_predecessor_and_distance`` pred dict order.

Bead br-r37-c1-0l76i. nx populates the predecessor dict in
edge-relaxation insertion order during traversal: pred[v] appears
in the dict at the moment a tentative shortest path to v is found,
not when v's distance is finalized. The previous local
implementation built ``pred = {node: predecessors[node] for node
in distances}`` which forced pred-key order to match distances-
iteration order — drifting from nx.

Repro:
  edges = [(a,b,1),(b,c,2),(c,d,1),(a,d,5),(b,d,3)]
  fnx (pre-fix) pred -> {a:[], b:[a], c:[b], d:[b,c]}
  nx pred             -> {a:[], b:[a], d:[b,c], c:[b]}

(d lands before c because (b,d) edge relaxation happens before
c is popped from the heap.)
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_weighted(lib, edges):
    g = lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_repro_pred_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred
    assert list(f_dist.keys()) == list(n_dist.keys())
    assert f_dist == n_dist


@needs_nx
def test_pred_keys_match_with_cutoff():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "a", cutoff=3)
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "a", cutoff=3)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred
    assert f_dist == n_dist


@needs_nx
def test_pred_keys_match_int_nodes():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 5), (1, 3, 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_directed():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 5), (1, 3, 3)]
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v, w in edges:
        dg.add_edge(u, v, weight=w)
        dgx.add_edge(u, v, weight=w)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(dg, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(dgx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_path_graph():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_unweighted_graph():
    """With no weights, default weight=1; algorithm reduces to BFS."""
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_custom_weight_attr():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, custom=w)
        gx.add_edge(u, v, custom=w)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a", weight="custom")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a", weight="custom")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_isolated_source():
    """Source with no edges: pred should be {source: []}."""
    g = fnx.Graph()
    g.add_node("a")
    gx = nx.Graph()
    gx.add_node("a")
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_disconnected_graph():
    """Source in one component; other component nodes shouldn't be in pred."""
    edges = [("a", "b", 1), ("c", "d", 1)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_missing_source_raises():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        fnx.dijkstra_predecessor_and_distance(g, "missing")


@needs_nx
def test_pred_values_match_when_keys_already_match():
    """Triangle: a-b, b-c, a-c with various weights to force ties."""
    edges = [("a", "b", 1), ("b", "c", 1), ("a", "c", 2)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert f_pred == n_pred
    assert list(f_pred.keys()) == list(n_pred.keys())
