"""Regression tests for the fnx-readwrite three-pass audit fixes.

These tests pin parser / writer error contracts to the wording
NetworkX uses, so future drift between the in-house Rust path and
the upstream nx behavior surfaces as a test failure rather than as
a silent divergence.

- Pass 1 (clippy ``manual_filter`` cleanups) is style-only — no
  behavioral test needed.
- Pass 2 (GML structural validation): duplicate node id, unbalanced
  brackets, stray ']' tokens.
- Pass 3 (boundary checks): create_using type validation, GraphML
  writer rejection of unsupported value types.
"""

from __future__ import annotations

import io
import json
import math

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Pass 2 — GML structural-error parity
# ---------------------------------------------------------------------------


class TestGmlStructuralErrorParity:
    """The Python ``parse_gml`` runs the Rust reader in strict mode so
    structural errors surface as ``NetworkXError`` matching nx."""

    def test_duplicate_node_id_raises_networkx_error_matching_nx(self):
        gml = (
            'graph [ node [ id 0 label "a" ]'
            ' node [ id 0 label "a2" ] ]'
        )
        with pytest.raises(fnx.NetworkXError, match=r"node id 0 is duplicated"):
            fnx.parse_gml(gml)
        # Mirror: nx itself raises the same base type with the same wording.
        with pytest.raises(nx.NetworkXError, match=r"node id 0 is duplicated"):
            nx.parse_gml(gml)

    def test_unbalanced_graph_block_raises_networkx_error(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("graph [ node [ id 0 ")

    def test_extra_closing_bracket_raises_networkx_error(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("graph [ ] ]")

    def test_stray_closing_bracket_in_prologue_raises(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("] graph [ ]")

    def test_empty_gml_raises_networkx_error_matching_nx(self):
        with pytest.raises(fnx.NetworkXError, match=r"input contains no graph"):
            fnx.parse_gml("")
        with pytest.raises(nx.NetworkXError, match=r"input contains no graph"):
            nx.parse_gml("")

    def test_valid_gml_round_trip_still_works(self):
        text = (
            'graph [ node [ id 0 label "a" ]'
            ' node [ id 1 label "b" ]'
            ' edge [ source 0 target 1 ] ]'
        )
        g = fnx.parse_gml(text)
        assert g.number_of_nodes() == 2
        assert g.number_of_edges() == 1


# ---------------------------------------------------------------------------
# Pass 3 — create_using validation
# ---------------------------------------------------------------------------


class TestCreateUsingTypeValidation:
    """parse_edgelist / parse_adjlist must raise ``TypeError`` with nx's
    wording when ``create_using`` is neither a Graph type nor instance.
    Previously fnx leaked an internal ``AttributeError: 'int' object
    has no attribute 'clear'`` for invalid arguments.
    """

    @pytest.mark.parametrize(
        "bad",
        [42, "string", 3.14, ["list"], {"dict": True}],
    )
    def test_parse_edgelist_invalid_create_using_raises(self, bad):
        with pytest.raises(
            TypeError,
            match=r"create_using is not a valid NetworkX graph type or instance",
        ):
            fnx.parse_edgelist(["0 1"], create_using=bad)

    @pytest.mark.parametrize(
        "bad",
        [42, 3.14],
    )
    def test_parse_adjlist_invalid_create_using_raises(self, bad):
        with pytest.raises(
            TypeError,
            match=r"create_using is not a valid NetworkX graph type or instance",
        ):
            fnx.parse_adjlist(["0 1"], create_using=bad)

    def test_parse_edgelist_valid_create_using_still_works(self):
        g = fnx.parse_edgelist(["0 1", "2 3"], create_using=fnx.DiGraph)
        assert g.is_directed()
        assert g.number_of_edges() == 2


# ---------------------------------------------------------------------------
# Pass 3 — GraphML writer attribute-type validation
# ---------------------------------------------------------------------------


class TestGraphmlWriterTypeValidation:
    """nx raises ``NetworkXError("GraphML writer does not support
    <class 'X'> as data values.")`` when an attribute value's type
    can't be encoded in GraphML. fnx silently coerced None / set /
    tuple / list to ``str(value)``, diverging from nx parity."""

    @pytest.mark.parametrize(
        "value,kind_pattern",
        [
            (b"bytes", r"bytes"),
            (None, r"NoneType"),
            ({"a", "b"}, r"set"),
            ((1.0, 2.0), r"tuple"),
            (["a", "b"], r"list"),
        ],
    )
    def test_unsupported_edge_attr_type_raises(self, value, kind_pattern):
        g = fnx.Graph()
        g.add_edge(0, 1, x=value)
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*" + kind_pattern,
        ):
            fnx.write_graphml(g, buf)

    @pytest.mark.parametrize(
        "value,kind_pattern",
        [
            (b"bytes", r"bytes"),
            (None, r"NoneType"),
            ({"a"}, r"set"),
        ],
    )
    def test_unsupported_node_attr_type_raises(self, value, kind_pattern):
        g = fnx.Graph()
        g.add_node(0, payload=value)
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*" + kind_pattern,
        ):
            fnx.write_graphml(g, buf)

    def test_unsupported_graph_attr_type_raises(self):
        g = fnx.Graph()
        g.graph["payload"] = b"bytes"
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*bytes",
        ):
            fnx.write_graphml(g, buf)

    def test_supported_types_pass_through(self):
        g = fnx.Graph()
        g.add_edge(0, 1, w=1.5, label="x", flag=True, count=42)
        g.add_node(2, name="payload")
        buf = io.BytesIO()
        fnx.write_graphml(g, buf)
        # Round-trip restores the same number of edges/nodes
        text = buf.getvalue().decode("utf-8")
        round_trip = fnx.parse_graphml(text)
        assert round_trip.number_of_nodes() == 3
        assert round_trip.number_of_edges() == 1

    @pytest.mark.parametrize("scope", ["graph", "node", "edge"])
    def test_default_metadata_does_not_admit_dictionary_data_values(self, scope):
        g = fnx.Graph()
        g.graph["node_default"] = {"color": "blue"}
        g.graph["edge_default"] = {"weight": 1}
        g.add_edge("first", "last")
        data = {
            "graph": g.graph,
            "node": g.nodes["first"],
            "edge": g["first"]["last"],
        }[scope]
        data["payload"] = {"nested": "unsupported"}
        with pytest.raises(fnx.NetworkXError, match=r"GraphML writer does not support .*dict"):
            fnx.write_graphml(g, io.BytesIO())

    @pytest.mark.parametrize("scalar_name,value", [("bool_", True), ("complex64", 1j)])
    @pytest.mark.parametrize("scope", ["graph", "node", "edge"])
    def test_unsupported_numpy_types_still_fail_closed(self, scalar_name, value, scope):
        np = pytest.importorskip("numpy")
        scalar = getattr(np, scalar_name)(value)
        graphs = [nx.Graph(), fnx.Graph()]
        for graph in graphs:
            graph.add_edge("first", "last")
            data = {
                "graph": graph.graph,
                "node": graph.nodes["first"],
                "edge": graph["first"]["last"],
            }[scope]
            data["value"] = scalar
        # NetworkX's optional lxml writer and its XML fallback use different
        # exception classes, but both reject these unsupported scalar types.
        with pytest.raises((TypeError, nx.NetworkXError), match="GraphML .*not support"):
            nx.write_graphml(graphs[0], io.BytesIO())
        with pytest.raises(fnx.NetworkXError, match="GraphML writer does not support"):
            fnx.write_graphml(graphs[1], io.BytesIO())
        for library, graph in zip((nx, fnx), graphs):
            with pytest.raises((TypeError, library.NetworkXError), match="GraphML .*not support"):
                list(library.generate_graphml(graph))


