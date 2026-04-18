"""Tests for GEXF compatibility wrappers."""

from pathlib import Path

import franken_networkx as fnx


def _sample_graph():
    graph = fnx.DiGraph()
    graph.add_node("n0", label="Node Zero", color="red")
    graph.add_node("n1", label="Node One")
    graph.add_edge("n0", "n1", weight=2.5)
    return graph


def test_generate_and_parse_gexf_round_trip():
    graph = _sample_graph()
    gexf = "\n".join(fnx.generate_gexf(graph))
    parsed = fnx.parse_gexf(gexf)

    assert parsed.is_directed()
    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed.nodes["n0"]["label"] == "Node Zero"
    assert parsed.nodes["n0"]["color"] == "red"
    assert parsed["n0"]["n1"]["weight"] == 2.5


def test_read_and_write_gexf_round_trip(tmp_path: Path):
    graph = _sample_graph()
    path = tmp_path / "graph.gexf"

    fnx.write_gexf(graph, path)
    parsed = fnx.read_gexf(path)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed.is_directed()
    assert parsed.nodes["n1"]["label"] == "Node One"


def test_relabel_gexf_graph_uses_label_attribute():
    graph = _sample_graph()
    relabeled = fnx.relabel_gexf_graph(graph)

    assert "Node Zero" in relabeled
    assert "Node One" in relabeled


def test_gexf_helpers_do_not_delegate_to_networkx(monkeypatch, tmp_path: Path):
    import networkx as nx

    def fail(*args, **kwargs):
        raise AssertionError("GEXF helper delegated to NetworkX")

    monkeypatch.setattr(nx, "read_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "write_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "generate_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "relabel_gexf_graph", fail, raising=False)

    graph = _sample_graph()
    path = tmp_path / "native.gexf"
    fnx.write_gexf(graph, path)
    parsed = fnx.read_gexf(path)
    generated = "\n".join(fnx.generate_gexf(parsed))
    reparsed = fnx.parse_gexf(generated)
    relabeled = fnx.relabel_gexf_graph(reparsed)

    assert reparsed.number_of_edges() == 1
    assert "Node Zero" in relabeled
