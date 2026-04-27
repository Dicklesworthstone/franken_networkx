"""Tests for Pajek, LEDA, and multiline adjacency-list wrappers."""

import gzip
from pathlib import Path
import warnings

import franken_networkx as fnx
import networkx as nx


def test_generate_and_parse_pajek_round_trip():
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.5)

    lines = list(fnx.generate_pajek(graph))
    parsed = fnx.parse_pajek(lines)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed["a"]["b"][0]["weight"] == 2.5


def test_generate_pajek_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.DiGraph()
    graph.add_node("left node", x=1.5, y=2.5, shape="box", color="deep blue")
    graph.add_node("right", id="7", empty="", score=4)
    graph.add_edge("left node", "right", weight=2.25, label="main edge", ignored=3)

    expected_graph = nx.DiGraph()
    expected_graph.add_node(
        "left node",
        x=1.5,
        y=2.5,
        shape="box",
        color="deep blue",
    )
    expected_graph.add_node("right", id="7", empty="", score=4)
    expected_graph.add_edge(
        "left node",
        "right",
        weight=2.25,
        label="main edge",
        ignored=3,
    )
    with warnings.catch_warnings(record=True) as expected_warnings:
        warnings.simplefilter("always")
        expected = list(nx.generate_pajek(expected_graph))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "generate_pajek", fail)

    with warnings.catch_warnings(record=True) as got_warnings:
        warnings.simplefilter("always")
        got = list(fnx.generate_pajek(graph))

    assert got == expected
    assert [str(w.message) for w in got_warnings] == [
        str(w.message) for w in expected_warnings
    ]


def test_read_and_write_pajek_round_trip(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("left", "right", weight=1.25)
    path = tmp_path / "graph.net"

    fnx.write_pajek(graph, path)
    parsed = fnx.read_pajek(path)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed["left"]["right"][0]["weight"] == 1.25


def test_parse_pajek_matches_networkx_without_fallback(monkeypatch):
    lines = [
        "*network demo",
        "*vertices 2",
        '1 "left node" 1.5 2.5 box color "deep blue"',
        "2 right",
        "*arcs",
        '1 2 3.5 label "main edge"',
    ]
    expected = fnx.readwrite._from_nx_graph(nx.parse_pajek(lines))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "parse_pajek", fail)

    parsed = fnx.parse_pajek(lines)

    assert parsed.is_directed()
    assert dict(parsed.graph) == dict(expected.graph)
    assert dict(parsed.nodes["left node"]) == dict(expected.nodes["left node"])
    assert dict(parsed.nodes["right"]) == dict(expected.nodes["right"])
    assert parsed["left node"]["right"][0] == expected["left node"]["right"][0]


def test_write_pajek_uses_local_generator_without_fallback(tmp_path: Path, monkeypatch):
    graph = fnx.DiGraph()
    graph.add_node("left node", x=1.0, y=2.0, shape="box", color="blue")
    graph.add_node("right")
    graph.add_edge("left node", "right", weight=3.5, label="main edge")

    expected_graph = nx.DiGraph()
    expected_graph.add_node("left node", x=1.0, y=2.0, shape="box", color="blue")
    expected_graph.add_node("right")
    expected_graph.add_edge("left node", "right", weight=3.5, label="main edge")
    expected = "".join(f"{line}\n" for line in nx.generate_pajek(expected_graph))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "write_pajek", fail)

    path = tmp_path / "graph.net"
    gz_path = tmp_path / "graph.net.gz"
    fnx.write_pajek(graph, path)
    fnx.write_pajek(graph, gz_path)

    assert path.read_text(encoding="UTF-8") == expected
    with gzip.open(gz_path, "rt", encoding="UTF-8") as fh:
        assert fh.read() == expected


