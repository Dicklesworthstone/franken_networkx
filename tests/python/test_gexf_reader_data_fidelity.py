"""GEXF interchange must preserve data before graph construction changes shape."""

from io import BytesIO, StringIO

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import readwrite


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _payload(graph, *, version="1.2draft", encoding="utf-8"):
    stream = BytesIO()
    nx.write_gexf(graph, stream, version=version, encoding=encoding)
    return stream.getvalue()


def _assert_same(actual, expected):
    assert type(actual).__name__ == type(expected).__name__
    assert dict(actual.graph) == expected.graph
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    if expected.is_multigraph():
        assert list(actual.edges(keys=True, data=True)) == list(
            expected.edges(keys=True, data=True)
        )
    else:
        assert list(actual.edges(data=True)) == list(expected.edges(data=True))


def _forbid_gexf_delegation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Complete GEXF decoding must not delegate or copy a NetworkX graph")

    monkeypatch.setattr(nx, "read_gexf", forbidden)
    monkeypatch.setattr(nx.readwrite.gexf, "read_gexf", forbidden)
    monkeypatch.setattr(nx.readwrite.gexf, "GEXFReader", forbidden)
    monkeypatch.setattr(readwrite, "_from_nx_graph", forbidden)


def _rich_graph(graph_type, version="1.2draft"):
    graph = getattr(nx, graph_type)(name="Measurements")
    graph.add_node(
        "01", label="First", count=2**80 + 1,
        viz={
            "color": {"r": 1, "g": 2, "b": 3, "a": 0.5},
            "size": 2.5,
            "position": {"x": 1.0, "y": 2.0, "z": 3.0},
        },
    )
    graph.add_node("1", label="Second", history=[(1, 0.0, 1.0), (2, 1.0, 2.0)])
    graph.add_node("9", label="Last", start=0.0, end=3.0)
    interval_key = "slices" if version == "1.1draft" else "spells"
    graph.nodes["9"][interval_key] = [(0.0, 3.0)]
    graph.add_edge(
        "01", "9", weight=2.5, count=-(2**80 + 3),
        history=[(3, 0.0, 2.0), (4, 2.0, 3.0)],
        **{interval_key: [(0.0, 3.0)]},
    )
    graph.add_edge("1", "9", weight=3.5)
    if graph.is_multigraph():
        graph.add_edge("01", "9", key=1, weight=4.5, note="parallel")
    return graph


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("version", ("1.1draft", "1.2draft", "1.3"))
@pytest.mark.parametrize("entrypoint", ("top_level", "readwrite", "gexf", "parse"))
def test_rich_gexf_data_matches_networkx(monkeypatch, graph_type, version, entrypoint):
    payload = _payload(_rich_graph(graph_type, version), version=version)
    expected = nx.read_gexf(BytesIO(payload), version=version)
    _forbid_gexf_delegation(monkeypatch)
    if entrypoint == "parse":
        actual = readwrite.parse_gexf(payload, version=version)
    else:
        reader = {
            "top_level": fnx.read_gexf,
            "readwrite": readwrite.read_gexf,
            "gexf": readwrite.gexf.read_gexf,
        }[entrypoint]
        actual = reader(BytesIO(payload), version=version)
    _assert_same(actual, expected)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
