"""Parity coverage for find_negative_cycle on directed graphs.

Bead franken_networkx-94ld: the Rust implementation rejected directed
graphs with NetworkXNotImplemented; the Python wrapper now routes
directed inputs through networkx so both the success path and the
missing-source / no-cycle error contracts match upstream exactly.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_find_negative_cycle_directed_graph_matches_networkx():
    edges = [(0, 1, 1), (1, 2, -3), (2, 0, 1)]
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from(edges)
    ng = nx.DiGraph()
    ng.add_weighted_edges_from(edges)

    f_cycle = fnx.find_negative_cycle(fg, 0)
    n_cycle = nx.find_negative_cycle(ng, 0)
    # Node list parity.
    assert f_cycle == n_cycle


def test_find_negative_cycle_directed_missing_source_matches_networkx():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])

    with pytest.raises((fnx.NodeNotFound, nx.NodeNotFound), match="Source 99 not in G"):
        fnx.find_negative_cycle(fg, 99)
    with pytest.raises(nx.NodeNotFound, match="Source 99 not in G"):
        nx.find_negative_cycle(ng, 99)


def test_find_negative_cycle_directed_no_cycle_raises_networkx_error():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])

    with pytest.raises(
        (fnx.NetworkXError, nx.NetworkXError), match="No negative cycles detected"
    ):
        fnx.find_negative_cycle(fg, 0)
    with pytest.raises(nx.NetworkXError, match="No negative cycles detected"):
        nx.find_negative_cycle(ng, 0)


def test_find_negative_cycle_undirected_still_uses_native_path():
    """Undirected inputs must still go through the native Rust
    implementation (not the nx fallback).
    """
    from unittest import mock

    fg = fnx.Graph()
    fg.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    with mock.patch(
        "networkx.find_negative_cycle",
        side_effect=AssertionError("undirected must use native path"),
    ):
        cycle = fnx.find_negative_cycle(fg, 0)
    assert cycle  # non-empty cycle found
