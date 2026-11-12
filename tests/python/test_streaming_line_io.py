"""Compressed, incremental line-format I/O and observable prefix contracts."""

import bz2
import gzip
import io

import networkx as nx
import pytest

import franken_networkx as fnx
import franken_networkx.readwrite as readwrite


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
FORMATS = ("weighted_edgelist", "multiline_adjlist")
PARSERS = ("edgelist", "adjlist", "multiline_adjlist")


def _snapshot(graph):
    edges = (
        list(graph.edges(keys=True, data=True))
        if graph.is_multigraph()
        else list(graph.edges(data=True))
    )
    return list(graph), edges, {node: list(graph[node]) for node in graph}


def _graph(lib, graph_type):
    graph = getattr(lib, graph_type)()
    graph.add_node("isolated")
    graph.add_edge("naïve", "café", weight=1.5)
    graph.add_edge("café", "third")
    graph.add_edge("third", "third", weight=-2)
    graph.add_edge("naïve", "café", weight=3)
    if graph.is_directed():
        graph.add_edge("café", "naïve", weight=4)
    return graph


def _payload(kind):
    if kind == "multiline_adjlist":
        return "0 1\n1 {'weight': 2}\n1 1\n2 {'weight': 3}\n2 0\n"
    if kind == "weighted_edgelist":
        return "0 1 2\n1 2 3\n"
    return "0 1\n1 2\n"


def _decompressed(path, encoding):
    if path.suffix in (".gz", ".gzip"):
        opener = gzip.open
    elif path.suffix == ".bz2":
        opener = bz2.open
    else:
        opener = open
    with opener(path, "rb") as handle:
        return handle.read().decode(encoding)


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("suffix", (".txt", ".gz", ".gzip", ".bz2"))
@pytest.mark.parametrize("encoding", ("utf-8", "latin-1"))
def test_compressed_roundtrip_and_cross_library_payload(
    tmp_path, kind, graph_type, suffix, encoding
):
    path = tmp_path / ("graph" + suffix)
    actual_graph = _graph(fnx, graph_type)
    expected_graph = _graph(nx, graph_type)
    writer = getattr(fnx, "write_" + kind)
    reader = getattr(fnx, "read_" + kind)
    # Alternate str and pathlib paths without doubling the whole matrix.
    destination = str(path) if graph_type in ("Graph", "MultiDiGraph") else path
    writer(actual_graph, destination, encoding=encoding)
    actual = reader(
        destination, create_using=getattr(fnx, graph_type), encoding=encoding
    )
    expected_bytes = io.BytesIO()
    getattr(nx, "write_" + kind)(expected_graph, expected_bytes, encoding=encoding)
    expected_bytes.seek(0)
    expected = getattr(nx, "read_" + kind)(
        expected_bytes, create_using=getattr(nx, graph_type), encoding=encoding
    )
    assert _snapshot(actual) == _snapshot(expected)
    payload = _decompressed(path, encoding)
    expected_payload = expected_bytes.getvalue().decode(encoding)
    # Timestamp headers are independent of graph serialization.
    assert [line for line in payload.splitlines() if not line.startswith("#")] == [
        line for line in expected_payload.splitlines() if not line.startswith("#")
    ]
    cross_read = getattr(nx, "read_" + kind)(
        destination, create_using=getattr(nx, graph_type), encoding=encoding
    )
    assert _snapshot(cross_read) == _snapshot(expected)


@pytest.mark.parametrize("kind", PARSERS)
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_interrupted_iterator_retains_prefix(kind, graph_type):
    graphs = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        graph.add_node("removed")

        def lines():
            assert not graph
            yield "0 1\n"
            if kind == "multiline_adjlist":
                assert list(graph) == [0]
                yield "1\n"
            assert list(graph) == [0, 1]
            assert graph.has_edge(0, 1)
            raise OSError("source interrupted")

        with pytest.raises(OSError, match="source interrupted"):
            getattr(lib, "parse_" + kind)(
                lines(), nodetype=int, create_using=graph
            )
        graphs.append(graph)
    assert _snapshot(graphs[0]) == _snapshot(graphs[1])


@pytest.mark.parametrize("kind", PARSERS)
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_late_conversion_error_keeps_source_and_prior_edges(kind, graph_type):
    lines = ["0 1\n", "2 bad\n"]
    if kind == "multiline_adjlist":
        lines = ["0 1\n", "1\n", "2 1\n", "bad\n"]
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        with pytest.raises(TypeError) as error:
            getattr(lib, "parse_" + kind)(
                iter(lines), nodetype=int, create_using=graph
            )
        results.append((_snapshot(graph), str(error.value)))
    assert results[0] == results[1]


