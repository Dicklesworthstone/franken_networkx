"""Parity for ``bridges`` iteration order.

Bead br-r37-c1-h83lo. fnx.bridges returned bridge edges in canonical
alphabetical order; nx returns them in DFS-discovery order from the
algorithm's traversal. Drop-in code that iterated bridges in the
algorithm's order — e.g. for visualization or sequential processing
— got different output.

Fix delegates to nx so iteration order matches nx exactly.
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
def test_bridges_dfs_order_matches_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.bridges(g))
    n = list(nx.bridges(gx))
    assert f == n


@needs_nx
def test_path_graph_bridges_match():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.bridges(g))
    n = list(nx.bridges(gx))
    assert f == n


@needs_nx
def test_cycle_graph_no_bridges():
    g = fnx.cycle_graph(5)
    gx = nx.cycle_graph(5)
    f = list(fnx.bridges(g))
    n = list(nx.bridges(gx))
    assert f == n == []


@needs_nx
def test_multigraph_parallel_edges_not_bridges():
    """Parallel edges aren't bridges — only the singleton (1,2) is."""
    mg = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    mgx = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    f = list(fnx.bridges(mg))
    n = list(nx.bridges(mgx))
    assert f == n


@needs_nx
def test_bridges_with_root_kwarg():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.bridges(g, root="a"))
    n = list(nx.bridges(gx, root="a"))
    assert f == n


@needs_nx
def test_disconnected_graph_bridges():
    """Disconnected graph: each component's bridges are reported."""
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = list(fnx.bridges(g))
    n = list(nx.bridges(gx))
    assert f == n


@needs_nx
def test_complete_graph_no_bridges():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = list(fnx.bridges(g))
    n = list(nx.bridges(gx))
    assert f == n == []
