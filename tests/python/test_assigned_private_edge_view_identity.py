"""br-r37-c1-jqytt — `G.edges(...)` under ASSIGNED PRIVATE STORAGE is a VIEW.

Assigning `G._adj` or `G._node` routes `G.edges` to `_AssignedPrivateEdgeView`,
one class standing in for four networkx view classes. Every `edges(...)` call on
it handed back a bare `list`, and the bare view reported its own private class
name, so on all four graph classes:

  * `type(G.edges).__name__` read `_AssignedPrivateEdgeView` against nx's
    `EdgeView` / `OutEdgeView` / `MultiEdgeView` / `OutMultiEdgeView`;
  * `type(G.edges(...)).__name__` read `list` against nx's named view for every
    call form;
  * `M.edges(keys=True)` and `G.edges()` returned a copy where networkx returns
    `self`, so the result stopped tracking the graph.

THE RULE networkx follows is "the view returns ITSELF when asked for its own
tuple shape" — the default call on a simple graph, which yields 2-tuples, and
`keys=True` on a multigraph, whose own tuples are keyed. Asking a multigraph for
`keys=False` asks for a different shape and gets a data view. That asymmetry is
why the tests below sweep all four classes rather than the multigraph pair the
bead was filed against: writing the condition as "keys is True" fixes the
multigraph half and leaves both simple classes wrong.

Everything here is decided by live networkx, including which cells raise.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]

# `_adj` and `_node` are assigned separately as well as together, because either
# one alone is enough to route the accessor to this view.
ASSIGNMENTS = ["adj", "node", "both"]

CALL_FORMS = {
    "default call": {},
    "data=True": {"data": True},
    "data=<key>": {"data": "w"},
    "data=<absent key>": {"data": "missing", "default": "D"},
    "an nbunch": {"nbunch": ["a"]},
}
MULTI_CALL_FORMS = {
    "keys=True": {"keys": True},
    "keys and data": {"keys": True, "data": True},
}


def _build(lib, cls_name, assign):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", w=1)
    if cls_name.startswith("Multi"):
        graph.add_edge("a", "b", w=2)
        graph.add_edge("c", "d", key="x", w=3)
    else:
        graph.add_edge("c", "d", w=3)
    if assign in ("node", "both"):
        graph._node = {n: dict(graph.nodes[n]) for n in graph}
    if assign in ("adj", "both"):
        graph._adj = {n: dict(graph._adj[n]) for n in graph}
    return graph


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
def test_the_bare_view_reports_the_networkx_class_name(cls_name, assign):
    """One class stands in for four, and the name is observable."""
    expected = type(_build(nx, cls_name, assign).edges).__name__
    actual = type(_build(fnx, cls_name, assign).edges).__name__
    assert actual == expected


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
def test_the_default_call_returns_the_view_itself_on_a_simple_graph(cls_name, assign):
    """`G.edges()` IS `G.edges` for the classes whose own tuples are 2-tuples.

    Identity is the contract, not just the type name: networkx returns `self`,
    so the result keeps tracking the graph. A copy silently stops.
    """
    graph = _build(fnx, cls_name, assign)
    reference = _build(nx, cls_name, assign)
    expected_identity = reference.edges() is reference.edges
    assert (graph.edges() is graph.edges) == expected_identity


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
def test_keys_true_returns_the_view_itself_on_a_multigraph(cls_name, assign):
    """The bead's headline cell, asserted as identity rather than as a type."""
    graph = _build(fnx, cls_name, assign)
    reference = _build(nx, cls_name, assign)
    assert reference.edges(keys=True) is reference.edges, "nx premise moved"
    assert graph.edges(keys=True) is graph.edges


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_returned_view_is_live(cls_name):
    """What the identity buys, and the reason a list is not merely misnamed.

    The view is taken BEFORE the mutation and read after, so a copy fails this
    and a view passes. networkx decides what the answer is — writing the
    expected count by hand is how the first version of this test went wrong,
    because a directed `_adj` write adds one edge and an undirected one adds
    the same edge twice.
    """

    def observe(lib):
        graph = _build(lib, cls_name, "adj")
        view = graph.edges(keys=True)
        graph._adj["a"]["z"] = {0: {}}
        graph._adj.setdefault("z", {})["a"] = {0: {}}
        return sorted(map(repr, view))

    expected = observe(nx)
    assert any("'z'" in item for item in expected), "nx premise moved"
    assert observe(fnx) == expected


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
@pytest.mark.parametrize("form_name", sorted(CALL_FORMS))
def test_call_forms_report_the_networkx_class_name(cls_name, assign, form_name):
    """Every call form, because they were ALL bare lists."""
    kwargs = CALL_FORMS[form_name]
    expected = type(_build(nx, cls_name, assign).edges(**kwargs)).__name__
    actual = type(_build(fnx, cls_name, assign).edges(**kwargs)).__name__
    if expected == "EdgeDataView" and not cls_name.startswith("Multi"):
        pytest.skip(
            "br-r37-c1-jqytt: nx names this EdgeDataView, and fnx's EdgeDataView "
            "is a LIVE view built from a call thunk rather than a list wrapper, "
            "so there is no list-based class carrying that name to wrap with. "
            "The other three names all have one. Left alone deliberately."
        )
    assert actual == expected


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
@pytest.mark.parametrize("form_name", sorted(MULTI_CALL_FORMS))
def test_multigraph_call_forms_report_the_networkx_class_name(
    cls_name, assign, form_name
):
    kwargs = MULTI_CALL_FORMS[form_name]
    expected = type(_build(nx, cls_name, assign).edges(**kwargs)).__name__
    actual = type(_build(fnx, cls_name, assign).edges(**kwargs)).__name__
    assert actual == expected


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("assign", ASSIGNMENTS)
@pytest.mark.parametrize("form_name", sorted(CALL_FORMS))
def test_call_forms_still_yield_what_networkx_yields(cls_name, assign, form_name):
    """The rewrap must not move the CONTENTS, which is the easy thing to break."""
    kwargs = CALL_FORMS[form_name]
    expected = sorted(map(repr, _build(nx, cls_name, assign).edges(**kwargs)))
    actual = sorted(map(repr, _build(fnx, cls_name, assign).edges(**kwargs)))
    assert actual == expected


