"""Tests for GEXF compatibility wrappers."""

from io import BytesIO
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx


def _sample_graph():
    graph = fnx.DiGraph()
    graph.add_node("n0", label="Node Zero", color="red")
    graph.add_node("n1", label="Node One")
    graph.add_edge("n0", "n1", weight=2.5)
    return graph


def test_generate_and_parse_gexf_round_trip():
    graph = _sample_graph()
    gexf = "\n".join(fnx.generate_gexf(graph))
    parsed = fnx.readwrite.parse_gexf(gexf)

    assert parsed.is_directed()
    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed.nodes["n0"]["label"] == "Node Zero"
    assert parsed.nodes["n0"]["color"] == "red"
    assert parsed["n0"]["n1"]["weight"] == 2.5


def test_read_and_write_gexf_round_trip(tmp_path: Path):
    graph = _sample_graph()
    path = tmp_path / "graph.gexf"

    fnx.write_gexf(graph, path)
    parsed = fnx.read_gexf(path)

    assert parsed.number_of_nodes() == 2
    assert parsed.number_of_edges() == 1
    assert parsed.is_directed()
    assert parsed.nodes["n1"]["label"] == "Node One"


def _minimal_gexf(namespace="http://www.gexf.net/1.2draft", version="1.2"):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gexf xmlns="{namespace}" version="{version}">\n'
        '  <graph mode="static" defaultedgetype="undirected">\n'
        '    <nodes><node id="0" label="zero"/></nodes>\n'
        "    <edges/>\n"
        "  </graph>\n"
        "</gexf>"
    ).encode("utf-8")


@pytest.mark.parametrize("version", ["1.2", "not-a-version"])
def test_gexf_unknown_version_errors_match_networkx(version):
    payload = _minimal_gexf()
    expected_message = f"Unknown GEXF version {version}."

    with pytest.raises(nx.NetworkXError) as nx_err:
        nx.read_gexf(BytesIO(payload), version=version)
    assert str(nx_err.value) == expected_message

    with pytest.raises(fnx.NetworkXError) as fnx_err:
        fnx.read_gexf(BytesIO(payload), version=version)
    assert str(fnx_err.value) == expected_message


def test_read_gexf_accepts_version_13_like_networkx():
    payload = _minimal_gexf(namespace="http://gexf.net/1.3", version="1.3")

    expected = nx.read_gexf(BytesIO(payload), version="1.3")
    actual = fnx.read_gexf(BytesIO(payload), version="1.3")

    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))


def test_generate_gexf_simple_graph_honors_version_13_namespace():
    actual_first_line = next(iter(fnx.generate_gexf(fnx.path_graph(1), version="1.3")))
    expected_first_line = next(iter(nx.generate_gexf(nx.path_graph(1), version="1.3")))

    assert actual_first_line == expected_first_line


def _multigraph_snapshot(graph):
    return (
        graph.is_directed(),
        sorted((node, tuple(sorted(attrs.items()))) for node, attrs in graph.nodes(data=True)),
        sorted(
            (u, v, key, tuple(sorted(attrs.items())))
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        ),
    )


def test_gexf_version_13_multigraph_round_trip_matches_networkx():
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    for graph in (fnx_graph, nx_graph):
        graph.add_node("n0", label="Node Zero")
        graph.add_node("n1", label="Node One")
        graph.add_edge("n0", "n1", key="k1", weight=1.0)
        graph.add_edge("n0", "n1", key="k2", weight=2.0, label="parallel-edge")

    fnx_payload = "\n".join(fnx.generate_gexf(fnx_graph, version="1.3")).encode()
    nx_payload = "\n".join(nx.generate_gexf(nx_graph, version="1.3")).encode()

    assert b'xmlns="http://gexf.net/1.3"' in fnx_payload

    actual = fnx.read_gexf(BytesIO(fnx_payload), version="1.3")
    expected = nx.read_gexf(BytesIO(nx_payload), version="1.3")

    assert actual.is_multigraph()
    assert _multigraph_snapshot(actual) == _multigraph_snapshot(expected)


def test_write_gexf_accepts_reserved_simple_node_attrs():
    graph = fnx.Graph()
    graph.add_node("n0")
    graph.nodes["n0"]["node_for_adding"] = "node-value"

    buffer = BytesIO()
    fnx.write_gexf(graph, buffer)

    assert b"node_for_adding" in buffer.getvalue()


def test_write_gexf_accepts_reserved_simple_edge_attrs():
    graph = fnx.Graph()
    graph.add_edge("n0", "n1")
    graph["n0"]["n1"]["u_of_edge"] = "left-value"
    graph["n0"]["n1"]["v_of_edge"] = "right-value"

    buffer = BytesIO()
    fnx.write_gexf(graph, buffer)

    payload = buffer.getvalue()
    assert b"u_of_edge" in payload
    assert b"v_of_edge" in payload


def test_write_gexf_accepts_multigraph_edge_key_attr():
    graph = fnx.MultiGraph()
    graph.add_edge("n0", "n1", key="edge-key", label="parallel-edge")
    graph["n0"]["n1"]["edge-key"]["key"] = "user-key-attr"

    buffer = BytesIO()
    fnx.write_gexf(graph, buffer)

    payload = buffer.getvalue()
    assert b"parallel-edge" in payload


def test_relabel_gexf_graph_uses_label_attribute():
    graph = _sample_graph()
    relabeled = fnx.relabel_gexf_graph(graph)

    assert "Node Zero" in relabeled
    assert "Node One" in relabeled


def test_gexf_helpers_do_not_delegate_to_networkx(monkeypatch, tmp_path: Path):
    import networkx as nx

    def fail(*args, **kwargs):
        raise AssertionError("GEXF helper delegated to NetworkX")

    monkeypatch.setattr(nx, "read_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "write_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "generate_gexf", fail, raising=False)
    monkeypatch.setattr(nx, "relabel_gexf_graph", fail, raising=False)

    graph = _sample_graph()
    path = tmp_path / "native.gexf"
    fnx.write_gexf(graph, path)
    parsed = fnx.read_gexf(path)
    generated = "\n".join(fnx.generate_gexf(parsed))
    reparsed = fnx.readwrite.parse_gexf(generated)
    relabeled = fnx.relabel_gexf_graph(reparsed)

    assert reparsed.number_of_edges() == 1
    assert "Node Zero" in relabeled
