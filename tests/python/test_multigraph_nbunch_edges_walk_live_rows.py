"""br-r37-c1-u5tyh — mutating mid-iteration of ``MG.edges(nbunch)``.

networkx's multigraph nbunch edge view captures ``[(n, adjdict[n]) for n in
nbunch]`` when iteration starts and then walks those ROW DICTS. It has no
mutation policy of its own: what you get is whatever CPython says about the
mappings it happens to be standing in, and those mappings are the graph's OWN.
Two consequences follow, and fnx matched neither on the multigraph classes:

  a mutation to a row networkx has NOT REACHED YET is visible, because the row
  dict is shared with the graph — fnx had already built its whole answer, so it
  reported the pre-mutation graph;

  a mutation that RESIZES a mapping under iteration raises RuntimeError, and the
  mappings are the row (distinct neighbours) and the cell (edge keys), NOT the
  degree.

fnx now re-materialises when its staleness guard sees the graph move and decides
the move is not one networkx raises for — which is precisely when networkx would
be reading the changed rows. The sweep below covers the mutations that closes;
the three that remain are pinned separately, strictly, at the bottom.

Every cell is decided by live networkx rather than by a table, so the file
cannot go vacuous if a future networkx changes its mind about one of these.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph"]

# Mutations are described by where they land RELATIVE TO THE WALK, because that
# is the only thing networkx's behaviour depends on here.
MUTATIONS = {
    "grow a LATER row": lambda g: g.add_edge("n2", "zz"),
    "shrink a LATER row": lambda g: g.remove_edge("n2", "n3"),
    "parallel edge on a LATER cell": lambda g: g.add_edge("n2", "n3", key="k9"),
    "drop a parallel key, LATER cell": lambda g: g.remove_edge("n2", "n3", key="p"),
    "add a self-loop on a LATER row": lambda g: g.add_edge("n2", "n2"),
    "add an isolated node": lambda g: g.add_node("zz"),
    "remove an unrelated node": lambda g: g.remove_node("n7"),
    "clear the whole graph": lambda g: g.clear(),
    "no mutation at all": lambda g: None,
}

# Every ``edges()`` spelling, because the divergence was present in all of them.
FORMS = {
    "plain": {},
    "data=True": {"data": True},
    "data=<key>": {"data": "w"},
    "data=<absent key>": {"data": "missing", "default": "D"},
    "keys=True": {"keys": True},
    "keys and data": {"keys": True, "data": True},
    "keys and data=<key>": {"keys": True, "data": "w", "default": "D"},
}

NBUNCHES = {
    "a list": ["n1", "n2"],
    "a one-element list": ["n1"],
    "a tuple": ("n1", "n2"),
    "a list naming an absent node": ["n1", "ABSENT", "n2"],
    "a list whose row owns a self-loop": ["n5", "n1"],
}


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    for index in range(10):
        graph.add_edge(f"n{index}", f"n{(index + 1) % 10}", key="p", w=index)
    graph.add_edge("n5", "n5", key="p", w=5)
    return graph


def _drain(graph, nbunch, kwargs, mutate, advance=1):
    """Start iterating, mutate mid-walk, and report what comes back.

    The result is a plain comparable value in every case — the remaining items,
    or the exception type and message — so the two libraries can be compared
    without the test deciding in advance which of those it expects.
    """
    iterator = iter(graph.edges(nbunch, **kwargs))
    for _ in range(advance):
        next(iterator, None)
    try:
        mutate(graph)
    except Exception as exc:  # noqa: BLE001 - a mutation networkx also rejects
        return f"MUTATION {type(exc).__name__}"
    try:
        return sorted(map(repr, iterator))
    except Exception as exc:  # noqa: BLE001 - the contract under test
        return f"{type(exc).__name__}: {exc}"


def _both(cls_name, nbunch, kwargs, mutate):
    return (
        _drain(_build(fnx, cls_name), nbunch, kwargs, mutate),
        _drain(_build(nx, cls_name), nbunch, kwargs, mutate),
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("nbunch_name", sorted(NBUNCHES))
@pytest.mark.parametrize("form_name", sorted(FORMS))
@pytest.mark.parametrize("mutation_name", sorted(MUTATIONS))
def test_mutating_mid_walk_matches_networkx(
    cls_name, nbunch_name, form_name, mutation_name
):
    """THE SWEEP: 630 cells, networkx deciding every one of them."""
    actual, expected = _both(
        cls_name, NBUNCHES[nbunch_name], FORMS[form_name], MUTATIONS[mutation_name]
    )
    assert actual == expected, f"{cls_name} nbunch={nbunch_name} {form_name}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("advance", [0, 1])
def test_a_later_row_is_read_when_the_walk_reaches_it(cls_name, advance):
    """The defect stated directly, with no oracle at all.

    An edge added to a row the iteration has not reached yet must appear. This
    held on ``Graph`` and ``DiGraph`` before and on neither multigraph class.

    ADVANCE STOPS AT 1 ON PURPOSE: ``MultiDiGraph`` yields OUT-edges, so this
    nbunch has exactly two items and a third ``next()`` has already left ``n2``'s
    row. Growing a row the walk stands in is the case that must RAISE, which is
    a different rule, not this one.
    """
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"]))
    for _ in range(advance):
        next(iterator, None)
    graph.add_edge("n2", "BRAND_NEW")
    assert ("n2", "BRAND_NEW") in list(iterator)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_clearing_the_graph_still_drains_the_captured_rows(cls_name):
    """The rows networkx captured DETACH rather than empty, and that matters.

    ``G.clear()`` empties the outer adjacency dict; it does not touch the row
    dicts, and networkx is holding those objects, so it keeps walking their
    pre-mutation contents and completes. fnx's un-refreshed list is that same
    snapshot — so the fix has to know NOT to rebuild here. Rebuilding returned an
    empty answer for 112 cells in the first version of this change, which is why
    the case is pinned on its own rather than left to the sweep.
    """
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"]))
    next(iterator)
    graph.clear()
    assert list(iterator)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_untouched_graph_iterates_without_rebuilding(cls_name):
    """The rebuild must hang off the guard's trigger, not run per read.

    If it ever fires on an unmutated graph the change stops being free, so this
    counts calls rather than trusting the placement.
    """
    graph = _build(fnx, cls_name)
    view = graph.edges(["n1", "n2"])
    calls = []
    original = type(view)._fnx_rematerialise_rows
    try:
        type(view)._fnx_rematerialise_rows = lambda self: (
            calls.append(1), original(self)
        )[1]
        assert list(iter(view)) == list(view)
    finally:
        type(view)._fnx_rematerialise_rows = original
    assert calls == [], "rebuilt an unmutated view"


# ---------------------------------------------------------------------------
# WHAT THIS CHANGE DOES NOT FIX. Strict, so each one shouts on the day it is
# fixed rather than quietly continuing to be skipped.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-u5tyh: fnx OVER-RAISES. The guard compares `degree`, which "
    "counts parallel edges; the row dict networkx iterates counts DISTINCT "
    "NEIGHBOURS. Adding an edge between two ALREADY-ADJACENT nodes moves the "
    "first and not the second, so nothing networkx stands in was resized and it "
    "completes. One scalar per row cannot express nx's two-level rule — measured: "
    "swapping the scalar to the row length fixes these 63 cells and breaks 35 "
    "others, because on MultiDiGraph the SAME mutation resizes the key-dict the "
    "walk is standing in and nx does raise. The real fix is the live-row walk, "
    "which is blocked on multigraph rows having no live PyDict mirror.",
)
@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_parallel_edge_on_a_later_cell_does_not_raise(cls_name):
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"], keys=True))
    next(iterator)
    graph.add_edge("n1", "n2", key="ADDED")
    assert ("n1", "n2", "ADDED") in list(iterator)


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-u5tyh: `data=<key>` projects `attrs.get(key, default)` when "
    "the view is built, where networkx projects it as it passes the edge. Editing "
    "an attribute IN PLACE moves neither nodes_seq nor edges_seq, so the guard's "
    "trigger never fires and there is nothing to hang a rebuild off. Needs a "
    "different signal, not a different rebuild.",
)
@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_attribute_edited_in_place_is_seen_by_a_data_key_view(cls_name):
    graph = _build(fnx, cls_name)
    iterator = iter(graph.edges(["n1", "n2"], data="w"))
    next(iterator)
    graph["n2"]["n3"]["p"].update(w=99)
    assert any(edge[2] == 99 for edge in iterator)


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-u5tyh: fnx UNDER-RAISES on a SINGLE-ROW nbunch. On "
    "MultiDiGraph `['n1']` yields one out-edge, so after one `next()` the walk "
    "has drained the row and the guard has no `previous` row left to ask about; "
    "networkx is still suspended inside the captured row dict and raises when it "
    "resizes. A two-element nbunch gets this right, which is what makes it a gap "
    "in the guard's row bookkeeping rather than in the rebuild.",
)
def test_growing_a_single_row_nbunch_on_multidigraph_matches_networkx():
    actual, expected = _both("MultiDiGraph", ["n1"], {}, lambda g: g.add_edge("n1", "zz"))
    assert actual == expected
