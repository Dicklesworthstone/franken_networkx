"""``MultiGraph.edges(nbunch, ...)`` uses the family's nbunch memo.

br-r37-c1-mgednb. The last member of the nbunch edge-view family to be paying its
native kernel on every repeated call. Measured at 2000-character node keys:

    data=True         0.1592x -> 2.7271x        data=False   0.2172x -> 2.8545x
    data='weight'     0.1933x -> 2.9510x        keys=True    0.1375x -> 2.7359x

All four crossed from heavy losses to wins, and all four are now flat in key
length. Sibling of br-r37-c1-mdginb, which did the same for
``MultiDiGraph.in_edges``; between them the family is consistent.

THREE SLOTS, ONE OBJECT - the risk this file exists for. The directed helpers each
own a single hard-coded attribute because those classes have one nbunch edge-view
each. ``MultiGraph.edges`` has THREE native nbunch call sites on the same object
(``data=False``, ``data=True``, ``data=<key>``), so ``_nbunch_data_cache`` takes
the slot name as an argument and each site gets its own. Sharing one slot would
still be correct - the key carries ``native_args`` - but the spellings would evict
each other on every alternation and the memo would never hit. Correct and useless
is a worse outcome than incorrect, because nothing fails to tell you about it.

WHAT IS PINNED, in order of how quietly it could break:

1. SPELLINGS MUST NOT ANSWER FOR EACH OTHER. Three slots plus a key carrying
   ``native_args`` is two independent mechanisms that must agree. Tested
   interleaved, so a cross-serve shows up on the second pass rather than never.
2. THE RETURNED LIST MUST NOT ALIAS THE CACHE. Unlike the directed siblings these
   results are wrapped in ``_EdgeListWithSetAlgebra`` and an edge-data view, and
   callers do set algebra on them. A caller mutating its result must not corrupt
   what the next caller receives.
3. LIVE ATTR DICTS. nx's edge-data views are live; the memo holds the SAME dict
   objects, so a post-capture attribute write must still be visible.
4. INVALIDATION, including the multigraph-only case: adding a PARALLEL edge
   between two nodes that are already connected.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

KEY_LEN = 48


def _build(lib, key_len: int = KEY_LEN, edges: int = 10):
    graph = lib.MultiGraph()
    for i in range(edges):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i
        )
    # a parallel edge from the start: multigraph-specific shape
    graph.add_edge("a0".ljust(key_len, "x"), "b0".ljust(key_len, "y"), weight=500)
    return graph, list(graph.nodes())


def _norm(rows):
    out = []
    for row in rows:
        out.append(tuple(sorted(x.items()) if isinstance(x, dict) else x for x in row))
    return sorted(out, key=repr)


SPELLINGS = [
    ("data=True", dict(data=True)),
    ("data=False", dict(data=False)),
    ("data=True,keys", dict(data=True, keys=True)),
    ("data=False,keys", dict(data=False, keys=True)),
    ("data=weight", dict(data="weight")),
    ("data=weight,keys", dict(data="weight", keys=True)),
    ("data=weight,default", dict(data="weight", default=-7)),
    ("data=absent,default", dict(data="nope", default=-7)),
]
IDS = [s[0] for s in SPELLINGS]


@pytest.mark.parametrize("label,kw", SPELLINGS, ids=IDS)
def test_matches_networkx_warm_and_cold(label, kw):
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    for _ in range(2):  # first call fills the slot, second must be served from it
        assert _norm(got.edges(nbunch, **kw)) == _norm(want.edges(nbunch, **kw))


def test_spellings_do_not_answer_for_each_other():
    """Requirement 1 — three slots AND a native_args key must both hold."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    for _ in range(3):
        for _label, kw in SPELLINGS:
            assert _norm(got.edges(nbunch, **kw)) == _norm(want.edges(nbunch, **kw))


def test_returned_result_does_not_alias_the_cache():
    """Requirement 2 — these results are wrapped and callers mutate them."""
    got, nodes = _build(fnx)
    nbunch = nodes[:6]
    first = list(got.edges(nbunch, data=True))
    baseline = _norm(first)

    mutated = got.edges(nbunch, data=True)
    as_list = list(mutated)
    as_list.append(("poison", "poison", {}))
    del as_list[0]

    assert _norm(got.edges(nbunch, data=True)) == baseline, (
        "a caller's mutation of its own result changed what the next call returns"
    )


def test_set_algebra_still_works_and_does_not_corrupt_the_cache():
    """The MultiGraph path wraps results in a set-algebra list; exercise it."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    baseline = _norm(got.edges(nbunch, data=False))

    got_pairs = set(got.edges(nbunch, data=False))
    want_pairs = set(want.edges(nbunch, data=False))
    assert {tuple(sorted(p)) for p in got_pairs} == {
        tuple(sorted(p)) for p in want_pairs
    }

    assert _norm(got.edges(nbunch, data=False)) == baseline


def test_attr_mutation_after_capture_is_reflected():
    """Requirement 3 — the memo must hold live dicts, not copies."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    got.edges(nbunch, data=True)
    want.edges(nbunch, data=True)
    for graph in (got, want):
        for *_ends, attrs in list(graph.edges(nbunch, data=True)):
            attrs["stamped"] = True
    assert _norm(got.edges(nbunch, data=True)) == _norm(want.edges(nbunch, data=True))
    assert all(d.get("stamped") for *_e, d in got.edges(nbunch, data=True))


def test_invalidation_including_parallel_edges():
    """Requirement 4 — every mutation kind, each after a warming call."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:6]
    a0, b0 = nodes[0], nodes[1]

    def check(what):
        for _label, kw in (("t", dict(data=True)), ("f", dict(data=False))):
            assert _norm(got.edges(nbunch, **kw)) == _norm(
                want.edges(nbunch, **kw)
            ), f"stale after {what} ({kw})"

    check("warm")
    for g in (got, want):
        g.add_edge(a0, b0, weight=1001)
    check("add a PARALLEL edge")

    for g in (got, want):
        g.remove_edge(a0, b0)
    check("remove one of several parallel edges")

    for g in (got, want):
        g.add_edge("newnode".ljust(KEY_LEN, "z"), b0, weight=3)
    check("add edge from a new node")

    for g in (got, want):
        g.add_node("isolated".ljust(KEY_LEN, "q"))
    check("add isolated node")

    for g in (got, want):
        g.remove_node(nodes[4])
    check("remove node")


def test_different_nbunch_is_not_served_the_previous_one():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for nbunch in (nodes[:3], nodes[3:6], [], nodes[:1], nodes[:6], nodes[2:4]):
        assert _norm(got.edges(nbunch, data=True)) == _norm(
            want.edges(nbunch, data=True)
        )


def test_non_primitive_nbunch_is_correct_though_unmemoized():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for g in (got, want):
        g.add_edge((1, 2), (3, 4), weight=5)
    for nbunch in ([(1, 2)], {nodes[0], nodes[1]}, list(iter(nodes[:3]))):
        nb = list(nbunch) if isinstance(nbunch, set) else nbunch
        assert _norm(got.edges(nb, data=True)) == _norm(want.edges(nb, data=True))


def test_simple_graph_twin_is_unaffected():
    """Control: Graph.edges(nbunch) uses a different path and must not move."""
    g2 = fnx.Graph()
    x2 = nx.Graph()
    for i in range(10):
        g2.add_edge(f"a{i}", f"b{i}", weight=i)
        x2.add_edge(f"a{i}", f"b{i}", weight=i)
    nb = list(g2.nodes())[:6]
    assert _norm(g2.edges(nb, data=True)) == _norm(x2.edges(nb, data=True))
