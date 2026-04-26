"""Parity for ``strongly_connected_components`` emission order.

Bead br-r37-c1-2vdtt. The previous wrapper applied ``reversed()`` to
the Rust binding's output to flip source-first into sink-first order.
That heuristic only matched nx for small symmetric inputs; on multi-
component DiGraphs where Rust's DFS start node differs from nx's, the
flipped order disagreed with nx's Tarjan-discovery contract.

Drop-in code that iterates SCCs in nx's order broke. Fix delegates
``strongly_connected_components`` to nx for parity.
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


def _make_dg(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_two_components_str_nodes_match_nx():
    """Repro from the bead description."""
    edges = [
        ("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"),
        ("c", "a"), ("e", "f"), ("f", "e"),
    ]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_disjoint_two_cycles_match_nx():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_three_node_cycle_with_attached_pair_match_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "d"), ("a", "d")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_int_nodes_match_nx():
    edges = [("0", "1"), ("1", "0"), ("2", "3"), ("3", "2"), ("0", "2")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_single_component_match_nx():
    edges = [(0, 1), (1, 2), (2, 0)]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_dag_each_node_own_component():
    edges = [(0, 1), (1, 2), (2, 3)]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_undirected_input_raises_not_implemented():
    """fnx mirrors nx's ``@not_implemented_for('undirected')`` error."""
    g = fnx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        list(fnx.strongly_connected_components(g))


@needs_nx
def test_empty_digraph():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n == []


@needs_nx
def test_isolated_nodes_each_their_own_component():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for n in ["a", "b", "c"]:
        g.add_node(n)
        gx.add_node(n)
    f = list(fnx.strongly_connected_components(g))
    n_ = list(nx.strongly_connected_components(gx))
    assert f == n_