@pytest.mark.parametrize("relabel", (False, True))
def test_node_type_runs_before_parallel_edge_detection(graph_type, mode, relabel):
    graph = getattr(nx, graph_type)()
    graph.add_nodes_from([("01", {"label": "First"}), ("1", {"label": "Second"}),
                          ("9", {"label": "Last"})])
    if graph.is_multigraph():
        graph.add_edge("01", "9", key="left", weight=2.5)
        graph.add_edge("1", "9", key="right", weight=3.5)
    else:
        graph.add_edge("01", "9", weight=2.5)
        graph.add_edge("1", "9", weight=3.5)
    payload = _payload(graph)
    expected = nx.read_gexf(BytesIO(payload), node_type=int, relabel=relabel)
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), node_type=int, relabel=relabel, **options)
    _assert_same(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 2
    if mode is not None:
        assert actual.mode == mode
        assert actual.decision_records()
        assert all(record["mode"] == mode for record in actual.decision_records())
        assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("suffix", (".gexf.gz", ".gexf.bz2"))
def test_compressed_writer_reader_roundtrip(graph_type, suffix, tmp_path):
    source = _rich_graph(graph_type)
    graph = getattr(fnx, graph_type)()
    graph.graph.update(source.graph)
    graph.add_nodes_from(source.nodes(data=True))
    if source.is_multigraph():
        graph.add_edges_from(source.edges(keys=True, data=True))
    else:
        graph.add_edges_from(source.edges(data=True))
    path = tmp_path / ("measurements" + suffix)
    fnx.write_gexf(graph, path)
    _assert_same(fnx.read_gexf(path), nx.read_gexf(path))
    _assert_same(fnx.read_gexf(str(path)), nx.read_gexf(path))


@pytest.mark.parametrize("stream_type", (BytesIO, StringIO))
def test_caller_owned_streams_stay_open(stream_type):
    payload = _payload(_rich_graph("DiGraph"))
    stream = stream_type(payload if stream_type is BytesIO else payload.decode())
    _assert_same(fnx.read_gexf(stream), nx.read_gexf(BytesIO(payload)))
    assert not stream.closed


@pytest.mark.parametrize("encoding", ("iso-8859-1", "utf-16"))
def test_xml_declared_encoding_is_respected(encoding):
    graph = nx.Graph()
    graph.add_edge("café", "élève")
    payload = _payload(graph, encoding=encoding)
    _assert_same(fnx.read_gexf(BytesIO(payload)), nx.read_gexf(BytesIO(payload)))


def _document(body, direction="undirected"):
    return (
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">'
        f'<graph defaultedgetype="{direction}">{body}</graph></gexf>'
    ).encode()


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_mutual_edges_preserve_reverse_arcs(mode):
    payload = _document(
        '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="both" source="a" target="b" type="mutual" weight="2.5"/></edges>',
        direction="directed",
    )
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), **options)
    _assert_same(actual, nx.read_gexf(BytesIO(payload)))
    assert actual.number_of_edges() == 2
    if mode is not None:
        assert actual.mode == mode
        assert all(record["action"] == "allow" for record in actual.decision_records())


def test_reverse_undirected_pairs_preserve_parallel_edges():
    payload = _document(
        '<nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge id="first" source="a" target="b" weight="2"/>'
        '<edge id="second" source="b" target="a" weight="3"/></edges>'
    )
    actual = fnx.read_gexf(BytesIO(payload))
    _assert_same(actual, nx.read_gexf(BytesIO(payload)))
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 2


def test_node_and_edge_attribute_ids_have_separate_scopes():
    payload = _document(
        '<attributes class="node"><attribute id="0" title="rank" type="long"/></attributes>'
        '<attributes class="edge"><attribute id="0" title="color" type="string"/></attributes>'
        '<nodes><node id="a"><attvalues><attvalue for="0" value="7"/></attvalues></node>'
        '<node id="b"/></nodes><edges><edge source="a" target="b">'
        '<attvalues><attvalue for="0" value="blue"/></attvalues></edge></edges>'
    )
    _assert_same(fnx.read_gexf(BytesIO(payload)), nx.read_gexf(BytesIO(payload)))


@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_clean_dynamic_data_retains_runtime_policy(mode):
    graph = nx.DiGraph()
    graph.add_node("a", history=[(1, 0.0, 1.0), (2, 1.0, 2.0)],
                   viz={"size": 2.5})
    graph.add_node("b", spells=[(0.0, 2.0)])
    graph.add_edge("a", "b", history=[(3, 0.0, 2.0)])
    payload = _payload(graph)
    actual = fnx.read_gexf(BytesIO(payload), mode=mode)
    _assert_same(actual, nx.read_gexf(BytesIO(payload)))
    assert actual.mode == mode
    assert actual.decision_records()
    assert all(record["mode"] == mode for record in actual.decision_records())
    assert all(record["action"] == "allow" for record in actual.decision_records())


