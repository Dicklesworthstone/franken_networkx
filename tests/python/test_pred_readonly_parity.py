"""Parity coverage for DiGraph.pred / MultiDiGraph.pred read-only semantics.

Upstream NetworkX wraps predecessor mappings in AdjacencyView / MultiAdjacencyView,
which reject __setitem__. FrankenNetworkX must reject the same mutations so that
G.pred['b']['x'] = {} raises TypeError instead of silently succeeding.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_digraph_pred_neighbor_is_readonly():
    fg = fnx.DiGraph()
    fg.add_edges_from([("a", "b"), ("c", "b")])
    ng = nx.DiGraph()
    ng.add_edges_from([("a", "b"), ("c", "b")])

    # Upstream contract: AtlasView rejects item assignment.
    with pytest.raises(TypeError):
        ng.pred["b"]["x"] = {}

    # FrankenNetworkX must raise the same error.
    with pytest.raises(TypeError):
        fg.pred["b"]["x"] = {}

    # The graph must remain unchanged.
    assert not fg.has_edge("x", "b")
    assert dict(fg.pred["b"]) == dict(ng.pred["b"])


def test_multidigraph_pred_neighbor_is_readonly():
    fg = fnx.MultiDiGraph()
    fg.add_edge("a", "b")
    fg.add_edge("c", "b")
    ng = nx.MultiDiGraph()
    ng.add_edge("a", "b")
    ng.add_edge("c", "b")

    with pytest.raises(TypeError):
        ng.pred["b"]["x"] = {}

    with pytest.raises(TypeError):
        fg.pred["b"]["x"] = {}

    assert not fg.has_edge("x", "b")
    # Same predecessor structure on both sides.
    assert sorted(fg.pred["b"]) == sorted(ng.pred["b"])


def test_digraph_pred_top_level_is_readonly():
    fg = fnx.DiGraph()
    fg.add_edges_from([("a", "b"), ("c", "b")])
    ng = nx.DiGraph()
    ng.add_edges_from([("a", "b"), ("c", "b")])

    with pytest.raises(TypeError):
        ng.pred["z"] = {}

    with pytest.raises(TypeError):
        fg.pred["z"] = {}


def test_multidigraph_pred_top_level_is_readonly():
    fg = fnx.MultiDiGraph()
    fg.add_edge("a", "b")
    ng = nx.MultiDiGraph()
    ng.add_edge("a", "b")

    with pytest.raises(TypeError):
        ng.pred["z"] = {}

    with pytest.raises(TypeError):
        fg.pred["z"] = {}