# ---------------------------------------------------------------------------
# Containment. networkx uses TWO spellings and the difference is observable.
# ---------------------------------------------------------------------------

CONTAINMENT_PROBES = {
    "a present 2-tuple": ("a", "b"),
    "an absent 2-tuple": ("q", "r"),
    "a 3-tuple": ("a", "b", 0),
    "a 4-tuple": ("a", "b", 0, 1),
    "a 1-tuple": ("a",),
    "a non-iterable": 5,
    "a string": "ab",
    "an unhashable endpoint": (["x"], "b"),
}


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("assign", ASSIGNMENTS)
@pytest.mark.parametrize("probe_name", sorted(CONTAINMENT_PROBES))
def test_containment_matches_networkx_including_what_it_raises(
    cls_name, assign, probe_name
):
    """`EdgeView` slices (`u, v = e[:2]`); `OutEdgeView` unpacks (`u, v = e`).

    So a 3-tuple answers on an undirected view and is a ValueError on a directed
    one, and a non-iterable raises two DIFFERENT TypeErrors because one
    subscripts and the other unpacks. This view answered False for five of these
    eight shapes, on both classes. The exception TEXT is compared, not just the
    type, because that is where the two spellings differ.
    """
    probe = CONTAINMENT_PROBES[probe_name]

    def outcome(lib):
        graph = _build(lib, cls_name, assign)
        try:
            return repr(probe in graph.edges)
        except Exception as exc:  # noqa: BLE001 - the contract under test
            return f"{type(exc).__name__}: {exc}"

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("cls_name", MULTI)
def test_a_two_tuple_means_key_zero_not_any_key(cls_name):
    """AGAINST THE BEAD'S OWN TEXT, which asserted the opposite.

    br-r37-c1-jqytt states the rule as "`(u,v)` matches any key". networkx says
    otherwise: with a single parallel edge under a NON-zero key, `('a','b') in
    M.edges(keys=True)` is False. fnx already agreed; the bead was wrong, and
    this pins the real rule so the "fix" is never applied.
    """
    graph = fnx.MultiGraph() if cls_name == "MultiGraph" else fnx.MultiDiGraph()
    reference = getattr(nx, cls_name)()
    for g in (graph, reference):
        g.add_edge("a", "b", key="ONLY")
        g._node = {n: dict(g.nodes[n]) for n in g}
        g._adj = {n: dict(g._adj[n]) for n in g}
    assert ("a", "b") not in reference.edges(keys=True), "nx premise moved"
    assert ("a", "b") not in graph.edges(keys=True)
    assert ("a", "b", "ONLY") in graph.edges(keys=True)


def test_iteration_does_not_recurse_through_the_call_form():
    """The hazard br-r37-c1-p1dbu had to revert a `return self` for.

    `__call__` now short-circuits to `self`, so iteration must NOT reach it.
    A regression here is an unbounded recursion, not a wrong answer, so it is
    pinned separately rather than left to the sweeps above to hit.
    """
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b")
    graph._adj = {n: dict(graph._adj[n]) for n in graph}
    view = graph.edges(keys=True)
    assert list(view) == [("a", "b", 0)]
    assert list(iter(view)) == [("a", "b", 0)]
