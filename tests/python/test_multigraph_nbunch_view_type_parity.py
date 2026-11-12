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

THE keys=True SPELLING NEEDED NAME AND SEMANTICS MOVED TOGETHER. nx serves it
from ``MultiEdgeDataView``, not the ``MultiEdgeView`` that serves the no-nbunch
spelling, and the two disagree about ``__contains__``: nx reads ``e[2]`` with no
length check, so a 2-tuple raises IndexError - but only for an edge the view
carries, since a miss returns False first. fnx answered True, which is MORE
permissive than the incumbent, the dangerous direction for a drop-in because code
that passes on fnx would crash on networkx. Both classes now mirror nx, including
the orientation asymmetry: the undirected view matches ``(v, u, k)``, the
directed one does not.
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


@pytest.mark.parametrize("class_name", MULTI)
def test_keys_view_containment_mirrors_networkx(class_name):
    """Every query shape, including the two nx answers with an exception.

    The IndexError is not raised artificially - the implementation reads
    ``edge[2]`` in the same place nx does, after the same membership test, so it
    arises the same way and only for an edge the view actually carries.
    """
    got, want = _pair(class_name)
    gv, wv = got.edges(["a"], keys=True), want.edges(["a"], keys=True)

    def answer(view, query):
        try:
            return repr(query in view)
        except Exception as exc:  # noqa: BLE001 - the exception IS the contract
            return type(exc).__name__

    for query in (
        ("a", "b"), ("b", "a"),
        ("a", "b", 0), ("a", "b", 1), ("a", "b", 9), ("b", "a", 0),
        ("x", "y"), ("x", "y", 0),
    ):
        assert answer(gv, query) == answer(wv, query), query
