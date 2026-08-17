"""br-r37-c1-s8dj1 — the KEYED has_edge index path must agree with the string path.

`PyMultiGraph::has_edge` had an O(1) route only while `key` was `None`: both fast
paths were gated on `key.is_none()`. Measured on the same function, the 2-arg
form is FLAT in node key length (181.2 ns at K=2, 175.6 ns at K=2000) while the
3-arg form grew 3.6x (360.5 ns to 1303.2 ns). That slope is the whole of
`(u, v) in G.edges` — the worst cell on the surface at 0.1322x against networkx —
because the shim's `_MultiGraphEdgeView.__contains__` routes here with key 0.

The new path resolves both endpoints to POSITIONS through CPython's cached `str`
hash and reaches the edge by `edge_attrs_by_indices`, skipping both canonicals.

WHAT THIS GUARDS, in order of how badly each would fail silently:

  1. THE TWO INDEX SPACES. Positions are converted to SLOTS inside
     `edge_attrs_by_indices`. Handing a position straight to the slot-keyed store
     reports a real edge as ABSENT after any node removal — a wrong answer on an
     ordinary read. The removal cases below exist for this and nothing else.
  2. THE GATE. The path is taken only for exact `str` endpoints with an exact
     `int` key on a graph whose display keys are pristine. Remapped keys, string
     keys, float keys, bool keys, negative keys and non-string endpoints must all
     keep the previous behaviour exactly.
  3. KEY IDENTITY. A 2-element membership test means key ZERO, not "any key"
     (br-r37-c1-6fs77). An edge added with `key='x'` must NOT answer True for
     `('a','b')`, and the fast path must not weaken that into a pair-existence
     check.

Every assertion compares against live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
LONG = "z" * 2000


def _pair(cls_name):
    return getattr(nx, cls_name)(), getattr(fnx, cls_name)()


def _same_has_edge(gnx, gfx, u, v, key):
    want = gnx.has_edge(u, v, key) if key is not None else gnx.has_edge(u, v)
    got = gfx.has_edge(u, v, key) if key is not None else gfx.has_edge(u, v)
    return got == want, want, got


# ------------------------------------------------------------- the happy path


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("key_len", [2, len(LONG)])
def test_keyed_has_edge_matches_networkx(cls_name, key_len):
    u, v, w = ("u" * key_len, "v" * key_len, "w" * key_len)
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge(u, v, weight=1.0)
        g.add_edge(u, v, weight=2.0)
        g.add_edge(v, w, weight=3.0)
    for a, b in [(u, v), (v, u), (v, w), (u, w), (u, "absent")]:
        for key in (0, 1, 2, 7):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{cls_name} has_edge({a[:3]}..,{b[:3]}..,{key}) nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_edges_membership_matches_networkx(cls_name):
    """The caller this fix exists for."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("a", "b", weight=2.0)
        g.add_edge("b", "c", weight=3.0)
    for probe in [("a", "b"), ("b", "a"), ("a", "b", 0), ("a", "b", 1),
                  ("a", "b", 5), ("a", "zz"), ("zz", "a"), ("b", "c", 0)]:
        assert (probe in gfx.edges) == (probe in gnx.edges), probe


# -------------------------------------------------- the two index spaces (1)


@pytest.mark.parametrize("cls_name", MULTI)
def test_keyed_has_edge_after_node_removal_renumbers_positions(cls_name):
    """THE hazard. Removing an earlier node shifts every later POSITION down,
    while the store is keyed by SLOT. If the conversion is skipped, a real edge
    reports absent."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        for n in ("n0", "n1", "n2", "n3", "n4"):
            g.add_node(n)
        g.add_edge("n2", "n3", weight=1.0)
        g.add_edge("n2", "n3", weight=2.0)
        g.add_edge("n1", "n4", weight=3.0)
    assert _same_has_edge(gnx, gfx, "n2", "n3", 0)[0]

    for g in (gnx, gfx):
        g.remove_node("n0")
    for a, b in [("n2", "n3"), ("n1", "n4"), ("n3", "n2")]:
        for key in (0, 1):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"after removal {a},{b},{key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_keyed_has_edge_after_removal_and_readd(cls_name):
    """A re-add reuses a slot; positions move again."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("c", "d", weight=2.0)
        g.remove_node("a")
        g.add_edge("e", "d", weight=3.0)
        g.add_edge("a", "d", weight=4.0)
    for a, b in [("a", "d"), ("c", "d"), ("e", "d"), ("a", "b")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok, f"{a},{b}: nx={want} fnx={got}"


# --------------------------------------------------------------- the gate (2)


@pytest.mark.parametrize("cls_name", MULTI)
def test_non_integer_and_remapped_keys_keep_the_string_path(cls_name):
    """String, float and bool keys, and a graph with a REMAPPED display key,
    are all excluded from the fast path and must be unchanged."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", key="x", weight=1.0)
        g.add_edge("a", "b", key=5, weight=2.0)
        g.add_edge("c", "d", weight=3.0)
    for key in ("x", 5, 0, 1, 2.0, True, False, -1, "0"):
        for a, b in [("a", "b"), ("c", "d")]:
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{cls_name} key={key!r} on {a},{b}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_non_string_endpoints_keep_the_string_path(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge(1, 2, weight=1.0)
        g.add_edge(1, 2, weight=2.0)
        g.add_edge((3, 4), 5, weight=3.0)
    for a, b in [(1, 2), (2, 1), ((3, 4), 5), (1, 9)]:
        for key in (0, 1):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{a!r},{b!r},{key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_absent_endpoint_answers_false_without_raising(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
    for a, b in [("missing", "b"), ("a", "missing"), ("missing", "other")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok and got is False, f"{a},{b}: nx={want} fnx={got}"


# ------------------------------------------------------------ key identity (3)


@pytest.mark.parametrize("cls_name", MULTI)
def test_key_zero_is_not_any_key(cls_name):
    """br-r37-c1-6fs77: a 2-element membership test means key ZERO. An edge
    whose only key is 'x' must not answer True — the fast path must not decay
    into a pair-existence check."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", key="x", weight=1.0)
    assert (("a", "b") in gfx.edges) == (("a", "b") in gnx.edges) is False
    assert gfx.has_edge("a", "b", 0) == gnx.has_edge("a", "b", 0) is False
    assert gfx.has_edge("a", "b", "x") == gnx.has_edge("a", "b", "x") is True
    assert gfx.has_edge("a", "b") == gnx.has_edge("a", "b") is True


@pytest.mark.parametrize("cls_name", MULTI)
def test_removed_key_stops_answering_true(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("a", "b", weight=2.0)
    assert _same_has_edge(gnx, gfx, "a", "b", 1)[0]
    for g in (gnx, gfx):
        g.remove_edge("a", "b", 1)
    for key in (0, 1):
        ok, want, got = _same_has_edge(gnx, gfx, "a", "b", key)
        assert ok, f"after remove_edge key={key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_direction_is_preserved_on_the_directed_class(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("src", "dst", weight=1.0)
    for a, b in [("src", "dst"), ("dst", "src")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok, f"{a}->{b}: nx={want} fnx={got}"
    if cls_name == "MultiDiGraph":
        assert gnx.has_edge("dst", "src", 0) is False, "networkx oracle changed"