def test_read_pajek_uses_local_parser_without_fallback(tmp_path: Path, monkeypatch):
    content = (
        "*vertices 2\n"
        '1 "left node" 1.0 2.0 box color blue\n'
        "2 right\n"
        "*arcs\n"
        '1 2 3.5 label "main edge"\n'
    )
    path = tmp_path / "graph.net"
    gz_path = tmp_path / "graph.net.gz"
    path.write_text(content, encoding="UTF-8")
    with gzip.open(gz_path, "wt", encoding="UTF-8") as fh:
        fh.write(content)

    expected = fnx.readwrite._from_nx_graph(nx.parse_pajek(content))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "read_pajek", fail)

    parsed = fnx.read_pajek(path)
    parsed_gz = fnx.read_pajek(gz_path)

    assert dict(parsed.nodes["left node"]) == dict(expected.nodes["left node"])
    assert parsed["left node"]["right"][0] == expected["left node"]["right"][0]
    assert dict(parsed_gz.nodes["left node"]) == dict(expected.nodes["left node"])
    assert parsed_gz["left node"]["right"][0] == expected["left node"]["right"][0]


def test_parse_leda_sample():
    lines = [
        "LEDA.GRAPH",
        "string",
        "int",
        "-2",
        "2",
        "|{a}|",
        "|{b}|",
        "1",
        "1 2 0 |{5}|",
    ]

    parsed = fnx.parse_leda(lines)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed["a"]["b"]["label"] == "5"


def test_parse_leda_matches_networkx_without_fallback(monkeypatch):
    lines = [
        "# ignored comment",
        "LEDA.GRAPH",
        "string",
        "int",
        "-1",
        "3",
        "|{a}|",
        "|{}|",
        "|{c}|",
        "2",
        "1 2 0 |{first}|",
        "2 3 0 |{second}|",
    ]
    expected = fnx.readwrite._from_nx_graph(nx.parse_leda(lines))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "parse_leda", fail)

    parsed = fnx.parse_leda(lines)

    assert parsed.is_directed()
    assert list(parsed.nodes()) == list(expected.nodes())
    assert parsed["a"]["2"]["label"] == expected["a"]["2"]["label"]
    assert parsed["2"]["c"]["label"] == expected["2"]["c"]["label"]


def test_read_leda_matches_networkx_without_fallback(monkeypatch, tmp_path: Path):
    content = "\n".join(
        [
            "LEDA.GRAPH",
            "string",
            "int",
            "-2",
            "3",
            "|{a}|",
            "|{}|",
            "|{c}|",
            "2",
            "1 2 0 |{first}|",
            "2 3 0 |{second}|",
            "",
        ]
    )
    path = tmp_path / "graph.leda"
    gz_path = tmp_path / "graph.leda.gz"
    path.write_text(content, encoding="UTF-8")
    with gzip.open(gz_path, "wt", encoding="UTF-8") as fh:
        fh.write(content)

    expected = fnx.readwrite._from_nx_graph(nx.parse_leda(content.splitlines()))

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "read_leda", fail)

    parsed = fnx.read_leda(path)
    parsed_gz = fnx.read_leda(gz_path)

    assert list(parsed.nodes()) == list(expected.nodes())
    assert parsed["a"]["2"]["label"] == expected["a"]["2"]["label"]
    assert parsed["2"]["c"]["label"] == expected["2"]["c"]["label"]
    assert list(parsed_gz.nodes()) == list(expected.nodes())
    assert parsed_gz["a"]["2"]["label"] == expected["a"]["2"]["label"]
    assert parsed_gz["2"]["c"]["label"] == expected["2"]["c"]["label"]