class TestParseGmlLabelAndDestringizerParity:
    """parse_gml must accept the same ``label`` and ``destringizer``
    customizations as nx.parse_gml. Previously fnx.parse_gml raised
    ``NetworkXError("parse_gml currently supports only label='label'
    and no destringizer")`` for any non-default value, breaking drop-in
    parity. The wrapper now falls back to upstream ``nx.parse_gml`` for
    those modes and converts the result back to fnx via
    ``_from_nx_graph``.
    """

    def test_parse_gml_label_id_matches_networkx(self):
        # Two nodes with only ``id`` (no ``label``) — nx supports this
        # via ``label='id'``; fnx must accept it identically.
        gml = (
            "graph [\n"
            "  node [ id 0 ]\n"
            "  node [ id 1 ]\n"
            "  edge [ source 0 target 1 ]\n"
            "]"
        )
        nx_g = nx.parse_gml(gml, label="id")
        fnx_g = fnx.parse_gml(gml, label="id")
        assert sorted(fnx_g.nodes()) == sorted(nx_g.nodes()) == [0, 1]
        assert sorted(fnx_g.edges()) == sorted(nx_g.edges()) == [(0, 1)]

    def test_parse_gml_destringizer_int_coerces_labels(self):
        # Labels arrive as quoted strings ("42", "7") but destringizer=int
        # turns them into Python ints. nx and fnx must coerce identically.
        gml = (
            "graph [\n"
            '  node [ id 0 label "42" ]\n'
            '  node [ id 1 label "7" ]\n'
            "  edge [ source 0 target 1 ]\n"
            "]"
        )
        nx_g = nx.parse_gml(gml, destringizer=int)
        fnx_g = fnx.parse_gml(gml, destringizer=int)
        assert sorted(fnx_g.nodes()) == sorted(nx_g.nodes()) == [7, 42]
        assert all(isinstance(n, int) for n in fnx_g.nodes())

    def test_parse_gml_label_id_with_destringizer(self):
        gml = (
            "graph [\n"
            "  node [ id 0 ]\n"
            "  node [ id 1 ]\n"
            "  edge [ source 0 target 1 ]\n"
            "]"
        )
        fnx_g = fnx.parse_gml(gml, label="id", destringizer=str)
        nx_g = nx.parse_gml(gml, label="id", destringizer=str)
        # destringizer=str leaves int ids alone (id parsed as int by GML)
        assert sorted(fnx_g.nodes()) == sorted(nx_g.nodes())

    def test_parse_gml_default_still_uses_rust_reader(self):
        # Sanity: the default path is unaffected — labels still required
        # and the Rust reader's structural validations still fire.
        with pytest.raises(fnx.NetworkXError, match=r"has no 'label' attribute"):
            fnx.parse_gml("graph [ node [ id 0 ] ]")

    def test_parse_gml_empty_label_id_rejected_like_nx(self):
        # Empty input on the label='id' (nx-fallback) path must still
        # raise NetworkXError, matching the default-path behavior.
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("", label="id")

    def test_other_readwrite_parsers_reject_unexpected_backend_kwargs(self, tmp_path):
        """Companion follow-up: from_graph6_bytes, from_sparse6_bytes,
        parse_pajek, parse_leda, read_graph6, read_sparse6, read_pajek,
        read_leda used to silently swallow free kwargs like
        ``garbage_kw='x'``. They now route through
        ``_validate_backend_dispatch_keywords`` and raise TypeError
        the way nx does. ImportError for unknown ``backend=`` is
        the same path (via the validator).
        """
        # Parsers that operate on lines/bytes directly
        cases = [
            ("from_graph6_bytes", lambda fn: fn(b"A_", garbage_kw="x")),
            ("from_sparse6_bytes", lambda fn: fn(b":A_", garbage_kw="x")),
            ("parse_pajek", lambda fn: fn(["*Vertices 0"], garbage_kw="x")),
            (
                "parse_leda",
                lambda fn: fn(
                    ["LEDA.GRAPH", "void", "int", "-1", "0", "0"],
                    garbage_kw="x",
                ),
            ),
        ]
        for name, call in cases:
            fnx_fn = getattr(fnx, name, None) or getattr(fnx.readwrite, name)
            with pytest.raises(TypeError):
                call(fnx_fn)

        # Readers that take a path — write a tiny file then exercise
        # the wrapper with a garbage kwarg. They must still reject
        # before opening the file (the validation runs first).
        sample = tmp_path / "sample.g6"
        sample.write_bytes(b"A_")
        path_cases = ["read_graph6", "read_sparse6", "read_pajek", "read_leda"]
        for name in path_cases:
            fnx_fn = getattr(fnx, name, None) or getattr(fnx.readwrite, name)
            with pytest.raises(TypeError):
                fnx_fn(str(sample), garbage_kw="x")

    def test_parse_gml_rejects_invalid_backend_dispatch_kwargs(self):
        """br-r37-c1-a4yvc: parse_gml previously accepted any
        ``backend=`` / ``**backend_kwargs`` silently. nx raises
        ImportError for unknown backends and TypeError for stray
        positional kwargs — fnx must match both via the shared
        dispatch-keyword guard.
        """
        gml = (
            "graph [\n"
            '  node [ id 0 label "a" ]\n'
            '  node [ id 1 label "b" ]\n'
            "  edge [ source 0 target 1 ]\n"
            "]"
        )
        # Unknown backend — nx's guard raises ImportError
        with pytest.raises(ImportError):
            fnx.parse_gml(gml, backend="definitely_no_such_backend")
        # Random kwarg — nx raises TypeError
        with pytest.raises(TypeError):
            fnx.parse_gml(gml, garbage_kwarg=True)
        # Validation also fires on the nx-fallback (label='id') path
        with pytest.raises(TypeError):
            fnx.parse_gml(gml, label="id", garbage_kwarg=True)
        # backend=None is fine
        g = fnx.parse_gml(gml, backend=None)
        assert sorted(g.nodes()) == ["a", "b"]

    def test_remaining_readwrite_dispatch_wrappers_reject_stray_kwargs(self, tmp_path):
        """Review hardening: every readwrite wrapper with the nx
        dispatch surface must reject stray backend kwargs instead of
        silently accepting them.
        """
        parse_cases = [
            ("parse_adjlist", lambda fn: fn(["0 1"], garbage_kw="x")),
            ("parse_edgelist", lambda fn: fn(["0 1"], garbage_kw="x")),
            (
                "parse_multiline_adjlist",
                lambda fn: fn(["0 1", "1"], garbage_kw="x"),
            ),
        ]
        for name, call in parse_cases:
            with pytest.raises(TypeError):
                call(getattr(fnx, name))
            with pytest.raises(TypeError):
                call(getattr(nx, name))

        multiline_path = tmp_path / "sample.adjlist"
        multiline_path.write_text("0 1\n1\n")
        weighted_path = tmp_path / "sample.edgelist"
        weighted_path.write_text("0 1 2.0\n")
        gexf_path = tmp_path / "sample.gexf"
        nx.write_gexf(nx.path_graph(2), gexf_path)

        path_cases = [
            ("read_multiline_adjlist", multiline_path),
            ("read_weighted_edgelist", weighted_path),
            ("read_gexf", gexf_path),
        ]
        for name, path in path_cases:
            with pytest.raises(TypeError):
                getattr(fnx, name)(path, garbage_kw="x")
            with pytest.raises(TypeError):
                getattr(nx, name)(path, garbage_kw="x")


