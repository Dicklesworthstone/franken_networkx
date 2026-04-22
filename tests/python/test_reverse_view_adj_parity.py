"""Parity coverage for reverse_view adjacency mapping and item access.

Bead franken_networkx-b158: reverse_view must expose NetworkX's core
mapping interface — view.adj / view.adjacency() yield reversed-edge
adjacency with edge attributes, and view[node] returns the reversed
neighbor mapping directly.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _deep_adjacency(view):
    return [
        (node, {nbr: dict(attrs) for nbr, attrs in inner.items()})
        for node, inner in view.adjacency()
    ]


def test_reverse_view_getitem_returns_reversed_adjacency_mapping():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    # view[node] must return the reversed-neighbors mapping with edge attrs.
    assert dict(frv[2]) == dict(nrv[2])
    assert dict(frv[1]) == dict(nrv[1])
    assert dict(frv[3]) == dict(nrv[3])


def test_reverse_view_adjacency_yields_reversed_edge_attrs():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert _deep_adjacency(frv) == _deep_adjacency(nrv)


def test_reverse_view_adj_indexing_matches_networkx():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    # Going through .adj explicitly must produce the same dict.
    assert dict(frv.adj[2]) == dict(nrv.adj[2])
    assert dict(frv.adj[1]) == dict(nrv.adj[1])


def test_reverse_view_missing_node_raises():
    """view[missing_node] must raise, not return {}."""
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2)])
    frv = fnx.reverse_view(fg)
    with pytest.raises((KeyError, fnx.NodeNotFound, nx.NodeNotFound)):
        _ = frv[99]


def test_reverse_view_exposes_nbunch_iter():
    """Bead franken_networkx-9c3f: reverse_view exposes nbunch_iter
    matching upstream for subset+unknown, None, and single-node inputs.
    """
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3)])
    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert hasattr(frv, "nbunch_iter")
    assert list(frv.nbunch_iter([1, 99])) == list(nrv.nbunch_iter([1, 99]))
    assert sorted(frv.nbunch_iter(None)) == sorted(nrv.nbunch_iter(None))
    assert list(frv.nbunch_iter(2)) == list(nrv.nbunch_iter(2))
