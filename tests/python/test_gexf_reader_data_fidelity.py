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


@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_gexf_scope_selects_one_direct_graph(directed, mode):
    direction = "directed" if directed else "undirected"
    opposite = "undirected" if directed else "directed"
    payload = f'''<gexf xmlns="http://www.gexf.net/1.2draft">
      <meta><graph defaultedgetype="{opposite}" name="metadata">
        <nodes><node id="metadata"/></nodes></graph></meta>
      <graph defaultedgetype="{direction}" name="selected"><nodes>
        <node id="a" label="A"><graph defaultedgetype="{opposite}">
          <nodes><node id="nested"/></nodes></graph></node>
        <node id="b" label="B"/></nodes>
        <edges><edge id="ab" source="a" target="b"/></edges></graph>
      <graph defaultedgetype="{opposite}" name="later">
        <attributes class="node"><attribute id="rank" title="rank" type="long"/>
        </attributes><nodes><node id="a"><attvalues>
          <attvalue for="rank" value="invalid"/></attvalues></node>
        <node id="later"/></nodes></graph></gexf>'''.encode()
    expected = nx.read_gexf(BytesIO(payload))
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), **options)
    _assert_same(actual, expected)
    assert list(actual) == ["a", "b"]
    if mode is not None:
        assert actual.mode == mode
        assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
@pytest.mark.parametrize("entrypoint", ("top_level", "readwrite", "gexf"))
def test_gexf_scope_does_not_merge_plain_graph_siblings(mode, entrypoint):
    payload = b'''<gexf xmlns="http://www.gexf.net/1.2draft">
      <graph name="first" defaultedgetype="undirected"><nodes>
        <node id="a" label="first A"/><node id="b" label="first B"/></nodes>
        <edges><edge id="ab" source="a" target="b"/></edges></graph>
      <graph name="second" defaultedgetype="undirected"><nodes>
        <node id="a" label="second A"/><node id="c" label="C"/></nodes>
        <edges><edge id="ac" source="a" target="c"/></edges></graph></gexf>'''
    expected = nx.read_gexf(BytesIO(payload))
    reader = {
        "top_level": fnx.read_gexf,
        "readwrite": readwrite.read_gexf,
        "gexf": readwrite.gexf.read_gexf,
    }[entrypoint]
    options = {} if mode is None else {"mode": mode}
    stream = BytesIO(payload)
    actual = reader(stream, **options)
    _assert_same(actual, expected)
    assert not stream.closed
    assert stream.getvalue() == payload


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
@pytest.mark.parametrize("node_type", (None, int))
def test_gexf_scope_preserves_parent_attributes_after_nested_nodes(mode, node_type):
    payload = b'''<gexf xmlns="http://www.gexf.net/1.2draft">
      <graph defaultedgetype="undirected"><attributes class="node">
        <attribute id="rank" title="rank" type="long"/></attributes><nodes>
        <node id="1" label="Parent"><attvalues><attvalue for="rank" value="11"/>
        </attvalues><nodes><node id="2" label="Child"><nodes>
          <node id="3" label="Leaf"/></nodes><attvalues>
          <attvalue for="rank" value="22"/></attvalues></node>
          <node id="4" label="Sibling"/></nodes></node></nodes>
        <edges><edge id="12" source="1" target="2"/></edges></graph></gexf>'''
    expected = nx.read_gexf(BytesIO(payload), node_type=node_type)
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), node_type=node_type, **options)
    _assert_same(actual, expected)
    if mode is not None:
        assert actual.mode == mode
        assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_gexf_scope_requires_a_direct_graph_child(mode):
    payload = b'''<gexf xmlns="http://www.gexf.net/1.2draft"><meta>
      <graph name="metadata" defaultedgetype="undirected"><nodes>
        <node id="hidden"/></nodes></graph></meta></gexf>'''
    with pytest.raises(nx.NetworkXError, match="No <graph> element"):
        nx.read_gexf(BytesIO(payload))
    options = {} if mode is None else {"mode": mode}
    with pytest.raises(fnx.NetworkXError, match="No <graph> element"):
        fnx.read_gexf(BytesIO(payload), **options)


_GEXF_RECORD_SCOPE_CASES = (
    "second-nodes", "second-edges", "direct-node", "direct-edge",
    "metadata-node", "metadata-edge", "foreign-node", "foreign-edge",
    "other-version-node", "other-version-edge", "unqualified-node",
    "unqualified-edge",
)


def _record_scope_document(case, directed=False):
    nodes = '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
    edges = '<edges><edge id="ab" source="a" target="b" weight="2"/></edges>'
    extra = ''
    if case == "second-nodes":
        extra = '<nodes><node id="a" label="Overwritten"/><node id="ghost"/></nodes>'
    elif case == "second-edges":
        extra = '<edges><edge id="extra" source="b" target="ghost"/></edges>'
    elif case in ("direct-node", "metadata-node"):
        extra = '<node id="a"/><node id="ghost"/>'
    elif case in ("direct-edge", "metadata-edge"):
        extra = '<edge id="extra" source="b" target="ghost"/>'
    else:
        namespace = (
            "urn:extension" if case.startswith("foreign-")
            else "http://gexf.net/1.3" if case.startswith("other-version-")
            else ""
        )
        if case.endswith("-node"):
            nodes = nodes.replace(
                '</nodes>',
                f'<node xmlns="{namespace}" id="a"/>'
                f'<node xmlns="{namespace}" id="ghost"/></nodes>',
            )
        else:
            edges = edges.replace(
                '</edges>',
                f'<edge xmlns="{namespace}" id="extra" source="b" target="ghost"/></edges>',
            )
    if case.startswith("metadata-"):
        extra = '<meta>' + extra + '</meta>'
    direction = "directed" if directed else "undirected"
    return (
        '<gexf xmlns="http://www.gexf.net/1.2draft">'
        f'<graph defaultedgetype="{direction}">'
        + nodes + edges + extra + '</graph></gexf>'
    ).encode()


@pytest.mark.parametrize("case", _GEXF_RECORD_SCOPE_CASES)
@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("mode", (None, "strict", "hardened", "ambient"))
def test_gexf_record_scope_cannot_add_or_overwrite_graph_data(
    monkeypatch, case, directed, mode,
):
    payload = _record_scope_document(case, directed)
    expected = nx.read_gexf(BytesIO(payload))
    assert list(expected.nodes(data=True)) == [("a", {"label": "A"}), ("b", {"label": "B"})]
    assert list(expected.edges(data=True)) == [("a", "b", {"id": "ab", "weight": 2.0})]
    _forbid_gexf_delegation(monkeypatch)
    stream = BytesIO(payload)
    options = {} if mode in (None, "ambient") else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = fnx.read_gexf(stream, **options)
    _assert_same(actual, expected)
    assert stream.getvalue() == payload
    assert not stream.closed
    if mode is not None:
        assert actual.mode == ("hardened" if mode == "ambient" else mode)
        assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("body", (
    '', '<meta><description>metadata only</description></meta>',
    '<graph xmlns="urn:extension"><nodes><node id="ghost"/></nodes></graph>',
))
@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_gexf_missing_graph_is_not_an_empty_native_projection(body, mode):
    payload = (
        '<gexf xmlns="http://www.gexf.net/1.2draft">' + body + '</gexf>'
    ).encode()
    with pytest.raises(nx.NetworkXError, match="No <graph> element"):
        nx.read_gexf(BytesIO(payload))
    options = {} if mode is None else {"mode": mode}
    with pytest.raises(fnx.NetworkXError, match="No <graph> element"):
        fnx.read_gexf(BytesIO(payload), **options)