def _policy_payload():
    return _document(
        '<attributes class="node"><attribute id="rank" title="rank" type="long"/></attributes>'
        '<nodes><node id="0" label="Zero"><attvalues>'
        '<attvalue for="rank" value="5"/></attvalues></node>'
        '<node id="1" label="One"/></nodes>'
        '<edges><edge id="edge" source="0" target="1"/></edges>'
    )


@pytest.mark.parametrize("old,new", (
    (b'defaultedgetype="undirected"', b'defaultedgetype="bogus"'),
    (b'node id="0"', b'node'),
    (b' target="1"', b''),
    (b'attribute id="rank"', b'attribute'),
    (b'for="rank"', b'for="missing"'),
    (b'class="node"', b'class="edge"'),
    (b'value="5"', b'value="1_000"'),
))
def test_rich_features_do_not_bypass_native_recovery_rules(old, new):
    payload = _policy_payload().replace(old, new)
    for options in ({}, {"mode": "strict"}):
        with pytest.raises(OSError):
            fnx.read_gexf(BytesIO(payload), **options)
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


def test_wide_integer_recovery_still_follows_explicit_native_policy():
    payload = _policy_payload().replace(b'value="5"', f'value="{2**80 + 1}"'.encode())
    with pytest.raises(OSError, match="expected=integer"):
        fnx.read_gexf(BytesIO(payload), mode="strict")
    with fnx.compatibility_mode("hardened"):
        actual = fnx.read_gexf(BytesIO(payload))
    assert actual.nodes["0"]["rank"] == str(2**80 + 1)
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


def test_recovered_node_type_conversion_preserves_policy():
    payload = _policy_payload().replace(b'defaultedgetype="undirected"', b'defaultedgetype="bogus"')
    actual = fnx.read_gexf(BytesIO(payload), node_type=int, mode="hardened")
    assert list(actual) == [0, 1]
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


def test_recovered_label_merges_fail_instead_of_discarding_edges():
    payload = _document(
        '<nodes><node id="01"/><node id="1"/><node id="9"/></nodes>'
        '<edges><edge source="01" target="9"/><edge source="1" target="9"/></edges>',
        direction="bogus",
    )
    with pytest.raises(fnx.NetworkXNotImplemented, match="merging node_type"):
        fnx.read_gexf(BytesIO(payload), node_type=int, mode="hardened")


def test_plain_static_document_keeps_native_decoder(monkeypatch):
    def unexpected_decoder(*args, **kwargs):
        pytest.fail("Plain static GEXF should use its native decoder")

    payload = _payload(nx.path_graph(3))
    monkeypatch.setattr(readwrite, "_read_gexf_owned", unexpected_decoder)
    _assert_same(fnx.read_gexf(BytesIO(payload)), nx.read_gexf(BytesIO(payload)))


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_rich_documents_do_not_bypass_native_entity_validation(mode):
    payload = _policy_payload().replace(
        b"<gexf ", b'<!DOCTYPE gexf [<!ENTITY rank "5">]><gexf ', 1
    ).replace(b'value="5"', b'value="&rank;"')
    for reader in (fnx._fnx.read_gexf, fnx.read_gexf):
        with pytest.raises(OSError):
            reader(BytesIO(payload), mode=mode)


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_incompatible_edge_metadata_keeps_native_recovery(mode):
    payload = _document(
        '<attributes class="edge"><attribute id="x" '
        'title="__fnx_incompatible_future" type="string"/></attributes>'
        '<nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge source="a" target="b"><attvalues>'
        '<attvalue for="x" value="unsupported"/></attvalues></edge></edges>'
    )
    if mode != "hardened":
        with pytest.raises(OSError):
            fnx.read_gexf(BytesIO(payload), mode=mode)
    else:
        actual = fnx.read_gexf(BytesIO(payload), mode=mode)
        assert actual.number_of_edges() == 0
        assert actual.mode == "hardened"
        assert any(
            record["action"] == "full_validate" for record in actual.decision_records()
        )


