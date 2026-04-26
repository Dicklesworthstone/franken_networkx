"""Parity for ``johnson`` all-pairs shortest path inner-dict order.

Bead br-r37-c1-9l73c. The local
``dict(all_pairs_bellman_ford_path(G))`` short-circuit produced
inner-dict keys in Bellman-Ford-tree-discovery order, but nx's
johnson algorithm runs per-node Dijkstra after reweighting and
emits inner-dict keys in Dijkstra's discovery order (which differs
from BF's).

Drop-in code that iterated the inner dicts of johnson() in order
(e.g. for plotting paths or computing per-target metrics) silently
broke.

Repro: edges = [('a','b',1),('b','c',2),('c','d',1),('a','d',5),('b','d',3)]
  fnx['a'].keys() -> ['a','b','d','c']
  nx ['a'].keys() -> ['a','b','c','d']
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


def _make_weighted(lib, edges, directed=False):
    g = (lib.DiGraph if directed else lib.Graph)()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_undirected_repro_inner_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys()), (
            f"inner[{k}]: fnx={list(f[k].keys())} nx={list(n[k].keys())}"
        )


@needs_nx
def test_int_node_inner_dict_keys_match_nx():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 3), (0, 3, 1)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_directed_inner_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("a", "c", 4), ("c", "d", 1)]
    dg = _make_weighted(fnx, edges, directed=True)
    dgx = _make_weighted(nx, edges, directed=True)
    f = fnx.johnson(dg)
    n = nx.johnson(dgx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_paths_themselves_match_nx():
    """Path values (the lists from u to v) must also match nx — not
    just the dict iteration order."""
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    assert fnx.johnson(g) == nx.johnson(gx)


@needs_nx
def test_negative_weights_supported():
    """Johnson's main differentiator from Dijkstra is negative
    edges. Verify it works and matches nx."""
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v, w in [("a", "b", 1), ("b", "c", -2), ("a", "c", 4), ("c", "d", 3)]:
        dg.add_edge(u, v, weight=w)
        dgx.add_edge(u, v, weight=w)
    f = fnx.johnson(dg)
    n = nx.johnson(dgx)
    assert f == n
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_default_weight_attr_matches_nx():
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_custom_weight_attr_matches_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, custom=w)
        gx.add_edge(u, v, custom=w)
    f = fnx.johnson(g, weight="custom")
    n = nx.johnson(gx, weight="custom")
    assert f == n


@needs_nx
def test_callable_weight_matches_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    weight_fn = lambda u, v, d: d.get("weight", 1) * 2
    f = fnx.johnson(g, weight=weight_fn)
    n = nx.johnson(gx, weight=weight_fn)
    assert f == n


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.johnson(g) == nx.johnson(gx) == {}