@pytest.mark.parametrize("case", ("second-nodes", "direct-node", "foreign-node"))
def test_gexf_record_scope_keeps_native_structural_repairs_fail_closed(case):
    payload = _record_scope_document(case).replace(b'id="ghost"', b'id=""')
    with pytest.raises(OSError):
        fnx.read_gexf(BytesIO(payload), mode="strict")
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


@pytest.mark.parametrize("scope", (
    "second-attvalues", "direct-attvalue", "metadata-attvalue",
    "foreign-attvalue", "other-version-attvalue",
))
def test_gexf_ignored_scalar_recovery_cannot_overwrite_a_retained_value(scope):
    invalid = '<attvalue for="rank" value="invalid"/>'
    values = '<attvalues><attvalue for="rank" value="7"/></attvalues>'
    if scope == "second-attvalues":
        values += '<attvalues>' + invalid + '</attvalues>'
    elif scope == "direct-attvalue":
        values += invalid
    elif scope == "metadata-attvalue":
        values += '<meta>' + invalid + '</meta>'
    else:
        namespace = (
            "urn:extension" if scope == "foreign-attvalue"
            else "http://gexf.net/1.3"
        )
        invalid = invalid.replace('<attvalue ', f'<attvalue xmlns="{namespace}" ')
        values = values.replace('</attvalues>', invalid + '</attvalues>')
    payload = (
        '<gexf xmlns="http://www.gexf.net/1.2draft"><graph defaultedgetype="undirected">'
        '<attributes class="edge"><attribute id="rank" title="rank" type="long"/>'
        '</attributes><nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge source="a" target="b">' + values + '</edge></edges></graph></gexf>'
    ).encode()
    expected = nx.read_gexf(BytesIO(payload))
    assert expected["a"]["b"]["rank"] == 7
    # Strict native validation still rejects the malformed scalar. Hardened
    # mode must not return its projection, where the ignored value overwrites
    # the retained rank, or silently waive that validation through the decoder.
    with pytest.raises(OSError):
        fnx.read_gexf(BytesIO(payload), mode="strict")
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_gexf_scope_inspection_keeps_canonical_static_inputs_native(monkeypatch, directed, mode):
    direction = "directed" if directed else "undirected"
    payload = (
        '<gexf xmlns="http://www.gexf.net/1.2draft">'
        f'<graph defaultedgetype="{direction}"><nodes>'
        '<node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="ab" source="a" target="b" weight="2"/></edges></graph></gexf>'
    ).encode()
    expected = nx.read_gexf(BytesIO(payload))
    native_reader = fnx._fnx.read_gexf
    native_inputs = []

    def capture_native(stream, **options):
        native_input = stream.read()
        native_inputs.append(native_input)
        return native_reader(BytesIO(native_input), **options)

    def no_complete_decode(*args, **kwargs):
        pytest.fail("Canonical static GEXF should keep the native reader")

    monkeypatch.setattr(fnx._fnx, "read_gexf", capture_native)
    monkeypatch.setattr(readwrite, "_read_gexf_owned", no_complete_decode)
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), **options)
    _assert_same(actual, expected)
    assert native_inputs == [payload]


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("qualified_first", (False, True))
@pytest.mark.parametrize("field", (
    "direction", "name", "node-id", "node-label", "edge-id", "source",
    "target", "weight", "edge-label",
))
def test_gexf_qualified_attributes_cannot_override_core_fields(
    mode, directed, qualified_first, field,
):
    direction = "directed" if directed else "undirected"
    graph = f'<graph defaultedgetype="{direction}" name="">'
    nodes = '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
    edges = '<edges><edge id="ab" source="a" target="b" weight="2" label="AB"/></edges>'
    owner, name, value, shadow = {
        "direction": ("graph", "defaultedgetype", direction,
                      "undirected" if directed else "directed"),
        "name": ("graph", "name", "", "extension graph"),
        "node-id": ("nodes", "id", "a", "ghost"),
        "node-label": ("nodes", "label", "A", "overwritten"),
        "edge-id": ("edges", "id", "ab", "wrong"),
        "source": ("edges", "source", "a", "ghost"),
        "target": ("edges", "target", "b", "ghost"),
        "weight": ("edges", "weight", "2", "7"),
        "edge-label": ("edges", "label", "AB", "overwritten"),
    }[field]
    core = f'{name}="{value}"'
    qualified = f'ext:{name}="{shadow}"'
    replacement = f"{qualified} {core}" if qualified_first else f"{core} {qualified}"
    fragments = {"graph": graph, "nodes": nodes, "edges": edges}
    fragments[owner] = fragments[owner].replace(core, replacement, 1)
    payload = (
        '<gexf xmlns="http://www.gexf.net/1.2draft" xmlns:ext="urn:extension">'
        + fragments["graph"] + fragments["nodes"] + fragments["edges"]
        + '</graph></gexf>'
    ).encode()
    expected = nx.read_gexf(BytesIO(payload))
    options = {} if mode is None else {"mode": mode}
    stream = BytesIO(payload)
    actual = fnx.read_gexf(stream, **options)
    _assert_same(actual, expected)
    assert not stream.closed
    assert stream.getvalue() == payload
    if mode is not None:
        assert actual.mode == mode
        assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
@pytest.mark.parametrize("directed", (False, True))
def test_gexf_edges_before_nodes_preserve_declared_node_order(mode, directed):
    direction = "directed" if directed else "undirected"
    payload = (
        '<gexf xmlns="http://www.gexf.net/1.2draft">'
        f'<graph defaultedgetype="{direction}">'
        '<edges><edge id="ba" source="b" target="a"/>'
        '<edge id="ca" source="implicit" target="a"/></edges><nodes>'
        '<node id="a" label="A"/><node id="isolated" label="I"/>'
        '<node id="b" label="B"/></nodes></graph></gexf>'
    ).encode()
    expected = nx.read_gexf(BytesIO(payload))
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), **options)
    _assert_same(actual, expected)
    assert list(actual) == ["a", "isolated", "b", "implicit"]