@pytest.mark.parametrize("kind", PARSERS)
def test_converter_and_graph_method_order_on_public_graph_protocol(kind):
    def run(parser):
        events = []

        class Observed(nx.DiGraph):
            def clear(self):
                events.append(("clear", list(self)))
                return super().clear()

            def add_node(self, node, **attrs):
                events.append(("node", node))
                return super().add_node(node, **attrs)

            def add_edge(self, u, v, **attrs):
                events.append(("edge", u, v))
                return super().add_edge(u, v, **attrs)

            def add_edges_from(self, edges, **attrs):
                events.append(("edges", list(self)))
                return super().add_edges_from(edges, **attrs)

        graph = Observed()
        graph.add_node("removed")
        events.clear()

        def lines():
            for line in _payload(kind).splitlines():
                events.append(("next", line, list(graph), list(graph.edges())))
                yield line

        def convert(token):
            events.append(("convert", token, list(graph), list(graph.edges())))
            return int(token)

        parser(lines(), nodetype=convert, create_using=graph)
        return events, _snapshot(graph)

    assert run(getattr(fnx, "parse_" + kind)) == run(getattr(nx, "parse_" + kind))


@pytest.mark.parametrize("kind", PARSERS)
def test_custom_source_iterator_protocol_matches_networkx(kind):
    def run(lib):
        events = []
        graph = lib.DiGraph()

        class Lines:
            def __init__(self):
                self.records = iter(_payload(kind).splitlines())

            def __iter__(self):
                events.append(("iter", list(graph)))
                return self

            def __next__(self):
                events.append(("next", list(graph)))
                return next(self.records)

        getattr(lib, "parse_" + kind)(Lines(), create_using=graph, nodetype=int)
        return events, _snapshot(graph)

    actual, expected = run(fnx), run(nx)
    assert actual == expected, (actual, expected)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_native_adjacency_rows_preserve_custom_converter_observations(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)()
        events = []

        def convert(token):
            events.append((token, list(graph), graph.number_of_edges()))
            return int(token)

        lib.parse_adjlist(
            iter(["0 1 2", "2 3 4"]), create_using=graph, nodetype=convert
        )
        return events, _snapshot(graph)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("hook", ("instance", "class"))
def test_adjacency_row_rechecks_live_method_hook(monkeypatch, hook):
    graph = fnx.DiGraph()
    original = fnx.DiGraph.add_edges_from
    observed = []

    def add_edges(self, edges, **attrs):
        observed.append((type(edges).__name__, list(self)))
        return original(self, edges, **attrs)

    def lines():
        yield "0 1"
        if hook == "instance":
            monkeypatch.setattr(graph, "add_edges_from", add_edges.__get__(graph))
        else:
            monkeypatch.setattr(fnx.DiGraph, "add_edges_from", add_edges)
        yield "2 3"

    fnx.parse_adjlist(lines(), create_using=graph, nodetype=int)
    assert observed == [("generator", [0, 1, 2])]
    assert list(graph.edges()) == [(0, 1), (2, 3)]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_adjacency_parser_keeps_native_subclass_mutation_hook(graph_type):
    observed = []

    class Observed(getattr(fnx, graph_type)):
        def add_edges_from(self, edges, **attrs):
            observed.append((type(edges).__name__, list(self)))
            return super().add_edges_from(edges, **attrs)

    graph = Observed()
    fnx.parse_adjlist(iter(["0 1", "2 3"]), create_using=graph, nodetype=int)
    assert observed == [("generator", [0]), ("generator", [0, 1, 2])]
    assert graph.number_of_edges() == 2


def test_adjacency_parser_respects_assigned_native_graph_storage():
    graph = fnx.DiGraph()
    adjacency, predecessors, nodes = {}, {}, {}
    graph._adj = adjacency
    graph._pred = predecessors
    graph._node = nodes
    fnx.parse_adjlist(iter(["0 1", "2 3"]), create_using=graph, nodetype=int)
    assert list(adjacency) == list(predecessors) == list(nodes) == [0, 1, 2, 3]
    assert list(adjacency[0]) == [1]
    assert list(adjacency[2]) == [3]
    assert list(predecessors[1]) == [0]
    assert list(predecessors[3]) == [2]


