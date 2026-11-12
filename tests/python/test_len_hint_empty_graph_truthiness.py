"""br-r37-c1-ORTRUTH — an emptied live graph must not be discarded by `or`.

`_fnx_take_len_hint` selected its graph with
``getattr(self, "_fnx_live_graph", None) or getattr(self, "_fnx_guard_graph", None)``.
An EMPTY graph is falsy, so `or` throws away a live graph that has been
cleared — exactly the mutation br-r37-c1-af0ig was filed for. That bead fixed
`_fnx_refresh`, whose comment states the rule ("`is None`, never `or`"), and left
this sibling three lines above on the old form.

SCOPE, stated honestly: I could not reach the divergent state through the public
API. On the paths exercised by `len(v); list(v)` neither attribute is set, so
both forms return None and agree. This is therefore a consistency fix removing a
latent trap, not a demonstrated user-visible bug, and the tests drive the helper
directly because that is the only way the two forms can be told apart.

The NEGATIVE CASE is the point of the file: an empty-but-present live graph must
be USED, and a genuinely absent one must still fall through.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

# Graph's edges(nbunch) returns an EdgeDataView, which does not carry the
# len-hint handoff at all; DiGraph returns OutEdgeDataView and the multigraphs
# return _EdgeListWithSetAlgebra, all three of which do. Scoping to the classes
# that actually have the helper — a first draft parametrised all four and failed
# five ways on Graph for want of the attribute, which measures the fixture and
# not the fix.
CLASSES = ["DiGraph", "MultiGraph", "MultiDiGraph"]


def _view(cls_name):
    graph = getattr(fnx, cls_name)()
    for i in range(10):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 10}")
    return graph, graph.edges(["n1"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_emptied_live_graph_is_still_used_for_the_hint(cls_name):
    """POSITIVE: a cleared (falsy) live graph must be selected, not skipped.

    Under `or` this returned False because the empty graph is falsy and the
    guard graph is absent; under `is None` the token is compared properly.
    """
    graph, view = _view(cls_name)
    graph.clear()
    assert not graph, "fixture must leave the graph falsy"
    view._fnx_live_graph = graph
    view._fnx_guard_graph = None
    view._fnx_len_hint = fnx._edge_list_freshness_token(graph)
    assert view._fnx_take_len_hint() is True, (
        f"{cls_name}: an emptied live graph was discarded — the `or` truthiness "
        "trap of br-r37-c1-af0ig"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_stale_hint_on_an_emptied_graph_is_rejected(cls_name):
    """The hint must still be VALIDATED, not merely accepted."""
    graph, view = _view(cls_name)
    stale = fnx._edge_list_freshness_token(graph)
    graph.clear()
    view._fnx_live_graph = graph
    view._fnx_guard_graph = None
    view._fnx_len_hint = stale
    assert view._fnx_take_len_hint() is False, (
        f"{cls_name}: a hint from before clear() was accepted"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_absent_graphs_still_fall_through(cls_name):
    """NEGATIVE CASE: with no graph at all the answer must stay False.

    The fix must not turn "no graph" into "use something"; only an emptied but
    PRESENT graph changes behaviour.
    """
    _graph, view = _view(cls_name)
    view._fnx_live_graph = None
    view._fnx_guard_graph = None
    view._fnx_len_hint = (0, 0)
    assert view._fnx_take_len_hint() is False


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_guard_graph_is_still_the_fallback(cls_name):
    """NEGATIVE CASE: when the live graph is genuinely absent, fall back."""
    graph, view = _view(cls_name)
    view._fnx_live_graph = None
    view._fnx_guard_graph = graph
    view._fnx_len_hint = fnx._edge_list_freshness_token(graph)
    assert view._fnx_take_len_hint() is True


def test_the_scope_claim_is_still_true():
    """Non-vacuity: pin WHICH views carry the handoff.

    If Graph ever grows one, these tests silently stop covering it, so the
    exclusion is asserted rather than assumed.
    """
    carriers = {}
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        graph = getattr(fnx, cls_name)()
        graph.add_edge("a", "b")
        carriers[cls_name] = hasattr(graph.edges(["a"]), "_fnx_take_len_hint")
    assert carriers["Graph"] is False, (
        "Graph's edges(nbunch) view now carries the len-hint handoff; add it to "
        "CLASSES so it is covered"
    )
    assert all(carriers[c] for c in CLASSES), carriers


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_hint_is_consumed_exactly_once(cls_name):
    """The hint is a one-shot handoff; a second read must not reuse it."""
    graph, view = _view(cls_name)
    view._fnx_live_graph = graph
    view._fnx_guard_graph = None
    view._fnx_len_hint = fnx._edge_list_freshness_token(graph)
    assert view._fnx_take_len_hint() is True
    assert view._fnx_take_len_hint() is False, "the hint was not consumed"
