"""Mutating during `G.neighbors(n)` raises exactly when networkx raises.

br-r37-c1-pyzv0. MultiGraph and MultiDiGraph UNDER-raised: `remove_node` of some
OTHER node, `remove_nodes_from`, and `clear_edges` all completed the iteration
and reported the pre-mutation neighbours, where networkx raises RuntimeError.

CPython raises only when the dict THE ITERATOR HOLDS changes size. networkx
mutates the row dicts in place -- `for u in nbrs: del self._adj[u][n]`, and
`for nbr_dict in self._adj.values(): nbr_dict.clear()` -- so an open iterator
sees it. These three paths instead DROPPED the whole neighbour-row cache, which
leaves the iterator walking a row that is merely orphaned: same object, same
size, no error.

THE DROP IS STILL THERE AND MUST BE. br-r37-c1-txkrn added it for a worse bug:
a surviving row is not caught by its own generation stamp, because the next
`add_edge` calls `restamp_neighbor_rows` and writes the CURRENT sequences onto
the stale row, laundering it into looking fresh -- and `G.neighbors(n)` then
reported a phantom neighbour permanently. So the fix is to edit the live rows in
place FIRST (which is what delivers the raise) and drop the cache after (which is
what keeps staleness impossible). Both halves are tested here: the matrix below
for the raise, and the laundering tests for the staleness.

TWO SHAPES MUST NOT RAISE, and they are the reason this is not simply "clear
everything in place":

  * `G.clear()` -- networkx clears only the OUTER mapping, leaving each row dict
    untouched, so an in-flight iterator completes.
  * removing the node BEING iterated -- networkx drops its row from `_adj`
    without touching the dict, so that iterator completes too.

A fix that cleared rows indiscriminately would pass every raise test in this file
and turn both of these into a spurious RuntimeError.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

MUTATIONS = [
    ("add an edge to the row", lambda g: g.add_edge("n0", "fresh")),
    ("add an unrelated edge", lambda g: g.add_edge("x", "y")),
    ("remove an edge from the row", lambda g: g.remove_edge("n0", "n3")),
    ("remove an unrelated edge", lambda g: g.remove_edge("u", "v")),
    ("remove_edges_from the row", lambda g: g.remove_edges_from([("n0", "n3")])),
    ("add an isolated node", lambda g: g.add_node("lonely")),
    ("remove another node", lambda g: g.remove_node("n5")),
    ("remove the node being iterated", lambda g: g.remove_node("n0")),
    ("remove_nodes_from another", lambda g: g.remove_nodes_from(["n5"])),
    ("remove_nodes_from several", lambda g: g.remove_nodes_from(["n4", "n5"])),
    ("clear_edges", lambda g: g.clear_edges()),
    ("clear", lambda g: g.clear()),
]

IDS = [m[0] for m in MUTATIONS]


def _star(mod, cls_name):
    graph = getattr(mod, cls_name)()
    for i in range(1, 7):
        graph.add_edge("n0", "n%d" % i)
    graph.add_edge("u", "v")
    return graph


def _drive(mod, cls_name, mutate, reader="neighbors"):
    """Iterate one row, mutate on the first step, report what happened."""
    graph = _star(mod, cls_name)
    try:
        seen = 0
        for _ in getattr(graph, reader)("n0"):
            seen += 1
            if seen == 1:
                mutate(graph)
        return ("completed", seen)
    except RuntimeError as err:
        return ("RuntimeError", str(err))


@pytest.mark.parametrize("label,mutate", MUTATIONS, ids=IDS)
@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_raise_matches_networkx_for_every_mutation_shape(label, mutate, cls_name):
    """The matrix. Six cells of it were the bug, and two of them must NOT raise."""
    assert _drive(fnx, cls_name, mutate) == _drive(nx, cls_name, mutate), (label, cls_name)


@pytest.mark.parametrize("label,mutate", MUTATIONS, ids=IDS)
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_successors_and_predecessors_agree_too(label, mutate, cls_name):
    """`neighbors` is `successors` on a directed graph, but `predecessors` reads
    the OTHER row cache and is maintained by the same code."""
    for reader in ("successors", "predecessors"):
        got = _drive(fnx, cls_name, mutate, reader=reader)
        want = _drive(nx, cls_name, mutate, reader=reader)
        assert got == want, (label, cls_name, reader)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_clear_does_not_raise_because_networkx_does_not(cls_name):
    """Pinned on its own: the obvious over-fix turns this into a RuntimeError."""
    assert _drive(fnx, cls_name, lambda g: g.clear()) == ("completed", 6)
    assert _drive(nx, cls_name, lambda g: g.clear()) == ("completed", 6)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_removing_the_iterated_node_does_not_raise(cls_name):
    """networkx drops that row from `_adj` without touching the dict."""
    assert _drive(fnx, cls_name, lambda g: g.remove_node("n0")) == ("completed", 6)
    assert _drive(nx, cls_name, lambda g: g.remove_node("n0")) == ("completed", 6)


# ---- the staleness half: the drop is still doing its job (br-r37-c1-txkrn) ----

LAUNDERING = [
    ("remove_node then add_edge", lambda g: g.remove_node("n5")),
    ("remove_nodes_from then add_edge", lambda g: g.remove_nodes_from(["n5"])),
    ("clear_edges then add_edge", lambda g: g.clear_edges()),
    ("clear then add_edge", lambda g: g.clear()),
]


@pytest.mark.parametrize("label,mutate", LAUNDERING, ids=[c[0] for c in LAUNDERING])
@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_row_read_before_the_mutation_cannot_be_laundered_back(label, mutate, cls_name):
    """THE bug the drop exists for, re-asserted now that rows are edited first.

    A surviving row is not caught by its generation stamp: the `add_edge` below
    re-stamps it with the current sequences, so a row that outlived the mutation
    would look fresh forever and report a phantom neighbour.
    """
    fx, ref = _star(fnx, cls_name), _star(nx, cls_name)
    for graph in (fx, ref):
        for node in list(graph.nodes()):
            list(graph.neighbors(node))  # populate the row cache FIRST
        mutate(graph)
        graph.add_edge("n0", "after")  # the re-stamp

    assert sorted(map(str, fx.nodes())) == sorted(map(str, ref.nodes())), label
    for node in ref.nodes():
        assert sorted(map(str, fx.neighbors(node))) == sorted(
            map(str, ref.neighbors(node))
        ), (label, node)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_failed_removal_leaves_the_rows_intact(cls_name):
    """`remove_node` now checks presence BEFORE touching the cache.

    It mutated nothing, so nothing went stale - but the rows must still be right.
    """
    fx, ref = _star(fnx, cls_name), _star(nx, cls_name)
    for graph in (fx, ref):
        list(graph.neighbors("n0"))
        with pytest.raises(nx.NetworkXError):
            graph.remove_node("absent")

    assert sorted(map(str, fx.neighbors("n0"))) == sorted(map(str, ref.neighbors("n0")))
    for graph in (fx, ref):
        graph.add_edge("n0", "later")
    assert sorted(map(str, fx.neighbors("n0"))) == sorted(map(str, ref.neighbors("n0")))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_self_loop_is_dropped_from_its_own_row(cls_name):
    """A node is its own neighbour, so the in-place drop must reach that cell."""
    fx, ref = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    for graph in (fx, ref):
        graph.add_edge("a", "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        list(graph.neighbors("a"))
        list(graph.neighbors("b"))
        graph.remove_node("a")

    assert sorted(map(str, fx.nodes())) == sorted(map(str, ref.nodes()))
    assert sorted(map(str, fx.neighbors("b"))) == sorted(map(str, ref.neighbors("b")))


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_parallel_edges_do_not_hide_the_removal(cls_name):
    """The key row holds one cell per NEIGHBOUR, not per parallel edge."""
    fx, ref = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    for graph in (fx, ref):
        graph.add_edge("n0", "n1")
        graph.add_edge("n0", "n1")
        graph.add_edge("n0", "n2")

    assert sorted(map(str, fx.neighbors("n0"))) == sorted(map(str, ref.neighbors("n0")))

    got, want = [], []
    for graph, out in ((fx, got), (ref, want)):
        try:
            for _ in graph.neighbors("n0"):
                graph.remove_node("n1")
            out.append("completed")
        except RuntimeError:
            out.append("RuntimeError")
    assert got == want
