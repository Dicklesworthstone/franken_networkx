"""Tests for display and bipartite drawing helpers."""

import numpy as np
import pytest

import franken_networkx as fnx
from franken_networkx.drawing import nx_pylab


def test_display_falls_back_to_text_output():
    graph = fnx.path_graph(3)

    rendered = fnx.display(graph)

    assert isinstance(rendered, str)
    assert "0" in rendered


def test_draw_bipartite_uses_bipartite_layout_when_pos_missing(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge("top", "bottom")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["graph"] = G
        captured["pos"] = pos
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(graph, {"top"})

    assert result == "drawn"
    assert captured["graph"] is graph
    assert captured["pos"]["top"][0] < captured["pos"]["bottom"][0]


def test_draw_bipartite_transformed_graph_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")

    top_nodes = [("top", index) for index in range(2)]
    bottom_nodes = [("bottom", index) for index in range(2)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (top_nodes[0], bottom_nodes[0]),
            (top_nodes[1], bottom_nodes[0]),
            (top_nodes[1], bottom_nodes[1]),
        ]
    )
    expected_pos = fnx.bipartite_layout(graph, top_nodes)

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX bipartite layout helper was used")

    monkeypatch.setattr(nx, "bipartite_layout", fail)

    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["graph"] = G
        captured["pos"] = pos
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(graph, top_nodes, node_size=10)

    assert result == "drawn"
    assert captured["graph"] is graph
    assert captured["kwds"] == {"node_size": 10}
    assert set(captured["pos"]) == set(expected_pos) == set(graph.nodes())
    for node in graph.nodes():
        assert np.all(np.isfinite(captured["pos"][node]))
        assert np.allclose(captured["pos"][node], expected_pos[node])


def test_draw_bipartite_transformed_graph_respects_explicit_pos(monkeypatch):
    top_nodes = [("top-pos", index) for index in range(2)]
    bottom_nodes = [("bottom-pos", index) for index in range(2)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (top_nodes[0], bottom_nodes[0]),
            (top_nodes[1], bottom_nodes[0]),
            (top_nodes[1], bottom_nodes[1]),
        ]
    )
    explicit_pos = {
        top_nodes[0]: np.array([0.0, 0.0]),
        top_nodes[1]: np.array([0.0, 1.0]),
        bottom_nodes[0]: np.array([1.0, 0.0]),
        bottom_nodes[1]: np.array([1.0, 1.0]),
    }

    def fail(*args, **kwargs):
        raise AssertionError("draw_bipartite recomputed positions")

    monkeypatch.setattr(nx_pylab, "bipartite_layout", fail)

    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["graph"] = G
        captured["pos"] = pos
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(graph, top_nodes, pos=explicit_pos, node_size=10)

    assert result == "drawn"
    assert captured["graph"] is graph
    assert captured["pos"] is explicit_pos
    assert captured["kwds"] == {"node_size": 10}
