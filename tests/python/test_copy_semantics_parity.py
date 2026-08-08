"""Copy / deepcopy semantics parity with networkx.

Copy semantics are subtle and a recurring bug source (a deepcopy rebuild-walk
bug existed in this codebase): ``G.copy()`` creates fresh attribute dicts but
shares nested *values* (shallow on values), ``copy.deepcopy`` is fully
independent, and ``subgraph().copy()`` / ``to_directed()`` produce independent
graphs. This pins fnx to networkx's exact behavior on each.

No mocks: real fnx and real networkx, mutating copies and observing the
original.
"""

from __future__ import annotations

import copy

import pytest
import networkx as nx
import franken_networkx as fnx


def _build(lib):
    g = lib.Graph()
    g.add_node(0, d={"nested": [1, 2]})
    g.add_edge(0, 1, w={"k": "v"})
    g.graph["meta"] = {"a": 1}
    return g


def _copy_behavior(lib):
    g = _build(lib)
    gc = g.copy()
    gc[0][1]["w2"] = "new"          # fresh edge-attr dict
    new_key_leaked = "w2" in g[0][1]
    gc[0][1]["w"]["k"] = "changed"  # nested value is shared (shallow)
    nested_shared = g[0][1]["w"]["k"] == "changed"
    return new_key_leaked, nested_shared


def _deepcopy_behavior(lib):
    g = _build(lib)
    gd = copy.deepcopy(g)
    gd[0][1]["w"]["k"] = "deep"
    edge_shared = g[0][1]["w"]["k"] == "deep"
    gd.nodes[0]["d"]["nested"].append(99)
    node_shared = 99 in g.nodes[0]["d"]["nested"]
    return edge_shared, node_shared


def test_copy_creates_fresh_attr_dicts_sharing_values():
    assert _copy_behavior(fnx) == _copy_behavior(nx)
    # And concretely: new key does NOT leak, nested value IS shared.
    assert _copy_behavior(fnx) == (False, True)


def test_deepcopy_is_fully_independent():
    assert _deepcopy_behavior(fnx) == _deepcopy_behavior(nx)
    assert _deepcopy_behavior(fnx) == (False, False)


def test_subgraph_copy_is_independent():
    # br-r37-c1-sky48: a loop here built a `res` list and then discarded it —
    # every iteration appended to a fresh `[]` that nothing read. Removed; the
    # assertions below were already doing the work.
    fg = _build(fnx); fg.add_edge(1, 2); fsc = fg.subgraph([0, 1]).copy(); fsc.add_edge(0, 5)
    ng = _build(nx); ng.add_edge(1, 2); nsc = ng.subgraph([0, 1]).copy(); nsc.add_edge(0, 5)
    assert (fg.has_edge(0, 5), sorted(fsc.nodes())) == (
        ng.has_edge(0, 5), sorted(nsc.nodes())
    )
    assert not fg.has_edge(0, 5)  # copy is independent of the parent


def test_to_directed_is_independent():
    fg, ng = _build(fnx), _build(nx)
    fdg, ndg = fg.to_directed(), ng.to_directed()
    fdg.add_edge(9, 8)
    ndg.add_edge(9, 8)
    assert (fg.has_edge(9, 8) or fg.has_edge(8, 9)) == (
        ng.has_edge(9, 8) or ng.has_edge(8, 9)
    )
    assert not (fg.has_edge(9, 8) or fg.has_edge(8, 9))


# br-r37-c1-sky48: `_build` sets a graph-level attribute and no test ever
# mutated it, and the subgraph/to_directed tests checked only STRUCTURAL
# independence (adding an edge) — never whether attributes are shared. That is
# the half of the contract this module is named for, and the two operations do
# OPPOSITE things: to_directed deep-copies every attribute layer, while
# subgraph().copy() shares nested values like copy() does. Both verified against
# networkx before being asserted.
def _graph_attr_behavior(lib):
    g = _build(lib)
    gc = g.copy()
    gc.graph["new"] = "x"
    key_leaks = "new" in g.graph
    gc.graph["meta"]["a"] = 99
    nested_shared = g.graph["meta"]["a"] == 99

    g2 = _build(lib)
    gd = copy.deepcopy(g2)
    gd.graph["meta"]["a"] = 99
    deep_shared = g2.graph["meta"]["a"] == 99
    return key_leaks, nested_shared, deep_shared


def test_graph_level_attributes_follow_the_same_copy_contract():
    assert _graph_attr_behavior(fnx) == _graph_attr_behavior(nx)
    # copy(): fresh graph dict (no key leak) but the nested value IS shared;
    # deepcopy(): fully independent — the same shape as the node/edge layers.
    assert _graph_attr_behavior(fnx) == (False, True, False)


def _to_directed_sharing(lib):
    g = _build(lib)
    d = g.to_directed()
    d[0][1]["w"]["k"] = "changed"
    edge_shared = g[0][1]["w"]["k"] == "changed"

    g = _build(lib)
    d = g.to_directed()
    d.nodes[0]["d"]["nested"].append(99)
    node_shared = 99 in g.nodes[0]["d"]["nested"]

    g = _build(lib)
    d = g.to_directed()
    d.graph["meta"]["a"] = 99
    graph_shared = g.graph["meta"]["a"] == 99
    return edge_shared, node_shared, graph_shared


def test_to_directed_deep_copies_every_attribute_layer():
    """networkx documents to_directed as returning a deepcopy of the edge, node
    and graph attributes — so unlike ``copy()``, mutating a NESTED value in the
    result must not reach the original. Structural independence (the assertion
    above) would hold even if the attributes were shared.
    """
    assert _to_directed_sharing(fnx) == _to_directed_sharing(nx)
    assert _to_directed_sharing(fnx) == (False, False, False)


def _subgraph_copy_sharing(lib):
    g = _build(lib)
    sc = g.subgraph([0, 1]).copy()
    sc[0][1]["w"]["k"] = "changed"
    return g[0][1]["w"]["k"] == "changed"


def test_subgraph_copy_shares_nested_values_unlike_to_directed():
    """The contrast that makes both worth pinning: ``subgraph().copy()`` is a
    ``copy()`` — nested values are SHARED — where ``to_directed()`` deep-copies.
    Two copy-ish operations with opposite attribute semantics.
    """
    assert _subgraph_copy_sharing(fnx) == _subgraph_copy_sharing(nx)
    assert _subgraph_copy_sharing(fnx) is True
