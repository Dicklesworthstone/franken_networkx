"""Tests for drawing and visualization delegation helpers."""

import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
import franken_networkx as fnx


def _path_graph():
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    return graph


class _FakeScalarMappable:
    def __init__(self, cmap):
        self.cmap = cmap
        self.vmin = 0.0
        self.vmax = 1.0

    def set_clim(self, vmin, vmax):
        self.vmin = float(vmin)
        self.vmax = float(vmax)

    def to_rgba(self, value):
        value = float(value)
        span = self.vmax - self.vmin
        ratio = 0.0 if span == 0 else (value - self.vmin) / span
        return (ratio, value, self.vmin, self.vmax)


def _fake_matplotlib(monkeypatch):
    cm = SimpleNamespace(
        ScalarMappable=_FakeScalarMappable,
        viridis=object(),
        plasma=object(),
    )
    module = SimpleNamespace(cm=cm)
    monkeypatch.setitem(sys.modules, "matplotlib", module)
    return module


def test_draw_networkx_variants_do_not_error():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    graph = _path_graph()
    pos = fnx.spring_layout(graph, seed=7)
    fig, ax = plt.subplots()

    try:
        fnx.draw_networkx(graph, pos=pos, ax=ax)
        fnx.draw_networkx_nodes(graph, pos=pos, ax=ax)
        fnx.draw_networkx_edges(graph, pos=pos, ax=ax)
        fnx.draw_networkx_labels(graph, pos=pos, ax=ax)
        fnx.draw_networkx_edge_labels(
            graph,
            pos=pos,
            edge_labels={("a", "b"): "ab", ("b", "c"): "bc"},
            ax=ax,
        )
        fnx.draw_forceatlas2(graph, ax=ax)
    finally:
        plt.close(fig)


def test_draw_layout_wrappers_use_local_layouts_without_networkx_helpers(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX draw layout helper was used")

    for name in [
        "draw_circular",
        "draw_kamada_kawai",
        "draw_planar",
        "draw_random",
        "draw_shell",
        "draw_spectral",
        "draw_spring",
    ]:
        monkeypatch.setattr(nx, name, fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)
    graph = _path_graph()

    wrappers = [
        (fnx.draw_circular, {}),
        (fnx.draw_kamada_kawai, {}),
        (fnx.draw_planar, {}),
        (fnx.draw_random, {}),
        (fnx.draw_shell, {"nlist": [["a"], ["b", "c"]]}),
        (fnx.draw_spectral, {}),
        (fnx.draw_spring, {}),
    ]

    for wrapper, kwargs in wrappers:
        assert wrapper(graph, node_size=10, **kwargs) == "drawn"

    assert len(calls) == len(wrappers)
    for G, pos, kwargs in calls:
        assert G is graph
        assert set(pos) == set(graph.nodes())
        assert kwargs == {"node_size": 10}


def test_to_latex_variants_include_tikz_markup():
    graph = _path_graph()
    for node, coords in fnx.spring_layout(graph, seed=7).items():
        graph.nodes[node]["pos"] = tuple(coords)

    latex = fnx.to_latex(graph)
    raw = fnx.to_latex_raw(graph)

    assert "\\begin{tikzpicture}" in latex
    assert "\\begin{tikzpicture}" in raw
    assert "\\draw" in raw


def test_latex_wrappers_match_networkx_without_top_level_fallback(
    monkeypatch, tmp_path: Path
):
    nx = pytest.importorskip("networkx")
    graph = _path_graph()
    expected_graph = nx.Graph()
    expected_graph.add_edges_from([("a", "b"), ("b", "c")])
    for node, coords in fnx.spring_layout(graph, seed=7).items():
        position = tuple(coords)
        graph.nodes[node]["pos"] = position
        expected_graph.nodes[node]["pos"] = position

    expected = nx.to_latex(expected_graph, as_document=False, caption="demo")

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX top-level LaTeX fallback was used")

    monkeypatch.setattr(nx, "to_latex", fail)
    monkeypatch.setattr(nx, "write_latex", fail)

    got = fnx.to_latex(graph, as_document=False, caption="demo")
    path = tmp_path / "graph.tex"
    fnx.write_latex(graph, path, as_document=False, caption="demo")

    assert got == expected
    assert path.read_text(encoding="utf-8") == expected


def test_apply_matplotlib_colors_copies_node_attrs_back(monkeypatch):
    nx = pytest.importorskip("networkx")
    matplotlib = _fake_matplotlib(monkeypatch)

    graph = fnx.path_graph(3)
    expected = nx.path_graph(3)
    for node, value in enumerate([0.0, 0.5, 1.0]):
        graph.nodes[node]["score"] = value
        expected.nodes[node]["score"] = value

    nx.apply_matplotlib_colors(expected, "score", "rgba", matplotlib.cm.viridis)

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX apply_matplotlib_colors fallback was used")

    monkeypatch.setattr(nx, "apply_matplotlib_colors", fail)

    fnx.apply_matplotlib_colors(graph, "score", "rgba", matplotlib.cm.viridis)

    for node in graph:
        assert np.allclose(graph.nodes[node]["rgba"], expected.nodes[node]["rgba"])


def test_apply_matplotlib_colors_copies_multiedge_attrs_back(monkeypatch):
    nx = pytest.importorskip("networkx")
    matplotlib = _fake_matplotlib(monkeypatch)

    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=0, score=0.0)
    graph.add_edge("a", "b", key=1, score=1.0)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=0, score=0.0)
    expected.add_edge("a", "b", key=1, score=1.0)

    nx.apply_matplotlib_colors(
        expected,
        "score",
        "rgba",
        matplotlib.cm.plasma,
        nodes=False,
    )

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX apply_matplotlib_colors fallback was used")

    monkeypatch.setattr(nx, "apply_matplotlib_colors", fail)

    fnx.apply_matplotlib_colors(
        graph,
        "score",
        "rgba",
        matplotlib.cm.plasma,
        nodes=False,
    )

    for u, v, key in graph.edges(keys=True):
        assert np.allclose(graph[u][v][key]["rgba"], expected[u][v][key]["rgba"])


def test_write_latex_and_network_text(tmp_path: Path):
    graph = _path_graph()
    for node, coords in fnx.spring_layout(graph, seed=7).items():
        graph.nodes[node]["pos"] = tuple(coords)

    latex_path = tmp_path / "graph.tex"
    text_path = tmp_path / "graph.txt"

    fnx.write_latex(graph, latex_path)
    fnx.write_network_text(graph, text_path)

    assert latex_path.read_text(encoding="utf-8")
    rendered = text_path.read_text(encoding="utf-8")
    assert "a" in rendered
    assert "b" in rendered


def test_generate_network_text_returns_lines():
    graph = _path_graph()
    lines = list(fnx.generate_network_text(graph))
    assert lines
    assert any("a" in line for line in lines)
