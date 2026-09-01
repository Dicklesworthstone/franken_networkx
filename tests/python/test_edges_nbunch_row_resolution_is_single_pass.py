"""br-r37-c1-cnwof — `edges(nbunch)` resolves its nbunch WITHOUT `nbunch_iter`.

Every ``edges(nbunch)`` return on the three list-backed edge views used to hand
``_guarded_edge_list`` a ``graph.nbunch_iter(nbunch)`` generator purely so the
fail-fast row guard had the resolved node list, and ``_guarded_edge_list``
materialised it immediately with ``tuple(...)``. On a 200-node MultiGraph with a
one-node nbunch that round trip cost ~780 ns of a ~7300 ns call: a generator
frame, an exception translator that never fires, and ``nbunch_iter``'s
``if nbunch in self`` single-node probe that a LIST can never satisfy — on top
of ~75 ns of actual filtering.

``_resolved_nbunch_rows`` does the filtering directly against ``nbunch_iter``'s
own membership container. Two properties have to hold and neither is visible in
a timing:

  * the ANSWER is still ``nbunch_iter``'s answer, on every nbunch form and on a
    graph carrying assigned private storage (where the container is the
    adjacency, not the node mirror);
  * a TUPLE nbunch still goes the long way. A tuple can BE a node, and
    ``nbunch_iter``'s first rule resolves such a tuple to that ONE node rather
    than to its elements. A list is unhashable so it can never take that branch,
    which is why the shortcut is spelled ``type(nbunch) is list`` and not
    ``isinstance(nbunch, (list, tuple))``. Widening it would silently change
    what ``G.edges((1, 2))`` means. (fnx already diverges from networkx on that
    spelling for an unrelated reason — see br-r37-c1-jl8x1 — so the assertion
    here is against ``nbunch_iter``, which is correct today, not against the
    edge view, which is not.)

The call-count test is the one that fails on the unfixed arm: it is what makes
the cost visible instead of merely faster.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
LIST_BACKED = ["DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name, order=60):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=float(i))
    graph.add_node("iso")
    graph.add_edge((1, 2), (3, 4))
    graph.add_edge("n1", (1, 2))
    return graph


NBUNCHES = [
    ["n1"],
    ["n1", "n2"],
    ["n1", "n1"],
    ["nope"],
    [],
    ["iso"],
    ["n1", "nope", "n2"],
    [(1, 2)],
    [(1, 2), "n1"],
    "n1",
    (1, 2),
    ("n1", "n2"),
    None,
]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_resolved_rows_agree_with_nbunch_iter(cls_name):
    """The shortcut answers what the generator answers, form by form."""
    graph = _build(fnx, cls_name)
    for nbunch in NBUNCHES:
        want = list(graph.nbunch_iter(nbunch))
        got = fnx._resolved_nbunch_rows(graph, nbunch)
        assert list(want if got is None else got) == want, (cls_name, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_tuple_that_is_a_node_still_goes_through_nbunch_iter(cls_name):
    """The `type(nbunch) is list` gate, asserted as behaviour rather than spelling.

    ``(1, 2)`` is a NODE here. ``nbunch_iter`` resolves it to itself; a shortcut
    that treated it as a sequence would resolve it to the nodes ``1`` and ``2``,
    which do not exist, and answer with an empty list.
    """
    graph = _build(fnx, cls_name)
    assert list(graph.nbunch_iter((1, 2))) == [(1, 2)]
    assert list(fnx._resolved_nbunch_rows(graph, (1, 2))) == [(1, 2)]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_unhashable_element_still_raises_networkx_error(cls_name):
    """The error text is nbunch_iter's contract, so the shortcut must defer to it."""
    graph = _build(fnx, cls_name)
    rows = fnx._resolved_nbunch_rows(graph, ["n1", ["unhashable"]])
    with pytest.raises(fnx.NetworkXError):
        tuple(rows)
    with pytest.raises(nx.NetworkXError):
        tuple(_build(nx, cls_name).nbunch_iter(["n1", ["unhashable"]]))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_private_storage_uses_the_same_container(cls_name):
    """Assigned private storage moves the membership container to the adjacency.

    br-r37-c1-vbe1o: on such a graph the node set and the adjacency differ, and
    ``nbunch_iter`` filters against the ADJACENCY. The shortcut shares
    ``_nbunch_filter_container``, so this is a guard on that sharing rather than
    on a second copy of the rule.
    """
    graph = _build(fnx, cls_name)
    graph._adj = dict(graph._adj)
    graph._adj["ghost"] = {}
    nbunch = ["ghost", "n1", "nope"]
    assert list(fnx._resolved_nbunch_rows(graph, nbunch)) == list(
        graph.nbunch_iter(nbunch)
    )


def _count_nbunch_iter(callable_):
    """How many times one call reaches the `nbunch_iter` generator."""
    calls = []
    original = fnx._graph_nbunch_iter

    def counting(self, nbunch=None):
        calls.append(nbunch)
        return original(self, nbunch)

    for cls_name in CLASSES:
        getattr(fnx, cls_name).nbunch_iter = counting
    try:
        callable_()
    finally:
        for cls_name in CLASSES:
            getattr(fnx, cls_name).nbunch_iter = original
    return len(calls)


@pytest.mark.parametrize("cls_name", LIST_BACKED)
def test_edges_nbunch_does_not_call_nbunch_iter(cls_name):
    """THE BUDGET. Verified to FAIL on the unfixed arm before being banked.

    Run against ``git show HEAD:python/franken_networkx/__init__.py`` this reads
    ``MultiGraph: 1`` and ``MultiDiGraph: 1``. ``DiGraph`` reads 0 on BOTH arms —
    its edge view never passed ``nbunch_rows`` at all, which is why the A/B
    measured it flat (0.9985x / 0.9953x against MultiGraph's 1.0886x) — so the
    DiGraph row here is a forward guard against acquiring the cost, not evidence
    for this change. ``Graph`` is excluded because its object-based
    ``EdgeDataView`` never took this route either.
    """
    graph = _build(fnx, cls_name)
    count = _count_nbunch_iter(lambda: list(graph.edges(["n1"])))
    assert count == 0, (
        f"{cls_name}: edges([n]) reached nbunch_iter {count} time(s). Each one is "
        f"a generator frame plus a single-node probe a list can never satisfy, "
        f"for a filter the caller can do directly — see _resolved_nbunch_rows"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edges_nbunch_results_still_match_networkx(cls_name):
    """Whatever the route, the answer is networkx's."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for nbunch in (["n1"], ["n1", "n2"], ["n1", "n1"], ["nope"], [], ["iso"]):
        assert list(gfx.edges(nbunch)) == list(gnx.edges(nbunch)), (cls_name, nbunch)
        assert list(gfx.edges(nbunch, data=True)) == list(
            gnx.edges(nbunch, data=True)
        ), (cls_name, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_row_guard_still_sees_its_rows(cls_name):
    """The resolved rows exist to feed the fail-fast guard, so it must still fire.

    br-r37-c1-hihrf: an nbunch iteration raises only when the row being walked
    changes size, not when anything at all changes. Both halves of that rule are
    checked against networkx rather than asserted directly.
    """
    def walk(graph, mutate):
        iterator = iter(graph.edges(["n1"]))
        next(iterator, None)
        mutate(graph)
        try:
            list(iterator)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__

    for mutate in (
        lambda g: g.add_node("elsewhere"),
        lambda g: g.add_edge("n1", "in-the-row"),
    ):
        want = walk(_build(nx, cls_name), mutate)
        got = walk(_build(fnx, cls_name), mutate)
        assert got == want, (cls_name, want, got)
