"""Tests for display and bipartite drawing helpers."""

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