_GEXF_NAMESPACES = {
    "1.1draft": "http://www.gexf.net/1.1draft",
    "1.2draft": "http://www.gexf.net/1.2draft",
    "1.3": "http://gexf.net/1.3",
}


def _reader_document(body, *, version="1.2draft", graph_attributes=""):
    namespace = _GEXF_NAMESPACES[version]
    return (
        f'<gexf xmlns="{namespace}" xmlns:viz="{namespace}/viz">'
        f'<graph {graph_attributes}>{body}</graph></gexf>'
    ).encode()


def test_owned_gexf_reader_is_exposed_on_submodule():
    assert readwrite.gexf.GEXFReader is readwrite.GEXFReader
    assert readwrite.GEXFReader is not nx.readwrite.gexf.GEXFReader


@pytest.mark.parametrize("initial_version", tuple(_GEXF_NAMESPACES))
@pytest.mark.parametrize("document_version", tuple(_GEXF_NAMESPACES))
def test_gexf_reader_namespace_selection_and_multigraph_state_persist(
    initial_version, document_version
):
    readers = [
        reader_type(version=initial_version)
        for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader)
    ]
    parallel = _reader_document(
        '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="first" source="a" target="b"/>'
        '<edge id="second" source="a" target="b"/></edges>',
        version=document_version,
    )
    single = _reader_document(
        '<nodes><node id="next" label="Next"/></nodes>', version=document_version
    )
    for payload in (parallel, single):
        streams = [BytesIO(payload), BytesIO(payload)]
        expected, actual = [reader(stream) for reader, stream in zip(readers, streams)]
        _assert_same(actual, expected)
        assert actual.is_multigraph()
        assert not any(stream.closed for stream in streams)
        assert readers[1].version == readers[0].version
        assert readers[1].simple_graph is readers[0].simple_graph is False
        assert readers[1].xml.getroot().tag == readers[0].xml.getroot().tag


@pytest.mark.parametrize("version", tuple(_GEXF_NAMESPACES))
def test_gexf_nested_nodes_keep_conversion_order_and_parent_types(version):
    interval = (
        '<slices><slice start="2000" end="2001"/></slices>'
        if version == "1.1draft"
        else '<spells><spell start="2000" end="2001"/></spells>'
    )
    payload = _reader_document(
        '<nodes><node id="01" label="Root"><nodes>'
        '<node id="02" label="Child"><nodes>'
        '<node id="03" label="Leaf" start="2000" end="2001">'
        '<parents><parent for="01"/><parent for="02"/></parents>'
        + interval +
        '<viz:color r="1" g="2" b="3"/><viz:size value="2.5"/>'
        '<viz:thickness value="0.5"/><viz:shape shape="image" uri="asset.png"/>'
        '<viz:position x="2"/></node></nodes></node></nodes></node>'
        '<node id="04" label="Peer" pid="01"/></nodes>'
        '<edges><edge id="link" source="03" target="04"/></edges>',
        version=version, graph_attributes='timeformat="date" mode="dynamic"',
    )
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        calls = []

        def node_type(value):
            calls.append(value)
            return int(value)

        graph = reader_type(node_type=node_type, version=version)(BytesIO(payload))
        outcomes.append((graph, calls))
    _assert_same(outcomes[1][0], outcomes[0][0])
    assert outcomes[1][1] == outcomes[0][1] == ["01", "02", "03", "04", "03", "04"]
    graph = outcomes[1][0]
    assert list(graph) == [3, 2, 1, 4]
    assert graph.nodes[3]["pid"] == 2
    assert graph.nodes[4]["pid"] == "01"
    assert graph.nodes[3]["parents"] == ["01", "02"]
    assert graph.nodes[3]["viz"]["position"] == {"x": 2.0, "y": 0.0, "z": 0.0}


