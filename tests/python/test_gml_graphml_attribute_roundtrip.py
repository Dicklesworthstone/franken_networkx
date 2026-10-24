"""Attribute-preserving round-trips for GML and GraphML.

Richer than the structural file-IO round-trip: GML and GraphML retain typed
node/edge/graph attributes, so a write+read cycle must recover their values.

br-r37-c1-fxrd4
"""

from __future__ import annotations

import os
import io
import random
import tempfile

import pytest
import franken_networkx as fnx
import networkx as nx


GRAPHML_READERS = [
    fnx.read_graphml,
    fnx.readwrite.read_graphml,
    fnx.readwrite.graphml.read_graphml,
]
GRAPHML_READER_IDS = ["top-level", "readwrite", "graphml-submodule"]
GRAPHML_PARSERS = [
    fnx.parse_graphml,
    fnx.readwrite.parse_graphml,
    fnx.readwrite.graphml.parse_graphml,
]


def _assert_graphml_matches(actual, expected):
    assert actual.is_directed() == expected.is_directed()
    assert actual.is_multigraph() == expected.is_multigraph()
    assert actual.graph == expected.graph
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    kwargs = {"keys": True} if expected.is_multigraph() else {}
    assert list(actual.edges(data=True, **kwargs)) == list(expected.edges(data=True, **kwargs))


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("as_bytes", [False, True])
def test_parse_graphml_preserves_lexical_edge_keys(parser, mode, directed, as_bytes):
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="w" for="edge" attr.name="weight" attr.type="int"/>'
        f'<graph edgedefault="{direction}"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b" id="01"><data key="w">3</data></edge>'
        '<edge source="a" target="b" id="1"><data key="w">7</data></edge>'
        '</graph></graphml>'
    )
    if as_bytes:
        payload = payload.encode()
    expected = nx.parse_graphml(payload, edge_key_type=str)
    with fnx.compatibility_mode(mode):
        actual = parser(payload, edge_key_type=str)
    _assert_graphml_matches(actual, expected)
    assert actual.number_of_edges() == 2
    assert actual.mode == mode
    if mode == "hardened":
        assert actual.decision_records()


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("edge_key_type", [int, str])
def test_parse_graphml_force_multigraph_preserves_edge_id(parser, mode, directed, edge_key_type):
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        f'<graph edgedefault="{direction}"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b" id="007"/></graph></graphml>'
    )
    options = dict(force_multigraph=True, edge_key_type=edge_key_type)
    expected = nx.parse_graphml(payload, **options)
    with fnx.compatibility_mode(mode):
        actual = parser(payload, **options)
    _assert_graphml_matches(actual, expected)
    assert list(actual.edges(keys=True)) == [("a", "b", edge_key_type("007"))]


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("directed", [False, True])
def test_parse_graphml_converts_nodes_before_parallel_edge_detection(parser, mode, directed):
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="c" for="node" attr.name="color" attr.type="string"/>'
        f'<graph edgedefault="{direction}"><node id="01"><data key="c">red</data></node>'
        '<node id="1"><data key="c">blue</data></node><node id="2"/>'
        '<edge source="01" target="2" id="3"/>'
        '<edge source="1" target="2" id="4"/></graph></graphml>'
    )
    expected = nx.parse_graphml(payload, node_type=int)
    with fnx.compatibility_mode(mode):
        actual = parser(payload, node_type=int)
    _assert_graphml_matches(actual, expected)
    assert actual.is_multigraph()
    assert actual.number_of_edges() == 2


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_parse_graphml_key_converter_retains_unconvertible_id(parser, mode):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="directed"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b" id="01"/>'
        '<edge source="a" target="b" id="other"/></graph></graphml>'
    )
    expected = nx.parse_graphml(payload, edge_key_type=float)
    with fnx.compatibility_mode(mode):
        actual = parser(payload, edge_key_type=float)
    _assert_graphml_matches(actual, expected)


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("options", [
    {"node_type": int}, {"node_type": None},
    {"node_type": lambda node: []}, {"edge_key_type": None},
])
def test_parse_graphml_conversion_errors_match_networkx(parser, mode, options):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="undirected"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b" id="01"/></graph></graphml>'
    )
    with pytest.raises(Exception) as expected:
        nx.parse_graphml(payload, **options)
    with fnx.compatibility_mode(mode):
        with pytest.raises(type(expected.value)) as actual:
            parser(payload, **options)
        assert str(actual.value) == str(expected.value)
        assert fnx.get_compatibility_mode() == mode


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_parse_graphml_unicode_text_keeps_declared_encoding(parser, mode):
    payload = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="directed"><node id="café"/><node id="naïve"/>'
        '<edge source="café" target="naïve" id="01"/></graph></graphml>'
    )
    options = dict(force_multigraph=True, edge_key_type=str)
    expected = nx.parse_graphml(payload, **options)
    with fnx.compatibility_mode(mode):
        actual = parser(payload, **options)
    _assert_graphml_matches(actual, expected)


