"""Two view-surface divergences found by sweeping how views are CONSUMED.

A new axis. The earlier protocol sweep asked "does the attribute exist"; this
asks "does the object behave the same when a caller actually uses it" — dict(),
set(), sorted(), repr(), equality, re-iteration. 26 of 416 combinations diverged;
after discarding the ones that were downstream of already-filed beads
(br-r37-c1-p1dbu and br-r37-c1-dfivn), two independent defects remained.

------------------------------------------------------------------------------
br-r37-c1-ynpbt — Graph.adj[u] IS NOT EQUAL TO ITSELF
------------------------------------------------------------------------------

    g = fnx.Graph(); g.add_edge("a", "b", w=1.0)
    r = g.adj["a"]
    r == r                    -> False    networkx: True
    r == g.adj["a"]           -> False    networkx: True
    r == {"b": {"w": 1.0}}    -> True     networkx: True

`__eq__` handles a plain dict but not another view of its own type, so an object
compares unequal to ITSELF. Reflexivity is a language-level invariant — anything
that puts these in a set, dedupes them, or asserts `x == x` is silently wrong.

ONLY simple `Graph` diverges; DiGraph, MultiGraph and MultiDiGraph are all
correct. That is the tell: `Graph` is the class whose rows the shim routes to the
NATIVE `_fnx.AtlasView` (the `type(owner) is Graph` fast path in
`AdjacencyView.__getitem__`), so the native view's `__eq__` is the suspect and
the three Python-backed siblings are the control. They are pinned as passing
tests below.

------------------------------------------------------------------------------
br-r37-c1-ih59i — edge data views repr as a bare list
------------------------------------------------------------------------------

    DiGraph      edges(data=True)   nx OutEdgeDataView([...])       fnx [...]
    MultiGraph   edges(nbunch)      nx MultiEdgeDataView([...])     fnx [...]
    MultiDiGraph edges(data=True)   nx OutMultiEdgeDataView([...])  fnx [...]

These views are list subclasses that never override `__repr__`, so printing or
logging one shows bare list syntax. CONTENTS agree everywhere — this is repr
only, but it is user-visible on any `print()` of a view.

Sharper, and filed with it: `MultiDiGraph.edges()` reprs as `MultiEdgeDataView`,
the UNDIRECTED name, where networkx says `OutMultiEdgeDataView`. That is a wrong
class identity on a directed graph rather than a missing wrapper.

Neither is fixed here: both need a build to verify and the host is under a build
halt (disk at 73G against a 42G floor).
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
REPR_AFFECTED = ["DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=1.0)
        graph.add_edge("b", "c", w=2.0)
    return gnx, gfx


# --------------------------------------------------- br-r37-c1-ynpbt: equality


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-ynpbt: fnx's native AtlasView (simple Graph rows only) is "
    "not equal to itself — __eq__ handles a plain dict but not another view of "
    "its own type, breaking reflexivity. Needs a build to fix; halted.",
)
def test_simple_graph_adjacency_row_equals_itself():
    """Reflexivity. `x == x` must hold for any object."""
    _, gfx = _pair("Graph")
    row = gfx.adj["a"]
    assert (row == row) is True


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-ynpbt: two AtlasViews over the same row compare unequal on "
    "simple Graph. Needs a build to fix; halted.",
)
def test_simple_graph_adjacency_rows_of_the_same_node_are_equal():
    gnx, gfx = _pair("Graph")
    assert (gfx.adj["a"] == gfx.adj["a"]) == (gnx.adj["a"] == gnx.adj["a"])


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_the_other_three_classes_are_reflexive(cls_name):
    """THE CONTROL. These three are correct today, which is what localises the
    defect to the native view simple Graph uses. A fix must not disturb them."""
    gnx, gfx = _pair(cls_name)
    row_fx, row_nx = gfx.adj["a"], gnx.adj["a"]
    assert (row_fx == row_fx) is True
    assert (row_fx == row_fx) == (row_nx == row_nx)
    assert (gfx.adj["a"] == gfx.adj["a"]) == (gnx.adj["a"] == gnx.adj["a"])


@pytest.mark.parametrize("cls_name", ALL)
def test_rows_compare_equal_to_the_plain_dict_on_every_class(cls_name):
    """This half already works everywhere and must keep working — it is why the
    defect is easy to miss."""
    gnx, gfx = _pair(cls_name)
    as_dict = (
        {"b": {0: {"w": 1.0}}} if cls_name.startswith("Multi") else {"b": {"w": 1.0}}
    )
    assert (gfx.adj["a"] == as_dict) == (gnx.adj["a"] == as_dict)


# ------------------------------------------------------- br-r37-c1-ih59i: repr


@pytest.mark.parametrize(
    "cls_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-ih59i: edge data views are list subclasses that "
                "never override __repr__, so they print as a bare list where "
                "networkx prints ClassName([...]). Needs a build to verify a fix; "
                "halted.",
            ),
        )
        for name in REPR_AFFECTED
    ],
)
@pytest.mark.parametrize("form", ["data", "nbunch"])
def test_edge_data_view_repr_names_its_class(cls_name, form):
    gnx, gfx = _pair(cls_name)
    call = (
        (lambda g: g.edges(data=True))
        if form == "data"
        else (lambda g: g.edges(["a", "b"]))
    )
    want, got = repr(call(gnx)), repr(call(gfx))
    assert got.split("(")[0] == want.split("(")[0], f"nx={want[:60]} fnx={got[:60]}"


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-ih59i: MultiDiGraph.edges() reprs as MultiEdgeDataView — "
    "the UNDIRECTED class name — where networkx says OutMultiEdgeDataView. A "
    "wrong class identity on a directed graph, not merely a missing wrapper.",
)
def test_multidigraph_edges_call_reports_the_directed_class_name():
    gnx, gfx = _pair("MultiDiGraph")
    assert repr(gfx.edges()).split("(")[0] == repr(gnx.edges()).split("(")[0]


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("form", ["data", "nbunch"])
def test_edge_data_view_contents_agree(cls_name, form):
    """Bounds the repr fix: the CONTENTS already agree everywhere and must
    survive gaining a __repr__."""
    gnx, gfx = _pair(cls_name)
    call = (
        (lambda g: g.edges(data=True))
        if form == "data"
        else (lambda g: g.edges(["a", "b"]))
    )
    assert sorted(map(str, call(gfx))) == sorted(map(str, call(gnx)))
