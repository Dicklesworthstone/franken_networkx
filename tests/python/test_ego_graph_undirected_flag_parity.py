"""br-r37-c1-77okh — `undirected=True` must be honoured, and honoured first.

networkx branches on `undirected` BEFORE `distance`:

    if undirected:
        ... single_source_{dijkstra,shortest_path_length}(G.to_undirected(), ...)
    else:
        ... the same two over G

fnx had the tests the other way round, so `undirected` was consulted only when
`distance` was None AND the graph was directed. Two consequences.

THE SERIOUS ONE — with a `distance=` given, `undirected` was ignored entirely, so
a directed graph searched out-edges only and LOST NODES:

    D: a->b, c->a, b->d
    ego_graph(D, 'a', radius=2.0, distance='weight', undirected=True)
    networkx -> ['a', 'b', 'c']        fnx -> ['a', 'b']      'c' vanished

That is a wrong ANSWER, not a wrong order, and it is what this file mainly
guards.

THE SUBTLER ONE — on an already-undirected graph, `undirected=True` sent fnx
down a plain BFS over G while networkx searches `G.to_undirected()`, whose node
insertion order can differ. The ego node order is set-iteration order
(br-r37-c1-mqq4m), so node and edge ORDER diverged on 1-6 of 18 cases at every
PYTHONHASHSEED.

A RESIDUAL REMAINS AND IS PINNED, NOT HIDDEN. After this fix the node SETS agree
everywhere, but ordering still diverges in a minority of cases. That is
br-r37-c1-g7vr8: fnx's `single_source_shortest_path_length` returns its keys in a
different order than networkx's, and ego_graph consumes that order. The fix here
deliberately calls that function rather than hand-rolling a BFS, so when g7vr8
lands this residual closes with it and nothing here needs changing.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]
ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name, order, seed):
    rnd = random.Random(seed)
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for _ in range(order * 2):
        u, v = f"n{rnd.randrange(order)}", f"n{rnd.randrange(order)}"
        weight = float(rnd.randrange(1, 6))
        gnx.add_edge(u, v, weight=weight)
        gfx.add_edge(u, v, weight=weight)
    return gnx, gfx


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_undirected_with_distance_no_longer_loses_nodes(cls_name):
    """The wrong-ANSWER case, minimal and explicit.

    'c' reaches 'a' only against the edge direction, so it is in the ego graph
    exactly when `undirected=True` is honoured.
    """
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("c", "a", weight=1.0)
        graph.add_edge("b", "d", weight=5.0)
        ego = lib.ego_graph(
            graph, "a", radius=2.0, distance="weight", undirected=True
        )
        results.append(sorted(ego.nodes()))
    assert results[1] == results[0], cls_name
    assert "c" in results[0], "fixture no longer exercises the reverse direction"


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("distance", [None, "weight"])
@pytest.mark.parametrize("center", [True, False])
@pytest.mark.parametrize("seed", [0, 2, 4])
def test_ego_node_SET_matches_networkx_for_every_flag_combination(
    cls_name, distance, center, seed
):
    """The invariant that must hold unconditionally.

    Ordering is a separate, still-open concern (br-r37-c1-g7vr8); membership is
    not, and membership is what a wrong `undirected` gate breaks.
    """
    gnx, gfx = _pair(cls_name, 60, seed)
    for undirected in (False, True):
        for radius in ((1, 2, 3) if distance is None else (2.0, 5.0)):
            kwargs = {
                "radius": radius,
                "undirected": undirected,
                "center": center,
                "distance": distance,
            }
            want = nx.ego_graph(gnx, "n7", **kwargs)
            got = fnx.ego_graph(gfx, "n7", **kwargs)
            assert set(got.nodes()) == set(want.nodes()), (
                cls_name,
                distance,
                undirected,
                radius,
            )
            assert {frozenset(e[:2]) for e in got.edges()} == {
                frozenset(e[:2]) for e in want.edges()
            }


@pytest.mark.parametrize(
    "cls_name,distance",
    [
        ("DiGraph", None),
        ("DiGraph", "weight"),
        ("MultiDiGraph", None),
        pytest.param(
            "MultiDiGraph",
            "weight",
            marks=pytest.mark.skip(
                reason="br-r37-c1-4q95e: _raw_mdg_ss_dijkstra_path_length PANICS "
                "with a stale index once other graphs exist in the process. "
                "PRE-EXISTING — reproduced on an unmodified HEAD. Un-skip when "
                "that bead lands; this combination is otherwise in scope here."
            ),
        ),
    ],
)
def test_undirected_true_reaches_strictly_more_than_false(cls_name, distance):
    """A behavioural check that does not depend on networkx at all.

    If the flag were still ignored these two would be equal, which is how the
    bug looked from the outside.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("c", "a", weight=1.0)
    radius = 2.0 if distance else 1
    forward = set(
        fnx.ego_graph(
            graph, "a", radius=radius, distance=distance, undirected=False
        ).nodes()
    )
    both = set(
        fnx.ego_graph(
            graph, "a", radius=radius, distance=distance, undirected=True
        ).nodes()
    )
    assert forward < both, (cls_name, distance, forward, both)
    assert "c" in both and "c" not in forward


