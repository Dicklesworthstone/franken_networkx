"""br-r37-c1-aq6jv — the nbunch py-walk threshold is a floor, not a constant.

``G.edges(nbunch)`` on a simple Graph picks between a native kernel and a pure
Python walk over the live adjacency rows. The choice used to be a fixed nbunch
size of 8. But the kernel is O(graph order) while the walk is O(nbunch), so the
crossover moves with the graph: measured, the walk is slower than the kernel at
every size at N=2000 and faster than it at every size tested at N=32000. A fixed
threshold is therefore only correct near the graph size it was tuned on.

The limit now scales with the graph's order, and only ever RISES above the old
floor. That direction matters for more than speed: the module note on
``_EDGES_NBUNCH_PY_WALK_MAX`` records that lowering it to 0 resurrects the
br-r37-c1-u5tyh over-raise on Graph and DiGraph, because the Python walk is what
reproduces networkx's mutate-during-iteration semantics. Routing MORE calls onto
the walk moves toward networkx, never away.

So the two things worth locking are that the two routes agree on their answers,
and that a size which is now routed to the walk still behaves like networkx when
the graph is mutated mid-iteration.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(lib, order):
    graph = lib.Graph()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}")
    return graph


def _canonical(edges):
    return sorted(tuple(sorted(edge[:2])) + tuple(edge[2:]) for edge in edges)


@pytest.mark.parametrize("order", [50, 500, 2000, 9000])
@pytest.mark.parametrize("size", [1, 4, 8, 9, 16, 33])
@pytest.mark.parametrize("data", [False, True], ids=["nodata", "data"])
def test_both_routes_return_what_networkx_returns(order, size, data):
    """Whichever side of the threshold this lands on, the answer is nx's."""
    gnx, gfx = _build(nx, order), _build(fnx, order)
    nbunch = [f"n{i}" for i in range(size)]
    assert _canonical(gfx.edges(nbunch, data=data)) == _canonical(
        gnx.edges(nbunch, data=data)
    )


@pytest.mark.parametrize("order", [50, 2000, 9000])
@pytest.mark.parametrize("size", [4, 9, 16, 33])
def test_the_two_routes_agree_with_each_other(order, size):
    """Force each route on the SAME graph and compare.

    This is the assertion the threshold change actually rests on: moving a call
    from one side to the other must be invisible. Comparing each route to
    networkx separately would not catch a case where both drifted together.
    """
    graph = _build(fnx, order)
    nbunch = [f"n{i}" for i in range(size)]
    original = fnx._EDGES_NBUNCH_PY_WALK_MAX
    try:
        fnx._EDGES_NBUNCH_PY_WALK_MAX = 0
        kernel = _canonical(graph.edges(nbunch))
        fnx._EDGES_NBUNCH_PY_WALK_MAX = 10**9
        walk = _canonical(graph.edges(nbunch))
    finally:
        fnx._EDGES_NBUNCH_PY_WALK_MAX = original
    assert walk == kernel, (order, size)
    assert kernel == _canonical(_build(nx, order).edges(nbunch))


def test_the_limit_is_a_floor_and_rises_with_order():
    limit = fnx._edges_nbunch_py_walk_limit
    assert limit(_build(fnx, 50)) == fnx._EDGES_NBUNCH_PY_WALK_MAX
    assert limit(_build(fnx, 2000)) == fnx._EDGES_NBUNCH_PY_WALK_MAX
    small, large = limit(_build(fnx, 9000)), limit(_build(fnx, 40000))
    assert small > fnx._EDGES_NBUNCH_PY_WALK_MAX
    assert large > small, (small, large)


def test_the_limit_never_drops_below_the_floor_on_an_odd_graph():
    """A graph that cannot answer number_of_nodes keeps the fixed floor.

    The helper must degrade to the old constant rather than raising, because it
    sits on the hot path of every nbunch edges() call.
    """

    class Awkward:
        def number_of_nodes(self):
            raise RuntimeError("no order for you")

    assert (
        fnx._edges_nbunch_py_walk_limit(Awkward()) == fnx._EDGES_NBUNCH_PY_WALK_MAX
    )


@pytest.mark.parametrize("size", [4, 9, 16])
def test_mutation_during_iteration_still_matches_networkx(size):
    """The correctness half: sizes now routed to the walk must behave like nx.

    The graph is large enough that the scaled limit sends these onto the Python
    walk, which is exactly the route the u5tyh note says is the nx-faithful one.
    Adding an edge between two BRAND NEW nodes is legal in networkx during an
    nbunch iteration, and must stay legal here.
    """
    order = 20000
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, order)
        nbunch = [f"n{i}" for i in range(size)]
        try:
            seen = 0
            for _edge in graph.edges(nbunch):
                seen += 1
                if seen == 1:
                    graph.add_edge("brand", "new")
            results.append(("completes", seen))
        except RuntimeError:
            results.append(("RuntimeError",))
    assert results[1] == results[0], results


def test_a_removed_nbunch_node_still_raises_like_networkx():
    """br-r37-c1-2pia7's frozen-nbunch contract survives the wider walk."""
    order = 20000
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, order)
        view = graph.edges([f"n{i}" for i in range(12)])
        graph.remove_node("n3")
        try:
            results.append(("completes", len(list(view))))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__,))
    assert results[1][0] == results[0][0], results