# ---------------------------------------------------------------------------
# Standard node-link JSON file ingestion
# ---------------------------------------------------------------------------


class _JsonFileReadOnce:
    """A caller-owned stream with no seek operation or repeated-read allowance."""

    def __init__(self, payload):
        self.payload = payload
        self.reads = 0
        self.closed = False

    def read(self):
        self.reads += 1
        assert self.reads == 1
        return self.payload

    def close(self):
        self.closed = True


def _json_file_rich_graph(graph_type):
    graph = getattr(nx, graph_type)()
    large = 2**2000 + 17
    pair = (3, "β")
    graph.graph.update(
        name="node-link α",
        metadata={"values": [None, True, {"large": -large, "zero": -0.0}]},
    )
    graph.add_node(large, payload={"nested": [1, "one", False]})
    graph.add_node(str(large), label="same spelling, distinct node")
    graph.add_node(pair, payload=[{"active": True}, None])
    graph.add_node("isolate", note="retained")
    if graph.is_multigraph():
        graph.add_edge(large, pair, key="primary", weight=large, tags=["a", {"b": 2}])
        graph.add_edge(large, pair, key=-11, weight=-2, color="parallel")
        graph.add_edge(pair, pair, key=19, weight=0)
    else:
        graph.add_edge(large, pair, weight=large, key=[1, {"ordinary": "attribute"}])
        graph.add_edge(pair, pair, weight=0)
    if graph.is_directed():
        graph.add_edge(pair, large, weight=5)
    return graph


