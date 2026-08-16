"""Lock for the captured-row frame collapse on `v in G.adj[u]`.

cProfile put a multigraph membership test at FOUR Python frames —
``MultiAdjacencyView.__getitem__``, ``AdjacencyView.__contains__``,
``AdjacencyView._atlas`` and the capture lambda — against ONE on simple Graph,
whose row is a native view with a C-level contains slot. Two of the four were
pure indirection: ``_atlas()`` is ``return self._atlas_getter()`` and, for a row
captured by br-r37-c1-znpkv, that getter is a closure over a fixed object.

Holding the row directly removes both frames. The risk is not that membership
gives a wrong answer today — it is that the collapse silently un-collapses, or
that the captured row outlives something it should not, so this file pins both
the behaviour AND the structure.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        if graph.is_multigraph():
            graph.add_edge("a", "b")
        made.append(graph)
    return made


def _outcome(fn):
    try:
        return ("value", fn())
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "probe", ["b", "c", "zz", "", 0, 7, 2.5, True, (1, 2), frozenset({1})],
    ids=lambda p: repr(p)[:12],
)
def test_membership_still_matches_networkx(cls_name, probe):
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda: probe in gfx.adj["a"]) == _outcome(
        lambda: probe in gnx.adj["a"]
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("bad", [["x"], {"x": 1}, {"x"}], ids=["list", "dict", "set"])
def test_unhashable_still_raises_type_error(cls_name, bad):
    """The explicit hash is the TypeError contract and must not be optimised out.

    The native MultiAtlasView/MultiDiAtlasView answer False for an unhashable
    key rather than raising — the same gap br-r37-c1-espyz closed on the simple
    AtlasView — so removing the hash while reading a captured row would silently
    turn a TypeError into False.
    """
    gnx, gfx = _pair(cls_name)
    got = _outcome(lambda: bad in gfx.adj["a"])
    assert got == _outcome(lambda: bad in gnx.adj["a"])
    assert got[1] == "TypeError"


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_frames_stay_collapsed(cls_name):
    """Structural: a warm multigraph membership test must not call ``_atlas``.

    This is the whole lever. If someone reintroduces the indirection the answer
    stays correct and only the cost comes back, which is exactly the kind of
    regression no behavioural test would catch.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edges_from([("a", "b"), ("a", "c")])
    row = graph.adj["a"]
    assert row._fnx_captured_row is not None, "the row was not captured"

    calls = []
    original = fnx.AdjacencyView._atlas
    fnx.AdjacencyView._atlas = lambda self: (calls.append(1), original(self))[1]
    try:
        for _ in range(5):
            assert ("b" in graph.adj["a"]) is True
            assert ("zz" in graph.adj["a"]) is False
    finally:
        fnx.AdjacencyView._atlas = original
    assert calls == [], f"_atlas was called {len(calls)} times on the warm path"


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_classes_do_not_reach_this_path_at_all(cls_name):
    """Why Graph and DiGraph are controls, asserted rather than assumed.

    Their rows are native views whose ``__contains__`` is a C slot, so the
    Python ``AdjacencyView.__contains__`` is never entered. Any movement in
    their measured ratios across this change is host drift by construction.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edges_from([("a", "b"), ("a", "c")])
    calls = []
    original = fnx.AdjacencyView.__contains__
    fnx.AdjacencyView.__contains__ = lambda self, n: (
        calls.append(1),
        original(self, n),
    )[1]
    try:
        for _ in range(5):
            "b" in graph.adj["a"]
    finally:
        fnx.AdjacencyView.__contains__ = original
    assert calls == [], "a simple class reached the Python row __contains__"


@pytest.mark.parametrize("cls_name", MULTI)
def test_captured_row_stays_live_across_edge_churn(cls_name):
    """Capturing the ROW must not freeze its CONTENTS."""
    gnx, gfx = _pair(cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    for graph in (gnx, gfx):
        graph.add_edge("a", "d")
    assert ("d" in rfx) == ("d" in rnx) is True
    for graph in (gnx, gfx):
        graph.remove_edge("a", "c")
    assert ("c" in rfx) == ("c" in rnx) is False


@pytest.mark.parametrize("cls_name", MULTI)
def test_captured_row_is_dropped_when_the_node_set_moves(cls_name):
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.adj["a"]
        graph.remove_node("a")
    assert _outcome(lambda: gfx.adj["a"]) == _outcome(lambda: gnx.adj["a"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_row_detached_by_clear_answers_from_its_snapshot(cls_name):
    """br-r37-c1-s5pxs interacts with this directly.

    The captured row is consulted BEFORE the getter, so a detach that rebound
    only the getter would leave membership reading the live row it was meant to
    cut loose from — the row would report empty while iteration reported the
    stale contents.
    """
    gnx, gfx = _pair(cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    gnx.clear()
    gfx.clear()
    assert sorted(rfx) == sorted(rnx)
    for probe in ("b", "c", "zz"):
        assert (probe in rfx) == (probe in rnx), probe
    assert len(rfx) == len(rnx)


@pytest.mark.parametrize("cls_name", MULTI)
def test_membership_agrees_with_iteration_and_len(cls_name):
    gnx, gfx = _pair(cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    assert sorted(rfx) == sorted(rnx)
    assert len(rfx) == len(rnx)
    for neighbor in rnx:
        assert neighbor in rfx
