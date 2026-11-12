"""br-r37-c1-xpilu - MultiGraph / MultiDiGraph.add_edges_from returns the keys it gave.

networkx documents and returns ``keylist``: one key per ebunch entry, in order - an
explicit key echoed, a (u, v) or (u, v, data) entry given new_edge_key (len of the
pair's keydict, bumped past keys already taken). fnx returned None on every path, so
``keys = G.add_edges_from(...)`` then using the keys raised TypeError. The upstream
suite never asserts the return (its doctests only assign it).

Every row compares the returned list (and the resulting graph) with networkx, across
the paths that answer: the fresh-graph native batches (plain pairs, attributed
3-tuples, exact-str keys, explicit int 4-tuples, 4-tuples onto existing nodes), the
per-edge loop (pre-populated graphs, mixed shapes, tiny bunches), and the per-edge
path for an ebunch that reads the graph.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ("MultiGraph", "MultiDiGraph")
PAIRS = [(i % 4, (i * 3) % 5) for i in range(12)]


def _fresh(lib, cls):
    return getattr(lib, cls)()


def _populated(lib, cls):
    graph = getattr(lib, cls)()
    graph.add_edge(0, 3, key=0)
    graph.add_edge(0, 3, key=2)  # a naive len(keydict) key (2) would collide here
    graph.add_edge(1, 3, key="x")
    return graph


def _with_nodes(lib, cls):
    graph = getattr(lib, cls)()
    graph.add_nodes_from(range(6))
    return graph


BUNCHES = {
    "plain pairs": lambda: list(PAIRS),
    "plain pairs, tuple": lambda: tuple(PAIRS),
    "tiny": lambda: [(0, 3), (0, 3), (3, 0)],
    "attributed": lambda: [(u, v, {"w": i}) for i, (u, v) in enumerate(PAIRS)],
    "mixed 2- and 3-tuples": lambda: [
        (u, v) if i % 2 else (u, v, {"w": i}) for i, (u, v) in enumerate(PAIRS)
    ],
    "str keys": lambda: [(u, v, f"k{i}") for i, (u, v) in enumerate(PAIRS)],
    # br-r37-c1-75sg9: both must decline the str-keyed batch - a repeated
    # (u, v, key) updates the first edge, and an empty str third is DATA
    "str keys, a duplicate": lambda: [(u, v, f"k{i % 6}") for i, (u, v) in enumerate(PAIRS)]
    + [(0, 3, "k0")],
    "str keys, one empty": lambda: [(u, v, f"k{i}") for i, (u, v) in enumerate(PAIRS)] + [(0, 3, "")],
    "int 4-tuples": lambda: [(u, v, 10 + i, {"w": i}) for i, (u, v) in enumerate(PAIRS)],
    "mixed explicit and auto": lambda: [(0, 3), (0, 3, 1), (0, 3), (0, 3, "k", {"c": 1}), (0, 3)],
    "generator": lambda: (e for e in PAIRS),
}
GRAPHS = {"fresh": _fresh, "populated": _populated, "nodes only": _with_nodes}


def _state(graph):
    return sorted(map(repr, graph.edges(keys=True, data=True)))


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("graph_kind", sorted(GRAPHS))
@pytest.mark.parametrize("bunch", sorted(BUNCHES))
def test_add_edges_from_returns_networkx_keys(cls, graph_kind, bunch):
    expected_graph = GRAPHS[graph_kind](nx, cls)
    actual_graph = GRAPHS[graph_kind](fnx, cls)
    expected = expected_graph.add_edges_from(BUNCHES[bunch]())
    actual = actual_graph.add_edges_from(BUNCHES[bunch]())
    assert type(actual) is list
    assert actual == expected
    assert _state(actual_graph) == _state(expected_graph)


@pytest.mark.parametrize("cls", CLASSES)
def test_broadcast_attr_batch_returns_networkx_keys(cls):
    expected = getattr(nx, cls)().add_edges_from(list(PAIRS), weight=2)
    actual = getattr(fnx, cls)().add_edges_from(list(PAIRS), weight=2)
    assert actual == expected


@pytest.mark.parametrize("cls", CLASSES)
def test_graph_reading_generator_returns_networkx_keys(cls):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)()
        graph.add_edge(0, 1)
        keys = graph.add_edges_from(
            (u, v) for u, v in [(0, 1), (0, 1), (1, 2), (0, 1)] if graph.number_of_edges(u, v) < 2
        )
        results.append((keys, _state(graph)))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls", CLASSES)
def test_empty_ebunch_returns_empty_list(cls):
    assert getattr(fnx, cls)().add_edges_from([]) == getattr(nx, cls)().add_edges_from([]) == []


# br-r37-c1-lesqm: the plain-pair batch takes a graph that already has edges -
# each pair's next key is networkx's new_edge_key over the keys it holds, and
# existing nodes stay where they are - so the ORDER of everything, not only the
# edge set, is compared: nodes, every adjacency row (and pred row), each pair's
# keys, the edge walk. Graphs whose state the per-edge path maintains in place
# (a remapped int key, a held keydict, a live neighbour iterator, a node whose
# display object differs) keep the per-edge path and must match all the same.
GROW = [(0, 1), (1, 2), (0, 1), (5, 0), (2, 2), (7, 1), (0, 1), (1, 0), (8, 8), (2, 5), (0, 1), (9, 2)]


def _grown(build):
    def make(lib, cls):
        graph = getattr(lib, cls)()
        build(graph)
        return graph

    return make


EXISTING = {
    "batch-built, parallel": _grown(lambda g: g.add_edges_from([(0, 1), (0, 1), (1, 2), (2, 0), (1, 2), (3, 3), (0, 4), (4, 1)])),
    "add_edge-built": _grown(lambda g: [g.add_edge(u, v) for u, v in [(0, 1), (0, 1), (1, 2), (2, 0)]]),
    "a removed key's gap": _grown(
        lambda g: ([g.add_edge(0, 1) for _ in range(3)], g.remove_edge(0, 1, key=1), g.add_edge(1, 2))
    ),
    "key 0 removed": _grown(
        lambda g: ([g.add_edge(0, 1) for _ in range(3)], g.remove_edge(0, 1, key=0), g.add_edge(2, 1))
    ),
    "an explicit int key": _grown(lambda g: (g.add_edge(0, 1, key=5), g.add_edge(0, 1), g.add_edge(1, 2))),
    "a str key": _grown(lambda g: (g.add_edge(0, 1, key="a"), g.add_edge(0, 1), g.add_edge(2, 5))),
    "isolated nodes first": _grown(lambda g: (g.add_nodes_from([9, 8, 7]), g.add_edge(1, 0))),
    "self-loops": _grown(lambda g: (g.add_edge(2, 2), g.add_edge(2, 2), g.add_edge(0, 2))),
}


def _ordered_state(graph):
    rows = {n: [(m, list(graph.adj[n][m])) for m in graph.adj[n]] for n in graph}
    pred = {n: list(graph.pred[n]) for n in graph} if graph.is_directed() else None
    return list(graph), rows, pred, list(graph.edges(keys=True, data=True))


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("existing", list(EXISTING))
def test_a_batch_into_a_graph_with_edges_is_networkxs(cls, existing):
    results = []
    for lib in (nx, fnx):
        graph = EXISTING[existing](lib, cls)
        keys = graph.add_edges_from(list(GROW))
        again = graph.add_edges_from(tuple(GROW[::-1]))
        results.append((keys, again, _ordered_state(graph), graph.add_edge(0, 1)))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls", CLASSES)
def test_a_batch_reaches_a_held_keydict_and_a_live_neighbour_iterator(cls):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)([(0, 1), (0, 1), (1, 2)])
        held = graph[0][1]
        graph.add_edges_from(list(GROW))
        seen = sorted(held)
        live = iter(graph.neighbors(1))
        next(live)
        graph.add_edges_from([(1, 20 + i) for i in range(10)])
        try:
            next(live)
            outcome = "ok"
        except RuntimeError as exc:
            outcome = str(exc)
        results.append((seen, outcome, _ordered_state(graph)))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls", CLASSES)
def test_a_batch_whose_node_display_differs_matches_networkx(cls):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)([(1, 2), (2, 3)])
        keys = graph.add_edges_from([(1.0, 2), (True, 3)] + list(GROW))
        results.append((keys, _ordered_state(graph), [type(n).__name__ for n in graph]))
    assert results[1] == results[0]