def _assert_json_file_policy(graph, mode, data, edge_field="edges"):
    assert graph.mode == mode
    records = [
        record for record in graph.decision_records()
        if record["operation"] == "read_json_graph"
    ]
    assert len(records) == 1
    record = records[0]
    assert record["mode"] == mode
    assert record["action"] == "allow"
    assert record["rationale"] == "standard node-link JSON validation completed"
    evidence = {term["signal"]: term["observed_value"] for term in record["evidence"]}
    assert evidence["node_records"] == str(len(data["nodes"]))
    assert evidence["edge_records"] == str(len(data[edge_field]))
    assert evidence["edge_field"] == edge_field


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("edge_field", ["edges", "links"])
@pytest.mark.parametrize("binary", [False, True])
def test_json_graph_file_preserves_rich_graphs_and_original_policy(
    graph_type, mode, edge_field, binary, monkeypatch
):
    original = _json_file_rich_graph(graph_type)
    text = json.dumps(nx.node_link_data(original, edges=edge_field), ensure_ascii=False, indent=2)
    data = json.loads(text)
    expected = nx.node_link_graph(data, edges=edge_field)
    expected_data = nx.node_link_data(expected)

    def no_fallback(*args, **kwargs):
        raise AssertionError("standard input must use the owned complete decoder")

    monkeypatch.setattr(nx, "node_link_graph", no_fallback)
    monkeypatch.setattr(fnx, "_rust_read_json_graph", no_fallback)
    native_validate = fnx._fnx.validate_node_link_json
    validated = []

    def validate_original(payload, *args, **kwargs):
        validated.append(payload)
        return native_validate(payload, *args, **kwargs)

    monkeypatch.setattr(fnx._fnx, "validate_node_link_json", validate_original)
    stream = _JsonFileReadOnce(text.encode("utf-8") if binary else text)
    actual = fnx.read_json_graph(stream, mode=mode)

    assert type(actual) is getattr(fnx, graph_type)
    assert fnx.node_link_data(actual) == expected_data
    assert validated == [text]
    assert stream.reads == 1
    assert not stream.closed
    assert type(next(iter(actual))) is int
    assert next(iter(actual)) == 2**2000 + 17
    assert math.copysign(1, actual.graph["metadata"]["values"][2]["zero"]) == -1
    _assert_json_file_policy(actual, mode, data, edge_field)


