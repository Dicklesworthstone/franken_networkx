"""Tests for drawing and visualization delegation helpers."""

from io import StringIO
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
        "draw_forceatlas2",
        "draw_circular",
        "draw_kamada_kawai",
        "draw_planar",
        "draw_random",
        "draw_shell",
        "draw_spectral",
        "draw_spring",
        "forceatlas2_layout",
    ]:
        monkeypatch.setattr(nx, name, fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)
    graph = _path_graph()

    wrappers = [
        (fnx.draw_forceatlas2, {}),
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


def test_draw_planar_transformed_graph_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    mapping = {node: ("cycle-node", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.cycle_graph(4), mapping)
    graph.add_edge(("cycle-node", 0), ("cycle-node", 0))
    expected_pos = fnx.planar_layout(graph)

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX planar drawing helper was used")

    monkeypatch.setattr(nx, "draw_planar", fail)
    monkeypatch.setattr(nx, "planar_layout", fail)
    monkeypatch.setattr(nx, "combinatorial_embedding_to_pos", fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert fnx.draw_planar(graph, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(expected_pos) == set(graph.nodes())
    for node in graph.nodes():
        assert np.allclose(actual_pos[node], expected_pos[node])
    assert kwargs == {"node_size": 10}


def test_draw_shell_transformed_nlist_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    nodes = [("shell-node", index) for index in range(4)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (nodes[0], nodes[1]),
            (nodes[1], nodes[2]),
            (nodes[2], nodes[3]),
        ]
    )
    nlist = [[nodes[0]], nodes[1:]]
    expected_pos = fnx.shell_layout(graph, nlist=nlist)

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX shell drawing helper was used")

    monkeypatch.setattr(nx, "draw_shell", fail)
    monkeypatch.setattr(nx, "shell_layout", fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert fnx.draw_shell(graph, nlist=nlist, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(expected_pos) == set(graph.nodes())
    for node in graph.nodes():
        assert np.allclose(actual_pos[node], expected_pos[node])
    assert kwargs == {"node_size": 10}


@pytest.mark.parametrize(
    ("wrapper", "layout", "blocked_names"),
    [
        (
            fnx.draw_circular,
            fnx.circular_layout,
            ("draw_circular", "circular_layout"),
        ),
        (
            fnx.draw_spectral,
            fnx.spectral_layout,
            ("draw_spectral", "spectral_layout"),
        ),
        (
            fnx.draw_kamada_kawai,
            fnx.kamada_kawai_layout,
            ("draw_kamada_kawai", "kamada_kawai_layout"),
        ),
    ],
)
def test_draw_transformed_layout_wrappers_use_local_layout(
    wrapper,
    layout,
    blocked_names,
    monkeypatch,
):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    nodes = [("layout-node", index) for index in range(4)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (nodes[0], nodes[1]),
            (nodes[1], nodes[2]),
            (nodes[2], nodes[3]),
            (nodes[0], nodes[0]),
        ]
    )
    expected_pos = layout(graph)

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX transformed layout helper was used")

    for name in blocked_names:
        monkeypatch.setattr(nx, name, fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert wrapper(graph, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(expected_pos) == set(graph.nodes())
    for node in graph.nodes():
        assert np.allclose(actual_pos[node], expected_pos[node])
    assert kwargs == {"node_size": 10}


def test_draw_random_transformed_graph_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    nodes = [("random-node", index) for index in range(4)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (nodes[0], nodes[1]),
            (nodes[1], nodes[2]),
            (nodes[2], nodes[3]),
            (nodes[0], nodes[0]),
        ]
    )

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX random drawing helper was used")

    monkeypatch.setattr(nx, "draw_random", fail)
    monkeypatch.setattr(nx, "random_layout", fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert fnx.draw_random(graph, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(graph.nodes())
    for coords in actual_pos.values():
        coords = np.asarray(coords)
        assert coords.shape == (2,)
        assert np.all(np.isfinite(coords))
        assert np.all((0.0 <= coords) & (coords <= 1.0))
    assert kwargs == {"node_size": 10}


def test_draw_spring_transformed_graph_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    nodes = [("spring-node", index) for index in range(4)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (nodes[0], nodes[1]),
            (nodes[1], nodes[2]),
            (nodes[2], nodes[3]),
            (nodes[0], nodes[0]),
        ]
    )

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX spring drawing helper was used")

    monkeypatch.setattr(nx, "draw_spring", fail)
    monkeypatch.setattr(nx, "spring_layout", fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert fnx.draw_spring(graph, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(graph.nodes())
    for coords in actual_pos.values():
        coords = np.asarray(coords)
        assert coords.shape == (2,)
        assert np.all(np.isfinite(coords))
    assert kwargs == {"node_size": 10}


def test_draw_forceatlas2_transformed_graph_uses_local_layout(monkeypatch):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    nodes = [("forceatlas-node", index) for index in range(4)]
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (nodes[0], nodes[1]),
            (nodes[1], nodes[2]),
            (nodes[2], nodes[3]),
            (nodes[0], nodes[0]),
        ]
    )

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX ForceAtlas2 drawing helper was used")

    monkeypatch.setattr(nx, "draw_forceatlas2", fail)
    monkeypatch.setattr(nx, "forceatlas2_layout", fail)

    calls = []

    def fake_draw(G, pos=None, **kwargs):
        calls.append((G, pos, kwargs))
        return "drawn"

    monkeypatch.setattr(nx_pylab, "draw", fake_draw)

    assert fnx.draw_forceatlas2(graph, node_size=10) == "drawn"

    assert len(calls) == 1
    drawn_graph, actual_pos, kwargs = calls[0]
    assert drawn_graph is graph
    assert set(actual_pos) == set(graph.nodes())
    for coords in actual_pos.values():
        coords = np.asarray(coords)
        assert coords.shape == (2,)
        assert np.all(np.isfinite(coords))
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
        raise AssertionError("NetworkX LaTeX fallback was used")

    monkeypatch.setattr(nx, "to_latex", fail)
    monkeypatch.setattr(nx, "to_latex_raw", fail)
    monkeypatch.setattr(nx, "write_latex", fail)

    got = fnx.to_latex(graph, as_document=False, caption="demo")
    path = tmp_path / "graph.tex"
    fnx.write_latex(graph, path, as_document=False, caption="demo")

    assert got == expected
    assert path.read_text(encoding="utf-8") == expected


def test_to_latex_raw_edge_cases_match_networkx_without_fallback(monkeypatch):
    nx = pytest.importorskip("networkx")
    graph = fnx.DiGraph()
    expected_graph = nx.DiGraph()

    graph.add_edge(
        "a",
        "b",
        edge_options="line width=2",
        edge_label="ab",
        edge_label_options="near start",
    )
    graph.add_edge("b", "b", edge_label="loop")
    expected_graph.add_edge(
        "a",
        "b",
        edge_options="line width=2",
        edge_label="ab",
        edge_label_options="near start",
    )
    expected_graph.add_edge("b", "b", edge_label="loop")

    for target in [graph, expected_graph]:
        target.nodes["a"]["pos"] = (0.0, 1.25)
        target.nodes["a"]["node_options"] = "draw,blue"
        target.nodes["a"]["label"] = "$A$"
        target.nodes["b"]["pos"] = "(45:2)"
        target.nodes["b"]["label"] = "$B$"

    expected = nx.to_latex_raw(
        expected_graph,
        tikz_options="[scale=2]",
        default_node_options="[circle]",
        default_edge_options="red",
    )

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX raw LaTeX fallback was used")

    monkeypatch.setattr(nx, "to_latex_raw", fail)

    got = fnx.to_latex_raw(
        graph,
        tikz_options="[scale=2]",
        default_node_options="[circle]",
        default_edge_options="red",
    )

    assert got == expected


def test_to_latex_raw_error_cases_match_networkx():
    graph = _path_graph()

    with pytest.raises(fnx.NetworkXError, match="node b has no specified pos"):
        fnx.to_latex_raw(graph, pos={"a": (0.0, 0.0)})

    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        fnx.to_latex_raw(fnx.MultiGraph())


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


def test_network_text_helpers_do_not_delegate_to_networkx(monkeypatch):
    import franken_networkx.drawing.nx_pylab as nx_pylab

    def fail(*args, **kwargs):
        raise AssertionError("network_text delegated to NetworkX")

    monkeypatch.setattr(nx_pylab, "_delegate_draw", fail)

    graph = _path_graph()
    lines = list(fnx.generate_network_text(graph, ascii_only=True))

    buffer = StringIO()
    fnx.write_network_text(graph, path=buffer.write, ascii_only=True, end="")

    assert lines
    assert buffer.getvalue() == "".join(lines)


def test_network_text_matches_networkx_for_labeled_directed_options():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    graph = fnx.DiGraph()

    edges = [("root", "left"), ("root", "right"), ("left", "leaf")]
    graph.add_edges_from(edges)
    graph.nodes["root"]["label"] = "Root"
    graph.nodes["left"]["label"] = "Left"
    graph.nodes["right"]["label"] = "Right"
    graph.nodes["leaf"]["label"] = "Leaf"

    options = {
        "sources": ["root"],
        "with_labels": "label",
        "ascii_only": True,
        "vertical_chains": True,
        "max_depth": 2,
    }

    expected_graph = nx_pylab._as_nx_graph(graph)
    expected_lines = list(nx.generate_network_text(expected_graph, **options))
    actual_lines = list(fnx.generate_network_text(graph, **options))

    expected_buffer = StringIO()
    actual_buffer = StringIO()
    nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
    fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

    assert actual_lines == expected_lines
    assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_undirected_cycle_options():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    graph = fnx.Graph()
    graph.add_edges_from(
        [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
            ("leaf", "right"),
        ]
    )
    for node, label in [
        ("root", "Root"),
        ("left", "Left"),
        ("right", "Right"),
        ("leaf", "Leaf"),
    ]:
        graph.nodes[node]["label"] = label

    options = {
        "sources": ["root"],
        "with_labels": "label",
        "ascii_only": True,
        "vertical_chains": True,
        "max_depth": 2,
    }

    expected_graph = nx_pylab._as_nx_graph(graph)
    expected_lines = list(nx.generate_network_text(expected_graph, **options))
    actual_lines = list(fnx.generate_network_text(graph, **options))

    expected_buffer = StringIO()
    actual_buffer = StringIO()
    nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
    fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

    assert actual_lines == expected_lines
    assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_collapse_and_multiple_sources():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    graph = fnx.DiGraph()
    graph.add_edges_from(
        [
            ("a", "b"),
            ("b", "c"),
            ("x", "y"),
            ("x", "z"),
        ]
    )
    graph.nodes["b"]["collapse"] = True
    graph.nodes["a"]["label"] = "A"
    graph.nodes["b"]["label"] = "B"
    graph.nodes["c"]["label"] = "C"
    graph.nodes["x"]["label"] = "X"
    graph.nodes["y"]["label"] = "Y"
    graph.nodes["z"]["label"] = "Z"

    options = {
        "sources": ["a", "x"],
        "with_labels": "label",
        "ascii_only": True,
        "vertical_chains": False,
        "max_depth": None,
    }

    expected_graph = nx_pylab._as_nx_graph(graph)
    expected_lines = list(nx.generate_network_text(expected_graph, **options))
    actual_lines = list(fnx.generate_network_text(graph, **options))

    expected_buffer = StringIO()
    actual_buffer = StringIO()
    nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
    fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

    assert actual_lines == expected_lines
    assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_default_sources():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    directed = fnx.DiGraph()
    directed.add_edges_from(
        [
            ("a", "b"),
            ("b", "a"),
            ("c", "d"),
            ("d", "e"),
            ("x", "y"),
        ]
    )

    undirected = fnx.Graph()
    undirected.add_edges_from([("a", "b"), ("c", "d"), ("d", "e")])
    undirected.add_node("solo")

    options = {
        "with_labels": True,
        "ascii_only": True,
        "vertical_chains": False,
        "max_depth": None,
    }

    for graph in [directed, undirected]:
        expected_graph = nx_pylab._as_nx_graph(graph)
        expected_lines = list(nx.generate_network_text(expected_graph, **options))
        actual_lines = list(fnx.generate_network_text(graph, **options))

        expected_buffer = StringIO()
        actual_buffer = StringIO()
        nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
        fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

        assert actual_lines == expected_lines
        assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_empty_and_max_depth():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    empty_options = {"with_labels": True, "ascii_only": True}
    for graph in [fnx.Graph(), fnx.DiGraph()]:
        expected_graph = nx_pylab._as_nx_graph(graph)
        assert list(fnx.generate_network_text(graph, **empty_options)) == list(
            nx.generate_network_text(expected_graph, **empty_options)
        )

    directed = fnx.DiGraph()
    directed.add_edges_from(
        [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
            ("leaf", "root"),
        ]
    )

    undirected = fnx.Graph()
    undirected.add_edges_from(
        [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
            ("leaf", "right"),
        ]
    )

    cases = [
        (
            directed,
            {
                "sources": ["root"],
                "with_labels": True,
                "ascii_only": False,
                "vertical_chains": True,
            },
        ),
        (
            undirected,
            {
                "sources": ["root"],
                "with_labels": True,
                "ascii_only": True,
                "vertical_chains": False,
            },
        ),
    ]

    for graph, base_options in cases:
        expected_graph = nx_pylab._as_nx_graph(graph)
        for max_depth in [0, 1, 2, None]:
            options = {**base_options, "max_depth": max_depth}
            expected_lines = list(nx.generate_network_text(expected_graph, **options))
            actual_lines = list(fnx.generate_network_text(graph, **options))

            expected_buffer = StringIO()
            actual_buffer = StringIO()
            nx.write_network_text(
                expected_graph,
                path=expected_buffer.write,
                end="",
                **options,
            )
            fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

            assert actual_lines == expected_lines
            assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_label_modes():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    graph = fnx.DiGraph()
    graph.add_edges_from(
        [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
        ]
    )
    graph.nodes["root"]["label"] = "Root Label"
    graph.nodes["right"]["label"] = "Right Label"
    graph.nodes["root"]["part"] = "R"
    graph.nodes["left"]["part"] = "L"
    graph.nodes["right"]["part"] = "Q"
    graph.nodes["leaf"]["part"] = "Z"

    expected_graph = nx_pylab._as_nx_graph(graph)
    for with_labels in [False, True, "part"]:
        options = {
            "sources": ["root"],
            "with_labels": with_labels,
            "ascii_only": True,
            "vertical_chains": False,
            "max_depth": None,
        }
        expected_lines = list(nx.generate_network_text(expected_graph, **options))
        actual_lines = list(fnx.generate_network_text(graph, **options))

        expected_buffer = StringIO()
        actual_buffer = StringIO()
        nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
        fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

        assert actual_lines == expected_lines
        assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_network_text_matches_networkx_for_multigraphs():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    undirected = fnx.MultiGraph()
    undirected.add_edge("root", "left")
    undirected.add_edge("root", "left")
    undirected.add_edge("left", "leaf")
    undirected.add_edge("root", "right")

    directed = fnx.MultiDiGraph()
    directed.add_edge("root", "left")
    directed.add_edge("root", "left")
    directed.add_edge("left", "leaf")
    directed.add_edge("right", "root")

    cases = [
        (
            undirected,
            {
                "sources": ["root"],
                "with_labels": True,
                "ascii_only": True,
                "vertical_chains": False,
                "max_depth": None,
            },
        ),
        (
            directed,
            {
                "sources": ["right"],
                "with_labels": True,
                "ascii_only": True,
                "vertical_chains": True,
                "max_depth": None,
            },
        ),
    ]

    for graph, options in cases:
        expected_graph = nx_pylab._as_nx_graph(graph)
        expected_lines = list(nx.generate_network_text(expected_graph, **options))
        actual_lines = list(fnx.generate_network_text(graph, **options))

        expected_buffer = StringIO()
        actual_buffer = StringIO()
        nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
        fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

        assert actual_lines == expected_lines
        assert actual_buffer.getvalue() == expected_buffer.getvalue()


def test_write_network_text_matches_networkx_for_paths_and_custom_end(tmp_path: Path):
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    graph = fnx.Graph()
    graph.add_edges_from(
        [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
        ]
    )
    graph.nodes["root"]["label"] = "Root"
    graph.nodes["left"]["label"] = "Left"
    graph.nodes["right"]["label"] = "Right"
    graph.nodes["leaf"]["label"] = "Leaf"

    options = {
        "sources": ["root"],
        "with_labels": "label",
        "ascii_only": True,
        "vertical_chains": False,
        "max_depth": None,
        "end": "|",
    }

    expected_path = tmp_path / "networkx.txt"
    actual_path = tmp_path / "fnx.txt"
    expected_graph = nx_pylab._as_nx_graph(graph)

    nx.write_network_text(expected_graph, path=expected_path, **options)
    fnx.write_network_text(graph, path=actual_path, **options)

    assert actual_path.read_text(encoding="utf-8") == expected_path.read_text(
        encoding="utf-8"
    )


def test_network_text_matches_networkx_for_dense_backedges():
    nx = pytest.importorskip("networkx")
    import franken_networkx.drawing.nx_pylab as nx_pylab

    undirected = fnx.Graph()
    undirected.add_edges_from(
        [
            ("a", "b"),
            ("a", "c"),
            ("a", "d"),
            ("b", "c"),
            ("b", "d"),
            ("c", "d"),
        ]
    )

    directed = fnx.DiGraph()
    directed.add_edges_from(
        [
            ("a", "b"),
            ("a", "c"),
            ("b", "a"),
            ("b", "c"),
            ("c", "a"),
            ("c", "b"),
        ]
    )

    cases = [
        (
            undirected,
            {
                "sources": ["a"],
                "with_labels": True,
                "ascii_only": False,
                "vertical_chains": False,
                "max_depth": None,
            },
        ),
        (
            directed,
            {
                "sources": ["a"],
                "with_labels": True,
                "ascii_only": True,
                "vertical_chains": False,
                "max_depth": None,
            },
        ),
    ]

    for graph, options in cases:
        expected_graph = nx_pylab._as_nx_graph(graph)
        expected_lines = list(nx.generate_network_text(expected_graph, **options))
        actual_lines = list(fnx.generate_network_text(graph, **options))

        expected_buffer = StringIO()
        actual_buffer = StringIO()
        nx.write_network_text(expected_graph, path=expected_buffer.write, end="", **options)
        fnx.write_network_text(graph, path=actual_buffer.write, end="", **options)

        assert actual_lines == expected_lines
        assert actual_buffer.getvalue() == expected_buffer.getvalue()
