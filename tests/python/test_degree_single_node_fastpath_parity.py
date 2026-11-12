"""Lock for br-r37-c1-dlqkq — the single-node `G.degree(n)` fast path.

Two orderings changed on this path, both of them pure reorderings that must not
move any answer:

1. The degree is now asked for FIRST and its failure treated as absence, instead
   of testing membership and then looking the degree up — one node resolution
   instead of two on the common present-node case.
2. The sequence-branch predicate tests `str`/`bytes` FIRST and short-circuits,
   instead of evaluating a 4-tuple ``isinstance`` and a ``hasattr`` before
   rejecting every string key.

Both are equivalence claims, so this file is a truth table rather than a
performance test: every argument shape that could route differently is compared
against live networkx, and the shapes that must NOT take the single-node branch
(lists, tuples, sets, frozensets, generators) are pinned alongside the ones that
must.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(["a", "b", "c", "n", "o", "p", "e"])
        graph.add_edges_from([("a", "b"), ("b", "c"), ("a", "c"), ("n", "o")])
        made.append(graph)
    return made


def _outcome(fn, graph):
    try:
        result = fn(graph)
    except Exception as exc:  # noqa: BLE001 - the exception is part of the contract
        return ("raised", type(exc).__name__, str(exc))
    if isinstance(result, (int, float)):
        return ("number", result)
    return ("view", type(result).__name__, sorted(dict(result).items()))


class _Unhashable(str):
    __hash__ = None


class _WeirdIterable:
    def __iter__(self):
        return iter(["a", "b"])


ARGUMENTS = {
    "present-str": "a",
    "absent-str": "zzz",
    "absent-str-with-char-nodes": "nope",
    "empty-str": "",
    "absent-int": 999,
    "absent-bytes": b"zz",
    "list": ["a", "b"],
    "list-with-absent": ["a", "zzz"],
    "tuple": ("a", "b"),
    "set": {"a", "b"},
    "frozenset": frozenset({"a", "b"}),
    "empty-list": [],
    "custom-iterable": _WeirdIterable(),
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("arg_name", list(ARGUMENTS))
def test_degree_argument_shapes_match_networkx(cls_name, arg_name):
    """The full truth table of argument shapes, unchanged by the reordering."""
    gnx, gfx = _pair(cls_name)
    arg = ARGUMENTS[arg_name]
    assert _outcome(lambda g: g.degree(arg), gfx) == _outcome(
        lambda g: g.degree(arg), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_present_node_returns_the_int_degree(cls_name):
    """The fast path's whole reason to exist: a present node answers a number."""
    gnx, gfx = _pair(cls_name)
    for node in gnx.nodes():
        assert gfx.degree(node) == gnx.degree(node)
        assert isinstance(gfx.degree(node), int)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_key_matches_networkx(cls_name):
    """An unhashable key must not be swallowed by the new except clause.

    The reorder catches TypeError from the native lookup, which is exactly what
    an unhashable key raises — so this is the case most at risk of silently
    changing shape.
    """
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: g.degree(_Unhashable("a")), gfx) == _outcome(
        lambda g: g.degree(_Unhashable("a")), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight", [None, "weight"])
def test_weighted_single_node_is_unaffected(cls_name, weight):
    gnx, gfx = [], []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=2.5)
        graph.add_edge("b", "c", weight=1.0)
        (gnx if lib is nx else gfx).append(graph)
    graph_nx, graph_fx = gnx[0], gfx[0]
    for arg in ("a", "zzz", ["a", "b"]):
        assert _outcome(lambda g: g.degree(arg, weight=weight), graph_fx) == _outcome(
            lambda g: g.degree(arg, weight=weight), graph_nx
        ), arg


@pytest.mark.parametrize("cls_name", CLASSES)
def test_degree_no_argument_still_returns_the_whole_view(cls_name):
    gnx, gfx = _pair(cls_name)
    assert sorted(gfx.degree()) == sorted(gnx.degree())
    assert sorted(gfx.degree) == sorted(gnx.degree)
    assert type(gfx.degree()).__name__ == type(gnx.degree()).__name__


@pytest.mark.parametrize("cls_name", CLASSES)
def test_degree_reflects_later_mutation(cls_name):
    """The fast path must not memoize a stale answer."""
    gnx, gfx = _pair(cls_name)
    assert gfx.degree("a") == gnx.degree("a")
    for graph in (gnx, gfx):
        graph.add_edge("a", "zzz")
    assert gfx.degree("a") == gnx.degree("a")
    assert gfx.degree("zzz") == gnx.degree("zzz")
    for graph in (gnx, gfx):
        graph.remove_node("zzz")
    assert gfx.degree("a") == gnx.degree("a")
    assert _outcome(lambda g: g.degree("zzz"), gfx) == _outcome(
        lambda g: g.degree("zzz"), gnx
    )