@pytest.mark.parametrize("suffix", [".json", ".json.gz", ".json.bz2"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_reads_paths_and_compressed_files(tmp_path, suffix, mode):
    import bz2
    import gzip

    expected = _json_file_rich_graph("MultiDiGraph")
    data = nx.node_link_data(expected)
    content = json.dumps(data, ensure_ascii=False).encode("utf-8")
    path = tmp_path / ("graph" + suffix)
    opener = gzip.open if suffix.endswith(".gz") else bz2.open if suffix.endswith(".bz2") else open
    with opener(path, "wb") as stream:
        stream.write(content)
    actual = fnx.read_json_graph(path, mode=mode)
    assert type(actual) is fnx.MultiDiGraph
    assert fnx.node_link_data(actual) == nx.node_link_data(expected)
    _assert_json_file_policy(actual, mode, data)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_accepts_custom_pathlike(tmp_path, mode):
    path = tmp_path / "graph.json"
    path.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")

    class Path:
        def __fspath__(self):
            return str(path)

    actual = fnx.read_json_graph(Path(), mode=mode)
    assert type(actual) is fnx.MultiGraph
    assert len(actual) == 0
    _assert_json_file_policy(actual, mode, {"nodes": [], "edges": []})


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("ambient", ["strict", "hardened"])
@pytest.mark.parametrize("explicit", [None, "strict", "hardened"])
def test_json_graph_file_honors_ambient_and_explicit_modes(graph_type, ambient, explicit):
    data = nx.node_link_data(getattr(nx, graph_type)([(0, 1)]))
    stream = io.StringIO(json.dumps(data))
    previous = fnx.get_compatibility_mode()
    with fnx.compatibility_mode(ambient):
        actual = fnx.read_json_graph(stream, mode=explicit)
        assert fnx.get_compatibility_mode() == ambient
    assert fnx.get_compatibility_mode() == previous
    assert type(actual) is getattr(fnx, graph_type)
    assert not stream.closed
    _assert_json_file_policy(actual, explicit or ambient, data)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_preserves_default_ids_aliases_and_implicit_nodes(mode):
    data = {
        "nodes": [{"id": 1, "first": 1}, {"id": True, "second": 2},
                  {"name": "automatic"}, {"id": 2.0, "third": 3}],
        "edges": [{"source": True, "target": 2.0, "weight": 1},
                  {"source": 1.0, "target": False, "weight": 2},
                  {"source": 1, "target": 2, "weight": 4}],
    }
    expected = nx.node_link_graph(data)
    actual = fnx.read_json_graph(io.StringIO(json.dumps(data)), mode=mode)
    assert type(actual) is fnx.MultiGraph
    assert fnx.node_link_data(actual) == nx.node_link_data(expected)
    assert [(type(node), node) for node in actual] == [
        (type(node), node) for node in expected
    ]
    _assert_json_file_policy(actual, mode, data)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_preserves_nested_tuple_nodes_and_null_edge_key(mode):
    data = {
        "multigraph": True,
        "nodes": [{"id": [1, None, [2, "nested"]]}],
        "edges": [{"source": [1, None, [2, "nested"]], "target": [], "key": None}],
    }
    actual = fnx.read_json_graph(io.StringIO(json.dumps(data)), mode=mode)
    assert list(actual) == [(1, None, (2, "nested")), ()]
    assert list(actual.edges(keys=True)) == [((1, None, (2, "nested")), (), 0)]
    _assert_json_file_policy(actual, mode, data)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_preserves_python_exponent_decoding(mode):
    text = '{"graph":{"overflow":1e400},"nodes":[{"id":1e400}],"edges":[]}'
    data = json.loads(text)
    actual = fnx.read_json_graph(io.StringIO(text), mode=mode)
    assert list(actual) == [float("inf")]
    assert actual.graph["overflow"] == float("inf")
    _assert_json_file_policy(actual, mode, data)


@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize(
    "text",
    [
        '{"nodes":[],"edges":[],"links":[]}',
        '{"nodes":[],"edges":[],"schema_version":2}',
        '{"nodes":[],"edges":[],"mode":"strict","graph":{}}',
        '{"nodes":[],"edges":[],"directed":1}',
        '{"nodes":[],"edges":[],"multigraph":"false"}',
        '{"nodes":[],"edges":[],"graph":null}',
        '{"nodes":[],"edges":[],"graph":{"__fnx_incompatible_codec":2}}',
        '{"nodes":[],"edges":[],"graph":{"value":NaN}}',
        '{"nodes":null,"edges":[]}',
        '{"nodes":["old-style-node"],"edges":[]}',
        '{"nodes":[{"id": null }],"edges":[]}',
        '{"nodes":[{"id":{"unhashable":1}}],"edges":[]}',
        '{"nodes":[{"id":0,"__fnx_incompatible_codec":2}],"edges":[]}',
        '{"nodes":[],"edges":null}',
        '{"nodes":[],"edges":[1]}',
        '{"nodes":[],"edges":[{"source":0}]}',
        '{"nodes":[],"edges":[{"source":0,"target":null}]}',
        '{"nodes":[],"edges":[{"source":0,"target":1,"key": [1] }]}',
        '{"nodes":[],"edges":[{"source":0,"target":1,"key": {"x":2} }]}',
        '{"nodes":[],"edges":[{"source":0,"target":1,"__fnx_incompatible_codec":2}]}',
        r'{"nodes":[],"edges":[{"source":0,"target":1,"\u005f_fnx_incompatible_codec":2}]}',
    ],
)
def test_json_graph_file_standard_malformed_input_fails_closed(text, mode):
    stream = _JsonFileReadOnce(text)
    with pytest.raises(OSError, match="node-link"):
        fnx.read_json_graph(stream, mode=mode)
    assert stream.reads == 1
    assert not stream.closed


@pytest.mark.parametrize("directed", [None, False, True])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_json_graph_file_retains_private_snapshot_documents(directed, mode):
    data = {
        "mode": "strict", "graph_attrs": {"name": "snapshot"},
        "nodes": ["left", "right", "isolate"],
        "edges": [{"left": "left", "right": "right", "attrs": {"weight": 3}}],
    }
    if directed is not None:
        data["directed"] = directed
    stream = io.StringIO(json.dumps(data))
    actual = fnx.read_json_graph(stream, mode=mode)
    assert type(actual) is (fnx.DiGraph if directed else fnx.Graph)
    assert list(actual) == ["left", "right", "isolate"]
    assert list(actual.edges(data=True)) == [("left", "right", {"weight": 3})]
    assert actual.graph == {"name": "snapshot"}
    assert actual.mode == mode
    assert not stream.closed
    assert any(record["operation"] == "read_json_graph" for record in actual.decision_records())


def test_json_graph_file_retains_native_legacy_recovery_and_incompatibility_rejection():
    payload = {
        "mode": "strict", "nodes": ["left", "right"],
        "edges": [{"left": "", "right": "right", "attrs": {}}],
    }
    with pytest.raises(OSError):
        fnx.read_json_graph(io.StringIO(json.dumps(payload)), mode="strict")
    with pytest.warns(RuntimeWarning):
        actual = fnx.read_json_graph(io.StringIO(json.dumps(payload)), mode="hardened")
    assert list(actual) == ["left", "right"]
    assert actual.number_of_edges() == 0
    assert any(record["action"] == "full_validate" for record in actual.decision_records())

    payload["edges"] = [{
        "left": "left", "right": "right", "attrs": {"__fnx_incompatible_codec": 2},
    }]
    for mode in ("strict", "hardened"):
        with pytest.raises(OSError, match="incompatible edge metadata"):
            fnx.read_json_graph(io.StringIO(json.dumps(payload)), mode=mode)