@pytest.mark.parametrize("graph_type", ("MultiGraph", "MultiDiGraph"))
@pytest.mark.parametrize("hook", ("instance", "class", "subclass"))
def test_adjacency_parser_preserves_multigraph_add_edge_hooks(monkeypatch, graph_type, hook):
    def run(lib):
        base = getattr(lib, graph_type)
        original = base.add_edge
        events = []

        def add_edge(self, u, v, key=None, **attrs):
            events.append((u, v, key, self.number_of_edges()))
            return original(self, u, v, key, **attrs)

        if hook == "subclass":
            graph_type_with_hook = type("Observed", (base,), {"add_edge": add_edge})
            graph = graph_type_with_hook()
        else:
            graph = base()
            if hook == "class":
                monkeypatch.setattr(base, "add_edge", add_edge)
            else:
                monkeypatch.setattr(graph, "add_edge", add_edge.__get__(graph))
        lib.parse_adjlist(iter(["0 1 2", "0 1"]), create_using=graph, nodetype=int)
        return events, _snapshot(graph)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", ("MultiGraph", "MultiDiGraph"))
def test_multigraph_add_edge_hook_invalid_return_preserves_error_prefix(graph_type):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        original = graph.add_edge

        def add_edge(u, v, key=None):
            actual_key = original(u, v, key)
            return actual_key if v == 1 else "missing-key"

        graph.add_edge = add_edge
        with pytest.raises(KeyError) as error:
            lib.parse_adjlist(["0 1 2"], nodetype=int, create_using=graph)
        results.append((_snapshot(graph), error.value.args))
    assert results[0] == results[1]


def test_custom_multigraph_row_hook_remains_authoritative():
    graph = fnx.MultiGraph()
    events = []

    def add_edge(*args, **kwargs):
        raise AssertionError("custom row hook must retain control")

    def add_edges(edges, **attrs):
        events.append(list(edges))

    graph.add_edge = add_edge
    graph.add_edges_from = add_edges
    fnx.parse_adjlist(["0 1 2"], nodetype=int, create_using=graph)
    assert events == [[(0, 1), (0, 2)]]
    assert list(graph) == [0]


@pytest.mark.parametrize("hook", ("instance", "class"))
def test_edge_parser_respects_native_graph_add_edge_hooks(monkeypatch, hook):
    graph = fnx.DiGraph()
    events = []
    original = fnx.DiGraph.add_edge

    def add_edge(self, u, v, **attrs):
        events.append((u, v, self.number_of_edges()))
        return original(self, u, v, **attrs)

    if hook == "class":
        monkeypatch.setattr(fnx.DiGraph, "add_edge", add_edge)
    else:
        monkeypatch.setattr(graph, "add_edge", add_edge.__get__(graph))
    fnx.parse_edgelist(["0 1", "1 2"], nodetype=int, create_using=graph)
    assert events == [(0, 1, 0), (1, 2, 1)]


@pytest.mark.parametrize("bad_line, data", [
    ("1 2 {3: 4}", True),
    ("1 2 {'weight':", True),
    ("1 2 invalid", (("weight", float),)),
    ("1 2 3 4", (("weight", float),)),
])
def test_edgelist_attribute_failure_preserves_prior_records(bad_line, data):
    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        with pytest.raises((TypeError, IndexError)) as error:
            lib.parse_edgelist(
                iter(["0 1", bad_line]), nodetype=int, data=data, create_using=graph
            )
        results.append((_snapshot(graph), type(error.value), str(error.value)))
    assert results[0] == results[1]


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("text", (False, True))
def test_line_only_caller_stream_is_incremental_and_stays_open(kind, text):
    base = io.StringIO if text else io.BytesIO

    class LineOnly(base):
        def read(self, *args):
            raise AssertionError("reader must iterate lines")

        def readlines(self, *args):
            raise AssertionError("reader must not buffer every line")

        def seek(self, *args):
            raise AssertionError("reader must not seek")

    payload = _payload(kind)
    stream = LineOnly(payload if text else payload.encode())
    actual = getattr(fnx, "read_" + kind)(stream, nodetype=int)
    expected = getattr(nx, "read_" + kind)(io.BytesIO(payload.encode()), nodetype=int)
    assert _snapshot(actual) == _snapshot(expected)
    assert not stream.closed


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("path_type", ("custom", "bytes"))
def test_existing_filesystem_path_extensions_still_roundtrip(tmp_path, kind, path_type):
    path = tmp_path / "graph.gz"

    class CustomPath:
        def __fspath__(self):
            return str(path)

    filename = CustomPath() if path_type == "custom" else bytes(path)
    graph = fnx.DiGraph()
    graph.add_edge(0, 1, weight=2)
    getattr(fnx, "write_" + kind)(graph, filename)
    parsed = getattr(fnx, "read_" + kind)(
        filename, nodetype=int, create_using=fnx.DiGraph
    )
    assert _snapshot(parsed) == _snapshot(graph)


