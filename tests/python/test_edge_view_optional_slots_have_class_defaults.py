"""br-r37-c1-5pjt3 — the edge-view family reads its optional slots directly.

`_EdgeListWithSetAlgebra` and its six subclasses carry nine optional `_fnx_`
slots. Every read of one used to be spelled `getattr(self, "_fnx_X", None)`,
the optional-slot idiom, on a view whose instance dict USUALLY HAS the
attribute. Counting `builtins.getattr` around one warm
`list(G.edges(["n1"]))` found nineteen of them per call on MultiGraph and
MultiDiGraph and nine on DiGraph. Class-level defaults let those be ordinary
attribute lookups.

THE WALL CLOCK DID NOT MOVE ENOUGH TO CLAIM, and that is recorded here rather
than hidden. Priced in isolation the idiom looked like 15.5 ns per site — 24.0
ns against 8.5 ns for a class-default lookup — which predicted ~4.5 percent of
MultiGraph's call. Two balanced-square A/Bs over two Python arms sharing one
ELF measured about +1 percent: favourable on all nine target rows in both runs,
but inside the spread, with the untouched control rows at +/-0.4 percent. The
isolated per-site price over-predicted by roughly 4x, which is what
`standalone_microtiming_misattributes` says it will do. No ratio is claimed.

What IS certain is the counted mechanism, and that is what this file locks: the
number of `getattr` calls per read. It is also the only cheap way to notice
someone reintroducing the idiom.

THE TRAP THE DEFAULTS CREATE is the second test. A class attribute makes
`hasattr` permanently True, so `_live_called_edge_view`'s old
`if not hasattr(result, "_fnx_token")` guard would have stopped firing and the
directional paths that depend on it would have kept a None token forever —
i.e. never refreshed. It is an `is None` test now. `vars()` still does NOT show
an unset slot, so anything inspecting `__dict__` is unaffected; both halves are
asserted below so the asymmetry is written down somewhere.
"""

from __future__ import annotations

import builtins

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Measured after the conversion, by wrapping builtins.getattr around one warm
# `list(G.edges(["n1"]))`. Before it these read 9 (DiGraph) and 19 (both Multi
# classes); Graph read 0 then and now, because its EdgeDataView is an object
# subclass that initialises its slots in __init__ and never used the idiom.
# Lower is better; these are ceilings.
VIEW_SLOT_GETATTR_BUDGET = {
    "Graph": 0,
    "DiGraph": 0,
    "MultiGraph": 0,
    "MultiDiGraph": 0,
}

# The `_fnx_` slots that remain are on the GRAPH, not on the view: a native
# kernel probe and a per-class result memo. They are a different mechanism and
# a class default cannot serve them, so they are budgeted separately rather
# than swept into the number above.
#
# DIGRAPH MOVED 0 -> 1 FOR br-r37-c1-8c7m5, and the trade is stated rather than
# absorbed. Its four `edges(nbunch, ...)` returns now pass `nbunch_rows`, as the
# multigraph views beside them always have — that is the whole fix, and it is
# why those two classes have sat at 2 all along. Resolving the rows costs one
# `getattr(graph, "_fnx_node_key_dict")` for the membership container.
#
# WHAT THE ONE PROBE BUYS: 122 differential cells against live networkx.
# Without `nbunch_rows` the iterator falls to its coarse guard and raises
# RuntimeError for `G.add_node('zz')` and for removing an unrelated node, both
# of which networkx completes through. One graph-attribute read per call
# against an over-raise on every unrelated mutation is not a close call, and
# the budget is raised to exactly 1 rather than loosened, so the next
# regression still fails here.
GRAPH_SLOT_GETATTR_BUDGET = {
    "Graph": 0,
    "DiGraph": 1,
    "MultiGraph": 2,
    "MultiDiGraph": 2,
}

VIEW_SLOTS = (
    "_fnx_live_graph",
    "_fnx_guard_graph",
    "_fnx_guard_edge_count",
    "_fnx_nbunch_rows",
    "_fnx_token",
    "_fnx_rebuild",
    "_fnx_lazy_rows",
    "_fnx_len_hint",
    "_fnx_frozen_nbunch",
)


def _build(lib, cls_name, order=200):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=1.0)
    return graph