@pytest.mark.parametrize("cls_name", ALL)
def test_undirected_search_does_not_change_which_graph_edges_come_from(cls_name):
    """networkx searches the undirected copy but builds H from the ORIGINAL G.

    So on a directed graph the resulting ego graph is still DIRECTED and its
    edges keep their original orientation. Searching and building must not be
    conflated.
    """
    gnx, gfx = _pair(cls_name, 40, seed=1)
    want = nx.ego_graph(gnx, "n3", radius=2, undirected=True)
    got = fnx.ego_graph(gfx, "n3", radius=2, undirected=True)
    assert got.is_directed() == want.is_directed()
    assert got.is_multigraph() == want.is_multigraph()
    # Orientation is NORMALISED for undirected graphs. An earlier draft compared
    # raw tuples and failed on some hash seeds: for an undirected graph an edge
    # is reported as (u, v) or (v, u) depending on which endpoint the node order
    # reaches first, and sorting tuples does not normalise that. The point of
    # this test is WHICH graph the edges come from, not their orientation, and
    # the ordering itself is br-r37-c1-g7vr8's residue.
    def _key(edge):
        head = edge[:2] if want.is_directed() else tuple(sorted(edge[:2]))
        return head + tuple(edge[2:])

    assert sorted(map(_key, got.edges())) == sorted(map(_key, want.edges()))


def test_the_ordering_residual_is_the_shortest_path_key_order_bead():
    """br-r37-c1-g7vr8, pinned so the remaining gap is on the record.

    fnx's single_source_shortest_path_length agrees with networkx on CONTENT and
    differs on KEY ORDER. ego_graph consumes that order via set(sp), so its
    ordering residual is downstream of it. Asserting the content equality here
    documents precisely which half is sound.
    """
    rnd = random.Random(0)
    gnx, gfx = nx.Graph(), fnx.Graph()
    for _ in range(120):
        u, v = f"n{rnd.randrange(60)}", f"n{rnd.randrange(60)}"
        gnx.add_edge(u, v)
        gfx.add_edge(u, v)
    want = dict(nx.single_source_shortest_path_length(gnx.to_undirected(), "n7"))
    got = dict(fnx.single_source_shortest_path_length(gfx.to_undirected(), "n7"))
    assert got == want, "distances must agree even while key order does not"
    if list(got) != list(want):
        return  # the known residue; nothing to assert beyond content
    pytest.skip(
        "key order matched at this PYTHONHASHSEED; br-r37-c1-g7vr8 is "
        "seed-dependent, so this is not evidence of a fix"
    )
