"""Tests for parse/generate I/O wrapper variants."""

from pathlib import Path
from unittest import mock

import franken_networkx as fnx
import franken_networkx._fnx as _fnx
import networkx as nx
import pytest


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


def test_parse_edgelist_dict_literal_attrs_uses_safe_literal_parser():
    parsed = fnx.parse_edgelist(["a b {'weight': 2.5, 'color': 'blue'}"], data=True)

    assert parsed["a"]["b"]["weight"] == 2.5
    assert parsed["a"]["b"]["color"] == "blue"


def test_parse_edgelist_explicit_delimiter_preserves_trailing_empty_field_without_fallback(
    monkeypatch,
):
    lines = ["1\t2\t3", "2\t3\t", "3\t4\t3.0"]
    expected = sorted(
        nx.parse_edgelist(
            lines, delimiter="\t", nodetype=int, data=[("value", str)]
        ).edges(data="value")
    )

    monkeypatch.setattr(
        nx,
        "parse_edgelist",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX parse_edgelist fallback was used")
        ),
    )

    actual = sorted(
        fnx.parse_edgelist(
            lines, delimiter="\t", nodetype=int, data=[("value", str)]
        ).edges(data="value")
    )

    assert actual == expected


def test_parse_edgelist_typed_data_rejects_arity_mismatch_like_networkx():
    lines = ["1 2 3 4"]
    data = [("weight", float)]

    with pytest.raises(IndexError) as nx_error:
        nx.parse_edgelist(lines, nodetype=int, data=data)

    with pytest.raises(IndexError) as fnx_error:
        fnx.parse_edgelist(lines, nodetype=int, data=data)

    assert str(fnx_error.value) == str(nx_error.value)


def test_parse_and_generate_gml_round_trip():
    graph = fnx.Graph()
    graph.add_node("a", label="A")
    graph.add_edge("a", "b", weight=3)

    lines = list(fnx.generate_gml(graph))
    with mock.patch.object(
        nx,
        "parse_gml",
        side_effect=AssertionError("NetworkX parse_gml fallback used"),
    ):
        parsed = fnx.parse_gml(lines)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1


def test_generate_gml_matches_networkx_without_fallback(monkeypatch):
    class Token:
        def __str__(self):
            return "token-value"

    def stringizer(value):
        if isinstance(value, str):
            return value
        if isinstance(value, Token):
            return str(value)
        raise ValueError

    graph = fnx.MultiDiGraph()
    graph.graph["name"] = "demo"
    graph.graph["flags"] = ["a", "b"]
    graph.add_node(("left", 1), color="red", nested={"score": 2})
    graph.add_node("right", empty=[])
    graph.add_edge(("left", 1), "right", key=3, weight=1.5, custom=Token())

    expected_graph = nx.MultiDiGraph()
    expected_graph.graph.update(graph.graph)
    expected_graph.add_node(("left", 1), color="red", nested={"score": 2})
    expected_graph.add_node("right", empty=[])
    expected_graph.add_edge(("left", 1), "right", key=3, weight=1.5, custom=Token())
    expected = list(nx.generate_gml(expected_graph, stringizer=stringizer))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "generate_gml", fail)

    assert list(fnx.generate_gml(graph, stringizer=stringizer)) == expected


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
    with mock.patch.object(
        nx,
        "parse_graphml",
        side_effect=AssertionError("NetworkX parse_graphml fallback used"),
    ):
        parsed = fnx.parse_graphml(graphml, node_type=int)
    graph = fnx.path_graph(2)
    generated = list(fnx.generate_graphml(graph, prettyprint=False, named_key_ids=True))
    expected = list(nx.generate_graphml(nx.path_graph(2), prettyprint=False, named_key_ids=True))

    assert list(parsed.nodes()) == [0, 1, 2]
    assert generated == expected


def test_generate_graphml_does_not_delegate_to_networkx(monkeypatch):
    from networkx.readwrite import graphml as nx_graphml

    graph = fnx.path_graph(2)
    expected = list(
        nx.generate_graphml(nx.path_graph(2), prettyprint=False, named_key_ids=True)
    )

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "generate_graphml", fail)
    monkeypatch.setattr(nx_graphml, "GraphMLWriter", fail)

    generated = list(fnx.generate_graphml(graph, prettyprint=False, named_key_ids=True))
    assert generated == expected


def test_rust_read_gml_preserves_graph_attrs(tmp_path: Path):
    path = tmp_path / "graph.gml"
    path.write_text(
        'graph [\n'
        '  directed 0\n'
        '  label "demo"\n'
        '  owner "qa"\n'
        '  node [ id 0 label "a" ]\n'
        '  node [ id 1 label "b" ]\n'
        '  edge [ source 0 target 1 ]\n'
        ']\n',
        encoding="utf-8",
    )

    graph = fnx.read_gml(path)

    assert dict(graph.graph) == {"label": "demo", "owner": "qa"}


def test_rust_read_graphml_preserves_graph_attrs(tmp_path: Path):
    path = tmp_path / "graph.graphml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <key id="g0" for="graph" attr.name="name" attr.type="string"/>\n'
        '  <key id="g1" for="graph" attr.name="version" attr.type="int"/>\n'
        '  <graph id="G" edgedefault="undirected">\n'
        '    <data key="g0">demo</data>\n'
        '    <data key="g1">3</data>\n'
        '    <node id="a"/>\n'
        '    <node id="b"/>\n'
        '    <edge source="a" target="b"/>\n'
        '  </graph>\n'
        '</graphml>\n',
        encoding="utf-8",
    )

    graph = fnx.read_graphml(path)

    assert graph.graph["name"] == "demo"
    assert graph.graph["version"] == 3


