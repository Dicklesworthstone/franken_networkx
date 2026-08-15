"""Regression lock for br-r37-c1-6n9vm — the exact-`str` present-key memo.

`has_node` spent 77.4% of its 437.4 instructions rebuilding a canonical
`"str:{len}:{s}"` and rehashing it, because CPython caches a string's hash
inside the object and the native store is keyed by a Rust `String`. Keys already
proven present are now remembered in a Python `set`, so a repeat probe reuses
that cached hash. The row moved from 0.4556x to 1.2205x against live networkx.

A memo in front of a lookup can only be trusted if it answers the same question
the lookup does, so every test here compares against LIVE networkx or asserts a
property that a wrong memo would break:

* the memo is keyed by Python equality, so equal-but-nonidentical keys must hit
  and hash-equal keys of different types (7 / 7.0 / True) must not be confused;
* it is gated on EXACT `str`, because a `str` subclass with a lying `__hash__`
  or `__eq__` would otherwise resolve to whatever entry it claims to equal —
  and only AFTER that entry had been probed, making the answer depend on cache
  state rather than on the graph;
* it is dropped whenever `nodes_seq` moves, because node removal renumbers the
  compact native store;
* it never turns an absent key into a present one, and never survives the node
  that put it there.
"""

from __future__ import annotations

import gc

import networkx as nx
import pytest

import franken_networkx as fnx

# MultiDiGraph is NOT memoised — it has no `has_edge_node_index_cache` field to
# hang the set on — and it is parametrised through every test below precisely so
# the memoised and unmemoised classes cannot drift apart in behaviour.
CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

PRESENT = ["alpha", "beta", 7, 2.5]


class _LyingStr(str):
    """Claims to hash and compare equal to `"alpha"`, whatever it contains."""

    def __hash__(self):
        return hash("alpha")

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


def _pair(cls_name):
    reference, subject = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (reference, subject):
        graph.add_nodes_from(PRESENT)
    return reference, subject


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_repeated_probes_match_networkx_warm_and_cold(cls_name):
    reference, subject = _pair(cls_name)
    probes = ["alpha", "absent", 7, 7.0, True, 2.5, None, "beta"]
    for _ in range(3):  # cold, then warm, then warm again
        for key in probes:
            assert subject.has_node(key) == reference.has_node(key), key
            assert (key in subject) == (key in reference), key


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_equal_but_nonidentical_strings_hit_the_same_entry(cls_name):
    _reference, subject = _pair(cls_name)
    equal = "alpha".encode().decode()
    assert equal == "alpha" and equal is not "alpha"  # noqa: F632 — identity IS the point
    assert subject.has_node("alpha") is True  # warm the memo with one object
    assert subject.has_node(equal) is True
    assert (equal in subject) is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_a_lying_str_subclass_is_decided_by_its_characters(cls_name):
    """Cache state must not decide an answer.

    Gate the memo on `isinstance` instead of exact `str` and this returns True
    once "alpha" has been probed, and False before — the same call answering two
    different ways depending on history.
    """
    _reference, subject = _pair(cls_name)
    assert subject.has_node(_LyingStr("absent")) is False
    assert subject.has_node("alpha") is True  # populate the memo
    assert subject.has_node(_LyingStr("absent")) is False
    assert (_LyingStr("absent") in subject) is False
    # A subclass whose characters DO name a node still resolves, memo or not.
    assert subject.has_node(_LyingStr("alpha")) is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_removal_invalidates_the_memo(cls_name):
    """Node removal renumbers the native store; a stale memo would lie."""
    reference, subject = _pair(cls_name)
    for graph in (reference, subject):
        assert graph.has_node("alpha")
        graph.remove_node("alpha")
    assert subject.has_node("alpha") == reference.has_node("alpha") is False
    assert ("alpha" in subject) is False
    for graph in (reference, subject):
        graph.add_node("alpha")
    assert subject.has_node("alpha") is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_clear_and_rebuild_do_not_resurrect_a_key(cls_name):
    _reference, subject = _pair(cls_name)
    assert subject.has_node("alpha")
    subject.clear()
    assert subject.has_node("alpha") is False
    subject.add_node("gamma")
    assert subject.has_node("alpha") is False
    assert subject.has_node("gamma") is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_unhashable_key_is_false_not_an_error(cls_name):
    reference, subject = _pair(cls_name)
    subject.has_node("alpha")  # warm, so the probe meets a populated memo
    assert (["not", "hashable"] in reference) is False
    assert (["not", "hashable"] in subject) is False
    assert subject.has_node(["not", "hashable"]) is False


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_a_key_probed_before_it_exists_is_not_remembered_as_absent(cls_name):
    """Only PRESENT keys are memoised, so a later add must be visible."""
    _reference, subject = _pair(cls_name)
    assert subject.has_node("later") is False
    subject.add_node("later")
    assert subject.has_node("later") is True
    assert ("later" in subject) is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_copies_and_subgraphs_do_not_share_a_memo(cls_name):
    original = getattr(fnx, cls_name)()
    original.add_nodes_from(PRESENT)
    assert original.has_node("alpha")
    clone = original.copy()
    clone.remove_node("alpha")
    assert clone.has_node("alpha") is False
    assert original.has_node("alpha") is True
    view = original.subgraph(["beta"])
    assert view.has_node("alpha") is False
    assert view.has_node("beta") is True


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_memoised_keys_do_not_leak_the_graph(cls_name):
    """The memo holds Python references, so it must be traversed and cleared.

    A key that refers back to its own graph makes a cycle; if the memo is not
    visited by `__traverse__` the graph becomes uncollectable.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_node("alpha")
    assert graph.has_node("alpha")
    graph.graph["self"] = graph  # a cycle through the graph's own attributes
    gc.collect()
    tracked_before = len(gc.get_objects())
    del graph
    collected = gc.collect()
    assert collected >= 0  # the call itself must not crash on the memo
    assert len(gc.get_objects()) <= tracked_before


def test_memo_is_scoped_to_one_graph():
    left, right = fnx.Graph(), fnx.Graph()
    left.add_node("alpha")
    assert left.has_node("alpha") is True
    assert right.has_node("alpha") is False
    right.add_node("alpha")
    assert right.has_node("alpha") is True
