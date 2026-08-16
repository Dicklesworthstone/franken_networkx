"""Parity lock for br-r37-c1-8itxk — the method-shadow eligibility memo.

Assigning a networkx private store (``G._node``, ``G._adj``, ...) makes fnx
shadow its raw PyO3 methods on that ONE instance with mapping-aware fallbacks
(br-r37-c1-qmi5w / 6q4wl / 57ba1 / heyxu). The installer used to re-derive,
for every assignment and every method name, whether the class's binding was a
raw method it may shadow — an MRO walk in a Python generator plus an ``any()``.
A reverse view assigns three private stores at construction, so
``DiGraph.reverse(copy=False)`` paid twelve of those walks per call.

That question is a property of the CLASS, so it is now memoised on
(class, method-name). This file pins the two things that makes risky:

* a SUBCLASS must get its own answer rather than inheriting the parent's
  cached one — the memo is keyed on the class for exactly this reason;
* the shadow behaviour itself must be unchanged, so the mapping-aware
  fallbacks still fire when a private store is assigned, on every class.

The behaviour assertions are differential against live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c", weight=2.0)
    return graph


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_node_store_still_shadows(cls_name):
    """The mechanism the memo sits inside must still work."""
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        graph._node = {"a": {}, "b": {}, "zz": {}}
        results.append(
            (
                graph.has_node("zz"),
                graph.has_node("c"),
                graph.number_of_nodes(),
                graph.order(),
            )
        )
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_adj_store_still_shadows(cls_name):
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        inner = {"b": {0: {}}} if graph.is_multigraph() else {"b": {}}
        graph._adj = {"a": inner, "b": {}, "zz": {}}
        results.append((graph.has_edge("a", "b"), graph.has_edge("a", "zz")))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_subclass_gets_its_own_memo_entry(cls_name):
    """The memo is keyed on the CLASS; a subclass override must win.

    If the eligibility answer were cached per method NAME alone, a subclass
    that defines its own has_node would inherit the base class's "shadowable"
    answer and get its override replaced.
    """
    base = getattr(fnx, cls_name)
    sentinel = object()

    class Sub(base):
        def has_node(self, n):  # noqa: D401 - deliberate override
            return sentinel

    graph = Sub()
    graph.add_edge("a", "b")
    assert graph.has_node("a") is sentinel
    # Assigning a private store must NOT replace a genuine subclass override.
    graph._node = {"a": {}, "b": {}}
    assert graph.has_node("a") is sentinel

    # And the base class is unaffected by the subclass's entry.
    plain = base()
    plain.add_edge("a", "b")
    assert plain.has_node("a") is True
    assert plain.has_node("zz") is False


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_is_correct_and_repeatable(cls_name):
    """The row that motivated this: reverse builds via private overrides."""
    for _ in range(3):
        gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
        rnx, rfx = gnx.reverse(copy=False), gfx.reverse(copy=False)
        assert sorted(map(str, rfx.edges)) == sorted(map(str, rnx.edges))
        assert sorted(map(str, rfx.nodes)) == sorted(map(str, rnx.nodes))
        assert dict(rfx.in_degree) == dict(rnx.in_degree)
        assert dict(rfx.out_degree) == dict(rnx.out_degree)
        assert rfx["b"]["a"] == rnx["b"]["a"]


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_many_reverse_views_do_not_interfere(cls_name):
    """The memo is shared across instances; instances must not be."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    views_nx = [gnx.reverse(copy=False) for _ in range(5)]
    views_fx = [gfx.reverse(copy=False) for _ in range(5)]
    for vnx, vfx in zip(views_nx, views_fx):
        assert sorted(map(str, vfx.edges)) == sorted(map(str, vnx.edges))
    # The originals are untouched.
    assert sorted(map(str, gfx.edges)) == sorted(map(str, gnx.edges))
