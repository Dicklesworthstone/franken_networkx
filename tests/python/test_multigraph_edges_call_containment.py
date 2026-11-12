"""br-r37-c1-rbu5n — `MG.edges()` yields 2-tuples, so only a 2-tuple is IN it.

`MG.edges()` and `MDG.edges()` yield 2-tuples. Their `__contains__` ignored
everything past index 1, so any 3-tuple whose first two elements named an edge
answered True — including one whose key does not exist:

    M.add_edge('a','b'); M.add_edge('a','b')
    ('a','b',9) in M.edges()    networkx False,  fnx True

A WRONG TRUE, not a looser contract. networkx's rule is not "is there an edge
between these two nodes" but
`any(e == self._report(u, v, k, dd) for k, dd in kdict.items())`, and `_report`
for this view is `(u, v)` — so a 3-tuple can never equal a yielded item. The
`keys=True` view is a DIFFERENT view with a different `_report`, which is why
`('a','b',0) in M.edges(keys=True)` is correctly True and is carried below as the
control that says this is a per-view rule rather than a global one.

SECOND DIVERGENCE, OPPOSITE DIRECTION, same six lines. networkx opens with
`u, v = e[:2]` and lets both failures out — TypeError for something unsliceable,
ValueError for a sequence shorter than two — where fnx guarded with
`isinstance(edge, tuple) and len(edge) >= 2, else False` and answered False. Same
class as br-r37-c1-q32e6 and br-r37-c1-c99d9, and the same fix: spell it the way
networkx does rather than guard around it.

NOTHING HERE WRITES DOWN AN EXPECTED ANSWER. Every case runs the same candidate
against both libraries and compares the value or the exception type, so the file
stays right if networkx's own rule moves.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]

# Real keys are 0 and 1 on ('a','b') and 'x' on ('c','d'); 9 and 'zz' are not.
CANDIDATES = {
    "2-tuple present": ("a", "b"),
    "2-tuple reversed": ("b", "a"),
    "2-tuple other edge": ("c", "d"),
    "2-tuple absent": ("q", "r"),
    "3-tuple real key": ("a", "b", 0),
    "3-tuple second key": ("a", "b", 1),
    "3-tuple ABSENT key": ("a", "b", 9),
    "3-tuple str key": ("c", "d", "x"),
    "3-tuple wrong str key": ("c", "d", "zz"),
    "3-tuple absent edge": ("q", "r", 0),
    "4-tuple": ("a", "b", 0, {}),
    "list": ["a", "b"],
    "list of three": ["a", "b", 0],
    "str": "ab",
    "str of three": "abc",
    "bytes": b"ab",
    "set": {"a", "b"},
    "int": 42,
    "None": None,
    "empty tuple": (),
    "1-tuple": ("a",),
}


def _graph(lib, cls_name):
    m = getattr(lib, cls_name)()
    m.add_edge("a", "b")
    m.add_edge("a", "b")
    m.add_edge("c", "d", key="x")
    return m


def _outcome(view, candidate):
    try:
        return ("ok", candidate in view)
    except Exception as exc:  # noqa: BLE001
        return ("exc", type(exc).__name__)


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("label", sorted(CANDIDATES))
def test_edges_call_containment_matches_networkx(cls_name, label):
    """THE SWEEP. 16 cells were wrong-TRUE and 8 swallowed an error."""
    candidate = CANDIDATES[label]
    want = _outcome(_graph(nx, cls_name).edges(), candidate)
    got = _outcome(_graph(fnx, cls_name).edges(), candidate)
    assert got == want, f"{cls_name} {label}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_a_key_that_does_not_exist_is_not_in_the_two_tuple_view(cls_name):
    """The sharpest cell, on its own and asserted without an oracle.

    ('a','b',9) names a key the graph does not have. Whatever networkx does,
    answering True here is wrong on its own terms — the view has no such item to
    match — so this one does not defer to the oracle.
    """
    view = _graph(fnx, cls_name).edges()
    assert ("a", "b", 9) not in view
    assert ("c", "d", "zz") not in view
    assert ("a", "b") in view, "the 2-tuple that IS yielded must still be in"


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("label", sorted(CANDIDATES))
def test_the_keys_view_keeps_its_own_rule(cls_name, label):
    """The CONTROL. `keys=True` is a different view and must NOT have moved.

    Its `_report` is `(u, v, k)`, so a 3-tuple with a real key IS in it — the
    opposite answer to the view above for the same candidate, which is exactly
    what says the rule is per-view.
    """
    candidate = CANDIDATES[label]
    want = _outcome(_graph(nx, cls_name).edges(keys=True), candidate)
    got = _outcome(_graph(fnx, cls_name).edges(keys=True), candidate)
    assert got == want, f"{cls_name} {label} (keys=True)"


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_two_views_disagree_with_each_other_as_networkx_does(cls_name):
    """Stated directly, because it looks like a bug until you know the rule."""
    gnx, gfx = _graph(nx, cls_name), _graph(fnx, cls_name)
    for graph in (gnx, gfx):
        assert ("a", "b", 0) not in graph.edges()
        assert ("a", "b", 0) in graph.edges(keys=True)


@pytest.mark.parametrize("cls_name", MULTI)
def test_containment_tracks_mutations(cls_name):
    """The view is live, so the answer must move with the graph."""
    gnx, gfx = _graph(nx, cls_name), _graph(fnx, cls_name)
    vnx, vfx = gnx.edges(), gfx.edges()
    assert (("e", "f") in vfx) == (("e", "f") in vnx) is False
    for graph in (gnx, gfx):
        graph.add_edge("e", "f")
    assert (("e", "f") in vfx) == (("e", "f") in vnx) is True
    assert (("e", "f", 0) in vfx) == (("e", "f", 0) in vnx) is False
    for graph in (gnx, gfx):
        graph.remove_edge("e", "f")
    assert (("e", "f") in vfx) == (("e", "f") in vnx) is False
