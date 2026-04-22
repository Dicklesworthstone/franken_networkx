"""Parity coverage for Graph/DiGraph.degree() callable surface with weight.

Bead franken_networkx-b2x7: Graph.degree and DiGraph.degree must
support the full callable contract — list(G.degree()), G.degree(node),
G.degree(node, weight=...) — matching upstream.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_graph_degree_callable_forms_match_networkx():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    assert list(fg.degree()) == list(ng.degree())
    assert fg.degree(0) == ng.degree(0)
    # nbunch form.
    assert list(fg.degree([0, 2])) == list(ng.degree([0, 2]))


def test_graph_degree_with_weight_matches_networkx():
    fg = fnx.path_graph(4)
    fg[0][1]["weight"] = 3.5
    ng = nx.path_graph(4)
    ng[0][1]["weight"] = 3.5
    assert fg.degree(0, weight="weight") == ng.degree(0, weight="weight")
    assert dict(fg.degree(weight="weight")) == dict(ng.degree(weight="weight"))


def test_digraph_degree_callable_forms_match_networkx():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3)])
    assert list(fg.degree()) == list(ng.degree())
    assert fg.degree(1) == ng.degree(1)


def test_digraph_degree_with_weight_sums_in_and_out():
    """Total degree on a DiGraph is in-weight + out-weight."""
    fg = fnx.DiGraph()
    fg.add_edge(0, 1, weight=2.5)
    fg.add_edge(1, 2, weight=3.0)
    ng = nx.DiGraph()
    ng.add_edge(0, 1, weight=2.5)
    ng.add_edge(1, 2, weight=3.0)
    # Node 1 has in-edge 2.5 and out-edge 3.0 → total 5.5.
    assert fg.degree(1, weight="weight") == ng.degree(1, weight="weight") == 5.5
    assert dict(fg.degree(weight="weight")) == dict(ng.degree(weight="weight"))
