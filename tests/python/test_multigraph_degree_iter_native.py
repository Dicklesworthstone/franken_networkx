"""Unweighted ``dict(G.degree())`` must not walk a multigraph node by node.

br-r37-c1-9iro1. ``MultiDegreeView.__iter__`` and ``MultiDiGraphDegreeView.__iter__``
routed both WEIGHTED spellings to native accumulators, and the simple classes
serve ``dict(G.degree())`` natively - but the UNWEIGHTED multigraph case fell
through to the per-node generator at the end of each method:

    return ((node, self[node]) for node in self._iter_nodes())

which pays a Python frame, a ``hash(node)`` and a lookup FOR EVERY NODE.
``_raw_base_view`` - the native multigraph DegreeView, already built in
``__init__`` - yields exactly the same pairs.

FOUND BY ``scripts/read_call_scaling_probe.py``, not by reading. Holding the
request fixed and growing the parent, Python-level call counts were:

    class          200 nodes   800 nodes   ratio
    Graph                 41          41    1.00   (native)
    DiGraph               41          41    1.00   (native)
    MultiGraph         12161       48161    3.96   <-- walked in Python
    MultiDiGraph       12161       48161    3.96   <-- walked in Python

and after the fix both multigraph rows read 101 flat. That is the shape this
file pins: NO GROWTH TERM. Counting rather than timing is what made the finding
admissible at all - it was made under a build freeze with benchmarks banned, on
a host at loadavg 16.

THE DIRECTED SIBLING WAS FOUND BY THE PROBE TOO, and that is worth recording
because it is the recurring failure mode in this area: fixing ``MultiGraph``
alone left ``MultiDiGraph`` still scaling, because it is served by a SEPARATE
view class carrying its own copy of the method. The probe caught it immediately;
reading the patched file would not have.

WHAT THIS FILE PINS:

  * pair-for-pair equality with networkx for both multigraph classes across
    parallel edges, self-loops, isolated nodes, empty and single-node graphs -
    the fixture shapes that distinguish a multigraph degree from a simple one;
  * the OTHER spellings still work, because the fix is gated on
    ``_weight is None and _nodes is None`` and must not touch them: weighted
    all-node, weighted nbunch, unweighted nbunch, subscript, ``len()``;
  * ``in_degree`` and ``out_degree`` on MultiDiGraph, which are separate views
    that the gate must leave alone;
  * RE-ITERABILITY. The replacement returns ``iter(self._raw_base_view)`` rather
    than a generator, so a second pass over the same view object must still
    yield everything. A one-shot iterator would pass every single-pass test in
    this file and break real callers.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
ALL = ["Graph", "DiGraph"] + MULTI


def _pairs(view):
    return [(str(n), d) for n, d in view]


def _build(lib, cls, shape):
    g = getattr(lib, cls)()
    if shape == "empty":
        return g
    if shape == "single":
        g.add_node("only")
        return g
    for i in range(20):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % 20), w=i + 1)
    if shape == "parallel":
        g.add_edge("n0", "n1", w=9)
    elif shape == "selfloop":
        g.add_edge("n3", "n3", w=2)
    elif shape == "isolated":
        g.add_node("iso")
    return g


SHAPES = ["plain", "parallel", "selfloop", "isolated", "empty", "single"]


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("shape", SHAPES)
def test_unweighted_all_node_degree_matches_networkx(cls, shape):
    got, want = _build(fnx, cls, shape), _build(nx, cls, shape)
    assert _pairs(got.degree) == _pairs(want.degree)
    assert dict(_pairs(got.degree)) == dict(_pairs(want.degree))
    assert len(got.degree) == len(want.degree)


@pytest.mark.parametrize("cls", MULTI)
@pytest.mark.parametrize("shape", SHAPES)
def test_the_other_spellings_are_untouched(cls, shape):
    """The gate is ``_weight is None and _nodes is None``; prove the rest still work."""
    got, want = _build(fnx, cls, shape), _build(nx, cls, shape)
    nbunch = [str(n) for n in list(got)[:3]]
    assert _pairs(got.degree(weight="w")) == _pairs(want.degree(weight="w"))
    assert _pairs(got.degree(nbunch)) == _pairs(want.degree(nbunch))
    assert _pairs(got.degree(nbunch, weight="w")) == _pairs(want.degree(nbunch, weight="w"))
    for node in nbunch:
        assert got.degree[node] == want.degree[node]
        assert got.degree(node) == want.degree(node)


@pytest.mark.parametrize("shape", SHAPES)
def test_directed_in_and_out_degree_are_untouched(shape):
    got, want = _build(fnx, "MultiDiGraph", shape), _build(nx, "MultiDiGraph", shape)
    assert _pairs(got.in_degree) == _pairs(want.in_degree)
    assert _pairs(got.out_degree) == _pairs(want.out_degree)
    assert _pairs(got.in_degree(weight="w")) == _pairs(want.in_degree(weight="w"))
    assert _pairs(got.out_degree(weight="w")) == _pairs(want.out_degree(weight="w"))


@pytest.mark.parametrize("cls", MULTI)
def test_the_view_is_re_iterable(cls):
    """``iter(_raw_base_view)`` must not be a one-shot iterator.

    Every other test here makes a single pass and would pass regardless.
    """
    graph = _build(fnx, cls, "parallel")
    view = graph.degree
    first, second = _pairs(view), _pairs(view)
    assert first == second
    assert first, "fixture produced no nodes"
    assert list(view) == list(view)


@pytest.mark.parametrize("cls", MULTI)
def test_the_view_tracks_a_mutating_graph(cls):
    """The degree view is LIVE; the native route must not snapshot."""
    got, want = _build(fnx, cls, "plain"), _build(nx, cls, "plain")
    assert _pairs(got.degree) == _pairs(want.degree)
    for g in (got, want):
        g.add_edge("n0", "n5")
        g.add_node("fresh")
    assert _pairs(got.degree) == _pairs(want.degree)
    for g in (got, want):
        g.remove_node("n1")
    assert _pairs(got.degree) == _pairs(want.degree)


@pytest.mark.parametrize("cls", MULTI)
def test_parallel_edges_and_self_loops_count_as_networkx_does(cls):
    """The multigraph-specific arithmetic, asserted against explicit numbers.

    A self-loop counts TWICE in an undirected multigraph's degree and once in
    each direction for a directed one; parallel edges each count.
    """
    graph = getattr(fnx, cls)()
    reference = getattr(nx, cls)()
    for g in (graph, reference):
        g.add_edge("a", "b")
        g.add_edge("a", "b")  # parallel
        g.add_edge("a", "a")  # self-loop
    assert dict(_pairs(graph.degree)) == dict(_pairs(reference.degree))
    assert dict(_pairs(graph.degree))["a"] == dict(_pairs(reference.degree))["a"]