@pytest.mark.parametrize("parser", GRAPHML_PARSERS, ids=GRAPHML_READER_IDS)
def test_parse_graphml_hardened_conversion_keeps_recovery_ledger(parser):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="z" for="node" attr.name="z" attr.type="complex"/>'
        '<graph edgedefault="undirected"><node id="01"><data key="z">1+2j</data>'
        '</node><node id="2"/><edge source="01" target="2"/></graph></graphml>'
    )
    with fnx.compatibility_mode("hardened"):
        with pytest.warns(RuntimeWarning, match="unsupported attr.type `complex`"):
            actual = parser(payload, node_type=int)
    assert actual.mode == "hardened"
    assert list(actual) == [1, 2]
    assert actual.nodes[1]["z"] == "1+2j"
    assert any(
        record["action"] == "full_validate"
        and "unsupported attr.type `complex`" in record["rationale"]
        for record in actual.decision_records()
    )
    # A requested multigraph recovery must fail before returning the lossy
    # simple projection produced by native validation.
    with fnx.compatibility_mode("hardened"):
        with pytest.warns(RuntimeWarning, match="unsupported attr.type `complex`"):
            with pytest.raises(fnx.NetworkXNotImplemented, match="GraphML recovery"):
                parser(payload, node_type=int, force_multigraph=True)


def _attributed_graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    g = fnx.Graph()
    g.graph["name"] = "test"
    g.graph["level"] = 3
    for i in range(n):
        g.add_node(i, color=rng.choice(["red", "blue"]), size=rng.randint(1, 10))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v, weight=rng.randint(1, 9), kind=rng.choice(["a", "b"]))
    return g


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _node_attrs(g):
    return {str(n): (d.get("color"), d.get("size")) for n, d in g.nodes(data=True)}


def _edge_attrs(g):
    return {
        (min(int(u), int(v)), max(int(u), int(v))): (d.get("weight"), d.get("kind"))
        for u, v, d in g.edges(data=True)
    }


@pytest.mark.parametrize("seed", range(30))
def test_gml_preserves_attributes(seed, tmpdir):
    g = _attributed_graph(seed)
    path = os.path.join(tmpdir, "g.gml")
    fnx.write_gml(g, path)
    rg = fnx.read_gml(path, destringizer=int)
    assert _node_attrs(rg) == _node_attrs(g)
    assert _edge_attrs(rg) == _edge_attrs(g)
    assert rg.graph.get("name") == "test"
    assert rg.graph.get("level") == 3


@pytest.mark.parametrize("seed", range(30))
def test_graphml_preserves_attributes(seed, tmpdir):
    g = _attributed_graph(seed)
    path = os.path.join(tmpdir, "g.graphml")
    fnx.write_graphml(g, path)
    rg = fnx.read_graphml(path, node_type=int)
    assert _node_attrs(rg) == _node_attrs(g)
    assert _edge_attrs(rg) == _edge_attrs(g)
    assert rg.graph.get("name") == "test"
    assert rg.graph.get("level") == 3


