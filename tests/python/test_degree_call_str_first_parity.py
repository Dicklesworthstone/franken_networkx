"""br-r37-c1-5n6mn — the exact-str test runs before the nbunch-is-None test.

`G.degree(n)` sat at 0.836x (Graph) and 0.766x (DiGraph). Decomposing the call
showed where the gap is NOT: the accessors are identical (networkx 0.0456us, fnx
0.0457us) and so are the subscripts (networkx 0.1191us, fnx 0.1192us, ratio
0.9990). The whole gap is the view's ``__call__`` wrapper — networkx 0.0896us
against fnx 0.1489us.

A `str` is never None, so testing for an exact `str` before testing
``nbunch is None`` cannot change either answer. It removes one comparison from
every ``G.degree("n")`` and adds one to the argument-less ``G.degree()``, which
builds a view and is not called in a loop. Paired A/B of the two orderings on the
same objects: 0.1515us -> 0.1450us, 1.0408x CI [1.0396, 1.0479].

A Python reroute was tried first and REFUTED: computing the degree as
``len(succ[n]) + len(pred[n])`` costs 0.5250us against the native 0.1207us, so
the native subscript is already the best available and the wrapper was the only
thing left to cut.

What needs locking is the equivalence claim across every argument shape, since
the reorder changes which branch a value meets first.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for i in range(30):
        gnx.add_edge(f"n{i}", f"n{(i * 7 + 3) % 30}", weight=2.0)
        gfx.add_edge(f"n{i}", f"n{(i * 7 + 3) % 30}", weight=2.0)
    gnx.add_node("iso")
    gfx.add_node("iso")
    return gnx, gfx


def _norm(value):
    return value if isinstance(value, (int, float)) else sorted(value)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize(
    "arg",
    ["n5", "iso", "zz", ["n1", "n2"], ("n1", "n2"), {"n1", "n2"}, [], ["n1", "zz"]],
    ids=["str", "isolated", "absent-str", "list", "tuple", "set", "empty", "mixed"],
)
def test_degree_matches_networkx_for_every_argument_shape(cls_name, weight, arg):
    """The equivalence the reorder rests on, across shapes AND weightedness."""
    gnx, gfx = _pair(cls_name)
    results = []
    for graph in (gnx, gfx):
        try:
            results.append(("ok", _norm(graph.degree(arg, weight=weight))))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__, exc.args))
    assert results[1] == results[0], (cls_name, weight, arg)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight", [None, "weight"])
def test_the_argument_less_call_still_returns_a_view(cls_name, weight):
    """The branch that now pays one extra comparison must be unchanged.

    `G.degree()` is the case the reorder makes marginally dearer, so its result
    is asserted explicitly rather than assumed.
    """
    gnx, gfx = _pair(cls_name)
    want = gnx.degree() if weight is None else gnx.degree(weight=weight)
    got = gfx.degree() if weight is None else gfx.degree(weight=weight)
    assert sorted(got) == sorted(want)
    assert len(got) == len(want) == len(gnx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_str_subclass_does_not_take_the_exact_str_branch(cls_name):
    """br-r37-c1-ey6ob's contract: the fast branch is EXACT `str` only.

    The native lookup resolves a key by its characters and never calls
    __hash__, so a str SUBCLASS must fall through to the sequence path and be
    walked character by character, exactly as networkx does.
    """

    class StrSub(str):
        pass

    gnx, gfx = _pair(cls_name)
    want = _norm(gnx.degree(StrSub("n5")))
    got = _norm(gfx.degree(StrSub("n5")))
    assert got == want


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_unhashable_argument_matches_networkx(cls_name):
    """The reorder must not change which error a bad argument produces."""
    gnx, gfx = _pair(cls_name)
    results = []
    for graph in (gnx, gfx):
        try:
            results.append(("ok", _norm(graph.degree(["n1", ["unhashable"]]))))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__,))
    assert results[1] == results[0]