@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_gexf_qualified_empty_fields_do_not_trigger_native_recovery(mode):
    payload = b'''<gexf xmlns="http://www.gexf.net/1.2draft" xmlns:ext="urn:extension">
      <graph defaultedgetype="directed"><attributes class="node" ext:class="edge">
        <attribute id="rank" ext:id="" title="rank" ext:title=""
          type="long" ext:type="unsupported"/></attributes><nodes>
        <node id="a" ext:id="" label="A"><attvalues>
          <attvalue for="rank" ext:for="" value="5" ext:value="invalid"/>
        </attvalues></node><node id="b" label="B"/></nodes>
        <edges><edge id="ab" source="a" ext:source="" target="b" ext:target=""/>
        </edges></graph></gexf>'''
    expected = nx.read_gexf(BytesIO(payload))
    actual = fnx.read_gexf(BytesIO(payload), mode=mode)
    _assert_same(actual, expected)
    assert actual.mode == mode
    assert all(record["action"] == "allow" for record in actual.decision_records())


def test_gexf_scope_scalar_recovery_keeps_nested_parent_data():
    payload = b'''<gexf xmlns="http://www.gexf.net/1.2draft">
      <graph defaultedgetype="undirected"><attributes class="node">
        <attribute id="rank" title="rank" type="long"/></attributes><nodes>
        <node id="parent" label="Parent"><nodes><node id="child" label="Child">
          <attvalues><attvalue for="rank" value="invalid"/></attvalues>
        </node></nodes><attvalues><attvalue for="rank" value="42"/></attvalues>
        </node></nodes></graph></gexf>'''
    with pytest.raises(OSError):
        fnx.read_gexf(BytesIO(payload), mode="strict")
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")
    assert list(actual.nodes(data=True)) == [
        ("child", {"rank": "invalid", "label": "Child", "pid": "parent"}),
        ("parent", {"rank": 42, "label": "Parent"}),
    ]
    assert dict(actual.graph) == {"mode": "static", "node_default": {}, "edge_default": {}}
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


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


