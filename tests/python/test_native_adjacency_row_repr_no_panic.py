"""br-r37-c1-98tci — `repr`/`str`/`==` on a native multigraph row must RAISE, never PANIC.

`MultiAtlasView::materialize` held a SHARED borrow of the graph across its loop
and, inside that loop, called `MultiKeyDictView::materialize`, whose first
statement is `self.graph.borrow_mut(py)`. A `borrow_mut` under a live `borrow` is
a PyO3 **panic**, not a catchable exception — it unwinds through the interpreter
as `pyo3_runtime.PanicException`:

    g = fnx.MultiGraph(); g.add_edges_from([('a','b'),('a','c')]); g.add_edge('a','b')
    repr(g._native_adjacency_row('a'))
    # thread panicked: Already borrowed: PyBorrowMutError

WHY THIS SURVIVED, and why it is still worth a test. Every PUBLIC path is clean:
`repr(G.adj[u])`, `repr(G[u])`, `repr(G.adj)`, `repr(G.edges)` and friends all
return normally on all four classes, because `G.adj[u]` hands back the PYTHON
`AdjacencyView`, not this native view. Only the private accessor reaches it — and
the shim itself calls `_native_adjacency_row` in three places, so any future code
that logs, reprs or compares one of those rows detonates rather than erroring.
The equality case is the sharpest: a bare `row == {}` looks entirely innocuous.

A panic is not an ordinary failure. It cannot be handled like an exception, and
it takes the interpreter with it — which is why this is pinned at the value level
AND at the "does not panic" level rather than merely asserting a return value.

THE FIX collects the neighbours and their display-key objects under the shared
borrow, releases it, and only then materialises each keydict. This file also pins
that the mapping is unchanged by that reordering: same neighbours, same order,
same nested key dicts as networkx's own adjacency row.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

EDGES = [("a", "b"), ("a", "c"), ("a", "b"), ("b", "c")]


def _pair():
    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    for u, v in EDGES:
        gnx.add_edge(u, v)
        gfx.add_edge(u, v)
    return gnx, gfx


def _native_row(graph, node):
    accessor = getattr(graph, "_native_adjacency_row", None)
    if accessor is None:
        pytest.skip("this build exposes no _native_adjacency_row")
    return accessor(node)


@pytest.mark.parametrize("op_name", ["repr", "str"])
def test_text_conversions_do_not_panic(op_name):
    """The reported repro. A PanicException here is the regression."""
    row = _native_row(_pair()[1], "a")
    op = repr if op_name == "repr" else str
    text = op(row)
    assert isinstance(text, str) and text, op_name


def test_equality_against_a_plain_dict_does_not_panic():
    """The sharpest case: `row == {}` looks completely innocuous."""
    row = _native_row(_pair()[1], "a")
    assert (row == {}) is False
    assert (row != {}) is True


def test_equality_against_the_true_mapping_is_true():
    """Not merely 'does not panic' — the comparison must be CORRECT."""
    gnx, gfx = _pair()
    row = _native_row(gfx, "a")
    want = {n: {k: dict(d) for k, d in kd.items()} for n, kd in gnx.adj["a"].items()}
    assert row == want


def test_self_equality_holds():
    row = _native_row(_pair()[1], "a")
    assert row == row


def test_materialised_mapping_matches_networkx_including_order():
    """The fix reorders when the borrow is released; the RESULT must not change.

    Collecting neighbours first and materialising after is only safe if the
    sequence is preserved, so both membership and order are pinned.
    """
    gnx, gfx = _pair()
    for node in ("a", "b", "c"):
        row = _native_row(gfx, node)
        want = {n: {k: dict(d) for k, d in kd.items()} for n, kd in gnx.adj[node].items()}
        got = {n: {k: dict(d) for k, d in kd.items()} for n, kd in dict(row).items()}
        assert got == want, node
        assert list(row) == list(gnx.adj[node]), node


def test_subscript_and_mapping_surface_still_work():
    """These were already fine; they must stay fine after the borrow change."""
    gnx, gfx = _pair()
    row = _native_row(gfx, "a")
    assert dict(row["b"]) == {k: dict(d) for k, d in gnx.adj["a"]["b"].items()}
    assert len(row) == len(gnx.adj["a"])
    assert ("b" in row) is True
    assert ("zz" in row) is False
    assert [k for k, _ in row.items()] == list(gnx.adj["a"])


def test_parallel_edges_and_self_loops_survive_the_repr():
    """The panic needed a nested keydict to trigger; keep those shapes covered."""
    gfx = fnx.MultiGraph()
    gfx.add_edge("a", "a")
    gfx.add_edge("a", "a")
    gfx.add_edge("a", "b", weight=1.0)
    row = _native_row(gfx, "a")
    text = repr(row)
    assert "a" in text
    assert dict(row["a"]) == {0: {}, 1: {}}
    assert dict(row["b"]) == {0: {"weight": 1.0}}


def test_repr_on_an_isolated_node_row():
    gfx = fnx.MultiGraph()
    gfx.add_node("lonely")
    row = _native_row(gfx, "lonely")
    assert repr(row) == "AdjacencyView({})"
    assert (row == {}) is True
    assert len(row) == 0


def test_the_public_surface_was_and_stays_clean():
    """Pins WHY this hid: the public views never reach the native row.

    If `G.adj[u]` ever starts returning the native view, this test keeps the
    public repr honest instead of letting a panic reach users.
    """
    gnx, gfx = _pair()
    for got, want in (
        (repr(gfx.adj["a"]), repr(gnx.adj["a"])),
        (repr(gfx["a"]), repr(gnx["a"])),
    ):
        assert isinstance(got, str) and got
    assert repr(gfx.adj["a"]) == repr(gnx.adj["a"])
