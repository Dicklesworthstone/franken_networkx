"""br-r37-c1-ppiei sibling: has_successor / has_predecessor must ask the MAPPING.

networkx is `u in self._succ and v in self._succ[u]`, so the assigned mapping
decides whether `u` exists. fnx asked `u in self` -- the node view -- and so
returned **False** where networkx returns **True** for a node carried only by an
assigned `_succ` / `_pred`.

This is the silent form of the defect fixed for `predecessors` in the parent
bead: no exception, just a wrong boolean. It was found by taking that bead's own
lesson -- check the sibling branches -- and sweeping the neighbouring directed
accessors, which is the only reason it surfaced at all.

Every case is asserted against live networkx rather than a written-down
expectation, so the file keeps testing the contract if nx changes it.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
PRED = {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_has_successor_sees_a_node_only_in_assigned_succ(cls):
    expected = build(nx, cls, "_succ", SUCC).has_successor("ZZ", "b")
    got = build(fnx, cls, "_succ", SUCC).has_successor("ZZ", "b")
    assert expected is True, "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_has_predecessor_sees_a_node_only_in_assigned_pred(cls):
    expected = build(nx, cls, "_pred", PRED).has_predecessor("ZZ", "a")
    got = build(fnx, cls, "_pred", PRED).has_predecessor("ZZ", "a")
    assert expected is True, "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_absent_endpoints_are_still_false_under_an_assignment(cls):
    """The fix must not turn the accessor into a rubber stamp."""
    for u, v in (("ZZ", "nope"), ("nope", "b"), ("nope", "nope")):
        expected = build(nx, cls, "_succ", SUCC).has_successor(u, v)
        got = build(fnx, cls, "_succ", SUCC).has_successor(u, v)
        assert expected is False
        assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, no behaviour change."""
    for u, v in (("a", "b"), ("b", "a"), ("a", "a"), ("nope", "b"), ("a", "nope")):
        gnx = getattr(nx, cls)()
        gnx.add_edge("a", "b")
        gfx = getattr(fnx, cls)()
        gfx.add_edge("a", "b")
        assert gfx.has_successor(u, v) == gnx.has_successor(u, v)
        assert gfx.has_predecessor(u, v) == gnx.has_predecessor(u, v)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_unhashable_endpoint_matches_networkx(cls):
    """Whatever nx does with an unhashable key, fnx must do the same."""
    for assignment in (None, ("_succ", SUCC)):
        def call(mod):
            g = getattr(mod, cls)()
            g.add_edge("a", "b")
            if assignment is not None:
                setattr(g, assignment[0], dict(assignment[1]))
            try:
                return ("ok", g.has_successor(["unhashable"], "b"))
            except Exception as exc:  # noqa: BLE001
                return (type(exc).__name__,)

        assert call(fnx) == call(nx)
