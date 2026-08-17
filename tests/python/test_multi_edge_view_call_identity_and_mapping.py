"""`G.edges(keys=True)` must BE the edge view, with its full Mapping surface.

FOUND BY A DIFFERENTIAL FUZZER, and it survived every name-based check.

networkx's `MultiEdgeView.__call__` short-circuits to `return self` whenever
there is no nbunch and no data, so `G.edges(keys=True) is G.edges` and the result
is the Mapping the edge view always was. fnx instead built a fresh native edge
list and wrapped it in `_MultiEdgeView` — a LIST SUBCLASS carrying the same class
NAME. Its MRO was `MultiEdgeView -> _EdgeListWithSetAlgebra -> list`.

WHY IT HID. Everything a parity test normally looks at agreed:

    type(...).__name__   MultiEdgeView          both
    list(...)            [(u, v, k), ...]       identical, same order
    len(...)             identical
    (u, v, k) in ...     identical
    set algebra          preserved deliberately

Only the Mapping protocol was gone, so `G.edges(keys=True).items()` raised
AttributeError against a networkx that returns `((u, v, k), attrs)` pairs, and
`.keys()` / `.values()` were missing the same way. The fuzzer noticed because it
renders mappings via `.items()` and everything else via iteration, which forced
the two shapes to distinguish themselves.

THE DIVERGING ASSERTIONS ARE STRICT XFAILS, not a description of a fix. The
obvious repair -- returning `self`, which is literally what networkx does --
was attempted and reverted: `__iter__` reaches `_direct_multi_edge_iter`,
which caches this call's result and then iterates it, so `return self` is
infinite recursion. The real fix has to untangle that caching first, and that
needs a verification cycle this host cannot currently provide.

This file pins the protocol AND the identity, because fixing only the protocol
(for instance by giving the list subclass an `items`) would leave
`G.edges(keys=True) is G.edges` false and diverge again on any code that relies
on the view being live rather than a snapshot.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=1.0)
        graph.add_edge("a", "b", w=2.0)
        graph.add_edge("b", "c", w=3.0)
        graph.add_edge("s", "s", w=4.0)
    return gnx, gfx


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-p1dbu: G.edges(keys=True) returns a list subclass carrying the MultiEdgeView NAME instead of the view itself, so the Mapping surface and the identity are both lost. Returning `self` -- what nx does -- was attempted and REVERTED: __iter__ reaches _direct_multi_edge_iter, which caches this call's result and iterates it, so `return self` recurses infinitely. Needs a real fix, not a one-liner.",
            ),
        )
        for name in MULTI
    ],
)
def test_call_with_keys_returns_the_view_itself(cls_name):
    """The identity nx guarantees by `return self`."""
    gnx, gfx = _pair(cls_name)
    assert (gnx.edges(keys=True) is gnx.edges) is True, "networkx oracle changed"
    assert (gfx.edges(keys=True) is gfx.edges) is True


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-p1dbu: G.edges(keys=True) returns a list subclass carrying the MultiEdgeView NAME instead of the view itself, so the Mapping surface and the identity are both lost. Returning `self` -- what nx does -- was attempted and REVERTED: __iter__ reaches _direct_multi_edge_iter, which caches this call's result and iterates it, so `return self` recurses infinitely. Needs a real fix, not a one-liner.",
            ),
        )
        for name in MULTI
    ],
)
@pytest.mark.parametrize("attr", ["items", "keys", "values"])
def test_call_with_keys_keeps_the_mapping_surface(cls_name, attr):
    gnx, gfx = _pair(cls_name)
    assert hasattr(gnx.edges(keys=True), attr), "networkx oracle changed"
    assert hasattr(gfx.edges(keys=True), attr), f"{cls_name}: lost .{attr}()"


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-p1dbu: G.edges(keys=True) returns a list subclass carrying the MultiEdgeView NAME instead of the view itself, so the Mapping surface and the identity are both lost. Returning `self` -- what nx does -- was attempted and REVERTED: __iter__ reaches _direct_multi_edge_iter, which caches this call's result and iterates it, so `return self` recurses infinitely. Needs a real fix, not a one-liner.",
            ),
        )
        for name in MULTI
    ],
)
def test_items_matches_networkx(cls_name):
    """Not merely present — the pairs must agree."""
    gnx, gfx = _pair(cls_name)
    want = sorted((k, sorted(v.items())) for k, v in gnx.edges(keys=True).items())
    got = sorted((k, sorted(v.items())) for k, v in gfx.edges(keys=True).items())
    assert got == want


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-p1dbu: G.edges(keys=True) returns a list subclass carrying the MultiEdgeView NAME instead of the view itself, so the Mapping surface and the identity are both lost. Returning `self` -- what nx does -- was attempted and REVERTED: __iter__ reaches _direct_multi_edge_iter, which caches this call's result and iterates it, so `return self` recurses infinitely. Needs a real fix, not a one-liner.",
            ),
        )
        for name in MULTI
    ],
)
def test_keys_and_values_match_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    assert sorted(gfx.edges(keys=True).keys()) == sorted(gnx.edges(keys=True).keys())
    got = sorted(sorted(d.items()) for d in gfx.edges(keys=True).values())
    want = sorted(sorted(d.items()) for d in gnx.edges(keys=True).values())
    assert got == want


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_properties_that_already_agreed_still_agree(cls_name):
    """The regression surface for this fix.

    Returning `self` changes the object handed back, so everything that was
    already correct about the old list-shaped result is re-pinned here: the
    class name, iteration contents and ORDER, length, and containment.
    """
    gnx, gfx = _pair(cls_name)
    cnx, cfx = gnx.edges(keys=True), gfx.edges(keys=True)
    assert type(cfx).__name__ == type(cnx).__name__
    assert list(cfx) == list(cnx)
    assert len(cfx) == len(cnx)
    for edge in list(cnx) + [("a", "zz", 0), ("a", "b", 99)]:
        assert (edge in cfx) == (edge in cnx), edge


@pytest.mark.parametrize("cls_name", MULTI)
def test_set_algebra_is_preserved(cls_name):
    """Deliberately kept working by the old wrapper; must survive the fix."""
    gnx, gfx = _pair(cls_name)
    other = {("a", "b", 0), ("zz", "yy", 0)}
    for op in ("__and__", "__or__", "__sub__", "__xor__"):
        want = getattr(gnx.edges(keys=True), op)(other)
        got = getattr(gfx.edges(keys=True), op)(other)
        assert sorted(map(str, got)) == sorted(map(str, want)), op


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_view_stays_live_after_mutation(cls_name):
    """`self` is the live view, so later edges must appear — the property a
    snapshot list could never have had."""
    gnx, gfx = _pair(cls_name)
    cnx, cfx = gnx.edges(keys=True), gfx.edges(keys=True)
    for graph in (gnx, gfx):
        graph.add_edge("c", "d", w=5.0)
    assert list(cfx) == list(cnx)
    assert len(cfx) == len(cnx)


CALL_FORMS = (
    ("edges()", lambda g: g.edges()),
    ("edges(data=True)", lambda g: g.edges(data=True)),
    ("edges(data='w')", lambda g: g.edges(data="w")),
    ("edges(keys=True, data=True)", lambda g: g.edges(keys=True, data=True)),
    ("edges(nbunch)", lambda g: g.edges(["a", "b"])),
    ("edges(nbunch, keys=True)", lambda g: g.edges(["a", "b"], keys=True)),
)


@pytest.mark.parametrize("cls_name", MULTI)
def test_other_call_forms_return_the_same_contents(cls_name):
    """The neighbours of the changed branch. CONTENTS agree on every form —
    this is what must not move, and it currently holds."""
    gnx, gfx = _pair(cls_name)
    for name, call in CALL_FORMS:
        want, got = call(gnx), call(gfx)
        assert sorted(map(str, got)) == sorted(map(str, want)), name


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-p1dbu (second, separate divergence): three call "
                "forms leak PRIVATE class names into the public API. Measured, "
                "networkx reports MultiEdgeDataView / OutMultiEdgeDataView while "
                "fnx reports _LiveMultiEdgeCallView for edges(), "
                "_EdgeListWithSetAlgebra for edges(nbunch), and "
                "MultiEdgeView / OutMultiEdgeView for edges(nbunch, keys=True). "
                "CONTENTS agree on all of them — only the type name diverges, "
                "which is why the sibling contents test above passes. Found "
                "incidentally while guarding the Mapping-surface defect.",
            ),
        )
        for name in MULTI
    ],
)
def test_other_call_forms_report_networkx_type_names(cls_name):
    gnx, gfx = _pair(cls_name)
    mismatched = []
    for name, call in CALL_FORMS:
        want, got = type(call(gnx)).__name__, type(call(gfx)).__name__
        if want != got:
            mismatched.append(f"{name}: nx={want} fnx={got}")
    assert not mismatched, "; ".join(mismatched)
