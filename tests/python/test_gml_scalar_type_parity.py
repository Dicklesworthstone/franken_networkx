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

from io import BytesIO, StringIO
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
def test_parse_gml_canonical_simple_payload_does_not_delegate(mode, monkeypatch):
    source = fnx.DiGraph()
    source.add_nodes_from(["first", "last", "isolated"])
    source.add_edge("first", "last", weight=3)
    lines = list(fnx.generate_gml(source))
    expected = nx.parse_gml(lines)

    _forbid_gml_delegation(monkeypatch)
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


def _forbid_gml_delegation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("complete GML decoding must be owned")

    for module in (nx, nx.readwrite.gml):
        monkeypatch.setattr(module, "parse_gml", forbidden)
        monkeypatch.setattr(module, "read_gml", forbidden)
    monkeypatch.setattr(nx.readwrite.gml, "parse_gml_lines", forbidden)
    monkeypatch.setattr(fnx.readwrite, "_from_nx_graph", forbidden)


def _gml_outcome(function, *args, **kwargs):
    try:
        return ("return", _gml_graph_state(function(*args, **kwargs)))
    except Exception as exc:
        return ("raise", type(exc).__name__, exc.args)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("label", [None, "label"])
@pytest.mark.parametrize("entrypoint", ["top", "readwrite", "submodule", "read"])
def test_owned_gml_wide_ids_and_edges_before_nodes(
    directed, multigraph, label, entrypoint, monkeypatch
):
    wide = 2**120 + 17
    text = (
        f"graph [ directed {int(directed)} multigraph {int(multigraph)} "
        f"edge [ source {wide} target {-wide} weight 3.5 ] "
        f'node [ id {-wide} label "second" ] '
        f'node [ id {wide} label "first" ] ]'
    )
    expected = nx.parse_gml(text, label=label)
    _forbid_gml_delegation(monkeypatch)
    if entrypoint == "read":
        actual = fnx.read_gml(BytesIO(text.encode("ascii")), label=label)
    else:
        reader = {
            "top": fnx.parse_gml,
            "readwrite": fnx.readwrite.parse_gml,
            "submodule": fnx.readwrite.gml.parse_gml,
        }[entrypoint]
        actual = reader(text, label=label)
    assert _gml_graph_state(actual) == _gml_graph_state(expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_owned_gml_complete_value_model_without_native_or_networkx_reparse(graph_type, monkeypatch):
    graph = getattr(nx, graph_type)()
    graph.graph["nested"] = {"values": [1, 2.5, "&#169;"], "single": [7]}
    graph.add_node("isolated", empty_list=[], empty_tuple=())
    graph.add_edge("second", "first", weight=2**100 + 1, text=r"C:\graph\edge")
    if graph.is_multigraph():
        graph.add_edge("second", "first", key="parallel", values=[1, 2])
    text = "\n".join(nx.generate_gml(graph))
    expected = nx.parse_gml(text)
    _forbid_gml_delegation(monkeypatch)

    def no_reparse(*args, **kwargs):
        raise AssertionError("strict complete decoding must not parse/write/reparse")

    monkeypatch.setattr(fnx._fnx, "read_gml", no_reparse)
    monkeypatch.setattr(fnx.readwrite, "generate_gml", no_reparse)
    actual = fnx.parse_gml(text)
    assert _gml_graph_state(actual) == _gml_graph_state(expected)


_GML_GRAMMAR_CASES = [
    "",
    "graph [ ]",
    "graph [ ] graph [ ]",
    "graph 1",
    "graph [ node [ id 0 ] ]",
    'graph [ node [ label "a" ] ]',
    'graph [ node [ id 0 label "a" ] node [ id 0 label "b" ] ]',
    'graph [ node [ id 0 label "a" ] node [ id 1 label "a" ] ]',
    'graph [ node [ id 0 label "a" ] edge [ source 0 ] ]',
    'graph [ node [ id 0 label "a" ] edge [ source 1 target 2 ] ]',
    'graph [ node [ id 0 label "a" ] edge [ source 0 target 2 ] ]',
    'graph [ node [ id 0 label "a" ] edge [ source 0 target 0 ] edge [ source 0 target 0 ] ]',
    'graph [ multigraph 1 node [ id 0 label "a" ] edge [ source 0 target 0 key 2 ] edge [ source 0 target 0 key 2 ] ]',
    'graph [ node [ id 0 label a ] ]',
    'graph [ node [ id alpha label "a" ] edge [ source alpha target alpha ] ]',
    'graph [ node [ id 0 label "a" value INF ] ]',
    'graph [ node [ id 0 label "a" value +INF ] ]',
    'graph [ node [ id 0 label "a" value -INF ] ]',
    'graph [ node [ id 0 label "a" value NAN ] ]',
    'graph [ node [ id 0 label "a" value 1E+4 ] ]',
    'graph [ node [ id 0 label "a" value .5E-3 ] ]',
    'graph [ node [ id 0 label "a" value 2. ] ]',
    'graph [ node [ id 0 label "a" value "&amp;&quot;&#169;&#x1f680;&unknown;&#999999999;" ] ]',
    'graph [ node [ id 0 label "a" value "_networkx_list_start" value 7 ] ]',
    'graph [ node [ id 0 label "a" value [ inner 1 inner 2 ] ] ]',
    'graph [ node [ id 0 label "a" value "[]" other "()" ] ]',
    'graph [ node [ id 0 label "a" value true ] ]',
    'graph [ node [ id 0 label "a" value +NAN ] ]',
    'graph [ _bad 1 ]',
    'graph [ node [ id 0 label "a" ] ] @',
    'graph [ node [ id 0 label "a" ]',
    '] graph [ ]',
    'graph [ ] ]',
    'graph [ node [ id 0 label "a" note "a\nline\nends"\n] ]',
    'graph [ node [ id 0 label "a" note "unfinished\n\n] ]',
    '# header\ngraph [ # graph comment\nnode [ id 0 label "a#b" ] ]',
]


@pytest.mark.parametrize("text", _GML_GRAMMAR_CASES)
@pytest.mark.parametrize("label", [None, "label"])
def test_owned_gml_grammar_and_failure_boundaries(text, label, monkeypatch):
    expected = _gml_outcome(nx.parse_gml, text, label=label)
    _forbid_gml_delegation(monkeypatch)
    actual = _gml_outcome(fnx.parse_gml, text, label=label)
    assert actual == expected


@pytest.mark.parametrize("failure", [None, ValueError, RuntimeError])
@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("suffix", ["", " @"])
def test_owned_gml_destringizer_order_and_errors(failure, falsey, suffix, monkeypatch):
    text = (
        'graph [ note "before" node [ id 0 label "0" nested [ value "1" ] ] '
        'node [ id 1 label "1" ] edge [ source 0 target 1 note "after" ] ]'
    ) + suffix
    outcomes = []
    for module in (nx, fnx):
        events = []

        class Convert:
            def __bool__(self):
                events.append("bool")
                return not falsey

            def __call__(self, value):
                events.append(("convert", value))
                if value == "1" and failure is not None:
                    raise failure("conversion stopped")
                try:
                    return int(value)
                except ValueError:
                    return value

        if module is fnx:
            _forbid_gml_delegation(monkeypatch)
        outcomes.append((_gml_outcome(module.parse_gml, text, destringizer=Convert()), events))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("suffix", [".gml", ".gml.gz", ".gml.bz2"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_owned_gml_compressed_roundtrip(graph_type, suffix, tmp_path, monkeypatch):
    graph = getattr(nx, graph_type)()
    graph.add_node("first", nested={"count": [3, 5]})
    graph.add_edge("second", "first", value=2**100)
    if graph.is_multigraph():
        graph.add_edge("second", "first", key="second-edge")
    path = tmp_path / ("complete" + suffix)
    nx.write_gml(graph, path)
    expected = nx.read_gml(path)
    _forbid_gml_delegation(monkeypatch)
    assert _gml_graph_state(fnx.read_gml(path)) == _gml_graph_state(expected)
    assert _gml_graph_state(fnx.read_gml(str(path))) == _gml_graph_state(expected)


@pytest.mark.parametrize("stream_type", [BytesIO, StringIO])
@pytest.mark.parametrize("text", ['graph [ node [ id 0 label "a" ] ]', 'graph [ @ ]'])
def test_owned_gml_stream_ownership_on_success_and_failure(stream_type, text, monkeypatch):
    expected = _gml_outcome(nx.read_gml, BytesIO(text.encode("ascii")))
    _forbid_gml_delegation(monkeypatch)
    stream = stream_type(text.encode("ascii") if stream_type is BytesIO else text)
    assert _gml_outcome(fnx.read_gml, stream) == expected
    assert not stream.closed


def test_owned_gml_reader_rejects_non_ascii_bytes(monkeypatch):
    payload = 'graph [ node [ id 0 label "café" ] ]'.encode("utf-8")
    expected = _gml_outcome(nx.read_gml, BytesIO(payload))
    _forbid_gml_delegation(monkeypatch)
    assert _gml_outcome(fnx.read_gml, BytesIO(payload)) == expected


@pytest.mark.parametrize(
    "body",
    [
        '__fnx_incompatible_future 1',
        'node [ id 0 label "a" __fnx_incompatible_future 1 ]',
        'node [ id 0 label "a" ] edge [ source 0 target 0 __fnx_incompatible_future 1 ]',
    ],
)
def test_owned_gml_rejects_incompatible_attribute_keys(body, monkeypatch):
    text = "graph [ " + body + " ]"
    expected = _gml_outcome(nx.parse_gml, text)
    assert expected[0:2] == ("raise", "NetworkXError")
    _forbid_gml_delegation(monkeypatch)
    assert _gml_outcome(fnx.parse_gml, text) == expected
    assert _gml_outcome(fnx.read_gml, BytesIO(text.encode("ascii"))) == expected


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("as_float", [False, True])
def test_owned_gml_equal_labels_preserve_type_and_relabel_order(
    directed, multigraph, as_float, monkeypatch
):
    text = (
        f"graph [ directed {int(directed)} multigraph {int(multigraph)} "
        + " ".join(
            f'node [ id {node} label "{float(node) if as_float else node}" ]'
            for node in range(3)
        )
        + " edge [ source 1 target 2 ] edge [ source 0 target 2 ] ]"
    )
    destringizer = nx.readwrite.gml.literal_destringizer
    expected = nx.parse_gml(text, destringizer=destringizer)
    _forbid_gml_delegation(monkeypatch)
    actual = fnx.parse_gml(text, destringizer=destringizer)
    assert _gml_graph_state(actual) == _gml_graph_state(expected)
    assert [list(actual.adj[node]) for node in actual] == [list(expected.adj[node]) for node in expected]
    if directed:
        assert [list(actual.pred[node]) for node in actual] == [list(expected.pred[node]) for node in expected]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("scope", ["node", "edge"])
@pytest.mark.parametrize(
    "key", ["node_for_adding", "u_of_edge", "v_of_edge", "u_for_edge", "v_for_edge", "self", "attr", "weight"]
)
def test_owned_gml_attribute_keyword_binding_matches_networkx(
    directed, multigraph, scope, key, monkeypatch
):
    attribute = f"{key} 7"
    node_attribute = attribute if scope == "node" else ""
    edge_attribute = attribute if scope == "edge" else ""
    text = (
        f"graph [ directed {int(directed)} multigraph {int(multigraph)} "
        f'node [ id 0 label "a" {node_attribute} ] node [ id 1 label "b" ] '
        f"edge [ source 0 target 1 {edge_attribute} ] ]"
    )
    expected = _gml_outcome(nx.parse_gml, text)
    _forbid_gml_delegation(monkeypatch)
    assert _gml_outcome(fnx.parse_gml, text) == expected


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("edge_count", [0, 1, 2])
def test_owned_gml_direction_flag_callback_order(
    directed, multigraph, edge_count, monkeypatch
):
    text = (
        'graph [ directed "DIRECTED" multigraph "MULTIGRAPH" '
        'node [ id 0 label "a" ] node [ id 1 label "b" ] '
        + "edge [ source 0 target 1 ] " * edge_count
        + "]"
    )
    outcomes = []
    for module in (nx, fnx):
        events = []

        class Flag:
            def __init__(self, name, value):
                self.name, self.value = name, value

            def __bool__(self):
                events.append(("bool", self.name))
                return self.value

        def convert(value):
            events.append(("convert", value))
            if value == "DIRECTED":
                return Flag("directed", directed)
            if value == "MULTIGRAPH":
                return Flag("multigraph", multigraph)
            return value

        if module is fnx:
            _forbid_gml_delegation(monkeypatch)
        outcomes.append((_gml_outcome(module.parse_gml, text, destringizer=convert), events))
    assert outcomes[0] == outcomes[1]


def test_owned_gml_parser_retains_eager_byte_line_normalization(monkeypatch):
    events = []
    text = 'graph [\nnode [ id 0 label "a" ]\n]'
    expected = nx.parse_gml(text)

    def lines():
        events.append("input")
        yield text.encode("utf-8")
        events.append("end")

    def convert(value):
        events.append(("convert", value))
        return value

    _forbid_gml_delegation(monkeypatch)
    actual = fnx.parse_gml(lines(), destringizer=convert)
    assert _gml_graph_state(actual) == _gml_graph_state(expected)
    assert events == ["input", "end", ("convert", "a")]
