"""``edges(data=True)`` must reflect every mutation on the NEXT call.

br-r37-c1-ml7s5. Landed AHEAD of the whole-list cache, because that cache is the
change most likely to break this and the breakage is silent.

WHY THIS IS THE NEXT LEVER. ``PyMultiGraph`` caches its materialised
``edges(data=True)`` tuples under ``(nodes_seq, edges_seq, keys)`` and returns
``clone_ref``s on a hit (br-r37-c1-o07ax). ``PyGraph`` has no such cache: the
no-nbunch path calls ``edge_alldata_items(py, &mut g, None)`` and rebuilds every
tuple on every call. That is a Graph-vs-MultiGraph asymmetry on the same
operation, the same shape as the directed/undirected asymmetries that produced
the last two fixes on this surface.

WHAT A CACHE GETS WRONG. A whole-list cache is only correct if EVERY mutation
that can change the answer also moves the key it is stamped with. The generation
counters are the load-bearing part:

  * ``add_edge`` / ``remove_edge`` move ``edges_seq``
  * ``add_node`` / ``remove_node`` move ``nodes_seq``
  * an ATTRIBUTE write moves NEITHER — it mutates a live dict in place, and the
    cached tuples hold that same dict, so the value is visible without any
    invalidation at all. That is correct, and it is also the case that makes a
    cache look safe when it is not: it passes whether or not the stamps work.

So the attribute case is asserted separately from the structural ones, and the
structural ones are the real test.

Every expectation comes from live networkx in the same test, so this pins the
incumbent's contract rather than fnx's current behaviour, and it cannot rot
against a networkx upgrade.

These pass today — ``PyGraph`` has no cache to get wrong, and ``PyMultiGraph``'s
existing cache already satisfies them. That is the point: the guard is in place
before the change, so a regression is a failure rather than a discovery.
"""

from __future__ import annotations

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
# Straddle the 128-byte canonical stack buffer.
KEY_LENGTHS = [3, 200]


def _build(lib, cls_name: str, key_len: int):
    graph = getattr(lib, cls_name)()
    nodes = [f"n{i}".ljust(key_len, "q") for i in range(5)]
    for i in range(4):
        graph.add_edge(nodes[i], nodes[i + 1], weight=i)
    return graph, nodes


def _snapshot(graph):
    """Comparable, order-insensitive view of edges(data=True)."""
    return sorted(
        (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in graph.edges(data=True)
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_added_edge_appears_on_the_next_call(cls_name, key_len):
    """edges_seq must move. A stale list silently omits the new edge."""
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, key_len)
        graph.edges(data=True)  # materialise, warming any cache
        before = _snapshot(graph)
        graph.add_edge(nodes[0], nodes[4], weight=99)
        after = _snapshot(graph)
        assert len(after) == len(before) + 1, (
            f"{lib.__name__} {cls_name} @{key_len}: the added edge did not appear "
            "on the next edges(data=True)"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_removed_edge_disappears_on_the_next_call(cls_name, key_len):
    """The dangerous direction: a stale list REPORTS AN EDGE THAT IS GONE."""
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, key_len)
        graph.edges(data=True)
        before = _snapshot(graph)
        graph.remove_edge(nodes[0], nodes[1])
        after = _snapshot(graph)
        assert len(after) == len(before) - 1, (
            f"{lib.__name__} {cls_name} @{key_len}: a removed edge still appears "
            "in edges(data=True)"
        )
        assert all(not (u == str(nodes[0]) and v == str(nodes[1])) for u, v, _ in after)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_node_removal_is_reflected(cls_name, key_len):
    """nodes_seq must move — removing a node drops its incident edges."""
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, key_len)
        graph.edges(data=True)
        graph.remove_node(nodes[2])
        after = _snapshot(graph)
        assert all(str(nodes[2]) not in (u, v) for u, v, _ in after), (
            f"{lib.__name__} {cls_name} @{key_len}: edges incident to a removed "
            "node survived in edges(data=True)"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_attribute_write_is_visible_without_any_invalidation(cls_name):
    """The case that passes whether or not the stamps work.

    An attribute write moves NEITHER generation counter. It is visible only
    because the cached tuples hold the graph's LIVE dict. Asserted separately so
    a reader does not mistake it for evidence that invalidation is correct.
    """
    for lib in (nx, fnx):
        graph, nodes = _build(lib, cls_name, 200)
        graph.edges(data=True)
        if graph.is_multigraph():
            graph[nodes[0]][nodes[1]][0]["weight"] = "rewritten"
        else:
            graph[nodes[0]][nodes[1]]["weight"] = "rewritten"
        found = [
            d for u, v, d in graph.edges(data=True) if {u, v} == {nodes[0], nodes[1]}
        ]
        assert found and found[0]["weight"] == "rewritten", (
            f"{lib.__name__} {cls_name}: an attribute write was not visible in a "
            "later edges(data=True)"
        )


def test_warmed_graph_edge_data_iterator_fails_fast_on_a_new_node():
    """The cached fast iterator must retain NetworkX's live-node guard.

    A tuple/list iterator would be faster but silently drain a pre-mutation
    snapshot.  NetworkX's dict-backed edge-data iterator instead raises once a
    new node changes the outer adjacency mapping; warming the cache first makes
    this specifically exercise the cached path.
    """
    for lib in (nx, fnx):
        graph, nodes = _build(lib, "Graph", 200)
        list(graph.edges(data=True))
        iterator = iter(graph.edges(data=True))
        next(iterator)
        graph.add_edge(nodes[0], "new-node".ljust(200, "q"), weight=99)
        with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
            next(iterator)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", KEY_LENGTHS)
def test_matches_networkx_after_a_mutation_sequence(cls_name, key_len):
    """Differential end-to-end: the same sequence must land in the same place."""
    fnx_graph, nodes = _build(fnx, cls_name, key_len)
    nx_graph, _ = _build(nx, cls_name, key_len)
    for graph in (fnx_graph, nx_graph):
        graph.edges(data=True)  # warm
        graph.add_edge(nodes[0], nodes[4], weight=99)
        graph.remove_edge(nodes[1], nodes[2])
        graph.add_node("isolated".ljust(key_len, "q"))
        graph.remove_node(nodes[3])
    assert _snapshot(fnx_graph) == _snapshot(nx_graph)