@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("explicit_mode", [False, True])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("source", ["stream", "path"])
@pytest.mark.parametrize("node_type", [str, int, lambda node: ("node", int(node))])
@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
def test_graphml_node_type_preserves_mode_and_attributes(
    mode, explicit_mode, directed, source, node_type, reader, tmp_path
):
    reference = nx.DiGraph() if directed else nx.Graph()
    reference.graph["name"] = "typed tutorial"
    reference.add_nodes_from([(12, {"color": "red"}), (2, {"color": "blue"}), (7, {})])
    reference.add_edge(12, 2, weight=3.5)
    reference.add_edge(2, 7, kind="next")
    output = io.BytesIO()
    nx.write_graphml(reference, output)
    payload = output.getvalue()
    expected = nx.read_graphml(io.BytesIO(payload), node_type=node_type)
    if source == "path":
        path = tmp_path / "typed.graphml"
        path.write_bytes(payload)
    else:
        path = io.BytesIO(payload)
    ambient_mode = "hardened" if explicit_mode and mode == "strict" else "strict"
    if not explicit_mode:
        ambient_mode = mode
    with fnx.compatibility_mode(ambient_mode):
        actual = reader(
            path, node_type=node_type, **({"mode": mode} if explicit_mode else {})
        )
        assert fnx.get_compatibility_mode() == ambient_mode
    assert actual.mode == mode
    assert actual.is_directed() == expected.is_directed()
    assert actual.is_multigraph() == expected.is_multigraph()
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    assert actual.graph == expected.graph
    assert fnx.to_dict_of_dicts(actual) == nx.to_dict_of_dicts(expected)
    assert list(actual.edges(data=True)) == list(expected.edges(data=True))


@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("node_type", [int, None, lambda node: []])
@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
def test_graphml_node_type_errors_propagate_without_poisoning_mode(mode, node_type, reader):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<graph edgedefault="undirected"><node id="not-an-integer"/></graph></graphml>'
    ).encode()
    with pytest.raises(Exception) as expected:
        nx.read_graphml(io.BytesIO(payload), node_type=node_type)
    with fnx.compatibility_mode("strict"):
        with pytest.raises(type(expected.value)) as actual_error:
            reader(io.BytesIO(payload), node_type=node_type, mode=mode)
        assert str(actual_error.value) == str(expected.value)
        assert fnx.get_compatibility_mode() == "strict"
        good = payload.replace(b"not-an-integer", b"12")
        assert list(reader(io.BytesIO(good), node_type=int, mode=mode)) == [12]


@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
def test_hardened_graphml_node_type_keeps_recovery_warning_and_ledger(reader):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="d0" for="node" attr.name="z" attr.type="complex"/>'
        '<graph edgedefault="undirected"><node id="12"><data key="d0">1+2j</data>'
        '</node><node id="2"/><edge source="12" target="2"/></graph></graphml>'
    ).encode()
    with pytest.warns(RuntimeWarning, match="unsupported attr.type `complex`"):
        graph = reader(io.BytesIO(payload), node_type=int, mode="hardened")
    assert graph.mode == "hardened"
    assert list(graph) == [12, 2]
    assert graph.nodes[12]["z"] == "1+2j"
    assert list(graph.edges()) == [(12, 2)]
    records = graph.decision_records()
    assert any(
        record["mode"] == "hardened"
        and record["action"] == "full_validate"
        and "unsupported attr.type `complex`" in record["rationale"]
        for record in records
    )
    assert graph.drain_decision_records() == records
    assert graph.decision_records() == []


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
def test_hardened_graphml_merging_node_type_keeps_attributes_and_recovery(directed, reader):
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="d0" for="node" attr.name="z" attr.type="complex"/>'
        '<key id="d1" for="node" attr.name="color" attr.type="string"/>'
        f'<graph edgedefault="{"directed" if directed else "undirected"}">'
        '<node id="01"><data key="d0">1+2j</data></node>'
        '<node id="1"><data key="d1">red</data></node></graph></graphml>'
    ).encode()
    clean = payload.replace(b'attr.type="complex"', b'attr.type="string"')
    expected = nx.read_graphml(io.BytesIO(clean), node_type=int)
    with fnx.compatibility_mode("strict"):
        with pytest.warns(RuntimeWarning, match="unsupported attr.type `complex`"):
            graph = reader(io.BytesIO(payload), node_type=int, mode="hardened")
        assert fnx.get_compatibility_mode() == "strict"
    assert graph.mode == "hardened"
    assert graph.is_directed() == expected.is_directed()
    assert list(graph.nodes(data=True)) == list(expected.nodes(data=True))
    assert graph.graph == expected.graph
    assert any(
        "unsupported attr.type `complex`" in record["rationale"]
        for record in graph.decision_records()
    )


