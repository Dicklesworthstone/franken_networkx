"""Parity for ``draw_bipartite`` with positional ``top_nodes``.

Bead br-r37-c1-bvf5w. fnx's draw_bipartite extends nx's
(G, **kwargs) signature with an optional ``top_nodes`` second
positional argument so callers can supply the bipartite partition
without routing through bipartite_sets. Three pre-existing tests
in test_drawing_extras.py call draw_bipartite(graph, top_nodes,
...) positionally and were failing pre-fix.
"""

from __future__ import annotations

import numpy as np
import pytest

import franken_networkx as fnx
from franken_networkx.drawing import nx_pylab


def test_top_nodes_passed_positionally(monkeypatch):
    """The second positional arg should be accepted as top_nodes."""
    g = fnx.Graph()
    g.add_edge("a", "x")
    g.add_edge("b", "x")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["pos"] = pos
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(g, ["a", "b"])
    assert result == "drawn"
    # 'a' and 'b' should be in the top column (smaller x coord
    # than 'x'); explicit top_nodes used the bipartite_layout.
    assert captured["pos"]["a"][0] < captured["pos"]["x"][0]
    assert captured["pos"]["b"][0] < captured["pos"]["x"][0]


def test_top_nodes_kwarg_still_supported(monkeypatch):
    """The kwarg-form (top_nodes=) should still work for backwards
    compatibility with the original nx-aligned API."""
    g = fnx.Graph()
    g.add_edge("a", "x")
    g.add_edge("b", "x")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["pos"] = pos
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(g, top_nodes={"a", "b"})
    assert result == "drawn"


def test_supplying_top_nodes_both_ways_is_python_error():
    """Python disallows the same parameter being both positional and
    kwarg. Verify that contract holds (this is a Python-level
    invariant, not a fnx-specific behaviour)."""
    g = fnx.Graph([("a", "x"), ("b", "x")])
    with pytest.raises(TypeError, match="multiple values"):
        fnx.draw_bipartite(g, ["a"], top_nodes={"x"})


def test_no_top_nodes_uses_bipartite_sets(monkeypatch):
    """If top_nodes isn't supplied, fall back to bipartite_sets."""
    g = fnx.Graph()
    g.add_edge("top", "bottom")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["pos"] = pos
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    result = fnx.draw_bipartite(g)
    assert result == "drawn"
    assert captured["pos"] is not None


def test_explicit_pos_short_circuits(monkeypatch):
    """If pos is supplied, no layout computation happens."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["pos"] = pos
        return "drawn"

    def fail(*args, **kwargs):
        raise AssertionError("layout was computed despite explicit pos")

    monkeypatch.setattr(nx_pylab, "bipartite_layout", fail)
    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    explicit = {"a": np.array([0.0, 0.0]), "b": np.array([1.0, 0.0])}
    result = fnx.draw_bipartite(g, ["a"], pos=explicit, node_size=10)
    assert result == "drawn"
    assert captured["pos"] is explicit


def test_kwargs_pass_through(monkeypatch):
    """node_size, etc. should be forwarded to draw."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    captured = {}

    def fake_draw(G, pos=None, **kwds):
        captured["kwds"] = kwds
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    fnx.draw_bipartite(g, ["a"], node_size=10, alpha=0.5)
    assert captured["kwds"]["node_size"] == 10
    assert captured["kwds"]["alpha"] == 0.5
