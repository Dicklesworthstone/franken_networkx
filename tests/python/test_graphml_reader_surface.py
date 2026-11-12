"""Oracle coverage for GraphMLReader's public parser surface.

br-r37-c1-ozpfa
"""

from __future__ import annotations

import importlib.util
import io
import sys
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

import franken_networkx as fnx
import networkx as nx
import pytest


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_graphml_reader"
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


GRAPHML = """<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="weight" for="edge" attr.name="weight" attr.type="int"/>
  <key id="label" for="node" attr.name="label" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="a"><data key="label">alpha</data></node>
    <node id="b"/>
    <edge source="a" target="b"><data key="weight">7</data></edge>
  </graph>
</graphml>"""


def _graph_state(graph):
    return (
        graph.is_directed(),
        sorted((node, dict(attrs)) for node, attrs in graph.nodes(data=True)),
        sorted((u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)),
        dict(graph.graph),
    )


def test_graphml_reader_constants_and_parser_methods_match_legacy_oracle():
    nx = _legacy_networkx()
    legacy_reader = nx.readwrite.GraphMLReader()
    reader = fnx.readwrite.GraphMLReader()

    for name in ("NS_GRAPHML", "NS_XSI", "NS_Y", "SCHEMALOCATION", "convert_bool"):
        assert getattr(fnx.readwrite.GraphMLReader, name) == getattr(
            nx.readwrite.GraphMLReader, name
        )

    reader.construct_types()
    assert reader.get_xml_type(int) == legacy_reader.get_xml_type(int)

    root = ElementTree.fromstring(GRAPHML)  # nosec B314: fixed test fixture
    legacy_keys, legacy_defaults = legacy_reader.find_graphml_keys(root)
    keys, defaults = reader.find_graphml_keys(root)
    assert keys == legacy_keys
    assert defaults == legacy_defaults

    node = root.find(f"{{{reader.NS_GRAPHML}}}graph/{{{reader.NS_GRAPHML}}}node")
    edge = root.find(f"{{{reader.NS_GRAPHML}}}graph/{{{reader.NS_GRAPHML}}}edge")
    assert reader.decode_data_elements(keys, node) == legacy_reader.decode_data_elements(
        legacy_keys, node
    )
    assert reader.decode_data_elements(keys, edge) == legacy_reader.decode_data_elements(
        legacy_keys, edge
    )


def test_graphml_reader_make_graph_and_call_match_legacy_oracle():
    nx = _legacy_networkx()
    root = ElementTree.fromstring(GRAPHML)  # nosec B314: fixed test fixture
    graph_xml = root.find(f"{{{fnx.readwrite.GraphMLReader.NS_GRAPHML}}}graph")

    legacy_reader = nx.readwrite.GraphMLReader()
    legacy_keys, legacy_defaults = legacy_reader.find_graphml_keys(root)
    reader = fnx.readwrite.GraphMLReader()
    keys, defaults = reader.find_graphml_keys(root)

    assert _graph_state(reader.make_graph(graph_xml, keys, defaults)) == _graph_state(
        legacy_reader.make_graph(graph_xml, legacy_keys, legacy_defaults)
    )
    assert _graph_state(next(reader(string=GRAPHML))) == _graph_state(
        next(nx.readwrite.GraphMLReader()(string=GRAPHML))
    )


def test_graphml_reader_add_node_and_edge_accept_fnx_graphs():
    root = ElementTree.fromstring(GRAPHML)  # nosec B314: fixed test fixture
    reader = fnx.readwrite.GraphMLReader()
    keys, defaults = reader.find_graphml_keys(root)
    graph_xml = root.find(f"{{{reader.NS_GRAPHML}}}graph")
    node_xml = graph_xml.find(f"{{{reader.NS_GRAPHML}}}node")
    edge_xml = graph_xml.find(f"{{{reader.NS_GRAPHML}}}edge")
    graph = fnx.MultiGraph()

    reader.add_node(graph, node_xml, keys, defaults)
    graph.add_node("b")
    reader.add_edge(graph, edge_xml, keys)

    assert dict(graph.nodes["a"]) == {"label": "alpha"}
    assert graph["a"]["b"][0]["weight"] == 7


def _ordered_graphml_state(graph):
    options = {"keys": True} if graph.is_multigraph() else {}
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        dict(graph.graph),
        list(graph.nodes(data=True)),
        list(graph.edges(data=True, **options)),
        [(node, list(graph.adj[node])) for node in graph],
    )


