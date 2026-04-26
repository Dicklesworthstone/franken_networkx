"""Parity for ``single_source_shortest_path`` / ``_length`` BFS-order.

Bead br-r37-c1-tlrdu. fnx yielded dict keys in arbitrary Rust internal
order. nx returns the dict with keys in BFS-visit order from the
source (visiting neighbours in adjacency-dict order at each layer).
Drop-in code that iterates 'for tgt, path in single_source_shortest_path(G, src).items(): ...'
broke.
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


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("name", [
    "single_source_shortest_path",
    "single_source_shortest_path_length",
])
@pytest.mark.parametrize("source", ["c", "d", "a", "b", "e"])
def test_bfs_order_matches_networkx(name, source):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(getattr(fnx, name)(g, source).keys())
    n = list(getattr(nx, name)(gx, source).keys())
    assert f == n


@needs_nx
def test_path_graph_int_source_order():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.single_source_shortest_path(g, 2).keys())
    n = list(nx.single_source_shortest_path(gx, 2).keys())
    assert f == n == [2, 1, 3, 0, 4]


@needs_nx
def test_cutoff_truncates_in_bfs_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.single_source_shortest_path(g, "c", cutoff=1).keys())
    n = list(nx.single_source_shortest_path(gx, "c", cutoff=1).keys())
    assert f == n == ["c", "d", "b"]


@needs_nx
def test_disconnected_components_only_reachable_yielded():
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = list(fnx.single_source_shortest_path(g, "a").keys())
    n = list(nx.single_source_shortest_path(gx, "a").keys())
    assert f == n == ["a", "b"]


@needs_nx
def test_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.single_source_shortest_path(g, "c")
    n = nx.single_source_shortest_path(gx, "c")
    for target in n:
        assert f[target] == n[target]


@needs_nx
def test_missing_source_raises_node_not_found():
    """The fix must not regress the missing-source error path."""
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_shortest_path(g, 99)
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_shortest_path_length(g, 99)
