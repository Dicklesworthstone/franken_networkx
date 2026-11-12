"""The directed nbunch edge-view family all shares one memo helper.

br-r37-c1-dinbfam. Completes the sweep begun in br-r37-c1-mdginb (MultiDiGraph
in_edges) and br-r37-c1-mgednb (MultiGraph edges). A full family scan - four
classes x {edges, in_edges, out_edges} x {data=True, data=False, data=<key>} -
showed a single clean pattern: EVERY memoized spelling won and EVERY unmemoized
one lost. Only ``data=True`` had ever been wired.

At 2000-character node keys, before -> after:

    DiGraph.edges(data=False)          0.5194x -> 1.5111x
    DiGraph.edges(data=<key>)          0.2725x -> 1.7006x
    DiGraph.in_edges(data=False)       0.6835x -> 4.5547x
    DiGraph.in_edges(data=<key>)       0.2778x -> 1.9102x
    DiGraph.out_edges(data=False)      0.6811x -> 4.5865x
    DiGraph.out_edges(data=<key>)      0.2781x -> 1.8877x
    MultiDiGraph.edges(data=False)     0.2494x -> 2.5354x
    MultiDiGraph.edges(data=<key>)     0.2393x -> 2.6514x
    MultiDiGraph.out_edges(data=False) 0.2616x -> 2.9235x
    MultiDiGraph.out_edges(data=<key>) 0.2410x -> 3.1488x

21 of the family's 24 spellings now beat networkx; the 3 that do not are simple
``Graph.edges``, which reaches a different path entirely and is untouched here.

SLOTS ARE SHARED ON PURPOSE, and that is what most of this file tests. On a
DiGraph, ``G.edges(nbunch, ...)`` and ``G.out_edges(nbunch, ...)`` are the same
query - nx defines the former as the latter - and both call the SAME native
kernel with the same arguments. They are therefore given the SAME slot, so a
caller alternating between the two spellings gets hits rather than evictions.
That is a deliberate aliasing of two entry points onto one cache, and it is only
safe while the two really do return equal rows. If anyone ever makes
``DiGraph.edges`` differ from ``out_edges``, ``test_edges_and_out_edges_agree``
fails and this decision is what to revisit.

The rest is the same contract the two sibling files pin: spellings must not answer
for each other, results must not alias the cache, attr dicts stay live, and every
mutation kind invalidates.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

KEY_LEN = 40


def _build(lib, cls: str, key_len: int = KEY_LEN, edges: int = 10):
    graph = getattr(lib, cls)()
    for i in range(edges):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i
        )
    # a back-edge so in_edges and out_edges genuinely differ
    graph.add_edge("b0".ljust(key_len, "y"), "a0".ljust(key_len, "x"), weight=77)
    if cls == "MultiDiGraph":
        graph.add_edge("a1".ljust(key_len, "x"), "b1".ljust(key_len, "y"), weight=88)
    return graph, list(graph.nodes())


def _norm(rows):
    out = []
    for row in rows:
        out.append(tuple(sorted(x.items()) if isinstance(x, dict) else x for x in row))
    return sorted(out, key=repr)


SPELLINGS = [
    ("data=True", dict(data=True)),
    ("data=False", dict(data=False)),
    ("data=weight", dict(data="weight")),
    ("data=weight,default", dict(data="weight", default=-3)),
    ("data=absent,default", dict(data="nope", default=-3)),
]
IDS = [s[0] for s in SPELLINGS]
CLASSES = ["DiGraph", "MultiDiGraph"]
METHODS = ["edges", "in_edges", "out_edges"]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("label,kw", SPELLINGS, ids=IDS)
def test_matches_networkx_twice(cls, method, label, kw):
    """Called twice: the first fills the slot, the second must be served by it."""
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    nbunch = nodes[:6]
    for _ in range(2):
        assert _norm(getattr(got, method)(nbunch, **kw)) == _norm(
            getattr(want, method)(nbunch, **kw)
        )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
def test_spellings_do_not_answer_for_each_other(cls, method):
    """Interleaved, so a cross-serve appears on a later pass rather than never."""
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    nbunch = nodes[:6]
    for _ in range(3):
        for _label, kw in SPELLINGS:
            assert _norm(getattr(got, method)(nbunch, **kw)) == _norm(
                getattr(want, method)(nbunch, **kw)
            )


@pytest.mark.parametrize("cls", CLASSES)
def test_methods_do_not_answer_for_each_other(cls):
    """in_edges and out_edges share a helper but MUST NOT share a slot.

    The fixture carries a back-edge precisely so the two differ; without one this
    test would pass on a graph where every answer happens to be the same.
    """
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    nbunch = nodes[:6]
    for _ in range(3):
        for method in METHODS:
            for _label, kw in SPELLINGS:
                assert _norm(getattr(got, method)(nbunch, **kw)) == _norm(
                    getattr(want, method)(nbunch, **kw)
                ), f"{cls}.{method} diverged under interleaving"
    # The guard on the guard. Over an nbunch covering BOTH endpoints of every
    # edge, in_edges and out_edges legitimately collect the same set, so the
    # check above would pass on a fixture that could not distinguish them. A
    # TARGET-ONLY nbunch is where they must differ: b-nodes have in-edges from
    # their a-node but (except b0) no out-edges at all.
    targets = [n for n in nodes if n.startswith("b")][:4]
    assert _norm(got.in_edges(targets, data=True)) != _norm(
        got.out_edges(targets, data=True)
    ), "fixture is degenerate: in_edges and out_edges must differ for this to test anything"
    assert _norm(got.in_edges(targets, data=True)) == _norm(
        want.in_edges(targets, data=True)
    )
    assert _norm(got.out_edges(targets, data=True)) == _norm(
        want.out_edges(targets, data=True)
    )


@pytest.mark.parametrize("cls", CLASSES)
def test_edges_and_out_edges_agree(cls):
    """The invariant that makes the shared slot legitimate."""
    got, nodes = _build(fnx, cls)
    nbunch = nodes[:6]
    for _label, kw in SPELLINGS:
        assert _norm(got.edges(nbunch, **kw)) == _norm(got.out_edges(nbunch, **kw)), (
            f"{cls}.edges and .out_edges disagree, so they must stop sharing a "
            "cache slot"
        )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
def test_every_mutation_kind_invalidates(cls, method):
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    nbunch = nodes[:6]
    a0, b0 = nodes[0], nodes[1]

    def check(what):
        for kw in (dict(data=True), dict(data=False), dict(data="weight")):
            assert _norm(getattr(got, method)(nbunch, **kw)) == _norm(
                getattr(want, method)(nbunch, **kw)
            ), f"{cls}.{method} stale after {what}"

    check("warm")
    for g in (got, want):
        g.add_edge(a0, b0, weight=555)
    check("add edge between existing nodes")
    for g in (got, want):
        g.add_edge("newsrc".ljust(KEY_LEN, "z"), b0, weight=6)
    check("add edge from a new node")
    for g in (got, want):
        g.add_node("lonely".ljust(KEY_LEN, "q"))
    check("add isolated node")
    for g in (got, want):
        g.remove_edge(a0, b0)
    check("remove edge")
    for g in (got, want):
        g.remove_node(nodes[4])
    check("remove node")


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
def test_result_does_not_alias_the_cache(cls, method):
    got, nodes = _build(fnx, cls)
    nbunch = nodes[:6]
    baseline = _norm(getattr(got, method)(nbunch, data=True))
    scratch = list(getattr(got, method)(nbunch, data=True))
    scratch.append(("poison", "poison", {}))
    if scratch:
        del scratch[0]
    assert _norm(getattr(got, method)(nbunch, data=True)) == baseline


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
def test_attr_dicts_stay_live(cls, method):
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    nbunch = nodes[:6]
    getattr(got, method)(nbunch, data=True)
    getattr(want, method)(nbunch, data=True)
    for graph in (got, want):
        for *_ends, attrs in list(getattr(graph, method)(nbunch, data=True)):
            attrs["live"] = 1
    assert _norm(getattr(got, method)(nbunch, data=True)) == _norm(
        getattr(want, method)(nbunch, data=True)
    )


@pytest.mark.parametrize("cls", CLASSES)
def test_a_different_nbunch_is_not_served_the_previous_one(cls):
    got, nodes = _build(fnx, cls)
    want, _ = _build(nx, cls)
    for nbunch in (nodes[:3], nodes[3:6], [], nodes[:1], nodes[:6], nodes[2:5]):
        for method in METHODS:
            assert _norm(getattr(got, method)(nbunch, data=True)) == _norm(
                getattr(want, method)(nbunch, data=True)
            )


def test_multidigraph_keys_argument_is_part_of_the_key():
    """``keys`` rides in ``native_args``; keys=True must not serve keys=False."""
    got, nodes = _build(fnx, "MultiDiGraph")
    want, _ = _build(nx, "MultiDiGraph")
    nbunch = nodes[:6]
    for _ in range(3):
        for keys in (False, True, False, True):
            for method in METHODS:
                assert _norm(getattr(got, method)(nbunch, data=True, keys=keys)) == _norm(
                    getattr(want, method)(nbunch, data=True, keys=keys)
                )
