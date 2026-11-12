"""Parity for ``trophic_levels`` on empty / single-node DiGraph.

Bead br-r37-c1-jk4ym. nx.trophic_levels raises
NetworkXError("This graph has no basal nodes...") on empty
DiGraph (because it iterates basal nodes and finds none). The
fnx project intent is to be more permissive on vacuous inputs
and return {} (no levels to compute).

Pre-existing test failure
test_trophic_parity.py::TestTrophicLevels::test_empty_graph
asserts the {} contract; this fix preserves it.
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


def test_empty_digraph_returns_empty_dict():
    """Drop-in convention: vacuous input → empty dict, not raise."""
    assert fnx.trophic_levels(fnx.DiGraph()) == {}


def test_empty_digraph_with_weight_kwarg_returns_empty_dict():
    assert fnx.trophic_levels(fnx.DiGraph(), weight="weight") == {}


@needs_nx
def test_chain_dag_still_matches_nx():
    """Non-empty case still delegates to nx and matches."""
    edges = [(0, 1), (1, 2), (2, 3)]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    fl = fnx.trophic_levels(fg)
    nl = nx.trophic_levels(ng)
    assert set(fl) == set(nl)
    for n in fl:
        assert abs(fl[n] - nl[n]) < 1e-10


@needs_nx
def test_diamond_dag_matches_nx():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    fl = fnx.trophic_levels(fg)
    nl = nx.trophic_levels(ng)
    for n in fl:
        assert abs(fl[n] - nl[n]) < 1e-10


def test_undirected_input_still_raises_not_implemented():
    """Directed-only constraint preserved (br-trophdir)."""
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.trophic_levels(g)


def test_single_node_with_no_edges_returns_level_one():
    """Sanity: a single node with no incoming edges is basal level 1."""
    dg = fnx.DiGraph()
    dg.add_node(0)
    tl = fnx.trophic_levels(dg)
    assert 0 in tl
    assert abs(tl[0] - 1.0) < 1e-10


def test_no_basal_nodes_still_raises_for_non_empty():
    """If the graph has nodes but no basal nodes (e.g. cycle), nx
    raises — fnx must match (only the *empty* edge case is
    short-circuited)."""
    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(fnx.NetworkXError, match="no basal nodes"):
        fnx.trophic_levels(dg)