@pytest.mark.parametrize("kind,value", [
    ("integer", "123"), ("long", str(2**90 + 1)), ("int", "17"),
    ("float", "2.5"), ("double", "1e200"), ("string", "a &amp; b"),
    ("anyURI", "urn:example:test"), ("liststring", "[a,b]"),
    ("boolean", "true"), ("boolean", "True"), ("boolean", "false"),
    ("boolean", "False"), ("boolean", "0"), ("boolean", "1"),
])
def test_gexf_reader_scalar_values_and_defaults_keep_types(kind, value):
    payload = _reader_document(
        f'<attributes class="node"><attribute id="x" title="value" type="{kind}">'
        f'<default>{value}</default></attribute></attributes>'
        '<nodes><node id="a"><attvalues>'
        f'<attvalue for="x" value="{value}"/></attvalues></node>'
        '<node id="b"/></nodes>'
    )
    expected = nx.readwrite.gexf.GEXFReader()(BytesIO(payload))
    actual = readwrite.GEXFReader()(BytesIO(payload))
    _assert_same(actual, expected)
    assert type(actual.nodes["a"]["value"]) is type(expected.nodes["a"]["value"])
    assert type(actual.graph["node_default"]["value"]) is type(
        expected.graph["node_default"]["value"]
    )
    assert "value" not in actual.nodes["b"]


@pytest.mark.parametrize("timeformat,start,end", [
    ("double", "0.5", "1.5"), ("long", "1", "2"),
    ("date", "2001-01-01", "2002-01-01"),
])
def test_gexf_reader_dynamic_attributes_keep_order_and_separate_defaults(timeformat, start, end):
    payload = _reader_document(
        '<attributes class="node" mode="dynamic">'
        '<attribute id="same" title="history" type="integer"><default>7</default></attribute>'
        '</attributes><attributes class="edge" mode="static">'
        '<attribute id="same" title="note" type="string"><default>unused</default></attribute>'
        '</attributes><nodes><node id="a"><attvalues>'
        f'<attvalue for="same" value="2" start="{start}" end="{end}"/>'
        f'<attvalue for="same" value="3" start="{start}" end="{end}"/>'
        '</attvalues></node><node id="b"/></nodes>'
        '<edges><edge source="a" target="b"><attvalues>'
        '<attvalue for="same" value="edge"/><attvalue for="weight" value="4.5"/>'
        '</attvalues></edge></edges>',
        graph_attributes=f'timeformat="{timeformat}" mode="dynamic" start="raw-start" end="raw-end"',
    )
    expected = nx.readwrite.gexf.GEXFReader()(BytesIO(payload))
    actual = readwrite.GEXFReader()(BytesIO(payload))
    _assert_same(actual, expected)
    assert len(actual.nodes["a"]["history"]) == 2
    assert actual.graph["node_default"] == {"history": 7}
    assert actual.graph["edge_default"] == {"note": "unused"}
    assert actual.graph["start"] == "raw-start"
    assert actual["a"]["b"]["weight"] == 4.5