@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("mode", ("strict", "hardened", "ambient"))
@pytest.mark.parametrize("entrypoint", ("top_level", "readwrite", "gexf"))
@pytest.mark.parametrize("typed_labels", (False, True))
def test_mode_gexf_preserves_complete_parallel_graph(
    monkeypatch, directed, mode, entrypoint, typed_labels,
):
    graph = (nx.MultiDiGraph if directed else nx.MultiGraph)(name="Mode graph")
    graph.graph["node_default"] = {"category": "default node"}
    graph.graph["edge_default"] = {"category": "default edge"}
    graph.add_node("01", label="First", history=[(1, 0.0, 1.0)], viz={"size": 2.5})
    graph.add_node("02", label="Second", category="measured")
    graph.add_node("09", label="Isolated")
    graph.add_edge("01", "02", key="first", weight=2.5, history=[(3, 0.0, 1.0)])
    graph.add_edge("01", "02", key="second", weight=4.5, note="parallel")
    graph.add_edge("02", "01", key="reverse", weight=1.5)
    graph.add_edge("02", "02", key="loop", weight=0.5)
    payload = _payload(graph)
    options = {"node_type": int, "relabel": True} if typed_labels else {}
    expected = nx.read_gexf(BytesIO(payload), **options)
    _forbid_gexf_delegation(monkeypatch)
    reader = {
        "top_level": fnx.read_gexf,
        "readwrite": readwrite.read_gexf,
        "gexf": readwrite.gexf.read_gexf,
    }[entrypoint]
    stream = BytesIO(payload)
    if mode == "ambient":
        with fnx.compatibility_mode("hardened"):
            actual = reader(stream, **options)
    else:
        actual = reader(stream, mode=mode, **options)
    _assert_same(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 4
    assert actual.mode == ("hardened" if mode == "ambient" else mode)
    assert actual.decision_records()
    assert all(record["action"] == "allow" for record in actual.decision_records())
    assert all(record["mode"] == actual.mode for record in actual.decision_records())
    assert not stream.closed


@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("invalid", ("numeric", "undeclared", "incompatible"))
@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_gexf_mode_validation_checks_later_parallel_records(directed, invalid, mode):
    title = "__fnx_incompatible_future" if invalid == "incompatible" else "rank"
    attribute_type = "string" if invalid == "incompatible" else "long"
    key = "missing" if invalid == "undeclared" else "r"
    value = "invalid" if invalid == "numeric" else "3"
    payload = _document(
        '<attributes class="edge">'
        f'<attribute id="r" title="{title}" type="{attribute_type}"/></attributes>'
        '<nodes><node id="a"/><node id="b"/></nodes><edges>'
        '<edge id="first" source="a" target="b"/>'
        '<edge id="second" source="a" target="b"><attvalues>'
        f'<attvalue for="{key}" value="{value}"/></attvalues></edge></edges>',
        direction="directed" if directed else "undirected",
    )
    conversions = []

    def node_type(value):
        conversions.append(value)
        return value

    if mode == "hardened" and invalid == "numeric":
        # The native policy retains only the malformed scalar as text. The
        # complete decoder must now retain both edges around that recovery.
        expected = nx.read_gexf(BytesIO(payload.replace(b'type="long"', b'type="string"')))
        actual = fnx.read_gexf(BytesIO(payload), node_type=node_type, mode=mode)
        _assert_same(actual, expected)
        assert conversions == ["a", "b", "a", "b", "a", "b"]
        assert any(record["action"] == "full_validate" for record in actual.decision_records())
        return
    expected_error = OSError if mode == "strict" else fnx.NetworkXNotImplemented
    with pytest.raises(expected_error):
        fnx.read_gexf(BytesIO(payload), node_type=node_type, mode=mode)
    assert conversions == []


def _scalar_recovery_document(kind, valid, default, directed, *, repaired=False):
    # Independent oracle input declares a string alternative for each title.
    # Only malformed values select it; valid values/defaults keep their type.
    rank = "r_text" if repaired else "r"
    history = "h_text" if repaired else "h"
    return _reader_document(
        '<attributes class="node" mode="static">'
        f'<attribute id="r" title="rank" type="{kind}"><default>{default}</default></attribute>'
        '<attribute id="r_text" title="rank" type="string"/>'
        '<attribute id="big" title="count" type="long"/>'
        '<attribute id="_fnx_recovered_0" title="tag" type="string"/>'
        '</attributes><attributes class="node" mode="dynamic">'
        '<attribute id="h" title="history" type="long"/>'
        '<attribute id="h_text" title="history" type="string"/>'
        '</attributes><attributes class="edge" mode="static">'
        f'<attribute id="r" title="rank" type="{kind}"><default>{default}</default></attribute>'
        '<attribute id="r_text" title="rank" type="string"/>'
        '<attribute id="big" title="count" type="long"/>'
        '</attributes><nodes><node id="01" label="First"><attvalues>'
        f'<attvalue for="r" value="{valid}"/>'
        '<attvalue for="_fnx_recovered_0" value="preserved"/>'
        '</attvalues></node><node id="1" label="Merged"><attvalues>'
        f'<attvalue for="{rank}" value="  not-a-scalar  "/>'
        f'<attvalue for="{history}" value="bad-history" start="0.0" end="1.0"/>'
        '<attvalue for="h" value="2" start="1.0" end="2.0"/>'
        '</attvalues></node><node id="9" label="Parent">'
        '<viz:size value="2.5"/><spells><spell start="0.0" end="2.0"/></spells>'
        '<nodes><node id="7" label="Child"><attvalues>'
        f'<attvalue for="r" value="{valid}"/>'
        f'<attvalue for="big" value="{2**90 + 1}"/>'
        '</attvalues></node></nodes></node></nodes><edges>'
        '<edge id="first" source="01" target="9"><attvalues>'
        f'<attvalue for="{rank}" value="  not-a-scalar  "/>'
        '</attvalues></edge><edge id="second" source="01" target="9"><attvalues>'
        f'<attvalue for="r" value="{valid}"/>'
        f'<attvalue for="big" value="{-2**90 - 1}"/>'
        '</attvalues></edge><edge id="merge" source="1" target="9"/></edges>',
        graph_attributes=(
            f'defaultedgetype="{"directed" if directed else "undirected"}" '
            'mode="dynamic" timeformat="double" name="Recovered measurements"'
        ),
    )


@pytest.mark.parametrize("kind,valid,default", (
    ("long", "17", "11"), ("double", "1.25", "0.5"), ("boolean", "true", "false"),
))
@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("typed_labels", (False, True))
def test_repaired_scalar_document_preserves_owned_gexf_decoding(
    monkeypatch, kind, valid, default, directed, typed_labels,
):
    payload = _scalar_recovery_document(kind, valid, default, directed)
    clean = _scalar_recovery_document(kind, valid, default, directed, repaired=True)
    options = {"node_type": int} if typed_labels else {}
    expected = nx.read_gexf(BytesIO(clean), **options)
    _forbid_gexf_delegation(monkeypatch)
    repaired = readwrite._gexf_repaired_values_payload(payload)
    assert repaired is not None
    # This checks XML repair and the complete decoder independently of the
    # native policy gate, which is exercised by the public tests below.
    actual = readwrite._read_gexf_owned(repaired, **options)
    _assert_same(actual, expected)
    node = 7 if typed_labels else "7"
    assert type(actual.nodes[node]["rank"]) is {"long": int, "double": float, "boolean": bool}[kind]
    assert type(actual.nodes[node]["count"]) is int
    assert type(actual.graph["node_default"]["rank"]) is type(expected.graph["node_default"]["rank"])


@pytest.mark.parametrize("extra", ("doctype", "cdata", "duplicate-key", "invalid-default", "native-boolean"))
def test_scalar_document_repair_declines_unrepresentable_inputs(extra):
    payload = _scalar_recovery_document("long", "17", "11", False)
    if extra == "doctype":
        payload = b'<!DOCTYPE gexf [<!ENTITY value "not-a-scalar">]>' + payload
    elif extra == "cdata":
        payload = payload.replace(b'<default>11</default>', b'<default><![CDATA[11]]></default>')
    elif extra == "duplicate-key":
        payload = payload.replace(
            b'<attribute id="r_text"', b'<attribute id="r" title="collision" type="string"/><attribute id="r_text"', 1,
        )
    elif extra == "invalid-default":
        payload = payload.replace(b'<default>11</default>', b'<default>invalid</default>')
    else:
        payload = payload.replace(b'type="long"', b'type="boolean"').replace(b'value="17"', b'value=" TRUE "')
        payload = payload.replace(b'<default>11</default>', b'<default>true</default>')
    assert readwrite._gexf_repaired_values_payload(payload) is None


@pytest.mark.parametrize("kind,valid,default", (
    ("long", "17", "11"), ("double", "1.25", "0.5"), ("boolean", "true", "false"),
))
@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("typed_labels", (False, True))
@pytest.mark.parametrize("entrypoint", ("top_level", "readwrite", "parse"))
def test_scalar_recovery_keeps_complete_gexf_data(
    monkeypatch, kind, valid, default, directed, typed_labels, entrypoint,
):
    payload = _scalar_recovery_document(kind, valid, default, directed)
    clean = _scalar_recovery_document(kind, valid, default, directed, repaired=True)
    options = {"node_type": int} if typed_labels else {}
    expected = nx.read_gexf(BytesIO(clean), **options)
    _forbid_gexf_delegation(monkeypatch)
    stream = BytesIO(payload)
    with fnx.compatibility_mode("strict"):
        if entrypoint == "parse":
            with fnx.compatibility_mode("hardened"):
                actual = readwrite.parse_gexf(payload, **options)
        else:
            reader = fnx.read_gexf if entrypoint == "top_level" else readwrite.read_gexf
            actual = reader(stream, mode="hardened", **options)
        assert fnx.get_compatibility_mode() == "strict"
    _assert_same(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 3
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())
    assert not stream.closed
    assert stream.getvalue() == payload


@pytest.mark.parametrize("extra", (
    '<node/>',
    '<node id="bad"><attvalues><attvalue for="missing" value="1"/></attvalues></node>',
    "incompatible-key",
    "invalid-direction",
))
def test_scalar_recovery_does_not_authorize_structural_repairs(extra):
    payload = _scalar_recovery_document("long", "17", "11", False)
    if extra == "incompatible-key":
        payload = payload.replace(b'title="rank"', b'title="__fnx_incompatible_future"')
    elif extra == "invalid-direction":
        payload = payload.replace(b'defaultedgetype="undirected"', b'defaultedgetype="bogus"')
    else:
        payload = payload.replace(b'<nodes><node id="01"', extra.encode() + b'<nodes><node id="01"', 1)
    conversions = []

    def node_type(value):
        conversions.append(value)
        return value

    with pytest.raises((OSError, fnx.NetworkXNotImplemented)):
        fnx.read_gexf(BytesIO(payload), node_type=node_type, mode="hardened")
    assert conversions == []


@pytest.mark.parametrize("extra", ("malformed-default", "native-boolean"))
def test_scalar_recovery_preserves_existing_simple_native_values(extra):
    payload = _policy_payload().replace(b'value="5"', b'value="not-an-int"')
    if extra == "malformed-default":
        payload = payload.replace(
            b'title="rank" type="long"/>',
            b'title="rank" type="long"><default>untyped</default></attribute>',
        )
    else:
        payload = payload.replace(
            b'</attributes>', b'<attribute id="flag" title="flag" type="boolean"/></attributes>',
        ).replace(
            b'</attvalues>', b'<attvalue for="flag" value=" TRUE "/></attvalues>',
        )
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")
    assert actual.nodes["0"]["rank"] == "not-an-int"
    if extra == "malformed-default":
        assert actual.graph["node_default"]["rank"] == "untyped"
    else:
        assert actual.nodes["0"]["flag"] is True
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


def test_scalar_recovery_rechecks_entire_gexf_beyond_retained_ledger(monkeypatch):
    payload = _document(
        '<attributes class="edge"><attribute id="r" title="rank" type="long"/></attributes>'
        '<nodes><node/><node id="a"/><node id="b"/></nodes><edges>'
        + '<edge source="a" target="b"/>' * 8300
        + '<edge source="a" target="b"><attvalues>'
        '<attvalue for="r" value="not-an-int"/></attvalues></edge></edges>'
    )
    validate = fnx._fnx.validate_gexf
    validations = []

    def capture_validation(*args, **kwargs):
        graph = validate(*args, **kwargs)
        validations.append(graph.decision_records())
        return graph

    monkeypatch.setattr(fnx._fnx, "validate_gexf", capture_validation)
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")
    # The early structural recovery was evicted; checking only the remaining
    # scalar warnings would incorrectly admit the original malformed graph.
    assert len(validations) == 1  # The strict recheck raises before returning.
    assert not any("node missing id" in record["rationale"] for record in validations[0])
    assert any("attr parse failed" in record["rationale"] for record in validations[0])


def test_early_scalar_recovery_survives_eviction_from_gexf_ledger(monkeypatch):
    payload = _document(
        '<attributes class="node"><attribute id="r" title="rank" type="long"/></attributes>'
        '<nodes><node id="a"><attvalues><attvalue for="r" value="not-an-int"/>'
        '</attvalues></node><node id="b"/></nodes><edges>'
        + '<edge source="a" target="b"/>' * 8300 + '</edges>'
    )
    expected = nx.read_gexf(BytesIO(payload.replace(b'type="long"', b'type="string"')))
    _forbid_gexf_delegation(monkeypatch)
    validate = fnx._fnx.validate_gexf
    validations = []

    def capture_validation(*args, **kwargs):
        graph = validate(*args, **kwargs)
        validations.append(graph.decision_records())
        return graph

    monkeypatch.setattr(fnx._fnx, "validate_gexf", capture_validation)
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")
    _assert_same(actual, expected)
    assert actual.number_of_edges() == 8300
    assert len(validations) == 2
    assert not any(record["action"] == "full_validate" for record in validations[0])
    # Retain the policy owner's real ledger; do not invent an evicted entry.
    assert actual.decision_records() == validations[0]
    assert actual.mode == "hardened"


@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_gexf_native_reader_does_not_return_validation_projection(mode):
    payload = _document(
        '<nodes><node id="a"/><node id="b"/></nodes><edges>'
        '<edge id="first" source="a" target="b"/>'
        '<edge id="second" source="a" target="b"/></edges>'
    )
    if mode == "strict":
        with pytest.raises(OSError):
            fnx._fnx.read_gexf(BytesIO(payload), mode=mode)
    else:
        native = fnx._fnx.read_gexf(BytesIO(payload), mode=mode)
        assert not native.is_multigraph()
        assert native.number_of_edges() == 1
        assert any(record["action"] == "full_validate" for record in native.decision_records())
    actual = fnx.read_gexf(BytesIO(payload), mode=mode)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 2
    assert all(record["action"] == "allow" for record in actual.decision_records())


@pytest.mark.parametrize("rich_body", (
    '<nodes><node id="a"/><node id="b"/></nodes><edges>'
    '<edge source="a" target="b"/><edge source="a" target="b"/></edges>',
    '<nodes><node id="a"><viz:size value="2.5"/></node></nodes>',
    '<nodes><node id="a"><nodes><node id="b"/></nodes></node></nodes>',
    '<attributes class="node" mode="dynamic"><attribute id="r" title="rank" type="long"/>'
    '</attributes><nodes><node id="a"><attvalues>'
    '<attvalue for="r" value="1" start="0" end="1"/></attvalues></node></nodes>',
))
def test_gexf_rich_recovery_cannot_return_lossy_simple_projection(rich_body):
    payload = _reader_document(rich_body, graph_attributes='defaultedgetype="bogus"')
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


def test_gexf_trailing_xml_error_retains_rich_recovery_guard():
    payload = _document(
        '<nodes><node id="a"/><node id="b"/></nodes><edges>'
        '<edge source="a" target="b"/><edge source="a" target="b"/></edges>'
    ).replace(b"</gexf>", b"</unexpected>")
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


@pytest.mark.parametrize("scope", ("node", "edge"))
@pytest.mark.parametrize("value", ("7", str(2**90 + 1)))
def test_gexf_malformed_xml_cannot_discard_defaults(scope, value):
    payload = _document(
        f'<attributes class="{scope}"><attribute id="r" title="rank" type="long">'
        f'<default>{value}</default></attribute></attributes>'
        '<nodes><node id="a"/><node id="b"/></nodes>'
        '<edges><edge source="a" target="b"/></edges>'
    )
    malformed = payload.replace(b"</gexf>", b"</unexpected>")
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(malformed), mode="hardened")

    repaired_direction = payload.replace(
        b'defaultedgetype="undirected"', b'defaultedgetype="bogus"'
    )
    actual = fnx.read_gexf(BytesIO(repaired_direction), mode="hardened")
    assert actual.graph[f"{scope}_default"] == {"rank": int(value)}
    assert type(actual.graph[f"{scope}_default"]["rank"]) is int
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_node_and_edge_attribute_ids_have_separate_scopes(mode):
    payload = _document(
        '<attributes class="node"><attribute id="0" title="rank" type="long"/></attributes>'
        '<attributes class="edge"><attribute id="0" title="color" type="string"/></attributes>'
        '<nodes><node id="a"><attvalues><attvalue for="0" value="7"/></attvalues></node>'
        '<node id="b"/></nodes><edges><edge source="a" target="b">'
        '<attvalues><attvalue for="0" value="blue"/></attvalues></edge></edges>'
    )
    options = {} if mode is None else {"mode": mode}
    actual = fnx.read_gexf(BytesIO(payload), **options)
    _assert_same(actual, nx.read_gexf(BytesIO(payload)))
    if mode is not None:
        assert actual.mode == mode
        assert all(record["action"] == "allow" for record in actual.decision_records())


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


