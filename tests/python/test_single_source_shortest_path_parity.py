"""Parity coverage for single_source_shortest_path(_length) missing-source error.

Bead franken_networkx-s7nb: both wrappers must raise NodeNotFound when
the source isn't in the graph, matching upstream NetworkX, instead of
silently returning an empty dict.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_single_source_shortest_path_missing_source_raises():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)

    with pytest.raises(fnx.NodeNotFound, match="Source .* not in G"):
        fnx.single_source_shortest_path(fg, "z")
    with pytest.raises(nx.NodeNotFound, match="Source .* not in G"):
        nx.single_source_shortest_path(ng, "z")


def test_single_source_shortest_path_length_missing_source_raises():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)

    with pytest.raises(fnx.NodeNotFound, match="Source .* is not in G"):
        fnx.single_source_shortest_path_length(fg, "z")
    with pytest.raises(nx.NodeNotFound, match="Source .* is not in G"):
        nx.single_source_shortest_path_length(ng, "z")


def test_single_source_shortest_path_valid_source_matches_networkx():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    assert fnx.single_source_shortest_path(fg, 0) == nx.single_source_shortest_path(
        ng, 0
    )
    assert fnx.single_source_shortest_path_length(
        fg, 0
    ) == dict(nx.single_source_shortest_path_length(ng, 0))


def test_single_source_shortest_path_cutoff_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert fnx.single_source_shortest_path(
        fg, 0, cutoff=2
    ) == nx.single_source_shortest_path(ng, 0, cutoff=2)


def test_single_source_shortest_path_directed_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (4, 0)])

    assert fnx.single_source_shortest_path(fg, 0) == nx.single_source_shortest_path(
        ng, 0
    )
    assert fnx.single_source_shortest_path_length(fg, 0) == dict(
        nx.single_source_shortest_path_length(ng, 0)
    )
    assert fnx.single_source_shortest_path(fg, 0, cutoff=1) == nx.single_source_shortest_path(
        ng, 0, cutoff=1
    )
