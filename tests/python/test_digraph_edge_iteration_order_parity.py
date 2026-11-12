"""Parity coverage for DiGraph edges() iteration order.

Bead franken_networkx-95zt: after adding edges in a given order, the
observable edges() iteration must match NetworkX. Previously fnx
diverged on insertion order a->b, b->a, b->c.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_digraph_edges_match_insertion_order_matches_networkx():
    edges = [("a", "b"), ("b", "a"), ("b", "c")]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for e in edges:
        fg.add_edge(*e)
        ng.add_edge(*e)
    assert list(fg.edges()) == list(ng.edges())


def test_digraph_edges_path_plus_backedge_matches_networkx():
    edges = [("x", "y"), ("y", "x"), ("y", "z"), ("z", "x")]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for e in edges:
        fg.add_edge(*e)
        ng.add_edge(*e)
    assert list(fg.edges()) == list(ng.edges())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_directed_edges_bead_fixture_order_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b")
    fg.add_edge("b", "a")
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b")
    ng.add_edge("b", "a")
    ng.add_edge("b", "c")
    # Compare (u, v) projections (multi may also emit key — strip).
    f_edges = [(u, v) for u, v, *_ in fg.edges(keys=True)] if fg.is_multigraph() else list(fg.edges())
    n_edges = [(u, v) for u, v, *_ in ng.edges(keys=True)] if ng.is_multigraph() else list(ng.edges())
    assert f_edges == n_edges