@pytest.mark.parametrize("directed", (False, True))
@pytest.mark.parametrize("mode", ("strict", "hardened", "ambient"))
@pytest.mark.parametrize("kind", ("int", "integer", "long"))
@pytest.mark.parametrize("value", (
    str(2**90 + 1), str(-(2**90 + 1)), "+0001237940039285380274899124225",
))
def test_wide_integer_modes_preserve_values_and_defaults(directed, mode, kind, value):
    payload = _document(
        '<attributes class="node">'
        f'<attribute id="r" title="rank" type="{kind}"><default>{value}</default>'
        '</attribute></attributes><attributes class="edge">'
        f'<attribute id="r" title="rank" type="{kind}"><default>{value}</default>'
        '</attribute></attributes><nodes><node id="a"><attvalues>'
        f'<attvalue for="r" value="{value}"/></attvalues></node>'
        '<node id="b"/></nodes><edges><edge source="a" target="b"><attvalues>'
        f'<attvalue for="r" value="{value}"/></attvalues></edge>'
        '<edge source="b" target="b"/></edges>',
        direction="directed" if directed else "undirected",
    )
    expected = nx.read_gexf(BytesIO(payload))
    if mode == "ambient":
        with fnx.compatibility_mode("hardened"):
            actual = fnx.read_gexf(BytesIO(payload))
    else:
        actual = fnx.read_gexf(BytesIO(payload), mode=mode)
    _assert_same(actual, expected)
    assert type(actual.nodes["a"]["rank"]) is int
    assert type(actual["a"]["b"]["rank"]) is int
    assert type(actual.graph["node_default"]["rank"]) is int
    assert type(actual.graph["edge_default"]["rank"]) is int
    assert actual.nodes["a"]["rank"] == int(value)
    assert "rank" not in actual.nodes["b"]
    assert "rank" not in actual["b"]["b"]
    assert actual.mode == ("hardened" if mode == "ambient" else mode)
    assert actual.decision_records()
    assert all(record["action"] == "allow" for record in actual.decision_records())


