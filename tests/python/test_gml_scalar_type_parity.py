"""Regression: the GML reader must type unquoted scalar attribute values the
way networkx does — bare integers as ``int``, bare reals as ``float``, quoted
values as ``str``.

The native Rust GML reader (used for the default ``label="label"`` path) used
to coerce *every* attribute value to a string: ``weight 2.5`` round-tripped
back as ``'2.5'`` (str) instead of ``2.5`` (float), and ``cap 7`` as ``'7'``
instead of ``7``. This silently corrupted every numeric attribute read from a
GML file (weighted kernels then saw strings). It escaped detection because the
round-trip identity test only compares attribute *keys* for the GML format,
never values. This locks the value types to nx's.
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


def _gml_lines(body):
    # split brackets onto their own tokens/lines so the reader tokenizes cleanly
    return body.replace("[", "[\n").replace("]", "\n]").split("\n")


def _node0_attrs(text):
    lines = _gml_lines(text)
    gn = nx.parse_gml(lines)
    gf = fnx.parse_gml(lines)
    nn = dict(gn.nodes(data=True))[list(gn.nodes())[0]]
    nf = dict(gf.nodes(data=True))[list(gf.nodes())[0]]
    return nn, nf


@pytest.mark.parametrize(
    "literal,expected_type,expected_value",
    [
        ("2.5", float, 2.5),
        ("7", int, 7),
        ("-3.5", float, -3.5),
        ("1.5e2", float, 150.0),
        ("007", int, 7),
        ("+4", int, 4),
        ('"2.5"', str, "2.5"),       # quoted -> string, not float
        ('"hello"', str, "hello"),
    ],
)
def test_gml_scalar_value_type_matches_networkx(literal, expected_type, expected_value):
    text = f'graph [ node [ id 0 label "0" v {literal} ] ]'
    nn, nf = _node0_attrs(text)
    # nx is the source of truth
    assert type(nn["v"]) is expected_type
    assert nn["v"] == expected_value
    # fnx must match nx exactly (type and value)
    assert type(nf["v"]) is type(nn["v"]), (
        f"{literal!r}: nx -> {type(nn['v']).__name__}, "
        f"fnx -> {type(nf['v']).__name__}"
    )
    assert nf["v"] == nn["v"]


def test_gml_edge_numeric_attrs_match_networkx():
    text = (
        'graph [ node [ id 0 label "0" ] node [ id 1 label "1" ] '
        'edge [ source 0 target 1 weight 2.5 cap 7 label "e" ] ]'
    )
    lines = _gml_lines(text)
    gn = nx.parse_gml(lines)
    gf = fnx.parse_gml(lines)
    en = gn.get_edge_data("0", "1")
    ef = gf.get_edge_data("0", "1")
    assert en == ef
    assert type(ef["weight"]) is float and ef["weight"] == 2.5
    assert type(ef["cap"]) is int and ef["cap"] == 7
    assert type(ef["label"]) is str and ef["label"] == "e"


def test_gml_numeric_weight_survives_roundtrip_for_weighted_kernel():
    # End-to-end: a graph written to GML and read back must still carry numeric
    # weights so a weighted kernel sees the real distances, not string '1.0'.
    G = fnx.Graph()
    G.add_edge(0, 1, weight=5.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(0, 2, weight=1.0)
    restored = fnx.parse_gml(list(fnx.generate_gml(G)))
    # nodes come back labelled by their string label; shortest 0->2 weighted is
    # the direct edge (1.0), not the 2-hop path (6.0) — only true if weights
    # are numeric.
    assert fnx.shortest_path_length(restored, "0", "2", weight="weight") == 1.0
    for _, _, d in restored.edges(data=True):
        assert isinstance(d["weight"], float)


def _gml_value_state(value):
    if isinstance(value, dict):
        return [(key, _gml_value_state(item)) for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [_gml_value_state(item) for item in value])
    if isinstance(value, float) and math.isnan(value):
        return ("float", "nan")
    return (type(value).__name__, value)


def _gml_graph_state(graph):
    edge_options = {"keys": True} if graph.is_multigraph() else {}
    return (
        graph.is_directed(), graph.is_multigraph(),
        _gml_value_state(graph.graph),
        _gml_value_state(list(graph.nodes(data=True))),
        _gml_value_state(list(graph.edges(data=True, **edge_options))),
    )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", ["parallel", "list", "singleton", "nested", "backslash", "nonfinite"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize(
    "parser", [fnx.parse_gml, fnx.readwrite.parse_gml, fnx.readwrite.gml.parse_gml],
    ids=["top-level", "readwrite", "gml-submodule"],
)
def test_parse_gml_preserves_full_document_values(graph_type, case, mode, parser):
    """Native projections may not silently replace the full GML data model."""
    source = getattr(nx, graph_type)()
    first = r"C:\network\first" if case == "backslash" else "first"
    source.add_node("isolated")
    source.add_edge(first, "last", weight=3)
    if case == "parallel":
        source.add_edge(first, "last", weight=7)
    else:
        value = {
            "list": [2, 3, 5],
            "singleton": [9],
            "nested": {"items": [1, 2], "named": {"score": 4.5}},
            "backslash": r"C:\network\nodes",
            "nonfinite": [float("inf"), float("-inf"), float("nan")],
        }[case]
        source.graph["values"] = value
        source.nodes[first]["values"] = value
        data = source[first]["last"][0] if source.is_multigraph() else source[first]["last"]
        data["values"] = value
    text = "\n".join(nx.generate_gml(source))
    expected = nx.parse_gml(text)
    with fnx.compatibility_mode(mode):
        actual = parser(text)
    assert _gml_graph_state(actual) == _gml_graph_state(expected)
    assert actual.mode == mode
    assert all(record["mode"] == mode for record in actual.decision_records())
    assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_parse_gml_canonical_simple_payload_keeps_native_route(mode, monkeypatch):
    source = fnx.DiGraph()
    source.add_nodes_from(["first", "last", "isolated"])
    source.add_edge("first", "last", weight=3)
    lines = list(fnx.generate_gml(source))
    expected = nx.parse_gml(lines)

    def no_fallback(*args, **kwargs):
        pytest.fail("canonical lossless GML must retain the native reader")

    monkeypatch.setattr(nx, "parse_gml", no_fallback)
    with fnx.compatibility_mode(mode):
        actual = fnx.parse_gml(iter(lines))
    assert _gml_graph_state(actual) == _gml_graph_state(expected)
    assert actual.mode == mode


def test_parse_gml_hardened_repair_keeps_native_decision_ledger():
    text = "graph [ node [ id 0 ] ]"
    with fnx.compatibility_mode("strict"):
        with pytest.raises(fnx.NetworkXError, match="has no 'label' attribute"):
            fnx.parse_gml(text)
    with fnx.compatibility_mode("hardened"):
        with pytest.warns(RuntimeWarning, match="missing label"):
            actual = fnx.parse_gml(text)
    assert list(actual) == ["0"]
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())
