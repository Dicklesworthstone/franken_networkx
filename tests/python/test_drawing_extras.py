"""Tests for display and bipartite drawing helpers."""

import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import pytest
from franken_networkx.drawing import nx_pylab


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_drawing_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_display_falls_back_to_text_output():
    graph = fnx.path_graph(3)

    rendered = fnx.display(graph)

    assert isinstance(rendered, str)
    assert "0" in rendered


def test_draw_bipartite_signature_matches_legacy_networkx():
    legacy = _legacy_networkx()

    assert str(inspect.signature(fnx.draw_bipartite)) == str(
        inspect.signature(legacy.draw_bipartite)
    )


def test_draw_bipartite_uses_unparameterized_bipartite_layout(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge("top", "bottom")
    captured = {}

    def fake_layout(G):
        captured["layout_graph"] = G
        return {"top": (0.0, 0.0), "bottom": (1.0, 0.0)}

    def fake_draw(G, pos=None, **kwds):
        captured["graph"] = G
        captured["pos"] = pos
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "bipartite_layout", fake_layout)
    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(graph, node_size=9)

    assert result == "drawn"
    assert captured["layout_graph"] is graph
    assert captured["graph"] is graph
    assert captured["pos"] == {"top": (0.0, 0.0), "bottom": (1.0, 0.0)}
    assert captured["kwds"] == {"node_size": 9}


def test_draw_bipartite_forwards_top_nodes_as_a_drawing_keyword(monkeypatch):
    graph = fnx.path_graph(2)
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["graph"] = G
        captured["pos"] = pos
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "bipartite_layout", lambda G: {0: (0, 0), 1: (1, 0)})
    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(graph, top_nodes={0}, node_size=10)

    assert result == "drawn"
    assert captured["graph"] is graph
    assert captured["kwds"] == {"top_nodes": {0}, "node_size": 10}


def test_draw_bipartite_rejects_explicit_pos_like_legacy(monkeypatch):
    graph = fnx.path_graph(2)
    legacy = _legacy_networkx()

    with pytest.raises(TypeError) as legacy_error:
        legacy.draw_bipartite(legacy.path_graph(2), pos={0: (0, 0), 1: (1, 0)})

    monkeypatch.setattr(nx_pylab, "bipartite_layout", lambda G: {0: (0, 0), 1: (1, 0)})

    with pytest.raises(type(legacy_error.value)) as fnx_error:
        fnx.draw_bipartite(graph, pos={0: (0, 0), 1: (1, 0)})

    expected_suffix = "draw() got multiple values for keyword argument 'pos'"
    assert str(legacy_error.value).endswith(expected_suffix)
    assert str(fnx_error.value).endswith(expected_suffix)