def test_wide_integer_native_reader_retains_bounded_scalar_contract():
    payload = _policy_payload().replace(b'value="5"', f'value="{2**80 + 1}"'.encode())
    with pytest.raises(OSError, match="expected=integer"):
        fnx._fnx.read_gexf(BytesIO(payload), mode="strict")
    with fnx.compatibility_mode("hardened"):
        actual = fnx._fnx.read_gexf(BytesIO(payload))
    assert actual.nodes["0"]["rank"] == str(2**80 + 1)
    assert actual.mode == "hardened"
    assert any(record["action"] == "full_validate" for record in actual.decision_records())


@pytest.mark.parametrize("mode", ("hardened", "ambient"))
@pytest.mark.parametrize("value", (str(2**80 + 1), f"\u00a0{2**80 + 1}\u00a0"))
def test_wide_integer_recovery_cannot_expose_string_projection(mode, value):
    payload = _policy_payload().replace(b'value="5"', f'value="{value}"'.encode())
    payload = payload.replace(b'defaultedgetype="undirected"', b'defaultedgetype="bogus"')
    conversions = []

    def node_type(value):
        conversions.append(value)
        return value

    with pytest.raises(fnx.NetworkXNotImplemented, match="wide integers"):
        if mode == "ambient":
            with fnx.compatibility_mode("hardened"):
                fnx.read_gexf(BytesIO(payload), node_type=node_type)
        else:
            fnx.read_gexf(BytesIO(payload), node_type=node_type, mode=mode)
    assert conversions == []


@pytest.mark.parametrize("scope", ("node", "edge"))
def test_wide_integer_recovery_recognizes_native_normalized_attribute_scopes(scope):
    values = f'<attvalues><attvalue for="r" value="{2**80 + 1}"/></attvalues>'
    node_values = values if scope == "node" else ""
    edge_values = values if scope == "edge" else ""
    payload = _document(
        f'<attributes class=" {scope.upper()} ">'
        '<attribute id="r" title="rank" type="long"/></attributes>'
        f'<nodes><node id="a">{node_values}</node><node id="b"/></nodes>'
        f'<edges><edge source="a" target="b">{edge_values}</edge></edges>',
        direction="bogus",
    )
    with pytest.raises(fnx.NetworkXNotImplemented, match="wide integers"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


@pytest.mark.parametrize("value", (
    "9223372036854775807", "-9223372036854775808",
    "+0009223372036854775807", "-0009223372036854775808",
))
def test_native_sized_integer_recovery_keeps_numeric_values(value):
    payload = _policy_payload().replace(b'value="5"', f'value="{value}"'.encode())
    payload = payload.replace(b'defaultedgetype="undirected"', b'defaultedgetype="bogus"')
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")
    assert actual.nodes["0"]["rank"] == int(value)
    assert type(actual.nodes["0"]["rank"]) is int
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


def _assert_inline_gexf_weight_graph(actual, expected):
    """Compare simple graphs while handling NaNs and signed zero explicitly."""
    import math

    assert type(actual).__name__ == type(expected).__name__
    assert dict(actual.graph) == expected.graph
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    assert list(actual.edges()) == list(expected.edges())

    actual_data = dict(actual.edges["a", "b"])
    expected_data = dict(expected.edges["a", "b"])
    actual_weight = actual_data.pop("weight")
    expected_weight = expected_data.pop("weight")
    assert actual_data == expected_data
    assert type(actual_weight) is float
    if math.isnan(expected_weight):
        assert math.isnan(actual_weight)
    else:
        assert actual_weight == expected_weight
        assert math.copysign(1.0, actual_weight) == math.copysign(
            1.0, expected_weight
        )


@pytest.mark.parametrize("weight", (
    " 1.5 ",
    "1_000.25",
    "١.٥",
    "&#9;-0.0&#10;",
    " +Inf ",
    " NaN ",
))
@pytest.mark.parametrize("mode", (None, "strict", "hardened", "ambient"))
@pytest.mark.parametrize("reader_name", ("top_level", "readwrite"))
def test_inline_gexf_weights_preserve_python_numeric_syntax(
    monkeypatch, weight, mode, reader_name,
):
    payload = _document(
        '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        f'weight="{weight}"/></edges>'
    )
    expected = nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)
    reader = fnx.read_gexf if reader_name == "top_level" else readwrite.read_gexf
    options = {} if mode in (None, "ambient") else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = reader(BytesIO(payload), **options)

    _assert_inline_gexf_weight_graph(actual, expected)
    effective_mode = "hardened" if mode in ("hardened", "ambient") else "strict"
    assert actual.mode == effective_mode
    if mode is not None:
        records = actual.decision_records()
        assert records
        assert all(record["mode"] == effective_mode for record in records)
        assert all(record["action"] == "allow" for record in records)


@pytest.mark.parametrize("weight", (
    "-0.0",
    "2.5E-10",
    "5.",
    ".5",
    "inf",
    "-Infinity",
    "NaN",
    "1e9999",
))
def test_inline_gexf_native_float_syntax_keeps_native_decoder(monkeypatch, weight):
    payload = _document(
        '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        f'weight="{weight}"/></edges>'
    )
    expected = nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)

    def unexpected_decoder(*args, **kwargs):
        pytest.fail("Native floating-point literals should keep native decoding")

    monkeypatch.setattr(readwrite, "_read_gexf_owned", unexpected_decoder)
    with fnx.compatibility_mode("strict"):
        actual = fnx.read_gexf(BytesIO(payload))
    _assert_inline_gexf_weight_graph(actual, expected)


