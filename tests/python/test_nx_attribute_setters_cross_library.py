"""br-r37-c1-l2j31: regression — nx.set_{node,edge}_attributes and
nx.get_{node,edge}_attributes must work when given an fnx graph.

These four functions are decorated as ``@_dispatchable`` and the
``set_*`` variants are flagged as mutation-preserving — so the
dispatcher refuses to auto-convert the input (the mutation would
otherwise land on a converted copy that the user can't observe).
Without an entry in ``franken_networkx.backend._SUPPORTED_ALGORITHMS``
the dispatcher raised ``NotImplementedError``.

Registering ``fnx.set_node_attributes`` / ``fnx.set_edge_attributes``
/ ``fnx.get_node_attributes`` / ``fnx.get_edge_attributes`` in the
backend table makes the dispatcher route the fnx graph through fnx's
own implementation — the mutation lands on the actual user graph.
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


@needs_nx
def test_set_node_attributes_via_nx_namespace_writes_back():
    g = fnx.path_graph(3)
    nx.set_node_attributes(g, {0: "red", 1: "blue"}, name="color")
    assert dict(g.nodes[0]) == {"color": "red"}
    assert dict(g.nodes[1]) == {"color": "blue"}
    assert dict(g.nodes[2]) == {}


@needs_nx
def test_set_edge_attributes_via_nx_namespace_writes_back():
    g = fnx.path_graph(3)
    nx.set_edge_attributes(g, {(0, 1): 5, (1, 2): 7}, name="weight")
    assert g[0][1]["weight"] == 5
    assert g[1][2]["weight"] == 7


@needs_nx
def test_get_node_attributes_via_nx_namespace():
    g = fnx.Graph()
    g.add_node(0, color="red")
    g.add_node(1, color="blue")
    g.add_node(2)
    assert nx.get_node_attributes(g, "color") == {0: "red", 1: "blue"}


@needs_nx
def test_get_edge_attributes_via_nx_namespace():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=5)
    g.add_edge(1, 2, weight=7)
    assert nx.get_edge_attributes(g, "weight") == {(0, 1): 5, (1, 2): 7}


@needs_nx
def test_set_attributes_via_nx_matches_fnx_direct():
    """Parity check — ``nx.set_X_attributes(fnx_g, ...)`` produces the
    same final graph state as ``fnx.set_X_attributes(fnx_g, ...)``."""
    g_via_nx = fnx.path_graph(3)
    nx.set_node_attributes(g_via_nx, {0: "red"}, name="color")
    g_via_fnx = fnx.path_graph(3)
    fnx.set_node_attributes(g_via_fnx, {0: "red"}, name="color")
    assert {n: dict(g_via_nx.nodes[n]) for n in g_via_nx.nodes()} == {
        n: dict(g_via_fnx.nodes[n]) for n in g_via_fnx.nodes()
    }


@needs_nx
def test_backend_registers_attribute_set_get():
    """The four attribute helpers must be in the backend's
    _SUPPORTED_ALGORITHMS table; otherwise the dispatcher will raise
    NotImplementedError on mutation-preserving functions."""
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    for fname in (
        "set_node_attributes",
        "set_edge_attributes",
        "get_node_attributes",
        "get_edge_attributes",
    ):
        assert fname in _SUPPORTED_ALGORITHMS, f"{fname} missing from backend table"
