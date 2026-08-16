"""Differential lock for br-r37-c1-sc825 — unhashable index raises TypeError.

Indexing any node-keyed view with an unhashable object is a programming error,
not a missing node, and networkx says so: the underlying dict lookup raises
``TypeError``. Two of fnx's views opened with a membership test instead, and a
membership test answers False for an unhashable argument rather than
propagating, so they reported ``KeyError`` — "that node is not in the graph" —
for something that could never be a node::

    g = DiGraph(); g.add_edge('a','b')
    g.reverse(copy=False).adj[['not','hashable']]

    networkx -> TypeError
    fnx      -> KeyError

The two sites were ``_ReverseAdjacencyView.__getitem__`` and the filtered
``NodeView.__getitem__``; between them they covered reverse views, subgraphs of
reverse views, reverses of subgraphs, and the node view of a plain subgraph — 90
divergent combinations in the sweep this file is distilled from.

The contract itself is not new. br-r37-c1-i9whv established that every
node-keyed view opens with a bare ``hash(node)``, and ``AdjacencyView`` /
``MultiAdjacencyView`` already did; these two were the ones that never got it,
which is why the plain-graph rows below are asserted alongside as the control.

Why it matters: TypeError and KeyError mean different things to a caller, and
that is precisely why networkx separates them. A bare ``except KeyError`` — the
normal way to probe for a missing node — silently swallows what should have
been a hard failure, so a bug in how a key is computed disappears instead of
surfacing.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]
UNDIRECTED = ["Graph", "MultiGraph"]

# Anything Python cannot hash. dict and set are included because a caller
# building a key from a comprehension most often lands on one of those.
UNHASHABLE = {
    "list": lambda: ["not", "hashable"],
    "dict": lambda: {"a": 1},
    "set": lambda: {1, 2},
}

KINDS = {
    "plain": lambda g: g,
    "subgraph": lambda g: g.subgraph(["a", "b"]),
    "edge_subgraph": lambda g: g.edge_subgraph(
        [("a", "b", 0)] if g.is_multigraph() else [("a", "b")]
    ),
}
DIRECTED_KINDS = {
    "reverse": lambda g: g.reverse(copy=False),
    "reverse_copy": lambda g: g.reverse(copy=True),
    "subgraph_of_reverse": lambda g: g.reverse(copy=False).subgraph(["a", "b"]),
    "reverse_of_subgraph": lambda g: g.subgraph(["a", "b"]).reverse(copy=False),
}

ACCESSORS = {
    "adj": lambda G, key: G.adj[key],
    "getitem": lambda G, key: G[key],
    "degree": lambda G, key: G.degree[key],
    "nodes": lambda G, key: G.nodes[key],
}
DIRECTED_ACCESSORS = {
    "pred": lambda G, key: G.pred[key],
    "succ": lambda G, key: G.succ[key],
    "in_degree": lambda G, key: G.in_degree[key],
    "out_degree": lambda G, key: G.out_degree[key],
}


def _build(lib, cls_name, make):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c", weight=2.0)
    return make(graph)


def _kinds_for(cls_name):
    kinds = dict(KINDS)
    if cls_name in DIRECTED:
        kinds.update(DIRECTED_KINDS)
    return kinds


def _accessors_for(cls_name):
    accessors = dict(ACCESSORS)
    if cls_name in DIRECTED:
        accessors.update(DIRECTED_ACCESSORS)
    return accessors


@pytest.mark.parametrize("cls_name", DIRECTED + UNDIRECTED)
@pytest.mark.parametrize("unhashable", list(UNHASHABLE), ids=list(UNHASHABLE))
def test_unhashable_index_raises_typeerror_like_networkx(cls_name, unhashable):
    make_key = UNHASHABLE[unhashable]
    for kind_name, make in _kinds_for(cls_name).items():
        for acc_name, accessor in _accessors_for(cls_name).items():
            gnx = _build(nx, cls_name, make)
            gfx = _build(fnx, cls_name, make)
            with pytest.raises(TypeError):
                accessor(gnx, make_key())
            with pytest.raises(TypeError):
                accessor(gfx, make_key())


@pytest.mark.parametrize("cls_name", DIRECTED + UNDIRECTED)
def test_missing_hashable_node_still_raises_keyerror_not_typeerror(cls_name):
    """The two exceptions must stay distinguishable in BOTH directions.

    A guard that raised TypeError too eagerly would pass the test above while
    destroying the missing-node contract, so the other side is asserted here,
    including the message wording settled by br-r37-c1-k4nsd.
    """
    for kind_name, make in _kinds_for(cls_name).items():
        gnx = _build(nx, cls_name, make)
        gfx = _build(fnx, cls_name, make)
        for acc_name, accessor in _accessors_for(cls_name).items():
            try:
                accessor(gnx, "zzz")
            except KeyError as exc:
                expected = exc.args
            else:
                pytest.fail(f"networkx did not raise for {cls_name}/{kind_name}/{acc_name}")
            with pytest.raises(KeyError) as caught:
                accessor(gfx, "zzz")
            assert caught.value.args == expected, (kind_name, acc_name)


@pytest.mark.parametrize("cls_name", DIRECTED + UNDIRECTED)
def test_present_node_lookups_are_unaffected(cls_name):
    """The hash() guard sits in front of a hot read path; it must only guard."""
    for kind_name, make in _kinds_for(cls_name).items():
        gnx = _build(nx, cls_name, make)
        gfx = _build(fnx, cls_name, make)
        assert sorted(gfx.adj["a"]) == sorted(gnx.adj["a"]), kind_name
        assert sorted(gfx.nodes["a"].items()) == sorted(gnx.nodes["a"].items()), kind_name
        assert gfx.degree["a"] == gnx.degree["a"], kind_name


@pytest.mark.parametrize("cls_name", DIRECTED + UNDIRECTED)
def test_hashable_but_exotic_keys_are_not_swept_up(cls_name):
    """tuple and frozenset ARE hashable and must behave as ordinary nodes."""
    for key in ((1, 2), frozenset({1, 2})):
        gnx = getattr(nx, cls_name)()
        gfx = getattr(fnx, cls_name)()
        for graph in (gnx, gfx):
            graph.add_node(key, tag="exotic")
        assert gfx.nodes[key] == gnx.nodes[key]
        assert gfx.degree[key] == gnx.degree[key]
        with pytest.raises(KeyError):
            gfx.adj[("absent", "pair")]
