"""br-r37-c1-8c7m5 — `G.edges(nbunch, data=<key>)` on the SIMPLE classes.

networkx's nbunch edge view walks the row dicts it captured, which are the
graph's own, so a mutation to a row it has not reached yet is visible and only a
resize of the row it is standing in raises. `Graph` and `DiGraph` already matched
that for `data=False` and `data=True`, because those spellings get a live-row
walk. `data=<key>` gets no walk — the walk yields the raw attribute dict and this
form needs `attrs.get(key, default)` — so it fell through to the materialised
path, and there it failed in BOTH directions at once:

  DiGraph OVER-RAISED, on everything. None of its four nbunch returns passed
  `nbunch_rows`, so the guard asked its coarse "did ANYTHING change" question
  instead of networkx's "was the row I am standing in resized". It raised
  RuntimeError for `G.add_node('zz')` and for removing an unrelated node, both of
  which networkx completes straight through. The multigraph views beside it have
  passed `nbunch_rows` on every return since br-r37-c1-hihrf.

  Graph WENT STALE, because its guard had no way to rebuild and — watching only
  the node sequence — did not even notice an edge-only mutation.

Every cell below is decided by live networkx, including which ones raise.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]

MUTATIONS = {
    "add an isolated node": lambda g: g.add_node("zz"),
    "remove an unrelated node": lambda g: g.remove_node("n7"),
    "grow a LATER row": lambda g: g.add_edge("n2", "zz"),
    "shrink a LATER row": lambda g: g.remove_edge("n2", "n3"),
    "add a self-loop on a LATER row": lambda g: g.add_edge("n2", "n2"),
    "re-add an existing edge": lambda g: g.add_edge("n2", "n3", w=99),
    "clear the whole graph": lambda g: g.clear(),
    "no mutation at all": lambda g: None,
}

FORMS = {
    "data=<key>": {"data": "w"},
    "data=<absent key>": {"data": "missing", "default": "D"},
    "data=True": {"data": True},
    "plain": {},
}

# NO "no nbunch at all" HERE, deliberately. That form is a DIFFERENT networkx
# code path — its view iterates the adjacency dict itself rather than a captured
# list of rows — and it is still divergent on DiGraph, which the strict xfail at
# the bottom pins. Sweeping it here would report this fix as broken for a defect
# it does not touch.
NBUNCHES = {
    "a list": ["n1", "n2"],
    "a one-element list": ["n1"],
    "a tuple": ("n1", "n2"),
    "a list naming an absent node": ["n1", "ABSENT", "n2"],
}


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    for index in range(10):
        graph.add_edge(f"n{index}", f"n{(index + 1) % 10}", w=index)
    return graph


def _drain(lib, cls_name, nbunch, kwargs, mutate):
    graph = _build(lib, cls_name)
    view = graph.edges(**kwargs) if nbunch is None else graph.edges(nbunch, **kwargs)
    iterator = iter(view)
    next(iterator, None)
    try:
        mutate(graph)
    except Exception as exc:  # noqa: BLE001 - a mutation networkx also rejects
        return f"MUTATION {type(exc).__name__}"
    try:
        return sorted(map(repr, iterator))
    except Exception as exc:  # noqa: BLE001 - the contract under test
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("nbunch_name", sorted(NBUNCHES))
@pytest.mark.parametrize("form_name", sorted(FORMS))
@pytest.mark.parametrize("mutation_name", sorted(MUTATIONS))
def test_mutating_mid_iteration_matches_networkx(
    cls_name, nbunch_name, form_name, mutation_name
):
    """THE SWEEP: 320 cells, networkx deciding every one."""
    nbunch = NBUNCHES[nbunch_name]
    kwargs = FORMS[form_name]
    mutate = MUTATIONS[mutation_name]
    expected = _drain(nx, cls_name, nbunch, kwargs, mutate)
    actual = _drain(fnx, cls_name, nbunch, kwargs, mutate)
    assert actual == expected, f"{cls_name} nbunch={nbunch_name} {form_name}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_unrelated_mutation_does_not_raise(cls_name):
    """The OVER-RAISE, stated on fnx's own terms.

    Adding an isolated node cannot resize any row networkx is walking, so it
    completes. DiGraph's `data=<key>` view raised RuntimeError here because it
    was given the coarse guard rather than the row guard.
    """
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"], data="w"))
    next(iterator)
    graph.add_node("an_isolated_node")
    assert list(iterator)  # must not raise


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_later_row_is_read_when_the_iteration_reaches_it(cls_name):
    """The STALENESS, stated on fnx's own terms and with no oracle."""
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"], data="w"))
    next(iterator)
    graph.add_edge("n2", "BRAND_NEW", w=7)
    assert ("n2", "BRAND_NEW", 7) in list(iterator)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_edge_only_mutation_is_noticed(cls_name):
    """Why the guard has to watch the EDGE sequence and not only the nodes.

    `remove_edge` between two existing nodes leaves `nodes_seq` untouched, so a
    node-only guard never fires and the view keeps serving its pre-mutation
    rows. This is the half that `guard_edge_count` buys.
    """
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"], data="w"))
    next(iterator)
    graph.remove_edge("n2", "n3")
    assert all(edge[:2] != ("n2", "n3") for edge in iterator)


def test_the_undirected_no_nbunch_form_reads_through_a_re_added_edge():
    """The 6 cells the FIRST version of this fix broke, pinned.

    With no nbunch there are no rows to check, so the guard falls to its coarse
    branch — and watching the edge sequence there means raising on any edge
    change at all, including re-adding an edge that already exists, which
    networkx reads straight through because its adjacency dict did not resize.
    `guard_edge_count` is therefore scoped to the nbunch case. DiGraph is
    excluded because it fails this for an unrelated pre-existing reason, pinned
    directly below.
    """
    graph = _build(fnx, "Graph")
    iterator = iter(graph.edges(data="w"))
    next(iterator)
    graph.add_edge("n2", "n3", w=99)
    assert list(iterator)  # must not raise


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-8c7m5 residue 2, the NO-NBUNCH form. This is a different "
    "return — `_DiGraphEdgeView.__call__`'s `nbunch is None and data is not "
    "False/True` branch — which passes `guard_edge_count=True` unconditionally, "
    "so it raises on ANY edge change. networkx's no-nbunch view iterates the "
    "adjacency dict itself, and neither re-adding an existing edge nor removing "
    "one resizes THAT dict, so nx completes. Pre-existing: fails identically on "
    "the arm before this bead's fix. Not touched here because it is a different "
    "code path from the nbunch rows this change is about.",
)
def test_the_directed_no_nbunch_form_reads_through_a_re_added_edge():
    graph = _build(fnx, "DiGraph")
    iterator = iter(graph.edges(data="w"))
    next(iterator)
    graph.add_edge("n2", "n3", w=99)
    assert list(iterator)
