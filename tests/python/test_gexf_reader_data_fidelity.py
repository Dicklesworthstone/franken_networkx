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
def test_rich_gexf_data_matches_networkx(graph_type, version, entrypoint):
    payload = _payload(_rich_graph(graph_type, version), version=version)
    expected = nx.read_gexf(BytesIO(payload), version=version)
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
    monkeypatch.setattr(readwrite, "_read_gexf_via_nx", unexpected_decoder)
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
