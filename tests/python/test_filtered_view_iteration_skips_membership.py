"""Iterating a filtered view must not re-check membership in the graph it walks.

br-r37-c1-x3829. ``_FilteredGraphView.__iter__`` walked ``self._graph`` and
then asked ``_node_visible`` about each node it had just been handed, and
``_node_visible`` opens with ``node in self._graph``. Every one of those
containment checks was answering a question the loop had already answered: the
node came OUT of that container. On ``restricted_view`` - which walks every
parent node - that was a wasted C-level lookup per node per walk, and when the
node filter is the default there was no predicate left to apply at all, so the
whole walk reduced to the parent's own iteration.

MEASURED with same-tree arms (scripts/make_python_arms.py, shared ELF, only
__init__.py differing), each arm computing its own fnx-vs-networkx ratio
in-process by ABBA - 9 rounds, 50 reps, 25 warm-up iterations, min per arm.
Arms alternated, two passes each:

    row                   HEAD baseline      with lever       self-speedup
    restricted_view 200   0.3051  0.2945     0.7819  0.7768   2.6x
    restricted_view 800   0.2747  0.2694     0.8970  0.8750   3.2x

The networkx arm held at 109-114us at N=800 across all four runs while the fnx
arm moved 398.4us -> 126.1us, which is what makes the change attributable to the
fnx side. loadavg 19.2-19.5, disk 201G. Full detail, including the one A/A null
of eight that missed the 2 percent bound, is in docs/NEGATIVE_EVIDENCE_cc.md.

WHAT THIS FILE PINS, and why each part is load-bearing:

  * the YIELDED SET and ORDER still match networkx exactly, for every view
    constructor and every graph class, before AND after the parent mutates -
    an iterator lever that changes order is a silent correctness change;
  * a bare walk invokes the node filter EXACTLY ONCE PER PARENT NODE, and no
    operation invokes it MORE OFTEN THAN NETWORKX does. This is the lever itself
    expressed as behaviour. A future refactor that reinstates a second filtering
    pass would still be correct and would silently give the time back, and no
    parity test would notice. The comparative half is there because the absolute
    half is not true of ``list()``, in either library - see below;
  * ``_node_visible`` is UNCHANGED. Its membership half is load-bearing for
    every other caller - ``__contains__``, ``_nbunch``, edge visibility - where
    the node arrives from OUTSIDE the parent. The removal is valid only inside
    the loop that produced the node, so the method must keep rejecting strangers.

THE SHORT-CIRCUIT BRANCH IS THE CONTROL. When the filter carries a ``.nodes``
set and is shorter than the parent, ``__iter__`` iterates the FILTER and checks
``node in self._graph``. There the check is real - those nodes never came from
the parent - and it is pinned here against a filter naming absent nodes.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls, n=12):
    g = getattr(lib, cls)()
    for i in range(n):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % n), weight=i)
    g.add_node("isolated")
    return g


def _views(lib, g):
    """Every filtered-view constructor, paired by label across libraries."""
    nodes = list(g)[:5]
    edges = list(g.edges(keys=True))[:3] if g.is_multigraph() else list(g.edges())[:3]
    return {
        "restricted_view": lib.restricted_view(g, nodes, []),
        "restricted_view_edges": lib.restricted_view(g, [], edges),
        "subgraph": g.subgraph(nodes),
        "edge_subgraph": g.edge_subgraph(edges),
        "induced_subgraph": lib.induced_subgraph(g, nodes),
        "as_view": g.copy(as_view=True),
    }


@pytest.mark.parametrize("cls", CLASSES)
def test_iteration_order_matches_networkx(cls):
    got, want = _build(fnx, cls), _build(nx, cls)
    fv, xv = _views(fnx, got), _views(nx, want)
    for label in fv:
        assert [str(n) for n in fv[label]] == [
            str(n) for n in xv[label]
        ], f"{cls}/{label}: iteration order diverged"
        assert len(fv[label]) == len(xv[label]), f"{cls}/{label}: len diverged"


@pytest.mark.parametrize("cls", CLASSES)
def test_iteration_tracks_a_mutating_parent(cls):
    """The views are LIVE; the lever must not have snapshotted the parent."""
    got, want = _build(fnx, cls), _build(nx, cls)
    fv, xv = _views(fnx, got), _views(nx, want)
    got.remove_node("n0")
    want.remove_node("n0")
    got.add_edge("fresh", "n3")
    want.add_edge("fresh", "n3")
    for label in fv:
        assert [str(n) for n in fv[label]] == [
            str(n) for n in xv[label]
        ], f"{cls}/{label}: diverged after the parent mutated"


@pytest.mark.parametrize("cls", CLASSES)
def test_membership_still_rejects_nodes_outside_the_parent(cls):
    """_node_visible keeps its membership half for callers that need it."""
    got, want = _build(fnx, cls), _build(nx, cls)
    fv, xv = _views(fnx, got), _views(nx, want)
    for label in fv:
        for probe in ("n0", "n7", "isolated", "never_added", ""):
            assert (probe in fv[label]) == (
                probe in xv[label]
            ), f"{cls}/{label}: containment of {probe!r} diverged"


def _count_filter_calls(lib, cls, consume):
    """Run ``consume`` over a counting-filtered view; return (calls, result)."""
    g = _build(lib, cls)
    calls = []
    view = lib.subgraph_view(g, filter_node=lambda n: (calls.append(n), True)[1])
    # Consume FIRST and bind it, then read the counter. Returning the tuple
    # directly reads len(calls) before consume() has run - it reported 0 calls.
    result = consume(view)
    return len(calls), result, len(g)


@pytest.mark.parametrize("cls", CLASSES)
def test_iteration_alone_calls_the_filter_once_per_node(cls):
    """THE LEVER, as behaviour: ONE predicate call per node for a bare walk.

    Deliberately not ``list(view)``. ``list()`` asks for a length hint first, and
    the ``__len__`` fallback for a non-default filter is its own O(N) walk - so
    ``list()`` legitimately costs two passes, in networkx as well. That is the
    next test. This one pins the walk itself.
    """
    calls, yielded, parent_nodes = _count_filter_calls(
        fnx, cls, lambda view: [node for node in iter(view)]
    )
    assert len(yielded) == parent_nodes
    assert calls == parent_nodes, (
        f"{cls}: node filter ran {calls} times for {parent_nodes} nodes - "
        "a second filtering pass has come back"
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "consume",
    [lambda v: list(v), lambda v: [n for n in iter(v)], lambda v: len(v)],
    ids=["list", "iterate", "len"],
)
def test_filter_is_not_called_more_often_than_networkx(cls, consume):
    """The comparative bound, which does not depend on CPython's length hint.

    networkx applies its own node filter inside ``FilterAtlas``; whatever the
    interpreter asks for, fnx must not apply the predicate MORE times than
    networkx does for the same operation.
    """
    fnx_calls, _, _ = _count_filter_calls(fnx, cls, consume)
    nx_calls, _, _ = _count_filter_calls(nx, cls, consume)
    assert fnx_calls <= nx_calls, (
        f"{cls}: fnx applied the node filter {fnx_calls} times where networkx "
        f"used {nx_calls}"
    )


@pytest.mark.parametrize("cls", CLASSES)
def test_a_rejecting_filter_still_excludes(cls):
    """One call per node must not mean the answer is ignored."""
    g = _build(fnx, cls)
    x = _build(nx, cls)
    hidden = {"n1", "n2", "isolated"}
    fv = fnx.subgraph_view(g, filter_node=lambda n: str(n) not in hidden)
    xv = nx.subgraph_view(x, filter_node=lambda n: str(n) not in hidden)
    assert [str(n) for n in fv] == [str(n) for n in xv]
    assert not any(str(n) in hidden for n in fv)
    assert len(fv) == len(xv)


@pytest.mark.parametrize("cls", CLASSES)
def test_default_node_filter_yields_the_parent_exactly(cls):
    """The default-filter path returns the parent's own iteration."""
    got, want = _build(fnx, cls), _build(nx, cls)
    fv = fnx.subgraph_view(got)
    xv = nx.subgraph_view(want)
    assert [str(n) for n in fv] == [str(n) for n in got]
    assert [str(n) for n in fv] == [str(n) for n in xv]
    got.add_node("added_after_the_view")
    want.add_node("added_after_the_view")
    assert [str(n) for n in fv] == [str(n) for n in xv]


@pytest.mark.parametrize("cls", CLASSES)
def test_short_circuit_branch_still_checks_membership(cls):
    """THE CONTROL: nodes from the FILTER need the check the loop dropped.

    ``subgraph`` on a small node set takes the branch that iterates the filter
    rather than the parent. Those nodes did not come from the parent, so
    membership is real work there - name absent ones and they must not appear.
    """
    got, want = _build(fnx, cls, n=40), _build(nx, cls, n=40)
    asked = ["n0", "n1", "ghost_a", "ghost_b", "n2"]
    fv, xv = got.subgraph(asked), want.subgraph(asked)
    assert [str(n) for n in fv] == [str(n) for n in xv]
    assert not any(str(n).startswith("ghost") for n in fv)
    assert len(fv) == len(xv) == 3