@pytest.mark.parametrize("weight", ("", "not-a-number", "1e", "İnf", "ınfinity"))
@pytest.mark.parametrize("mode", (None, "strict", "hardened", "ambient"))
def test_inline_gexf_invalid_weights_preserve_conversion_errors(
    monkeypatch, weight, mode,
):
    payload = _document(
        '<nodes><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        f'weight="{weight}"/></edges>'
    )
    with pytest.raises(ValueError) as expected:
        nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)
    options = {} if mode in (None, "ambient") else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        with pytest.raises(type(expected.value)) as actual:
            readwrite.read_gexf(BytesIO(payload), **options)
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("direction", ("undirected", "directed"))
@pytest.mark.parametrize("mode", (None, "strict", "hardened", "ambient"))
def test_inline_gexf_weights_preserve_rich_data_and_modes(
    monkeypatch, direction, mode,
):
    payload = _document(
        '<attributes class="node"><attribute id="r" title="rank" type="long">'
        '<default>7</default></attribute></attributes>'
        '<nodes><node id="a" label="A"><attvalues>'
        '<attvalue for="r" value="9"/></attvalues></node>'
        '<node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        'weight=" 1.5 "/></edges>',
        direction=direction,
    )
    expected = nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)
    options = {} if mode in (None, "ambient") else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = fnx.read_gexf(BytesIO(payload), **options)

    _assert_inline_gexf_weight_graph(actual, expected)
    assert type(actual.nodes["a"]["rank"]) is int
    assert type(actual.graph["node_default"]["rank"]) is int
    assert actual.mode == (
        "hardened" if mode in ("hardened", "ambient") else "strict"
    )


@pytest.mark.parametrize("weight", (" 1.5 ", "1_000.25", "not-a-number"))
@pytest.mark.parametrize("mode", ("hardened", "ambient"))
def test_inline_gexf_weights_cannot_escape_through_structural_recovery(weight, mode):
    payload = _document(
        '<nodes><node/><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        f'weight="{weight}"/></edges>'
    )
    options = {} if mode == "ambient" else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
            fnx.read_gexf(BytesIO(payload), **options)


def test_inline_gexf_native_weight_keeps_supported_structural_recovery():
    payload = _document(
        '<nodes><node/><node id="a" label="A"/><node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" weight="1.5"/></edges>'
    )
    expected = nx.read_gexf(BytesIO(payload.replace(b"<node/>", b"")))
    actual = fnx.read_gexf(BytesIO(payload), mode="hardened")

    _assert_inline_gexf_weight_graph(actual, expected)
    assert actual.mode == "hardened"
    assert any(
        record["action"] == "full_validate"
        for record in actual.decision_records()
    )


@pytest.mark.parametrize("weight", (" 1.5 ", "1_000.25"))
@pytest.mark.parametrize("mode", ("hardened", "ambient"))
def test_inline_gexf_weights_survive_independent_scalar_recovery(
    monkeypatch, weight, mode,
):
    payload = _document(
        '<attributes class="node"><attribute id="r" title="rank" type="long">'
        '<default>7</default></attribute>'
        '<attribute id="r_text" title="rank" type="string"/></attributes>'
        '<nodes><node id="a" label="A"><attvalues>'
        '<attvalue for="r" value="bad-rank"/></attvalues></node>'
        '<node id="b" label="B"/></nodes>'
        '<edges><edge id="weighted" source="a" target="b" '
        f'weight="{weight}"/></edges>'
    )
    # The oracle describes the intended repaired scalar independently:
    # malformed rank is text, while its valid default and edge weight
    # retain their original numeric types.
    clean = payload.replace(b'for="r"', b'for="r_text"')
    expected = nx.read_gexf(BytesIO(clean))
    _forbid_gexf_delegation(monkeypatch)
    options = {} if mode == "ambient" else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = fnx.read_gexf(BytesIO(payload), **options)

    _assert_inline_gexf_weight_graph(actual, expected)
    assert actual.nodes["a"]["rank"] == "bad-rank"
    assert type(actual.graph["node_default"]["rank"]) is int
    assert actual.mode == "hardened"
    assert any(
        record["action"] == "full_validate"
        for record in actual.decision_records()
    )


_GEXF_ENCODING_CASES = {
    "latin1": ("iso-8859-1", "ISO-8859-1", b""),
    "windows1252": ("cp1252", "windows-1252", b""),
    "utf16": ("utf-16", "UTF-16", b""),
    "utf16le": ("utf-16-le", "UTF-16LE", b""),
    "utf16be": ("utf-16-be", "UTF-16BE", b""),
    "utf16be-generic-declaration": ("utf-16-be", "UTF-16", b""),
    "utf16le-no-declaration": ("utf-16-le", None, b""),
    "utf16be-no-declaration": ("utf-16-be", None, b""),
    "utf16le-bom-no-declaration": ("utf-16-le", None, b"\xff\xfe"),
    "utf16be-bom-no-declaration": ("utf-16-be", None, b"\xfe\xff"),
    "utf8-bom-latin1": ("iso-8859-1", "ISO-8859-1", b"\xef\xbb\xbf"),
}


def _encoded_gexf_payload(document, encoding_case):
    codec, declaration, bom = _GEXF_ENCODING_CASES[encoding_case]
    declaration = (
        f"<?xml version='1.0' encoding = '{declaration}' standalone='yes'?>"
        if declaration is not None else ""
    )
    return bom + (declaration + " \n" + document).encode(codec)


@pytest.mark.parametrize("encoding_case", tuple(_GEXF_ENCODING_CASES))
@pytest.mark.parametrize("mode", (None, "strict", "hardened", "ambient"))
@pytest.mark.parametrize("rich", (False, True))
def test_encoded_gexf_preserves_data_and_native_policy(
    monkeypatch, encoding_case, mode, rich,
):
    declarations = (
        '<attributes class="node"><attribute id="name" title="category" '
        'type="string"><default>défaut</default></attribute></attributes>'
        if rich else ""
    )
    values = '<attvalues><attvalue for="name" value="mesuré"/></attvalues>' if rich else ""
    parallel = '<edge id="second" source="café" target="élève" weight="3.5"/>' if rich else ""
    document = _document(
        declarations + '<nodes><node id="café" label="Café">'
        + values + '</node><node id="élève" label="Élève"/></nodes>'
        '<edges><edge id="first" source="café" target="élève" weight="2.5"/>'
        + parallel + '</edges>',
        direction="directed" if rich else "undirected",
    ).decode()
    if encoding_case == "windows1252":
        document = document.replace('label="Café"', 'label="Café €"')
    elif encoding_case.startswith("utf16"):
        document = document.replace('label="Café"', 'label="Café 🧪"')
    payload = _encoded_gexf_payload(document, encoding_case)
    expected = nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)
    stream = BytesIO(payload)
    options = {} if mode in (None, "ambient") else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = fnx.read_gexf(stream, **options)

    _assert_same(actual, expected)
    assert stream.getvalue() == payload
    assert not stream.closed
    effective_mode = "hardened" if mode in ("hardened", "ambient") else "strict"
    assert actual.mode == effective_mode
    if mode is not None:
        records = actual.decision_records()
        assert records
        assert all(record["mode"] == effective_mode for record in records)
        assert all(record["action"] == "allow" for record in records)


