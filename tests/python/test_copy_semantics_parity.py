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
    for lib, res in ((fnx, []), (nx, [])):
        g = _build(lib)
        g.add_edge(1, 2)
        sc = g.subgraph([0, 1]).copy()
        sc.add_edge(0, 5)
        res.append((g.has_edge(0, 5), sorted(sc.nodes())))
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
