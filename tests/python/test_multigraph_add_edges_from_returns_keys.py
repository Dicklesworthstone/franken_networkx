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
