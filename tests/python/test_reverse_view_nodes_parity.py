"""Parity coverage for reverse_view.nodes NodeView contract.

Bead franken_networkx-fdu5: reverse_view(G).nodes must expose a
callable NodeView object (not a bound method), so .data(), .items(),
dict(), and similar mapping helpers all work matching upstream.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_reverse_view_nodes_is_not_a_method():
    fg = fnx.DiGraph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    frv = fnx.reverse_view(fg)
    # Must not be a bound method.
    assert type(frv.nodes).__name__ != "method"


def test_reverse_view_nodes_supports_mapping_helpers():
    fg = fnx.DiGraph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    ng = nx.DiGraph()
    ng.add_node("a", color="red")
    ng.add_node("b")

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert dict(frv.nodes) == dict(nrv.nodes)
    assert list(frv.nodes.data()) == list(nrv.nodes.data())


def test_reverse_view_nodes_callable_form():
    fg = fnx.DiGraph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    ng = nx.DiGraph()
    ng.add_node("a", color="red")
    ng.add_node("b")

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert list(frv.nodes(data=True)) == list(nrv.nodes(data=True))
    assert list(frv.nodes(data="color", default="blue")) == list(
        nrv.nodes(data="color", default="blue")
    )