@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("force_multigraph", [False, True])
@pytest.mark.parametrize("edge_key_type", [int, str])
def test_mode_graphml_preserves_edge_keys_parallel_edges_and_force(
    reader, mode, kind, force_multigraph, edge_key_type
):
    reference = getattr(nx, kind)()
    reference.add_nodes_from([12, 2, 7])
    if reference.is_multigraph():
        reference.add_edge(12, 2, key="01", weight=1.25)
        reference.add_edge(12, 2, key="other", weight=2.5)
    else:
        reference.add_edge(12, 2, weight=1.25)
    reference.add_edge(2, 7, weight=3)
    output = io.BytesIO()
    nx.write_graphml(reference, output)
    kwargs = dict(node_type=int, edge_key_type=edge_key_type, force_multigraph=force_multigraph)
    expected = nx.read_graphml(io.BytesIO(output.getvalue()), **kwargs)
    actual = reader(io.BytesIO(output.getvalue()), mode=mode, **kwargs)
    assert actual.mode == mode
    assert actual.is_directed() == expected.is_directed()
    assert actual.is_multigraph() == expected.is_multigraph()
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    assert actual.graph == expected.graph
    assert fnx.to_dict_of_dicts(actual) == nx.to_dict_of_dicts(expected)
    assert list(actual.edges(data=True, **({"keys": True} if actual.is_multigraph() else {}))) == (
        list(expected.edges(data=True, **({"keys": True} if expected.is_multigraph() else {})))
    )
    assert actual.decision_records(), "Mode-aware reads must keep the native validation ledger"


@pytest.mark.parametrize("directed", [False, True])
def test_graphml_validation_projection_preserves_ordinary_native_rejection(directed):
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        f'<graph edgedefault="{direction}"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b"/><edge source="a" target="b"/>'
        '</graph></graphml>'
    ).encode()
    # Raw native I/O has always mapped ReadWriteError to Python OSError.
    with pytest.raises(OSError, match="multiedge not supported") as first_error:
        fnx._fnx.read_graphml(io.BytesIO(payload), mode="strict")
    expected_error = (
        'readwrite `read_graphml` failed closed: graphml multiedge not supported: '
        'source="a" target="b"'
    )
    assert type(first_error.value) is OSError
    assert str(first_error.value) == expected_error
    projected = fnx._fnx.validate_graphml(io.BytesIO(payload), mode="strict")
    assert projected.is_directed() == directed
    assert projected.number_of_edges() == 1
    assert any(
        record["rationale"] == "graphml parallel edges require multigraph reconstruction"
        for record in projected.decision_records()
    )
    with pytest.raises(OSError, match="multiedge not supported") as second_error:
        fnx._fnx.read_graphml(io.BytesIO(payload), mode="strict")
    assert type(second_error.value) is OSError
    assert str(second_error.value) == expected_error


@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_mode_graphml_validates_later_parallel_edge_before_returning(reader, directed, mode):
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="w" for="edge" attr.name="weight" attr.type="int"/>'
        f'<graph edgedefault="{direction}"><node id="a"/><node id="b"/>'
        '<edge source="a" target="b"><data key="w">1</data></edge>'
        '<edge source="a" target="b"><data key="w">not-an-int</data></edge>'
        '</graph></graphml>'
    ).encode()
    if mode == "strict":
        with pytest.raises(OSError, match="not-an-int") as error:
            reader(io.BytesIO(payload), mode=mode)
        assert type(error.value) is OSError
        assert str(error.value) == (
            'readwrite `read_graphml` failed closed: graphml attr parse failed: '
            'key=w type=int expected=int value="not-an-int"'
        )
    else:
        with pytest.warns(RuntimeWarning, match="not-an-int"):
            with pytest.raises(fnx.NetworkXNotImplemented, match="GraphML recovery"):
                reader(io.BytesIO(payload), mode=mode)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("source_kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("target_kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_readwrite_policy_copy_isolated_from_source_and_ambient(mode, source_kind, target_kind):
    direction = "directed" if source_kind == "DiGraph" else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        f'<graph edgedefault="{direction}"><node id="a"/></graph></graphml>'
    ).encode()
    source = fnx._fnx.validate_graphml(io.BytesIO(payload), mode=mode)
    records = source.decision_records()
    assert records
    ambient = "hardened" if mode == "strict" else "strict"
    with fnx.compatibility_mode(ambient):
        target = getattr(fnx, target_kind)()
        target.add_edge(1, 2, weight=3)
        before = fnx.to_dict_of_dicts(target)
        fnx._fnx.copy_readwrite_policy(source, target)
        assert fnx.get_compatibility_mode() == ambient
    assert target.mode == mode
    assert target.decision_records() == records
    assert target.drain_decision_records() == records
    assert source.decision_records() == records
    fnx._fnx.copy_readwrite_policy(source, source)
    assert source.mode == mode
    assert source.decision_records() == records
    assert fnx.to_dict_of_dicts(target) == before