def _forbid_upstream_graphml(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("GraphML decoding delegated to NetworkX")

    monkeypatch.setattr(nx, "parse_graphml", forbidden)
    monkeypatch.setattr(nx, "read_graphml", forbidden)
    monkeypatch.setattr(nx.readwrite.graphml, "GraphMLReader", forbidden)


_OWNED_GRAPHML_CASES = {
    "typed-defaults": (
        '<key id="n" for="node" attr.name="label" attr.type="string">'
        '<default>untitled</default></key>'
        '<key id="e" for="edge" attr.name="weight" attr.type="long">'
        '<default>9007199254740993</default></key>'
        '<key id="b" for="graph" attr.name="enabled" attr.type="boolean"/>'
        '<graph edgedefault="directed"><data key="b">TRUE</data>'
        '<node id="01"><data key="n">  A &amp; B  </data></node><node id="2"/>'
        '<edge source="01" target="2" id="007"/></graph>'
    ),
    "parallel-lexical-ids": (
        '<graph edgedefault="undirected"><node id="01"/><node id="2"/>'
        '<edge source="01" target="2" id="01"/>'
        '<edge source="01" target="2" id="1"/></graph>'
    ),
    "converted-node-collisions": (
        '<graph edgedefault="directed"><node id="01"/><node id="1"/>'
        '<node id="2"/><edge source="01" target="2"/>'
        '<edge source="1" target="2"/></graph>'
    ),
    "duplicate-edge-id": (
        '<key id="w" for="edge" attr.name="weight" attr.type="double"/>'
        '<graph edgedefault="undirected"><node id="1"/><node id="2"/>'
        '<edge source="1" target="2" id="7"><data key="w">2.5</data></edge>'
        '<edge source="2" target="1" id="7"><data key="w">4.5</data></edge></graph>'
    ),
    "edge-data-key-and-id": (
        '<key id="k" for="edge" attr.name="key" attr.type="string"/>'
        '<key id="i" for="edge" attr.name="id" attr.type="string"/>'
        '<graph edgedefault="directed"><node id="1"/><node id="2"/>'
        '<edge source="1" target="2" id="007"><data key="i">data-id</data>'
        '<data key="k">data-key</data></edge></graph>'
    ),
    "implicit-nodes-and-late-declaration": (
        '<graph edgedefault="undirected"><node id="1"/>'
        '<edge source="1" target="3"/><node id="2"/>'
        '<edge source="4" target="2"/><node id="3"/></graph>'
    ),
}


@pytest.mark.parametrize("body", _OWNED_GRAPHML_CASES.values(), ids=_OWNED_GRAPHML_CASES)
@pytest.mark.parametrize("node_type", [str, int])
@pytest.mark.parametrize("edge_key_type", [str, int])
@pytest.mark.parametrize("force_multigraph", [False, True])
@pytest.mark.parametrize("entry", ["parse", "read", "reader"])
def test_configurable_graphml_decoding_is_owned(
    body, node_type, edge_key_type, force_multigraph, entry, monkeypatch
):
    payload = '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">' + body + '</graphml>'
    options = dict(node_type=node_type, edge_key_type=edge_key_type,
                   force_multigraph=force_multigraph)
    expected = _ordered_graphml_state(nx.parse_graphml(payload, **options))
    _forbid_upstream_graphml(monkeypatch)
    if entry == "parse":
        actual = fnx.parse_graphml(payload, **options)
    elif entry == "read":
        stream = io.BytesIO(payload.encode())
        actual = fnx.read_graphml(stream, **options)
        assert not stream.closed
    else:
        actual = next(fnx.readwrite.GraphMLReader(**options)(string=payload))
    assert _ordered_graphml_state(actual) == expected
    assert type(actual) in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)


def test_owned_graphml_conversion_callbacks_keep_order_and_errors(monkeypatch):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="directed"><node id="b"/><node id="a"/>'
        '<edge source="b" target="a" id="01"/>'
        '<edge source="a" target="c" id="other"/></graph></graphml>'
    )

    def convert(events):
        def node(value):
            events.append(("node", value))
            return ("converted", value)

        def key(value):
            events.append(("key", value))
            return int(value)  # ValueError retains the original lexical ID.

        return dict(node_type=node, edge_key_type=key, force_multigraph=True)

    expected_events = []
    expected = nx.parse_graphml(payload, **convert(expected_events))
    _forbid_upstream_graphml(monkeypatch)
    actual_events = []
    actual = fnx.parse_graphml(payload, **convert(actual_events))
    assert actual_events == expected_events
    assert _ordered_graphml_state(actual) == _ordered_graphml_state(expected)


@pytest.mark.parametrize("as_file", [False, True])
def test_owned_graphml_missing_namespace_recovery(as_file, monkeypatch):
    payload = '<graphml><graph edgedefault="directed"><node id="1"/></graph></graphml>'
    expected = nx.parse_graphml(payload, node_type=int)
    _forbid_upstream_graphml(monkeypatch)
    actual = (fnx.read_graphml(io.BytesIO(payload.encode()), node_type=int)
              if as_file else fnx.parse_graphml(payload, node_type=int))
    assert _ordered_graphml_state(actual) == _ordered_graphml_state(expected)


@pytest.mark.parametrize("entry", ["parse", "read"])
def test_owned_graphml_does_not_ignore_errors_in_later_graphs(entry, monkeypatch):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="undirected"><node id="ok"/></graph>'
        '<graph edgedefault="undirected"><node id="bad">'
        '<data key="unknown">value</data></node></graph></graphml>'
    )
    reference = nx.parse_graphml if entry == "parse" else nx.read_graphml
    with pytest.raises(nx.NetworkXError) as expected:
        reference(payload if entry == "parse" else io.BytesIO(payload.encode()))
    _forbid_upstream_graphml(monkeypatch)
    parser = fnx.parse_graphml if entry == "parse" else fnx.read_graphml
    with pytest.raises(fnx.NetworkXError) as actual:
        parser(payload if entry == "parse" else io.BytesIO(payload.encode()))
    assert str(actual.value) == str(expected.value)


def test_owned_graphml_reader_defers_callbacks_between_graphs(monkeypatch):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="undirected"><node id="1"/></graph>'
        '<graph edgedefault="directed"><node id="2"/></graph></graphml>'
    )
    expected_events, actual_events = [], []

    def converter(events):
        def node(value):
            events.append(value)
            return int(value)
        return node

    expected = nx.readwrite.GraphMLReader(node_type=converter(expected_events))(string=payload)
    _forbid_upstream_graphml(monkeypatch)
    actual = fnx.readwrite.GraphMLReader(node_type=converter(actual_events))(string=payload)
    assert expected_events == actual_events == []
    for expected_graph in expected:
        assert _ordered_graphml_state(next(actual)) == _ordered_graphml_state(expected_graph)
        assert actual_events == expected_events
    with pytest.raises(StopIteration):
        next(actual)
