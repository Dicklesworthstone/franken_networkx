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


# ---------------------------------------------------------------------------
# br-r37-c1-14pu1: MultiGraph constructor parity for dict-of-lists
# (symmetric dedupe) and 3-level dict-of-dicts.
# ---------------------------------------------------------------------------

@needs_nx
def test_multigraph_dict_of_lists_dedupes_symmetric_input():
    """nx.from_dict_of_lists tracks already-processed nodes for an
    undirected MultiGraph so the symmetric adjacency representation
    K3 = {1:[2,3], 2:[1,3], 3:[1,2]} produces 3 edges instead of 6.
    Pre-fix fnx added each edge once per direction, doubling counts.
    """
    payload = {1: [2, 3], 2: [1, 3], 3: [1, 2]}
    f = fnx.MultiGraph(payload)
    n = nx.MultiGraph(payload)
    assert f.number_of_edges() == n.number_of_edges() == 3
    assert sorted(f.edges(keys=True)) == sorted(n.edges(keys=True))


@needs_nx
def test_multigraph_dict_of_lists_asymmetric():
    """Asymmetric directed-style dict-of-lists into undirected
    MultiGraph: nx still uses the seen-set, so {1:[2], 2:[3], 3:[1]}
    yields just (1,2) and (2,3) — node 3 sees neighbour 1 already
    processed and skips."""
    payload = {1: [2], 2: [3], 3: [1]}
    f = fnx.MultiGraph(payload)
    n = nx.MultiGraph(payload)
    assert sorted(f.edges(keys=True)) == sorted(n.edges(keys=True))


@needs_nx
def test_multidigraph_dict_of_lists_no_dedupe():
    """For directed MultiDiGraph nx does NOT dedupe — every (u, nbr)
    pair becomes a distinct directed edge. fnx must match."""
    payload = {1: [2, 3], 2: [1, 3], 3: [1, 2]}
    f = fnx.MultiDiGraph(payload)
    n = nx.MultiDiGraph(payload)
    assert f.number_of_edges() == n.number_of_edges() == 6
    assert sorted(f.edges(keys=True)) == sorted(n.edges(keys=True))


@needs_nx
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_3level_dict_of_dicts_treats_inner_as_attrs(cls_name):
    """3-level ``{u: {v: attrs_dict}}`` for a multigraph is the
    ``multigraph_input=False`` shape: inner dict is the edge attrs,
    edge gets auto-key 0. Pre-fix fnx misread inner as ``{key: ...}``
    so ``MultiGraph({1:{2:{'w':1}}})`` produced edge (1,2,'w') with
    no attrs instead of (1,2,0,{'w':1})."""
    payload = {1: {2: {"w": 1}}, 2: {3: {"w": 2}}, 3: {}}
    fnx_cls = getattr(fnx, cls_name)
    nx_cls = getattr(nx, cls_name)
    f = fnx_cls(payload)
    n = nx_cls(payload)
    assert sorted(f.edges(keys=True, data=True)) == sorted(n.edges(keys=True, data=True))


@needs_nx
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_explicit_multigraph_input_kwarg_is_honored(cls_name):
    """Explicit multigraph_input=True forces 4-level interpretation
    even when the data could be parsed as 3-level."""
    payload_4level = {1: {2: {0: {"w": 1}, 1: {"w": 2}}}}
    fnx_cls = getattr(fnx, cls_name)
    nx_cls = getattr(nx, cls_name)
    f = fnx_cls(payload_4level, multigraph_input=True)
    n = nx_cls(payload_4level, multigraph_input=True)
    assert sorted(f.edges(keys=True, data=True)) == sorted(n.edges(keys=True, data=True))

    # multigraph_input=False on a payload that *could* be 4-level forces
    # the 3-level interpretation: inner becomes the attr dict.
    payload_amb = {1: {2: {"w": 1, "k": 2}}}
    f = fnx_cls(payload_amb, multigraph_input=False)
    n = nx_cls(payload_amb, multigraph_input=False)
    assert sorted(f.edges(keys=True, data=True)) == sorted(n.edges(keys=True, data=True))


@needs_nx
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_empty_inner_dict_no_edge(cls_name):
    """Per nx, ``{u: {v: {}}}`` is parseable as 4-level with zero keys
    in the inner dict — no edge is added. Regression guard for the
    auto-detect logic, which must default to 4-level for ambiguous
    empty-inner payloads to match nx's try-4-level-first behavior."""
    payload = {0: {0: {}}}
    fnx_cls = getattr(fnx, cls_name)
    nx_cls = getattr(nx, cls_name)
    f = fnx_cls(payload)
    n = nx_cls(payload)
    assert f.number_of_edges() == n.number_of_edges() == 0
