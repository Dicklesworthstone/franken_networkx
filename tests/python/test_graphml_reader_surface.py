"""Oracle coverage for GraphMLReader's public parser surface.

br-r37-c1-ozpfa
"""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

import franken_networkx as fnx


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
