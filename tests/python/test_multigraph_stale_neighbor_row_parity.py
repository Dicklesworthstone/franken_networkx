"""A live neighbour row must gain every edge added at its node.

``G.neighbors(u)``, ``G.adj[u]`` / ``G[u]`` iteration, subgraph views and
copies, and ``connected_components`` all read the multigraph's cached neighbour
rows. Those rows are created by the first walk over a node's neighbours (a
keydict walk, ``neighbors``, ``deepcopy``, ``to_directed()``, ...), are kept
up to date in place by each edge mutation, and are then re-stamped to the
current graph generation.

Two mutation paths added edges without touching the live rows:

* ``MultiGraph.add_edge(u, v, key=k)`` with int endpoints, an explicit int or
  str key, no attributes and a pair that had no edge yet (a native fast path);
* the native ``add_edges_from`` batches (8 or more edges into a graph that has
  nodes but no edges), on MultiGraph and MultiDiGraph.

Each only bumped the generation, which leaves the rows stale but detectable.
The next ordinary ``add_edge`` / ``remove_edge`` then re-stamped them as
current, and from then on the node's row silently lacked the new neighbour:
``G.adj[1]`` and ``neighbors(1)`` missed it while ``edges()``, ``has_edge`` and
``degree`` saw it, ``subgraph(...).copy()`` lost the edge for good, and
``connected_components`` returned overlapping components.

Every comparison below is against networkx itself, in the same process.
"""

from __future__ import annotations

import copy

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph", "Graph", "DiGraph"]


def _walk_values(G):
    return [list(nbrs.values()) for nbrs in G.adj.values()]


def _walk_private_values(G):
    return [list(nbrs.values()) for nbrs in G._adj.values()]


def _walk_keydict_items(G):
    return [list(cell.items()) for nbrs in G.adj.values() for cell in nbrs.values()]


# Reads that create (arm) the row for node 1, then reads that must not matter.
ARMS = {
    "row_keydicts": lambda G: [dict(cell) for cell in G[1].values()],
    "adj_values_walk": _walk_values,
    "private_adj_values_walk": _walk_private_values,
    "keydict_items_walk": _walk_keydict_items,
    "neighbors": lambda G: list(G.neighbors(1)),
    "adj_row_iter": lambda G: list(G.adj[1]),
    "deepcopy": copy.deepcopy,
    "to_directed": lambda G: G.to_directed(),
    "to_undirected": lambda G: G.to_undirected(),
    # controls: no row walk
    "nothing": lambda G: None,
    "one_cell": lambda G: dict(G[1][0]),
    "get_edge_data": lambda G: G.get_edge_data(0, 1),
    "copy": lambda G: G.copy(),
    "edges_data": lambda G: list(G.edges(data=True)),
}

# The new edge at node 1. On Graph/DiGraph ``key=`` is an ordinary edge
# attribute, in networkx and here alike.
KEYS = {"key_int_0": 0, "key_int_7": 7, "key_str": "s", "no_key": None}

# What happens after it. The re-stamp that hid the stale row came from the
# next ordinary add or remove anywhere in the graph.
FOLLOWUPS = {
    "add_elsewhere": lambda G: G.add_edge(3, 4),
    "add_and_remove_elsewhere": lambda G: (G.add_edge(5, 6), G.remove_edge(5, 6)),
    "add_parallel_on_row": lambda G: G.add_edge(0, 1),
    "nothing": lambda G: None,
}


def _edges(G):
    if G.is_multigraph():
        return list(G.edges(keys=True, data=True))
    return list(G.edges(data=True))


def _components(lib, G):
    if G.is_directed():
        return [set(c) for c in lib.weakly_connected_components(G)]
    return [set(c) for c in lib.connected_components(G)]


def _observe(lib, G):
    nodes = list(G)
    sub = G.subgraph(nodes)
    out = {
        "adjacency": {n: list(G.adj[n]) for n in nodes},
        "getitem": {n: list(G[n]) for n in nodes},
        "neighbors": {n: list(G.neighbors(n)) for n in nodes},
        "subgraph_view_edges": _edges(sub),
        "subgraph_copy_edges": _edges(sub.copy()),
        "components": _components(lib, G),
        "degree": list(G.degree()),
        "has_edge": [G.has_edge(1, 2), G.has_edge(2, 1)],
        "edges": _edges(G),
    }
    if G.is_directed():
        out["predecessors"] = {n: list(G.predecessors(n)) for n in nodes}
    return out


def _add_keyed(G, key):
    if key is None:
        G.add_edge(1, 2)
    else:
        G.add_edge(1, 2, key=key)


def _seeded(lib, cls_name):
    """Node 1 with one neighbour, 0. A directed graph also needs 1 -> 0 so
    that node 1's successor row is not empty."""
    G = getattr(lib, cls_name)()
    G.add_edge(0, 1)
    if G.is_directed():
        G.add_edge(1, 0)
    return G