def test_multiline_adjlist_round_trip(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    graph.add_node("solo")

    lines = list(fnx.generate_multiline_adjlist(graph))
    parsed = fnx.parse_multiline_adjlist(lines)
    path = tmp_path / "graph.adj"

    fnx.write_multiline_adjlist(graph, path)
    from_file = fnx.read_multiline_adjlist(path)

    assert parsed.number_of_nodes() == 3
    assert parsed.number_of_edges() == 1
    assert "solo" in parsed
    assert from_file.number_of_nodes() == 3
    assert from_file.number_of_edges() == 1
    assert "solo" in from_file


# ---------------------------------------------------------------------------
# br-r37-c1-y8m6q: write_/read_ multiline_adjlist and weighted_edgelist must
# accept file-like objects (BytesIO/StringIO), not just file paths. nx
# supports this via @open_file. Pre-fix fnx unconditionally called
# open(path, ...), so these accepted only paths and raised TypeError for
# in-memory buffers — a common pattern in tests, network handlers, and
# pipelines.
# ---------------------------------------------------------------------------


def test_write_multiline_adjlist_accepts_bytesio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)
    graph.add_edge(2, 3, weight=2.5)

    buf = io.BytesIO()
    fnx.write_multiline_adjlist(graph, buf)
    # Must not raise. The data lines (excluding nx's header comments)
    # are present.
    payload = buf.getvalue()
    assert b"1 1\n" in payload
    assert b"2 1\n" in payload  # node 2 has 1 neighbour (3); node 3 has 0


def test_write_multiline_adjlist_accepts_stringio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)

    buf = io.StringIO()
    fnx.write_multiline_adjlist(graph, buf)
    text = buf.getvalue()
    assert "1 1\n" in text


def test_read_multiline_adjlist_accepts_bytesio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)
    graph.add_edge(2, 3, weight=2.5)

    buf = io.BytesIO()
    fnx.write_multiline_adjlist(graph, buf)
    buf.seek(0)
    parsed = fnx.read_multiline_adjlist(buf, nodetype=int, edgetype=float)
    assert sorted(parsed.nodes()) == [1, 2, 3]
    assert sorted(parsed.edges()) == [(1, 2), (2, 3)]


def test_write_weighted_edgelist_accepts_bytesio_and_stringio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)
    graph.add_edge(2, 3, weight=2.5)

    # BytesIO matches nx exactly.
    buf_b = io.BytesIO()
    fnx.write_weighted_edgelist(graph, buf_b)
    nx_buf = io.BytesIO()
    nx.write_weighted_edgelist(nx.Graph(graph), nx_buf)
    assert buf_b.getvalue() == nx_buf.getvalue()

    # StringIO: fnx writes text. Lines should match the bytes-decoded form.
    buf_s = io.StringIO()
    fnx.write_weighted_edgelist(graph, buf_s)
    assert buf_s.getvalue() == buf_b.getvalue().decode("utf-8")


def test_read_weighted_edgelist_accepts_bytesio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)
    graph.add_edge(2, 3, weight=2.5)

    buf = io.BytesIO()
    fnx.write_weighted_edgelist(graph, buf)
    buf.seek(0)
    parsed = fnx.read_weighted_edgelist(buf, nodetype=int)
    assert sorted(parsed.edges(data=True)) == [
        (1, 2, {"weight": 1.5}),
        (2, 3, {"weight": 2.5}),
    ]


def test_read_weighted_edgelist_accepts_stringio():
    import io

    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1.5)

    buf = io.StringIO()
    fnx.write_weighted_edgelist(graph, buf)
    buf.seek(0)
    parsed = fnx.read_weighted_edgelist(buf, nodetype=int)
    assert (1, 2, {"weight": 1.5}) in list(parsed.edges(data=True))


def test_cross_compat_nx_writes_multiline_fnx_reads():
    """Drop-in: a buffer written by nx must be readable by fnx and
    vice versa, both via BytesIO."""
    import io

    g_fnx = fnx.Graph()
    g_fnx.add_edge(1, 2, weight=1.5)
    g_fnx.add_edge(2, 3, weight=2.5)
    g_nx = nx.Graph(g_fnx)

    nx_buf = io.BytesIO()
    nx.write_multiline_adjlist(g_nx, nx_buf)
    nx_buf.seek(0)
    parsed = fnx.read_multiline_adjlist(nx_buf, nodetype=int, edgetype=float)
    assert sorted(parsed.nodes()) == [1, 2, 3]
    assert sorted(parsed.edges()) == [(1, 2), (2, 3)]