@pytest.mark.parametrize("key_values", [(7, 7), (7, 8)])
def test_gexf_reader_detects_parallelism_before_converted_key_collision(key_values):
    payload = _reader_document(
        '<attributes class="edge"><attribute id="k" title="networkx_key" type="long"/></attributes>'
        '<nodes><node id="01"/><node id="1"/><node id="9"/></nodes>'
        '<edges><edge id="first" source="01" target="9"><attvalues>'
        f'<attvalue for="k" value="{key_values[0]}"/></attvalues></edge>'
        '<edge id="second" source="1" target="9"><attvalues>'
        f'<attvalue for="k" value="{key_values[1]}"/></attvalues></edge></edges>'
    )
    expected = nx.readwrite.gexf.GEXFReader(node_type=int)(BytesIO(payload))
    actual = readwrite.GEXFReader(node_type=int)(BytesIO(payload))
    _assert_same(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == len(set(key_values))
    assert actual[1][9][key_values[1]]["id"] == "second"


def test_gexf_reader_hooks_can_replace_later_node_and_edge_hooks():
    payload = _reader_document(
        '<nodes><node id="parent"><nodes><node id="child"/></nodes></node>'
        '<node id="next"/></nodes><edges><edge source="child" target="next"/></edges>'
    )
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        events = []

        class RebindingReader(reader_type):
            def add_node(self, graph, element, attributes, node_pid=None):
                events.append(("first-node", element.get("id")))

                def later_node(graph, element, attributes, node_pid=None):
                    events.append(("later-node", element.get("id")))
                    return reader_type.add_node(self, graph, element, attributes, node_pid)

                def later_edge(graph, element, attributes):
                    events.append(("later-edge", element.get("source"), element.get("target")))
                    return reader_type.add_edge(self, graph, element, attributes)

                self.add_node = later_node
                self.add_edge = later_edge
                return reader_type.add_node(self, graph, element, attributes, node_pid)

        graph = RebindingReader()(BytesIO(payload))
        outcomes.append((graph, events))
    _assert_same(outcomes[1][0], outcomes[0][0])
    assert outcomes[1][1] == outcomes[0][1] == [
        ("first-node", "parent"), ("later-node", "child"), ("later-node", "next"),
        ("later-edge", "child", "next"),
    ]


def test_gexf_reader_custom_scalar_conversion_and_decoding_hooks():
    payload = _reader_document(
        '<attributes class="node"><attribute id="x" title="number" type="custom">'
        '<default>0</default></attribute></attributes><nodes>'
        '<node id="a"><attvalues><attvalue for="x" value="7"/></attvalues></node></nodes>'
    )
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        events = []

        class CustomReader(reader_type):
            def construct_types(self):
                super().construct_types()

                def convert(value):
                    events.append(("convert", value))
                    return ("converted", int(value))

                self.python_type["custom"] = convert

            def decode_attr_elements(self, definitions, element):
                events.append(("decode", element.get("id")))
                data = super().decode_attr_elements(definitions, element)
                data["hook"] = True
                return data

        graph = CustomReader()(BytesIO(payload))
        outcomes.append((graph, events))
    _assert_same(outcomes[1][0], outcomes[0][0])
    assert outcomes[1][1] == outcomes[0][1] == [
        ("convert", "0"), ("decode", "a"), ("convert", "7"),
    ]


@pytest.mark.parametrize("scope", ["node", "edge"])
def test_gexf_reader_rejects_missing_attribute_titles_before_native_insertion(scope):
    values = '<attvalues><attvalue for="x" value="7"/></attvalues>'
    node_values = values if scope == "node" else ""
    edge_values = values if scope == "edge" else ""
    payload = _reader_document(
        f'<attributes class="{scope}"><attribute id="x" type="integer"/></attributes>'
        f'<nodes><node id="a">{node_values}</node><node id="b"/></nodes>'
        f'<edges><edge source="a" target="b">{edge_values}</edge></edges>'
    )
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        with pytest.raises(TypeError, match="keywords must be strings"):
            reader_type()(BytesIO(payload))


@pytest.mark.parametrize("title", ["key", "u_for_edge", "v_for_edge"])
@pytest.mark.parametrize("missing_first", [False, True])
def test_gexf_reader_invalid_edge_titles_preserve_keyword_error_precedence(title, missing_first):
    titles = [None, title] if missing_first else [title, None]
    definitions = []
    values = []
    for index, name in enumerate(titles):
        attribute_title = "" if name is None else f' title="{name}"'
        definitions.append(f'<attribute id="{index}"{attribute_title} type="integer"/>')
        values.append(f'<attvalue for="{index}" value="7"/>')
    payload = _reader_document(
        '<attributes class="edge">' + ''.join(definitions) + '</attributes>'
        '<nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge source="a" target="b"><attvalues>' + ''.join(values) +
        '</attvalues></edge></edges>'
    )
    message = "multiple values for keyword argument 'key'" if title == "key" else "keywords must be strings"
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        with pytest.raises(TypeError, match=message):
            reader_type()(BytesIO(payload))


def test_gexf_reader_failed_parallel_edge_retains_multigraph_state():
    payload = _reader_document(
        '<attributes class="edge"><attribute id="x" type="integer"/></attributes>'
        '<nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge source="a" target="b"/>'
        '<edge source="a" target="b"><attvalues>'
        '<attvalue for="x" value="7"/></attvalues></edge></edges>'
    )
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        reader = reader_type()
        with pytest.raises(TypeError, match="keywords must be strings"):
            reader(BytesIO(payload))
        assert reader.simple_graph is False
        assert reader(BytesIO(_reader_document('<nodes><node id="next"/></nodes>'))).is_multigraph()


@pytest.mark.parametrize("replacement_mode", ["dynamic", "static", None])
def test_gexf_reader_scalar_callback_can_replace_attribute_definition(replacement_mode):
    from xml.etree.ElementTree import fromstring

    element = fromstring(
        '<node xmlns="http://www.gexf.net/1.2draft"><attvalues>'
        '<attvalue for="k" value="7" start="2" end="3"/></attvalues></node>'
    )
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        reader = reader_type()
        reader.timeformat = "long"
        definitions = {
            "k": {
                "title": "before", "type": "integer",
                "mode": "dynamic" if replacement_mode == "static" else "static",
            },
        }

        def convert(value):
            if replacement_mode is None:
                del definitions["k"]
            else:
                definitions["k"] = {
                    "title": "after", "type": "string", "mode": replacement_mode,
                }
            return int(value)

        reader.python_type["integer"] = convert
        if replacement_mode is None:
            with pytest.raises(KeyError) as error:
                reader.decode_attr_elements(definitions, element)
            outcomes.append(error.value.args)
        else:
            outcomes.append(reader.decode_attr_elements(definitions, element))
    assert outcomes[0] == outcomes[1]
    if replacement_mode == "dynamic":
        assert outcomes[1] == {"before": [(7, 2, 3)]}
    elif replacement_mode == "static":
        assert outcomes[1] == {"before": 7}
    else:
        assert outcomes[1] == ("k",)


def _gexf_title_document(titles, *, scope="edge", directed=False, mutual=False):
    definitions = []
    values = []
    for index, title in enumerate(titles):
        title_attribute = "" if title is None else f' title="{title}"'
        definitions.append(f'<attribute id="{index}"{title_attribute} type="integer"/>')
        values.append(f'<attvalue for="{index}" value="7"/>')
    attributes = "<attvalues>" + "".join(values) + "</attvalues>"
    node_attributes = attributes if scope == "node" else ""
    edge_attributes = attributes if scope == "edge" else ""
    edge_type = 'type="mutual"' if mutual else ""
    direction = "directed" if directed else "undirected"
    return _reader_document(
        f'<attributes class="{scope}">' + "".join(definitions) + "</attributes>"
        f'<nodes><node id="a">{node_attributes}</node><node id="b"/></nodes>'
        f'<edges><edge id="e" source="a" target="b" {edge_type}>'
        f"{edge_attributes}</edge></edges>",
        graph_attributes=f'defaultedgetype="{direction}"',
    )


@pytest.mark.parametrize("scope", ["node", "edge"])
@pytest.mark.parametrize("title", ["self", "u_for_edge", "v_for_edge", "key"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("mutual", [False, True])
def test_gexf_reader_attribute_titles_preserve_method_binding(scope, title, directed, mutual):
    payload = _gexf_title_document([title], scope=scope, directed=directed, mutual=mutual)
    try:
        expected = nx.readwrite.gexf.GEXFReader()(BytesIO(payload))
    except TypeError as expected_error:
        with pytest.raises(TypeError) as actual_error:
            readwrite.GEXFReader()(BytesIO(payload))
        # Python and native bound methods have different qualification paths.
        expected_message = str(expected_error).partition("() ")[2]
        assert expected_message
        assert str(actual_error.value).endswith(expected_message)
    else:
        _assert_same(readwrite.GEXFReader()(BytesIO(payload)), expected)


@pytest.mark.parametrize(
    "titles",
    [
        ("self", "u_for_edge"), ("u_for_edge", "self"),
        ("self", "v_for_edge"), ("v_for_edge", "self"),
        ("self", "key"), ("key", "self"),
        ("self", None), (None, "self"),
        ("u_for_edge", "self", None), (None, "self", "u_for_edge"),
        ("self", None, "key"), ("key", None, "self"),
    ],
)
@pytest.mark.parametrize("directed", [False, True])
def test_gexf_reader_edge_title_binding_error_precedence(titles, directed):
    payload = _gexf_title_document(titles, directed=directed)
    errors = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        with pytest.raises(TypeError) as error:
            reader_type()(BytesIO(payload))
        message = str(error.value)
        errors.append(message.partition("() ")[2] if "() " in message else message)
    assert errors[1] == errors[0]


_GEXF_READER_ERRORS = (
    ("<attributes class=\"unknown\"/>", ""),
    ('<nodes><node id="a"><attvalues><attvalue for="missing" value="1"/></attvalues></node></nodes>', ""),
    ('<attributes class="node"><attribute id="x" title="x" type="boolean"/></attributes>'
     '<nodes><node id="a"><attvalues><attvalue for="x" value="TRUE"/></attvalues></node></nodes>', ""),
    ('<attributes class="node"><attribute id="x" title="x" type="unknown"><default>1</default></attribute></attributes>', ""),
    ('<attributes class="node"><attribute id="x" title="x" type="integer"/></attributes>'
     '<nodes><node id="a"><attvalues><attvalue for="x" value="bad"/></attvalues></node></nodes>', ""),
    ('<nodes><node id="a"><viz:color g="2" b="3"/></node></nodes>', ""),
    ('<nodes><node id="a"><viz:size value="large"/></node></nodes>', ""),
    ('<nodes><node id="a" start="1"/></nodes>', ""),
    ('<nodes><node id="a"><spells><spell start="1"/></spells></node></nodes>', 'timeformat="double"'),
    ('<nodes><node id="a"/></nodes><edges><edge source="a" target="b" type="directed"/></edges>', 'defaultedgetype="undirected"'),
    ('<nodes><node id="a"/></nodes><edges><edge source="a" target="b" type="undirected"/></edges>', 'defaultedgetype="directed"'),
    ('<nodes><node id="a"/></nodes><edges><edge source="a" target="b" weight="heavy"/></edges>', ""),
)


@pytest.mark.parametrize("body,graph_attributes", _GEXF_READER_ERRORS)
def test_gexf_reader_error_and_conversion_order_matches_oracle(body, graph_attributes):
    payload = _reader_document(body, graph_attributes=graph_attributes)
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        calls = []

        def convert(value):
            calls.append(value)
            return value

        reader = reader_type(node_type=convert)
        with pytest.raises(Exception) as error:
            reader(BytesIO(payload))
        outcomes.append((type(error.value).__name__, error.value.args, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("payload", [b"<gexf/>", b"<gexf><graph/></gexf>", b"<gexf>"])
def test_gexf_reader_invalid_document_retains_error_and_reader_state(payload):
    outcomes = []
    for reader_type in (nx.readwrite.gexf.GEXFReader, readwrite.GEXFReader):
        reader = reader_type(version="1.1draft")
        with pytest.raises(Exception) as error:
            reader(BytesIO(payload))
        outcomes.append((type(error.value).__name__, error.value.args, reader.version))
    assert outcomes[0] == outcomes[1]
