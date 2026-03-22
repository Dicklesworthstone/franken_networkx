"""Tests for graph6, sparse6, and weighted edgelist wrappers."""

from pathlib import Path

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


def test_weighted_edgelist_round_trip(tmp_path: Path):
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.5)
    graph.add_edge("b", "c", weight=1.5)
    path = tmp_path / "weighted.edgelist"

    fnx.write_weighted_edgelist(graph, path)
    restored = fnx.read_weighted_edgelist(path)

    assert restored["a"]["b"]["weight"] == 2.5
    assert restored["b"]["c"]["weight"] == 1.5
