"""br-r37-c1-2r06n: the degree views must read ASSIGNED private storage.

networkx's ``DiDegreeView`` sets ``self._nodes = self._succ`` and reads
``self._succ[n]`` / ``self._pred[n]``, so the assigned mapping is the authority
for both the value and for whether a single argument counts as a node. fnx used
the native Rust counters, which cannot see an assigned ``_succ``/``_pred``, and
asked ``nbunch in self._graph`` -- the node view -- for membership.

That produced a RETURN-TYPE divergence, which is worse than a wrong number:
``G.out_degree(n)`` handed back a whole DegreeView where networkx returns an int,
so a caller doing arithmetic on the result got a TypeError rather than a wrong
answer. The subscript form raised KeyError where networkx returns an int, because
the native counter answered 0 for a node it did not know and the membership probe
then rejected it.

NOTE THE ASYMMETRY IS NETWORKX'S. Because ``_nodes`` is ``_succ`` for the
in-degree view too, ``in_degree`` and ``out_degree`` legitimately disagree under
an assigned ``_succ``. These tests assert against live networkx precisely so that
the quirk is matched rather than smoothed away.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def outcome(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_out_degree_call_returns_an_int_for_a_node_only_in_assigned_succ(cls):
    expected = build(nx, cls, "_succ", SUCC).out_degree("ZZ")
    got = build(fnx, cls, "_succ", SUCC).out_degree("ZZ")
    assert isinstance(expected, int), "nx contract moved; update this file"
    assert isinstance(got, int), "returned a view where nx returns an int"
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_out_degree_subscript_for_a_node_only_in_assigned_succ(cls):
    expected = build(nx, cls, "_succ", SUCC).out_degree["ZZ"]
    got = build(fnx, cls, "_succ", SUCC).out_degree["ZZ"]
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_out_degree_value_uses_the_assigned_mapping_for_ordinary_nodes(cls):
    """'a' exists in both stores, but the assigned mapping is what nx counts."""
    expected = build(nx, cls, "_succ", SUCC).out_degree("a")
    got = build(fnx, cls, "_succ", SUCC).out_degree("a")
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_a_node_only_in_assigned_node_is_not_an_int(cls):
    """nx's authority is `_succ`, so `_node` alone does NOT make it a scalar."""
    expected = build(nx, cls, "_node", NODE).out_degree("ZZ")
    got = build(fnx, cls, "_node", NODE).out_degree("ZZ")
    assert not isinstance(expected, int), "nx contract moved; update this file"
    assert not isinstance(got, int), "returned an int where nx returns a view"


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_in_degree_keeps_networkx_own_asymmetry(cls):
    """Matched, not smoothed: nx's in-degree view also keys membership on _succ."""
    expected = build(nx, cls, "_pred", {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}})
    got = build(fnx, cls, "_pred", {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}})
    assert isinstance(expected.in_degree("ZZ"), int) == isinstance(
        got.in_degree("ZZ"), int
    )


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_a_view_cached_before_the_assignment_is_not_reused_stale(cls):
    """The private check is resolved once per view, so assignment must drop it.

    Touching `out_degree` first caches a view built for an ordinary graph,
    holding the native counter. Without invalidation that view survives the
    assignment and keeps answering from the Rust store.
    """
    gfx = getattr(fnx, cls)()
    gfx.add_edge("a", "b")
    gfx.out_degree  # noqa: B018 - cache a view built before the assignment
    gfx._succ = dict(SUCC)

    gnx = getattr(nx, cls)()
    gnx.add_edge("a", "b")
    gnx.out_degree  # noqa: B018
    gnx._succ = dict(SUCC)

    assert gfx.out_degree("ZZ") == gnx.out_degree("ZZ")


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, no behaviour change, including absence."""
    gnx = getattr(nx, cls)()
    gnx.add_edge("a", "b")
    gnx.add_node("iso")
    gfx = getattr(fnx, cls)()
    gfx.add_edge("a", "b")
    gfx.add_node("iso")

    for n in ("a", "b", "iso"):
        assert gfx.out_degree(n) == gnx.out_degree(n)
        assert gfx.in_degree(n) == gnx.in_degree(n)
        assert gfx.out_degree[n] == gnx.out_degree[n]
    assert dict(gfx.out_degree) == dict(gnx.out_degree)
    assert outcome(lambda: gfx.out_degree["nope"]) == outcome(
        lambda: gnx.out_degree["nope"]
    )


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_weighted_degree_still_matches_without_private_storage(cls):
    """The weighted native branch is gated by the same flag; guard it too."""
    gnx = getattr(nx, cls)()
    gnx.add_edge("a", "b", weight=3)
    gfx = getattr(fnx, cls)()
    gfx.add_edge("a", "b", weight=3)
    for n in ("a", "b"):
        assert gfx.out_degree(n, weight="weight") == gnx.out_degree(n, weight="weight")
        assert gfx.in_degree(n, weight="weight") == gnx.in_degree(n, weight="weight")
