"""Parity coverage for filtered-view .nodes NodeView contract.

Bead franken_networkx-zlce: restricted_view and subgraph_view expose
.nodes as a NodeView object (not a bound method), so .data(), .items(),
dict(), and similar helpers all work matching upstream.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    "builder_name",
    ["restricted_view", "subgraph_view"],
)
def test_filtered_view_nodes_is_not_a_method(builder_name):
    fg = fnx.Graph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    fg.add_edge("a", "b")
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
    else:
        fv = fnx.subgraph_view(fg)
    assert type(fv.nodes).__name__ != "method"


@pytest.mark.parametrize(
    "builder_name",
    ["restricted_view", "subgraph_view"],
)
def test_filtered_view_nodes_mapping_helpers_match_networkx(builder_name):
    fg = fnx.Graph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    fg.add_edge("a", "b")
    ng = nx.Graph()
    ng.add_node("a", color="red")
    ng.add_node("b")
    ng.add_edge("a", "b")

    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    assert dict(fv.nodes) == dict(nv.nodes)
    assert list(fv.nodes.data()) == list(nv.nodes.data())
    assert list(fv.nodes(data=True)) == list(nv.nodes(data=True))


# br-filtedgeop: _FilteredEdgeView must expose Set-algebra operators
# (nx.EdgeView inherits from collections.abc.Set) so nx.minimum_cycle_basis
# and other algorithms that do `G.edges - tree_edges` work on filtered views.
def test_filtered_edge_view_supports_set_subtraction():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])
    fv = fnx.subgraph_view(fg)
    diff = fv.edges - [(0, 1)]
    assert diff == {(0, 4), (1, 2), (2, 3), (3, 4)}


def test_filtered_edge_view_supports_reflected_set_ops():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    fv = fnx.subgraph_view(fg)
    assert {(0, 1), (999, 999)} - fv.edges == {(999, 999)}
    assert {(99, 100)} | fv.edges == {(0, 1), (1, 2), (2, 3), (99, 100)}
    assert {(0, 1), (77, 88)} & fv.edges == {(0, 1)}
    assert {(0, 1), (9, 9)} ^ fv.edges == {(1, 2), (2, 3), (9, 9)}


def test_filtered_edge_view_eq_matches_set():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2)])
    fv = fnx.subgraph_view(fg)
    assert fv.edges == {(0, 1), (1, 2)}


def test_filtered_edge_view_data_none_yields_three_tuples_with_default():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    fv = fnx.subgraph_view(fg)
    result = list(fv.edges(data=None, default="sentinel"))
    assert len(result) == 3
    assert all(len(t) == 3 for t in result)
    assert all(t[2] == "sentinel" for t in result)


def test_filtered_edge_view_supports_nx_minimum_cycle_basis():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)])

    fv = fnx.subgraph_view(fg)
    nv = nx.subgraph_view(ng)

    def canon(cycles):
        return sorted(tuple(sorted(c)) for c in cycles)

    assert canon(nx.minimum_cycle_basis(fv)) == canon(nx.minimum_cycle_basis(nv))