@pytest.mark.parametrize("encoding_case", ("latin1", "utf16", "utf16be"))
@pytest.mark.parametrize("mode", (None, "strict", "hardened"))
def test_encoded_gexf_keeps_policy_markup_and_entity_rejection(
    monkeypatch, encoding_case, mode,
):
    document = (
        '<!DOCTYPE gexf [<!ENTITY rank "5">]>\n'
        '<!-- café: preserve this comment -->\n'
        '<?extension encoding="original"?>\n'
        + _policy_payload().decode().replace('value="5"', 'value="&rank;"')
        .replace(
            '<graph ',
            '<meta><description><![CDATA[café < raw]]></description></meta>'
            '<extension xmlns="urn:future" encoding="unchanged"/><graph ',
            1,
        )
    )
    payload = _encoded_gexf_payload(document, encoding_case)
    expected_input = (
        "<?xml version='1.0' encoding = 'UTF-8' standalone='yes'?> \n"
        + document
    ).encode()
    native_validate = fnx._fnx.validate_gexf
    policy_inputs = []

    def capture_validation(stream, **options):
        policy_input = stream.read()
        policy_inputs.append(policy_input)
        return native_validate(BytesIO(policy_input), **options)

    monkeypatch.setattr(fnx._fnx, "validate_gexf", capture_validation)
    stream = BytesIO(payload)
    options = {} if mode is None else {"mode": mode}
    with pytest.raises(OSError):
        fnx.read_gexf(stream, **options)
    assert policy_inputs == [expected_input]
    assert stream.getvalue() == payload
    assert not stream.closed


def test_encoded_gexf_unknown_extensions_still_require_native_validation(monkeypatch):
    document = _policy_payload().decode().replace(
        '</graph>', '<extension xmlns="urn:future" name="café"/></graph>',
    )
    payload = _encoded_gexf_payload(document, "utf16")
    expected_input = (
        "<?xml version='1.0' encoding = 'UTF-8' standalone='yes'?> \n"
        + document
    ).encode()
    expected = nx.read_gexf(BytesIO(payload))
    _forbid_gexf_delegation(monkeypatch)
    native_validate = fnx._fnx.validate_gexf
    native_policy = native_validate(BytesIO(expected_input), mode="strict")
    policy_inputs = []

    def capture_validation(stream, **options):
        policy_input = stream.read()
        policy_inputs.append(policy_input)
        return native_validate(BytesIO(policy_input), **options)

    monkeypatch.setattr(fnx._fnx, "validate_gexf", capture_validation)
    # No explicit mode: an unknown extension must prevent the early owned
    # decoder route even when all of the known GEXF data is supported.
    with fnx.compatibility_mode("strict"):
        actual = fnx.read_gexf(BytesIO(payload))
    _assert_same(actual, expected)
    assert policy_inputs == [expected_input]
    assert [
        (record["mode"], record["action"], record["rationale"])
        for record in actual.decision_records()
    ] == [
        (record["mode"], record["action"], record["rationale"])
        for record in native_policy.decision_records()
    ]


@pytest.mark.parametrize("encoding_case", ("latin1", "utf16", "utf16be"))
@pytest.mark.parametrize("mode", ("hardened", "ambient"))
def test_encoded_gexf_scalar_recovery_retains_rich_data_and_inline_weights(
    monkeypatch, encoding_case, mode,
):
    document = _scalar_recovery_document("long", "17", "11", True).decode()
    clean = _scalar_recovery_document("long", "17", "11", True, repaired=True).decode()
    document = document.replace('label="First"', 'label="Café"').replace(
        '<edge id="first"', '<edge weight=" 1_000.25 " id="first"',
    )
    clean = clean.replace('label="First"', 'label="Café"').replace(
        '<edge id="first"', '<edge weight=" 1_000.25 " id="first"',
    )
    payload = _encoded_gexf_payload(document, encoding_case)
    expected = nx.read_gexf(BytesIO(_encoded_gexf_payload(clean, encoding_case)))
    _forbid_gexf_delegation(monkeypatch)
    stream = BytesIO(payload)
    options = {} if mode == "ambient" else {"mode": mode}
    with fnx.compatibility_mode("hardened" if mode == "ambient" else "strict"):
        actual = fnx.read_gexf(stream, **options)

    _assert_same(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 3
    assert actual["01"]["9"]["first"]["weight"] == 1000.25
    assert actual.mode == "hardened"
    assert any(
        record["action"] == "full_validate"
        for record in actual.decision_records()
    )
    assert stream.getvalue() == payload
    assert not stream.closed


@pytest.mark.parametrize("encoding_case", ("latin1", "utf16"))
@pytest.mark.parametrize("markup", ("doctype", "cdata"))
def test_encoded_gexf_does_not_weaken_scalar_repair_boundaries(encoding_case, markup):
    document = _scalar_recovery_document("long", "17", "11", False).decode()
    if markup == "doctype":
        document = '<!DOCTYPE gexf [<!ENTITY unused "café">]>' + document
    else:
        document = document.replace('<default>11</default>', '<default><![CDATA[11]]></default>')
    payload = _encoded_gexf_payload(document, encoding_case)
    with pytest.raises(fnx.NetworkXNotImplemented, match="GEXF recovery"):
        fnx.read_gexf(BytesIO(payload), mode="hardened")


@pytest.mark.parametrize("invalid", ("encoding-mismatch", "truncated-xml"))
@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_encoded_gexf_malformed_xml_retains_native_rejection(invalid, mode):
    document = _policy_payload().decode().replace('label="Zero"', 'label="Café"')
    if invalid == "encoding-mismatch":
        payload = ('<?xml version="1.0" encoding="UTF-8"?>' + document).encode("utf-16")
    else:
        payload = _encoded_gexf_payload(document.removesuffix('</gexf>'), "utf16")
    # Normalization must not fix an encoding mismatch or hide malformed XML.
    # The same original input must still fail at the native boundary.
    with pytest.raises(Exception) as expected:
        fnx._fnx.validate_gexf(BytesIO(payload), mode=mode)
    with pytest.raises(type(expected.value)) as actual:
        fnx.read_gexf(BytesIO(payload), mode=mode)
    assert actual.value.args == expected.value.args