@pytest.mark.parametrize("kind", FORMATS)
def test_reader_late_decode_failure_keeps_prefix_and_stream_open(kind):
    prefix = "0 1 2\n" if kind == "weighted_edgelist" else "0 1\n1\n"
    results = []
    for lib in (nx, fnx):
        stream = io.BytesIO(prefix.encode() + b"\xff\n")
        graph = lib.DiGraph()
        with pytest.raises(UnicodeDecodeError):
            getattr(lib, "read_" + kind)(
                stream, nodetype=int, create_using=graph, encoding="utf-8"
            )
        assert not stream.closed
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("kind", PARSERS)
def test_parsers_do_not_retain_prior_input_records(kind):
    live = set()

    class TrackedLine(str):
        def __new__(cls, value):
            result = super().__new__(cls, value)
            live.add(id(result))
            return result

        def __del__(self):
            live.discard(id(self))

    def lines():
        for _ in range(300):
            assert len(live) < 4, "parser retained previously consumed records"
            yield TrackedLine("0 1\n")
            if kind == "multiline_adjlist":
                yield TrackedLine("1\n")

    graph = getattr(fnx, "parse_" + kind)(lines(), nodetype=int)
    assert list(graph.edges()) == [(0, 1)]
    assert not live


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("text", (False, True))
def test_writer_uses_records_and_retains_caller_stream(kind, text):
    base = io.StringIO if text else io.BytesIO

    class RecordSink(base):
        def write(self, payload):
            if isinstance(payload, str) == text:
                lines = payload.splitlines()
                marker = "#" if text else b"#"
                assert len(lines) == 1 or (
                    len(lines) == 3 and all(line.startswith(marker) for line in lines)
                )
            return super().write(payload)

    graph = _graph(fnx, "MultiDiGraph")
    stream = RecordSink()
    getattr(fnx, "write_" + kind)(graph, stream)
    assert not stream.closed
    payload = stream.getvalue()
    if text:
        payload = payload.encode()
    actual = getattr(fnx, "read_" + kind)(io.BytesIO(payload), create_using=fnx.MultiDiGraph)
    expected = getattr(nx, "read_" + kind)(io.BytesIO(payload), create_using=nx.MultiDiGraph)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("kind", FORMATS)
def test_writer_late_encoding_failure_preserves_prefix(kind):
    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        graph.add_edge("a", "b", weight=2)
        graph.add_edge("b", "snowman-☃", weight=3)
        stream = io.BytesIO()
        with pytest.raises(UnicodeEncodeError):
            getattr(lib, "write_" + kind)(graph, stream, encoding="ascii")
        assert not stream.closed
        results.append([
            line for line in stream.getvalue().splitlines()
            if not line.startswith(b"#")
        ])
    assert results[0] == results[1]
    assert results[0]


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("error_type", (OSError, TypeError))
def test_writer_propagates_later_sink_failure_without_retry(kind, error_type):
    class FailingSink(io.BytesIO):
        calls = 0

        def write(self, payload):
            self.calls += 1
            if self.calls == 2:
                raise error_type("destination failed")
            return super().write(payload)

    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=3)
        stream = FailingSink()
        with pytest.raises(error_type, match="destination failed"):
            getattr(lib, "write_" + kind)(graph, stream)
        assert not stream.closed
        results.append((stream.calls, stream.getvalue()))
    assert results[0] == results[1], results
    assert results[0][0] == 2