def _keyed_scenario(lib, cls_name, arm, key, followup):
    G = _seeded(lib, cls_name)
    ARMS[arm](G)
    _add_keyed(G, key)
    FOLLOWUPS[followup](G)
    return _observe(lib, G)


@pytest.mark.parametrize("followup", list(FOLLOWUPS))
@pytest.mark.parametrize("key", list(KEYS))
@pytest.mark.parametrize("arm", list(ARMS))
@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_sees_the_new_edge_after_any_arming_read(cls_name, arm, key, followup):
    expected = _keyed_scenario(nx, cls_name, arm, KEYS[key], followup)
    actual = _keyed_scenario(fnx, cls_name, arm, KEYS[key], followup)
    assert actual == expected


def test_the_reported_multigraph_sequence():
    """The minimal public-API sequence, spelled out."""
    results = []
    for lib in (fnx, nx):
        G = lib.MultiGraph()
        G.add_edge(0, 1)
        [dict(cell) for cell in G[1].values()]
        G.add_edge(1, 2, key=0)
        G.add_edge(3, 4)
        results.append(
            (
                sorted(G.adj[1]),
                sorted(G.neighbors(1)),
                sorted(map(sorted, lib.connected_components(G))),
                G.subgraph(list(G)).number_of_edges(),
                G.subgraph(list(G)).copy().number_of_edges(),
            )
        )
    assert results[0] == results[1] == (
        [0, 2],
        [0, 2],
        [[0, 1, 2], [3, 4]],
        3,
        3,
    )


@pytest.mark.parametrize("key", list(KEYS))
@pytest.mark.parametrize("cls_name", CLASSES)
def test_open_neighbors_iterator_sees_the_new_edge(cls_name, key):
    """networkx's ``neighbors`` iterates the live row dict, so an edge added at
    that node mid-iteration raises; the fast path used to leave the row alone
    and the iterator finished silently."""

    def drive(lib):
        G = _seeded(lib, cls_name)
        it = G.neighbors(1)
        first = next(it)
        _add_keyed(G, KEYS[key])
        try:
            return ("completed", first, list(it))
        except RuntimeError as err:
            return ("RuntimeError", first, str(err))

    assert drive(fnx) == drive(nx)


BATCHES = {
    "plain": [(i, i + 1) for i in range(10)],
    "data": [(i, i + 1, {"w": i}) for i in range(10)],
    "str_key": [(i, i + 1, "k") for i in range(10)],
    "int_key": [(i, i + 1, 0) for i in range(10)],
    "int_key_data": [(i, i + 1, 0, {}) for i in range(10)],
    "str_key_data": [(i, i + 1, "k", {"w": 1}) for i in range(10)],
}


def _simple_bunch(bunch):
    # A simple graph reads a 3-tuple's third element as data, so give it
    # data where the multigraph shape carries a key.
    out = []
    for edge in bunch:
        if len(edge) == 2:
            out.append(edge)
        else:
            data = edge[-1] if isinstance(edge[-1], dict) else {}
            out.append((edge[0], edge[1], data))
    return out


def _batch_scenario(lib, cls_name, shape, with_attr):
    G = getattr(lib, cls_name)()
    G.add_nodes_from(range(12))
    list(G.neighbors(1))
    if G.is_directed():
        list(G.predecessors(2))
    bunch = BATCHES[shape] if G.is_multigraph() else _simple_bunch(BATCHES[shape])
    if with_attr:
        G.add_edges_from(bunch, color="red")
    else:
        G.add_edges_from(bunch)
    G.add_edge(50, 51)
    return _observe(lib, G)


@pytest.mark.parametrize("with_attr", [False, True], ids=["no_attr", "attr"])
@pytest.mark.parametrize("shape", list(BATCHES))
@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_read_on_an_edgeless_graph_sees_a_batch_of_edges(cls_name, shape, with_attr):
    expected = _batch_scenario(nx, cls_name, shape, with_attr)
    actual = _batch_scenario(fnx, cls_name, shape, with_attr)
    assert actual == expected


@pytest.mark.parametrize("key", [0, 7, "s"])
def test_internal_unhashed_row_cursor_sees_the_fast_path_edge(key):
    """The private cursor that callback-sensitive algorithms iterate keeps no
    generation stamp at all, so a missed update there was permanent."""
    G = fnx.MultiGraph()
    G.add_edge(0, 1)
    list(type(G)._fnx_unhashed_neighbors_iter(G, 1))
    G.add_edge(1, 2, key=key)
    assert list(type(G)._fnx_unhashed_neighbors_iter(G, 1)) == [0, 2]
    assert list(type(G)._fnx_unhashed_neighbors_iter(G, 2)) == [1]
