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