@pytest.mark.parametrize("kind", FORMATS)
def test_writer_observes_later_attribute_changes_from_sink(kind):
    def run(lib):
        graph = lib.DiGraph()
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(2, 3, weight=3)

        class UpdatingSink(io.BytesIO):
            def write(self, payload):
                if not payload.startswith(b"#"):
                    graph[2][3]["weight"] = 9
                return super().write(payload)

        stream = UpdatingSink()
        getattr(lib, "write_" + kind)(graph, stream)
        return [line for line in stream.getvalue().splitlines() if not line.startswith(b"#")]

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_multiline_writer_observes_new_edge_in_later_row(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)()
        graph.add_nodes_from([0, 1, 2, 3])
        graph.add_edge(0, 1, weight=2)

        class UpdatingSink(io.BytesIO):
            updated = False

            def write(self, payload):
                if not self.updated and not payload.startswith(b"#"):
                    self.updated = True
                    graph.add_edge(2, 3, weight=9)
                return super().write(payload)

        stream = UpdatingSink()
        lib.write_multiline_adjlist(graph, stream)
        return [line for line in stream.getvalue().splitlines() if not line.startswith(b"#")]

    assert run(fnx) == run(nx)


def test_multiline_writer_honors_custom_adjacency_hook():
    graph = fnx.DiGraph()
    graph.adjacency = lambda: iter([("source", {"target": {"weight": 2}})])
    stream = io.BytesIO()
    fnx.write_multiline_adjlist(graph, stream)
    assert [line for line in stream.getvalue().splitlines() if not line.startswith(b"#")] == [
        b"source 1", b"target {'weight': 2}"
    ]


@pytest.mark.parametrize("kind", FORMATS)
@pytest.mark.parametrize("operation", ("read", "write"))
@pytest.mark.parametrize("fail", (False, True))
def test_compressed_path_handles_close_even_on_errors(tmp_path, monkeypatch, kind, operation, fail):
    path = tmp_path / "graph.gz"
    payload = _payload(kind)
    if operation == "read":
        if fail:
            payload += "bad 1\n" if kind == "multiline_adjlist" else "1 2 invalid\n"
        with gzip.open(path, "wb") as stream:
            stream.write(payload.encode())
    opened = []
    original_open = gzip.open

    def tracking_open(*args, **kwargs):
        handle = original_open(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(gzip, "open", tracking_open)

    def call():
        if operation == "read":
            return getattr(fnx, "read_" + kind)(path, nodetype=int)
        graph = fnx.Graph()
        graph.add_edge("a", "☃" if fail else "b", weight=2)
        return getattr(fnx, "write_" + kind)(graph, path, encoding="ascii")

    if fail:
        with pytest.raises((TypeError, UnicodeEncodeError)):
            call()
    else:
        call()
    assert opened
    assert all(handle.closed for handle in opened)


def test_weighted_writer_does_not_invent_missing_weights():
    graph = fnx.DiGraph()
    graph.add_edge("a", "b", weight=2)
    graph.add_edge("b", "c")
    stream = io.BytesIO()
    fnx.write_weighted_edgelist(graph, stream)
    assert stream.getvalue() == b"a b 2\nb c\n"
    stream.seek(0)
    parsed = fnx.read_weighted_edgelist(stream, create_using=fnx.DiGraph)
    assert parsed["b"]["c"] == {}


def test_ordinary_multiline_file_retains_byte_parser(tmp_path, monkeypatch):
    path = tmp_path / "graph.txt"
    path.write_text("0 1\n1\n1 0\n")

    def unexpected(*args, **kwargs):
        raise AssertionError("ordinary default file lost its byte-parser route")

    monkeypatch.setattr(readwrite, "parse_multiline_adjlist", unexpected)
    assert list(fnx.read_multiline_adjlist(path).edges()) == [("0", "1")]


def test_ordinary_weighted_file_retains_native_parser(tmp_path, monkeypatch):
    path = tmp_path / "graph.txt"
    path.write_text("0 1 2.5\n1 2 3\n")

    def unexpected(*args, **kwargs):
        raise AssertionError("ordinary default weighted file lost its native route")

    monkeypatch.setattr(readwrite, "parse_edgelist", unexpected)
    assert list(fnx.read_weighted_edgelist(str(path)).edges(data="weight")) == [
        ("0", "1", 2.5), ("1", "2", 3.0)
    ]


def test_string_convenience_parser_input_still_splits_lines():
    assert list(fnx.parse_edgelist("0 1\n1 2\n", nodetype=int).edges()) == [(0, 1), (1, 2)]
    assert list(fnx.parse_adjlist("0 1\n1 2\n", nodetype=int).edges()) == [(0, 1), (1, 2)]
    assert list(fnx.parse_multiline_adjlist("0 1\n1\n1 1\n2\n", nodetype=int).edges()) == [(0, 1), (1, 2)]