def test_readwrite_policy_copy_rejects_non_native_objects_without_mutation():
    source = fnx.Graph()
    records = source.decision_records()
    with pytest.raises(TypeError, match="source must be a native Graph or DiGraph"):
        fnx._fnx.copy_readwrite_policy(object(), source)
    with pytest.raises(TypeError, match="target must be a native graph"):
        fnx._fnx.copy_readwrite_policy(source, object())
    assert source.decision_records() == records


@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_mode_graphml_unicode_text_stream_retains_declared_encoding(reader, mode):
    payload = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="label" for="node" attr.name="label" attr.type="string"/>'
        '<graph edgedefault="undirected"><node id="café">'
        '<data key="label">naïve</data></node></graph></graphml>'
    )
    expected = nx.read_graphml(io.StringIO(payload))
    stream = io.StringIO(payload)
    graph = reader(stream, mode=mode)
    assert not stream.closed
    assert list(graph.nodes(data=True)) == list(expected.nodes(data=True))
    assert graph.mode == mode


@pytest.mark.parametrize("reader", GRAPHML_READERS[1:], ids=GRAPHML_READER_IDS[1:])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_namespace_default_graphml_keeps_full_numeric_and_encoding_surface(reader, mode):
    reference = nx.MultiDiGraph()
    reference.graph["large"] = 2**70
    reference.add_edge("café", "naïve", key="01", weight=2**70)
    reference.add_edge("café", "naïve", key="other", weight=2**71)
    output = io.BytesIO()
    nx.write_graphml(reference, output, encoding="ISO-8859-1")
    payload = output.getvalue()
    expected = nx.read_graphml(io.BytesIO(payload), edge_key_type=str)
    with fnx.compatibility_mode(mode):
        graph = reader(io.BytesIO(payload), edge_key_type=str)
    assert graph.mode == mode
    assert graph.graph == expected.graph
    assert list(graph.nodes(data=True)) == list(expected.nodes(data=True))
    assert list(graph.edges(keys=True, data=True)) == list(expected.edges(keys=True, data=True))


@pytest.mark.parametrize("reader", GRAPHML_READERS, ids=GRAPHML_READER_IDS)
@pytest.mark.parametrize("directed", [False, True])
def test_hardened_parallel_recovery_cannot_lose_marker_during_large_reconstruction(reader, directed):
    # More than the native ledger's 8192-record retention window. Internal
    # node reconstruction must not retire the parser's parallel-edge marker
    # and accidentally return the lossy simple projection after a recovery.
    direction = "directed" if directed else "undirected"
    payload = (
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        '<key id="z" for="node" attr.name="z" attr.type="complex"/>'
        f'<graph edgedefault="{direction}"><node id="a"><data key="z">1+2j</data>'
        '</node><node id="b"/>'
        + ''.join(f'<node id="isolate-{i}"/>' for i in range(9000))
        + '<edge source="a" target="b"/><edge source="a" target="b"/>'
        '</graph></graphml>'
    ).encode()
    clean = payload.replace(b'attr.type="complex"', b'attr.type="string"')
    expected = nx.read_graphml(io.BytesIO(clean))
    assert expected.is_multigraph()
    assert expected.number_of_nodes() == 9002
    assert expected.number_of_edges() == 2
    with pytest.warns(RuntimeWarning, match="unsupported attr.type `complex`"):
        with pytest.raises(fnx.NetworkXNotImplemented, match="GraphML recovery"):
            reader(io.BytesIO(payload), mode="hardened")