def _count_slot_getattrs(callable_):
    """Split `_fnx_` slot probes by whether the target is a view or a graph."""
    on_view = []
    on_graph = []
    original = builtins.getattr

    def counting(obj, name, *default):
        if name.startswith("_fnx_"):
            if isinstance(obj, fnx._EdgeListWithSetAlgebra):
                on_view.append(name)
            else:
                on_graph.append(name)
        return original(obj, name, *default)

    builtins.getattr = counting
    try:
        callable_()
    finally:
        builtins.getattr = original
    return on_view, on_graph


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edges_nbunch_stays_within_its_slot_getattr_budget(cls_name):
    """THE COUNTED MECHANISM. Fails high on a regression, low on an improvement."""
    graph = _build(fnx, cls_name)
    list(graph.edges(["n1"]))  # warm every memo first; cold counts differ
    on_view, on_graph = _count_slot_getattrs(lambda: list(graph.edges(["n1"])))

    budget = VIEW_SLOT_GETATTR_BUDGET[cls_name]
    assert len(on_view) <= budget, (
        f"{cls_name}: {len(on_view)} getattr(view, '_fnx_...', default) calls per "
        f"edges([n]), budget {budget} — {sorted(set(on_view))}. "
        f"_EdgeListWithSetAlgebra carries a class-level default for every optional "
        f"slot, so these reads can be plain attribute lookups"
    )
    graph_budget = GRAPH_SLOT_GETATTR_BUDGET[cls_name]
    assert len(on_graph) <= graph_budget, (
        f"{cls_name}: {len(on_graph)} getattr(graph, '_fnx_...') calls, budget "
        f"{graph_budget} — {sorted(set(on_graph))}"
    )
    if len(on_view) < budget or len(on_graph) < graph_budget:
        pytest.fail(
            f"{cls_name}: down to {len(on_view)} view / {len(on_graph)} graph slot "
            f"probes from {budget} / {graph_budget}. Lower the budget and bank it."
        )


@pytest.mark.parametrize("slot", VIEW_SLOTS)
def test_every_optional_slot_has_a_class_default(slot):
    """A missing default turns its read back into an AttributeError, not a None."""
    assert hasattr(fnx._EdgeListWithSetAlgebra, slot), slot
    default = getattr(fnx._EdgeListWithSetAlgebra, slot)
    expected = False if slot == "_fnx_guard_edge_count" else None
    assert default is expected, (slot, default)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_hasattr_is_no_longer_a_presence_test_but_vars_still_is(cls_name):
    """The trap, written down.

    A class default makes `hasattr` answer True for a slot that was never set,
    which is why `_live_called_edge_view`'s stamp guard had to become an
    `is None` test. `vars()` is unaffected — a class attribute does not appear
    in the instance dict — so anything inspecting `__dict__` keeps working.
    """
    fresh = fnx._EdgeListWithSetAlgebra([])
    assert hasattr(fresh, "_fnx_token") is True
    assert fresh._fnx_token is None
    assert "_fnx_token" not in vars(fresh)

    graph = _build(fnx, cls_name)
    view = graph.edges(["n1"])
    assert view._fnx_token is not None, "a real view must carry a stamp"
    assert "_fnx_token" in vars(view)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_views_still_refresh_after_a_mutation(cls_name):
    """The contract the stamp guard exists for — br-r37-c1-af0ig.

    If the `is None` rewrite of the `hasattr` guard were wrong, a view would
    keep a null stamp and never re-materialise. That is invisible until the
    graph moves, so it is asserted against networkx here rather than inferred.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for nbunch in (["n1"], None):
        view_nx = gnx.edges() if nbunch is None else gnx.edges(nbunch)
        view_fx = gfx.edges() if nbunch is None else gfx.edges(nbunch)
        assert sorted(view_fx, key=repr) == sorted(view_nx, key=repr)
        for graph in (gnx, gfx):
            graph.add_edge("n1", f"brand-new-{nbunch}")
        assert sorted(view_fx, key=repr) == sorted(view_nx, key=repr), (
            cls_name, nbunch, "view went stale after add_edge"
        )
        assert len(view_fx) == len(view_nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_directional_views_get_a_stamp(cls_name):
    """The paths the rewritten guard actually serves.

    `_guarded_edge_list` stamps the edges(...) routes; the directional views
    reach `_live_called_edge_view` without one, and the guard is what gives them
    theirs. With a class default present, a guard spelled `hasattr` would have
    skipped them silently.
    """
    graph = _build(fnx, cls_name)
    spellings = [lambda: graph.edges(["n1"])]
    if cls_name in ("DiGraph", "MultiDiGraph"):
        spellings += [lambda: graph.out_edges(["n1"]), lambda: graph.in_edges(["n1"])]
    for spelling in spellings:
        view = spelling()
        if isinstance(view, fnx._EdgeListWithSetAlgebra):
            assert view._fnx_token is not None, (cls_name, type(view).__name__)
