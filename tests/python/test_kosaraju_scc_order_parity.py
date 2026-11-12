"""Parity for ``kosaraju_strongly_connected_components`` emission order.

Bead br-r37-c1-53cwv. The Rust helper emitted SCCs in reverse order
from nx's Kosaraju-completion contract. For example on a DAG, fnx
yielded ``[{a},{b},{c},{d},{e}]`` while nx yields
``[{e},{d},{c},{b},{a}]``. Drop-in code that iterated SCCs in nx's
order broke.

Mirrors the sister fix br-r37-c1-2vdtt for
``strongly_connected_components``.
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
def test_dag_scc_order_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )


@needs_nx
def test_two_scc_with_bridge_matches_nx():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c"), ("a", "c")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )


@needs_nx
def test_single_cycle_one_scc_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )


@needs_nx
def test_disjoint_two_cycles_matches_nx():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )


@needs_nx
def test_int_node_dag_matches_nx():
    edges = [(0, 1), (1, 2), (2, 3), (3, 4)]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )


@needs_nx
def test_with_source_kwarg_matches_nx():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c"), ("a", "c")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.kosaraju_strongly_connected_components(dg, source="a")) == list(
        nx.kosaraju_strongly_connected_components(dgx, source="a")
    )


@needs_nx
def test_undirected_input_raises_not_implemented():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        list(fnx.kosaraju_strongly_connected_components(g))


@needs_nx
def test_empty_digraph_matches_nx():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    ) == []


@needs_nx
def test_isolated_nodes_each_own_scc_matches_nx():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for n in ["a", "b", "c"]:
        dg.add_node(n)
        dgx.add_node(n)
    assert list(fnx.kosaraju_strongly_connected_components(dg)) == list(
        nx.kosaraju_strongly_connected_components(dgx)
    )
