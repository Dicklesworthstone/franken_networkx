"""Parity for Graph constructor with dict-of-list (and dict-of-set/tuple) input.

Bead br-r37-c1-9m2vs. ``fnx.Graph({0: [1], 1: [0, 2]})`` returned a
graph with 3 nodes and 0 edges. nx correctly parses adjacency-list
input via ``nx.convert.from_dict_of_lists`` and returns 3 nodes and
2 edges. Drop-in code that builds a graph from a dict-of-list
adjacency representation got a wrong graph silently.

Same fix path as br-r37-c1-lc3em (dict-of-dict input) — extend
``_decode_dict_of_dicts_into`` to accept any non-dict iterable of
neighbour nodes too.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# dict-of-list (the original bug)
# ---------------------------------------------------------------------------

@needs_nx
def test_graph_from_dict_of_list_matches_networkx():
    payload = {0: [1], 1: [0, 2], 2: [1]}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert sorted(f.nodes) == sorted(n.nodes)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_digraph_from_dict_of_list_matches_networkx():
    """DiGraph: each entry yields directed edges from u to each
    listed neighbour."""
    payload = {0: [1, 2], 1: [2]}
    f = fnx.DiGraph(payload)
    n = nx.DiGraph(payload)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (0, 2), (1, 2)]


@needs_nx
def test_multigraph_from_dict_of_list_includes_parallel_edges():
    """MultiGraph: a duplicated neighbour in the list creates a
    parallel edge."""
    payload = {0: [1, 1, 2]}
    f = fnx.MultiGraph(payload)
    n = nx.MultiGraph(payload)
    assert sorted(f.edges(keys=True)) == sorted(n.edges(keys=True))


# ---------------------------------------------------------------------------
# dict-of-set / dict-of-tuple — any iterable of neighbours
# ---------------------------------------------------------------------------

@needs_nx
def test_graph_from_dict_of_set_matches_networkx():
    payload = {0: {1, 2}, 1: {0, 2}, 2: {0, 1}}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_graph_from_dict_of_tuple_matches_networkx():
    payload = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert sorted(f.edges) == sorted(n.edges)


# ---------------------------------------------------------------------------
# dict-of-dict (regression check from br-r37-c1-lc3em)
# ---------------------------------------------------------------------------

@needs_nx
def test_dict_of_dict_input_still_handled():
    """dict-of-dict must continue to work after the dict-of-list fix."""
    payload = {0: {1: {"w": 5}}, 1: {0: {"w": 5}, 2: {}}, 2: {1: {}}}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert list(f.edges(data=True)) == list(n.edges(data=True))


@needs_nx
def test_multigraph_dict_of_dict_of_dict_still_handled():
    payload = {0: {1: {0: {"w": 5}, 1: {"w": 6}}}}
    f = fnx.MultiGraph(payload)
    n = nx.MultiGraph(payload)
    assert sorted(f.edges(keys=True, data=True)) == sorted(n.edges(keys=True, data=True))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@needs_nx
def test_empty_dict_input_creates_empty_graph():
    f = fnx.Graph({})
    n = nx.Graph({})
    assert f.number_of_nodes() == n.number_of_nodes() == 0
    assert f.number_of_edges() == n.number_of_edges() == 0


@needs_nx
def test_dict_of_empty_list_adds_only_nodes():
    """{u: [], v: []} should produce nodes but no edges."""
    payload = {0: [], 1: [], 2: []}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert sorted(f.nodes) == sorted(n.nodes) == [0, 1, 2]
    assert list(f.edges) == list(n.edges) == []


@needs_nx
def test_string_node_keys_with_list_neighbours():
    payload = {"a": ["b", "c"], "b": ["a"]}
    f = fnx.Graph(payload)
    n = nx.Graph(payload)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_dict_of_generator_neighbours():
    """A generator of neighbours should also be accepted."""
    def make_payload():
        return {0: iter([1, 2]), 1: iter([2])}
    f = fnx.Graph(make_payload())
    n = nx.Graph(make_payload())
    assert sorted(f.edges) == sorted(n.edges)
