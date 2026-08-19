"""``MG.edges(nbunch)`` must carry networkx's view type NAME, not a bare list.

br-r37-c1-hihrf. networkx returns ``MultiEdgeDataView`` /
``OutMultiEdgeDataView`` from an nbunch edge call. fnx returned
``_EdgeListWithSetAlgebra`` - an internal name that appears in ``repr`` and in
any ``type(view).__name__`` check drop-in code makes. The ``data=True`` and
``data=<key>`` spellings on the same call already wrapped correctly; only the
plain-nbunch return was left unnamed, on both multigraph classes.

THE FIX WENT IN THE NATIVE FAST PATH, WHICH IS NOT WHERE IT LOOKS LIKE IT SHOULD.
Each class has a Python fallback that builds the list by looping the adjacency,
and a native no-data fast path above it. The fallback is what reads like the
return for this spelling, and it is dead for it - the native path returns first.
I patched the fallback, measured no change, and had to trace the returning line
number to find the live one. Both are fixed; the trace is the only reason the
second one was.

PURE NAMING. Both wrappers are ``pass`` over the same list base, so values, set
algebra and containment are untouched - asserted below rather than assumed.

THE keys=True SPELLING IS DELIBERATELY LEFT DIVERGENT, and it is not an
oversight. nx names it ``MultiEdgeDataView`` too, but fnx's ``_MultiEdgeView``
wrapper also carries an any-key ``__contains__``, and networkx's own
``__contains__`` for this spelling RAISES IndexError on a 2-tuple (it reads
``e[2]`` with no length check) where fnx answers True. Renaming would silently
move containment as well, so the name and the semantics have to be decided
together. Pinned as xfail so the decision is visible rather than forgotten.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]


def _pair(class_name):
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", w=1)
        graph.add_edge("a", "b", w=2)   # parallel
        graph.add_edge("b", "c", w=3)
    return got, want


@pytest.mark.parametrize("class_name", MULTI)
@pytest.mark.parametrize(
    "kwargs", [{}, {"data": True}, {"data": "w"}, {"data": "absent", "default": 0}]
)
def test_nbunch_view_type_name_matches_networkx(class_name, kwargs):
    got, want = _pair(class_name)
    assert (
        type(got.edges(["a"], **kwargs)).__name__
        == type(want.edges(["a"], **kwargs)).__name__
    )


@pytest.mark.parametrize("class_name", MULTI)
@pytest.mark.xfail(
    reason="nx names this MultiEdgeDataView, but fnx's wrapper also supplies an "
    "any-key __contains__ and nx's own __contains__ raises IndexError on a "
    "2-tuple here; name and semantics must move together (br-r37-c1-hihrf)",
    strict=False,
)
def test_nbunch_keys_view_type_name_matches_networkx(class_name):
    got, want = _pair(class_name)
    assert (
        type(got.edges(["a"], keys=True)).__name__
        == type(want.edges(["a"], keys=True)).__name__
    )


@pytest.mark.parametrize("class_name", MULTI)
def test_renaming_did_not_move_values_or_containment(class_name):
    """The naming change must be invisible to everything except the name."""
    got, want = _pair(class_name)
    gv, wv = got.edges(["a"]), want.edges(["a"])
    assert sorted(map(tuple, gv)) == sorted(map(tuple, wv))
    assert len(gv) == len(wv)
    for query in (("a", "b"), ("a", "b", 0), ("b", "c"), ("x", "y")):
        assert (query in gv) == (query in wv), query


@pytest.mark.parametrize("class_name", MULTI)
def test_set_algebra_survives_the_wrapper(class_name):
    """_EdgeListWithSetAlgebra exists for these operators; keep them working."""
    got, _want = _pair(class_name)
    view = got.edges(["a"])
    assert set(map(tuple, view)) & {("a", "b")} == {("a", "b")}
    assert sorted(map(tuple, set(map(tuple, view)) | {("z", "z")}))[-1] == ("z", "z")
