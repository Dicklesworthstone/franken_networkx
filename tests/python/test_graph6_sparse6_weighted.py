"""Tests for graph6, sparse6, and weighted edgelist wrappers."""

import builtins
from io import BytesIO
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx


def _path_graph():
    graph = fnx.path_graph(4)
    return graph


def test_graph6_byte_and_parse_round_trip():
    graph = _path_graph()

    encoded = fnx.to_graph6_bytes(graph, header=False)
    parsed = fnx.parse_graph6(encoded.decode("ascii"))
    restored = fnx.from_graph6_bytes(encoded)

    assert parsed.number_of_nodes() == 4
    assert parsed.number_of_edges() == 3
    assert restored.number_of_nodes() == 4
    assert restored.number_of_edges() == 3


def test_sparse6_byte_and_parse_round_trip():
    graph = _path_graph()

    encoded = fnx.to_sparse6_bytes(graph, header=False)
    parsed = fnx.parse_sparse6(encoded.decode("ascii"))
    restored = fnx.from_sparse6_bytes(encoded)

    assert parsed.number_of_nodes() == 4
    assert parsed.number_of_edges() == 3
    assert restored.number_of_nodes() == 4
    assert restored.number_of_edges() == 3


def test_graph6_and_sparse6_file_round_trip(tmp_path: Path):
    graph = _path_graph()
    graph6_path = tmp_path / "graph.g6"
    sparse6_path = tmp_path / "graph.s6"

    fnx.write_graph6(graph, graph6_path)
    fnx.write_sparse6(graph, sparse6_path)

    graph6_loaded = fnx.read_graph6(graph6_path)
    sparse6_loaded = fnx.read_sparse6(sparse6_path)

    assert graph6_loaded.number_of_nodes() == 4
    assert graph6_loaded.number_of_edges() == 3
    assert sparse6_loaded.number_of_nodes() == 4
    assert sparse6_loaded.number_of_edges() == 3


def test_graph6_known_networkx_encodings():
    assert fnx.to_graph6_bytes(fnx.Graph()) == b">>graph6<<?\n"
    assert fnx.to_graph6_bytes(fnx.path_graph(2)) == b">>graph6<<A_\n"
    assert fnx.to_graph6_bytes(fnx.complete_graph(4)) == b">>graph6<<C~\n"
    assert fnx.to_graph6_bytes(fnx.complete_graph(4), header=False) == b"C~\n"


def test_sparse6_known_networkx_encodings():
    assert fnx.to_sparse6_bytes(fnx.Graph()) == b">>sparse6<<:?\n"
    assert fnx.to_sparse6_bytes(fnx.path_graph(2)) == b">>sparse6<<:An\n"
    assert fnx.to_sparse6_bytes(fnx.complete_graph(4)) == b">>sparse6<<:CcKI\n"
    assert fnx.to_sparse6_bytes(fnx.complete_graph(4), header=False) == b":CcKI\n"


def test_sparse6_duplicate_edges_return_multigraph():
    graph = fnx.from_sparse6_bytes(b":A_")

    assert graph.is_multigraph()
    assert graph.number_of_nodes() == 2
    assert graph.number_of_edges() == 3
    assert list(graph.edges()) == [(0, 1), (0, 1), (0, 1)]


def test_sparse6_direct_bytes_keep_trailing_newline_payload():
    graph = fnx.from_sparse6_bytes(b":@\n")
    expected = nx.from_sparse6_bytes(b":@\n")

    assert graph.number_of_nodes() == expected.number_of_nodes() == 1
    assert graph.number_of_edges() == expected.number_of_edges() == 1
    assert list(graph.edges()) == list(expected.edges()) == [(0, 0)]


def test_graph6_and_sparse6_read_multiple_graphs_from_binary_stream():
    graph6_graphs = fnx.read_graph6(BytesIO(b"A_\nC~\n\n"))
    sparse6_graphs = fnx.read_sparse6(BytesIO(b":An\n:CcKI\n\n"))

    assert [graph.number_of_edges() for graph in graph6_graphs] == [1, 6]
    assert [graph.number_of_edges() for graph in sparse6_graphs] == [1, 6]


def test_graph6_sparse6_do_not_import_networkx(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "networkx" or name.startswith("networkx."):
            raise AssertionError(f"unexpected NetworkX import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    graph = fnx.path_graph(3)
    assert fnx.from_graph6_bytes(fnx.to_graph6_bytes(graph)).number_of_edges() == 2
    assert fnx.read_sparse6(BytesIO(fnx.to_sparse6_bytes(graph))).number_of_edges() == 2


def test_graph6_rejects_directed_and_multigraph_writes():
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.to_graph6_bytes(fnx.DiGraph())
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.to_graph6_bytes(fnx.MultiGraph())


def test_weighted_edgelist_round_trip(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.5)
    graph.add_edge("b", "c", weight=1.5)
    path = tmp_path / "weighted.edgelist"

    fnx.write_weighted_edgelist(graph, path)
    restored = fnx.read_weighted_edgelist(path)

    assert restored["a"]["b"]["weight"] == 2.5
    assert restored["b"]["c"]["weight"] == 1.5
