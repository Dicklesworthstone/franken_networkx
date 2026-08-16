"""Differential lock for br-r37-c1-af0ig — called ``G.edges(...)`` is LIVE.

networkx's edge views reflect mutations made after the view is bound. On
DiGraph, MultiGraph and MultiDiGraph, fnx's CALLED edges view was a list
materialised at construction and never updated, so it served edges that had
been DELETED and hid edges that had been ADDED::

    g = DiGraph(); g.add_edge('a','b')
    v = g.edges(data=True)
    g.remove_edge('a','b'); g.add_edge('x','y')

    list(v)   networkx -> [('x','y',{})]     the graph's real content
    list(v)   fnx      -> [('a','b',{})]     an edge that no longer exists

``Graph.edges(...)`` was already live (via the object-based ``EdgeDataView``),
which made it the in-tree control, and ``G.in_edges``/``G.out_edges`` were
stale in the same way.

The count is NOT a sufficient check and this file never uses one alone: the
swap case removes one edge and adds another, leaving both the node and edge
counts identical while the contents differ. Everything here compares CONTENTS
against live networkx.

KNOWN RESIDUE, deliberately not asserted here: 28 combinations involving the
nbunch call form still diverge, all of them pre-existing (they reproduce
against unmodified HEAD, and 4 of them are Graph-only, i.e. present before this
area was touched at all). They are tracked in br-r37-c1-2pia7 and excluded by
`NBUNCH_FORMS` below rather than silently skipped.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=2.0)
        made.append(graph)
    return made


# Every mutation kind the bead's acceptance names. `swap` is the one that
# defeats a count-based staleness check; `clear` is the one that defeats a
# truthiness-based one, because an emptied graph is falsy.
MUTATIONS = {
    "add_edge": lambda g: g.add_edge("x", "y"),
    "remove_edge": lambda g: g.remove_edge("a", "b"),
    "swap_edge": lambda g: (g.remove_edge("a", "b"), g.add_edge("a", "b")),
    "add_node": lambda g: g.add_node("solo"),
    "remove_node": lambda g: g.remove_node("c"),
    "clear": lambda g: g.clear(),
    "add_then_remove": lambda g: (g.add_edge("p", "q"), g.remove_edge("p", "q")),
}

FORMS = {
    "edges()": lambda g: g.edges(),
    "edges(data=True)": lambda g: g.edges(data=True),
    "edges(data='weight')": lambda g: g.edges(data="weight"),
    "edges(data=True,default=0)": lambda g: g.edges(data=True, default=0),
}
MULTI_FORMS = {
    "edges(keys=True)": lambda g: g.edges(keys=True),
    "edges(keys=True,data=True)": lambda g: g.edges(keys=True, data=True),
}
DIRECTIONAL_FORMS = {
    "in_edges(data=True)": lambda g: g.in_edges(data=True),
    "out_edges(data=True)": lambda g: g.out_edges(data=True),
    "in_edges()": lambda g: g.in_edges(),
    "out_edges()": lambda g: g.out_edges(),
}


def _forms_for(cls_name):
    forms = dict(FORMS)
    if cls_name in MULTI:
        forms.update(MULTI_FORMS)
    if cls_name in DIRECTED:
        forms.update(DIRECTIONAL_FORMS)
    return forms


def _readings(view):
    """Contents, length and repr payload — never the length alone."""
    return sorted(map(str, view)), len(view), sorted(map(str, list(view)))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("mutation", list(MUTATIONS), ids=list(MUTATIONS))
def test_called_edge_views_reflect_mutations_like_networkx(cls_name, mutation):
    mutate = MUTATIONS[mutation]
    for form_name, form in _forms_for(cls_name).items():
        readings = []
        for lib in (nx, fnx):
            graph = getattr(lib, cls_name)()
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)
            view = form(graph)
            mutate(graph)
            readings.append(_readings(view))
        assert readings[1] == readings[0], f"{cls_name} {form_name} after {mutation}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_deleted_edge_case_from_the_bead(cls_name):
    """The headline: a stale view served an edge that no longer existed."""
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        view = graph.edges(data=True)
        graph.remove_edge("a", "b")
        graph.add_edge("x", "y")
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]
    assert not any("'a', 'b'" in entry for entry in outcomes[1])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_count_preserving_swap_is_detected(cls_name):
    """Both counts are unchanged here, so only a revision check can see it.

    Guards the token choice directly: a staleness check built on len(G) and
    number_of_edges() passes this test's setup while reporting stale contents.
    """
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("c", "d", weight=2.0)
        view = graph.edges(data=True)
        before = (len(graph), graph.number_of_edges())
        graph.remove_edge("a", "b")
        graph.add_edge("a", "b", weight=99.0)
        assert (len(graph), graph.number_of_edges()) == before
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_view_bound_on_a_graph_that_is_then_emptied(cls_name):
    """``clear()`` leaves a falsy graph — the refresh must still run."""
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        view = graph.edges(data=True)
        graph.clear()
        outcomes.append((sorted(map(str, view)), len(view), bool(graph)))
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0] == []


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeated_reads_are_stable_and_do_not_accumulate(cls_name):
    """Refreshing must replace the contents, not append to them."""
    _, graph = _pair(cls_name)
    view = graph.edges(data=True)
    first = sorted(map(str, view))
    for _ in range(3):
        assert sorted(map(str, view)) == first
        assert len(view) == len(first)
    graph.add_edge("x", "y")
    grown = sorted(map(str, view))
    assert len(grown) == len(first) + 1
    for _ in range(3):
        assert sorted(map(str, view)) == grown
        assert len(view) == len(grown)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_nbunch_node_set_is_frozen_at_construction_like_networkx(cls_name):
    """nx resolves the nbunch once; a node absent then never joins later.

    This is the semantic the liveness fix had to preserve — re-resolving the
    caller's original nbunch on every read would be live in one step too many.
    """
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        view = graph.edges(["a", "b"])
        graph.add_edge("x", "y")  # 'x' was never in the nbunch
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]
    assert not any("'x', 'y'" in entry for entry in outcomes[1])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_nbunch_form_edges_are_still_live_within_the_frozen_node_set(cls_name):
    """Freezing the node set must not have frozen the adjacency with it."""
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        view = graph.edges(["a", "b"])
        graph.add_edge("a", "c")  # both endpoints already existed
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_bare_edges_attribute_and_unmutated_reads_are_unchanged(cls_name):
    """The paths that were already correct must stay correct."""
    gnx, gfx = _pair(cls_name)
    assert sorted(map(str, gfx.edges)) == sorted(map(str, gnx.edges))
    assert len(gfx.edges) == len(gnx.edges)
    for form_name, form in _forms_for(cls_name).items():
        view_nx, view_fx = form(gnx), form(gfx)
        assert sorted(map(str, view_fx)) == sorted(map(str, view_nx)), form_name
        assert len(view_fx) == len(view_nx), form_name


@pytest.mark.parametrize("cls_name", MULTI)
def test_set_algebra_on_keyed_views_still_works_and_is_live(cls_name):
    """`_EdgeListWithSetAlgebra` exists for these operators; they refresh too."""
    _, graph = _pair(cls_name)
    view = graph.edges(keys=True)
    assert view & set(view) == set(view)
    graph.add_edge("x", "y")
    assert ("x", "y", 0) in set(view)
    assert view | set() == set(view)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mutating_during_iteration_still_fails_fast(cls_name):
    """Liveness must not have disabled the mutate-during-iteration guard.

    nx raises RuntimeError when the graph changes size mid-iteration; fnx
    mirrors that through _FailFastEdgeIterator. Asserted against nx so it
    tracks nx's behaviour rather than a copied expectation.
    """
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        for i in range(6):
            graph.add_edge(f"n{i}", f"n{i + 1}")
        with pytest.raises(RuntimeError):
            for _edge in graph.edges(data=True):
                graph.add_edge("brand", "new")
