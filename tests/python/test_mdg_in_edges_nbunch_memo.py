"""``MultiDiGraph.in_edges(nbunch, ...)`` uses the family's nbunch memo.

br-r37-c1-mdginb. Found by scanning the WHOLE family rather than the half that
was under repair: ``edges(nbunch, data=True)`` across all four classes plus the
in/out split. Three of the four members of the directed nbunch family routed
through a last-call memo; ``MultiDiGraph.in_edges`` did not, and paid its native
kernel on every repeated call.

    MultiDiGraph.in_edges(nbunch, data=True)   0.1282x  ->  3.1834x   (K=2000)
    its own out_edges twin, unchanged                       3.0326x

The sibling WAS the control. ``_digraph_in_edges_data_cache`` already existed as
a written, documented mirror of ``_digraph_out_edges_data_cache``; the out helper
was wired at FOUR call sites and the in helper at exactly ONE. Nothing had to be
designed - the fix was to call the function that was already there.

WHY IT LOOKED LIKE A KERNEL PROBLEM, recorded because it cost the most time here.
The two native kernels are near-identical to read, so the obvious story was that
``predecessors`` must be slower than ``successors``. It is not: both cores are
symmetric index-backed lookups. A key-length probe settled it - ``in_edges`` grew
3.15x-7.76x from 3- to 2000-character keys while ``out_edges`` was FLAT (0.97x,
1.01x). A path that is flat in key length is not running the canonicalising
kernel at all, and profiling confirmed the winner never enters native code. Read
two functions side by side and they look alike; measure them and one of them
isn't running.

WHAT THIS FILE PINS. A memo is a correctness liability before it is a speedup, so
every test here is about it being WRONG, not fast. The cache key is
``(nodes_seq, edges_seq, nbunch) + native_args``, and the ways that can betray
you are: a mutation that does not move a seq, a different nbunch, and - the one
that would be silent - a different ARGUMENT SPELLING reusing one attribute slot.
``data=True``, ``keys=True`` and ``data='weight'`` all write to the SAME
``_fnx_in_edges_nbunch_data_cache`` attribute, so they must be separated by the
key or one spelling will answer for another.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

KEY_LEN = 64


def _build(lib, key_len: int = KEY_LEN, edges: int = 12):
    graph = lib.MultiDiGraph()
    for i in range(edges):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i
        )
    graph.add_edge("a0".ljust(key_len, "x"), "b0".ljust(key_len, "y"), weight=99)
    return graph, list(graph.nodes())


def _norm(rows):
    out = []
    for row in rows:
        out.append(tuple(sorted(x.items()) if isinstance(x, dict) else x for x in row))
    return sorted(out, key=repr)


CALLS = [
    ("data=True", dict(data=True)),
    ("data=True,keys", dict(data=True, keys=True)),
    ("data=False", dict(data=False)),
    ("data=False,keys", dict(data=False, keys=True)),
    ("data=weight", dict(data="weight")),
    ("data=weight,default", dict(data="weight", default=-1)),
    ("data=missing,default", dict(data="nope", default=-1)),
    ("data=weight,keys", dict(data="weight", keys=True)),
]


@pytest.mark.parametrize("label,kw", CALLS, ids=[c[0] for c in CALLS])
def test_matches_networkx_for_every_spelling(label, kw):
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:8]
    # Twice: the first call populates the memo, the second must be served by it
    # and must still agree.
    for _ in range(2):
        assert _norm(got.in_edges(nbunch, **kw)) == _norm(want.in_edges(nbunch, **kw))


def test_argument_spellings_do_not_answer_for_each_other():
    """THE silent failure: every spelling writes one cache attribute.

    Interleaved deliberately, so a key that ignored ``native_args`` would serve
    the previous spelling's rows and the assertion would catch it on the second
    pass rather than the first.
    """
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:8]
    for _ in range(3):
        for _label, kw in CALLS:
            assert _norm(got.in_edges(nbunch, **kw)) == _norm(
                want.in_edges(nbunch, **kw)
            )


def test_a_different_nbunch_is_not_served_the_previous_one():
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for nbunch in (nodes[:4], nodes[4:8], nodes[:1], [], nodes[:8], nodes[2:3]):
        assert _norm(got.in_edges(nbunch, data=True)) == _norm(
            want.in_edges(nbunch, data=True)
        )


def test_structural_mutation_invalidates():
    """Every mutation kind, each after a warming call that fills the memo."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:8]
    a0, b0 = nodes[0], nodes[1]

    def check(what):
        assert _norm(got.in_edges(nbunch, data=True)) == _norm(
            want.in_edges(nbunch, data=True)
        ), f"stale after {what}"

    check("warm")
    for graph in (got, want):
        graph.add_edge(a0, b0, weight=1234)
    check("add parallel edge")

    for graph in (got, want):
        graph.add_edge("fresh-source".ljust(KEY_LEN, "z"), b0, weight=7)
    check("add edge from a new node")

    for graph in (got, want):
        graph.remove_edge(a0, b0)
    check("remove one parallel edge")

    for graph in (got, want):
        graph.add_node("lonely".ljust(KEY_LEN, "q"))
    check("add isolated node")

    for graph in (got, want):
        graph.remove_node(nodes[3])
    check("remove node")


def test_attr_mutation_after_capture_is_reflected():
    """nx's EdgeDataView is LIVE: the memo must hold the same dicts, not copies."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:8]
    got.in_edges(nbunch, data=True)  # warm the memo
    want.in_edges(nbunch, data=True)

    for graph in (got, want):
        for _s, _t, _k, attrs in list(graph.in_edges(nbunch, data=True, keys=True)):
            attrs["marker"] = "set-after-capture"

    assert _norm(got.in_edges(nbunch, data=True)) == _norm(
        want.in_edges(nbunch, data=True)
    )
    assert all("marker" in d for _s, _t, d in got.in_edges(nbunch, data=True))


def test_out_edges_twin_is_unaffected():
    """The control: the sibling that already had the memo must not change."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    nbunch = nodes[:8]
    for _ in range(2):
        assert _norm(got.out_edges(nbunch, data=True)) == _norm(
            want.out_edges(nbunch, data=True)
        )


def test_non_primitive_nbunch_is_not_memoized_but_still_correct():
    """``_primitive_nbunch_cache_key`` returns None for these; correctness stands."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    got.add_edge((1, 2), (3, 4), weight=5)
    want.add_edge((1, 2), (3, 4), weight=5)
    for nbunch in ([(3, 4)], iter(nodes[:4]), {nodes[0], nodes[1]}):
        nb = list(nbunch) if not isinstance(nbunch, (list, set)) else nbunch
        assert _norm(got.in_edges(nb, data=True)) == _norm(want.in_edges(nb, data=True))