def test_rust_write_gml_preserves_graph_attrs(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    graph.graph["label"] = "demo"
    graph.graph["owner"] = "qa"
    path = tmp_path / "graph.gml"

    fnx.write_gml(graph, path)

    content = path.read_text(encoding="utf-8")
    assert 'label "demo"' in content
    assert 'owner "qa"' in content


def test_rust_write_graphml_preserves_graph_attrs(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    graph.graph["name"] = "demo"
    graph.graph["version"] = 3
    graph.graph["public"] = True
    path = tmp_path / "graph.graphml"

    fnx.write_graphml(graph, path)

    content = path.read_text(encoding="utf-8")
    assert 'for="graph" attr.name="name" attr.type="string"' in content
    assert 'for="graph" attr.name="version" attr.type="int"' in content
    assert 'for="graph" attr.name="public" attr.type="boolean"' in content
    assert '<data key="g0">demo</data>' in content
    assert '<data key="g1">true</data>' in content
    assert '<data key="g2">3</data>' in content


def test_raw_write_graphml_string_preserves_graph_attrs_and_compact_mode():
    graph = fnx.Graph()
    graph.graph["label"] = "demo"
    graph.graph["version"] = 3
    graph.add_node("a", score=3)
    graph.add_node("b")
    graph.add_edge("a", "b", eid="E1", weight=2)

    xml = _fnx.write_graphml_string_rust(
        graph,
        prettyprint=False,
        named_key_ids=True,
        edge_id_from_attribute="eid",
    )

    assert 'for="graph" attr.name="label"' in xml
    assert 'for="graph" attr.name="version"' in xml
    assert '<data key="label">demo</data>' in xml
    assert '<data key="version">3</data>' in xml
    assert 'id="E1"' in xml
    assert "\n" not in xml


def test_raw_write_graphml_string_fails_closed_for_multigraphs():
    multigraph = fnx.MultiGraph()
    multigraph.add_edge("a", "b", key=0, weight=1)
    multigraph.add_edge("a", "b", key=1, weight=2)

    with pytest.raises(TypeError, match="does not support MultiGraph"):
        _fnx.write_graphml_string_rust(multigraph)

    multidigraph = fnx.MultiDiGraph()
    multidigraph.add_edge("a", "b", key=0, weight=1)
    multidigraph.add_edge("a", "b", key=1, weight=2)

    with pytest.raises(TypeError, match="does not support .*MultiDiGraph"):
        _fnx.write_graphml_string_rust(multidigraph)


def test_raw_node_link_data_preserves_graph_attrs_and_directed_flag():
    graph = fnx.DiGraph()
    graph.add_edge("a", "b")
    graph.graph["name"] = "demo"
    graph.graph["version"] = 3

    payload = _fnx.node_link_data(graph)

    assert payload["directed"] is True
    assert payload["graph_attrs"] == {"name": "demo", "version": 3}


def test_raw_node_link_graph_preserves_directed_type_and_graph_attrs():
    payload = {
        "mode": "strict",
        "directed": True,
        "graph_attrs": {"name": "demo", "version": 3},
        "nodes": ["a", "b"],
        "edges": [{"left": "a", "right": "b", "attrs": {}}],
    }

    graph = _fnx.node_link_graph(payload)

    assert graph.is_directed()
    assert dict(graph.graph) == {"name": "demo", "version": 3}


def test_raw_serializers_fail_closed_for_multigraphs(tmp_path: Path):
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b")
    graph.add_edge("a", "b")

    with pytest.raises(TypeError):
        _fnx.node_link_data(graph)

    with pytest.raises(TypeError):
        _fnx.write_gml(graph, tmp_path / "graph.gml")

    with pytest.raises(TypeError):
        _fnx.write_graphml(graph, tmp_path / "graph.graphml")


def test_raw_node_link_graph_fails_closed_for_multigraph_payload():
    payload = {
        "mode": "strict",
        "directed": False,
        "multigraph": True,
        "graph_attrs": {},
        "nodes": ["a", "b"],
        "edges": [
            {"left": "a", "right": "b", "attrs": {"w": 1}},
            {"left": "a", "right": "b", "attrs": {"w": 2}},
        ],
    }

    with pytest.raises(TypeError):
        _fnx.node_link_graph(payload)


def test_raw_node_link_graph_rejects_non_bool_flags():
    payload = {
        "mode": "strict",
        "directed": "yes",
        "multigraph": False,
        "graph_attrs": {},
        "nodes": ["a", "b"],
        "edges": [{"left": "a", "right": "b", "attrs": {}}],
    }

    with pytest.raises(TypeError):
        _fnx.node_link_graph(payload)


def test_raw_read_graphml_detects_directed_with_single_quotes(tmp_path: Path):
    path = tmp_path / "directed.graphml"
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<graphml xmlns='http://graphml.graphdrawing.org/xmlns'>\n"
        "  <graph id='G' edgedefault='directed'>\n"
        "    <node id='a'/>\n"
        "    <node id='b'/>\n"
        "    <edge source='a' target='b'/>\n"
        "  </graph>\n"
        "</graphml>\n",
        encoding="utf-8",
    )

    graph = _fnx.read_graphml(path)

    assert graph.is_directed()
    assert graph.has_edge("a", "b")


def test_raw_read_gml_ignores_directed_text_in_graph_attrs(tmp_path: Path):
    path = tmp_path / "graph.gml"
    path.write_text(
        'graph [\n'
        '  label "mentions directed 1"\n'
        "  directed 0\n"
        '  node [ id 0 label "a" ]\n'
        '  node [ id 1 label "b" ]\n'
        "  edge [ source 0 target 1 ]\n"
        "]\n",
        encoding="utf-8",
    )

    graph = _fnx.read_gml(path)

    assert not graph.is_directed()
    assert graph.has_edge("a", "b")
