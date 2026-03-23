"""Tests for parse/generate I/O wrapper variants."""

from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def test_parse_and_generate_adjlist_round_trip():
    graph = fnx.path_graph(4)
    lines = list(fnx.generate_adjlist(graph))
    parsed = fnx.parse_adjlist(lines)

    assert parsed.number_of_nodes() == graph.number_of_nodes()
    assert parsed.number_of_edges() == graph.number_of_edges()


def test_parse_and_generate_edgelist_round_trip_with_attrs():
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.5)
    graph.add_edge("b", "c", weight=1.5)

    lines = list(fnx.generate_edgelist(graph, data=["weight"]))
    parsed = fnx.parse_edgelist(lines, data=[("weight", float)])

    assert parsed["a"]["b"]["weight"] == 2.5
    assert parsed["b"]["c"]["weight"] == 1.5


def test_parse_and_generate_gml_round_trip():
    graph = fnx.Graph()
    graph.add_node("a", label="A")
    graph.add_edge("a", "b", weight=3)

    lines = list(fnx.generate_gml(graph))
    parsed = fnx.parse_gml(lines)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1


def test_graphml_variant_writers_delegate_to_core_writer(tmp_path: Path):
    graph = fnx.path_graph(3)
    xml_path = tmp_path / "graph_xml.graphml"
    lxml_path = tmp_path / "graph_lxml.graphml"

    fnx.write_graphml_xml(graph, xml_path)
    fnx.write_graphml_lxml(graph, lxml_path)

    assert "<graphml" in xml_path.read_text(encoding="utf-8")
    assert "<graphml" in lxml_path.read_text(encoding="utf-8")


def test_parse_and_generate_graphml_honor_networkx_kwargs(tmp_path: Path):
    graph_nx = nx.path_graph(3)
    path = tmp_path / "typed.graphml"
    nx.write_graphml(graph_nx, path)

    graphml = path.read_text(encoding="utf-8")
    parsed = fnx.parse_graphml(graphml, node_type=int)
    graph = fnx.path_graph(2)
    generated = list(fnx.generate_graphml(graph, prettyprint=False, named_key_ids=True))
    expected = list(nx.generate_graphml(nx.path_graph(2), prettyprint=False, named_key_ids=True))

    assert list(parsed.nodes()) == [0, 1, 2]
    assert generated == expected
