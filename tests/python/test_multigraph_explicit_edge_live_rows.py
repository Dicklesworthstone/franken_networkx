"""A fresh explicit-key edge must update rows already exposed to Python."""

import copy

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "read",
    [
        lambda g: [dict(keys) for keys in g[1].values()],
        lambda g: [list(row.values()) for row in g.adj.values()],
        lambda g: [list(row.values()) for row in g._adj.values()],
        lambda g: [list(keys.items()) for row in g.adj.values() for keys in row.values()],
        copy.deepcopy,
        lambda g: g.to_directed(),
        lambda g: g.to_undirected(),
    ],
    ids=["row-values", "adj-values", "private-values", "key-items", "deepcopy", "directed", "undirected"],
)
def test_explicit_key_insert_survives_later_mutation(class_name, read):
    def observe(lib):
        graph = getattr(lib, class_name)()
        graph.add_edge(0, 1)
        read(graph)
        graph.add_edge(1, 2, key=7)
        graph.add_edge(3, 4)
        view = graph.subgraph(list(graph))
        components = (
            lib.weakly_connected_components if graph.is_directed() else lib.connected_components
        )
        return (
            list(graph.adj[1]),
            list(graph.neighbors(1)),
            sorted(view.edges(keys=True)),
            sorted(view.copy().edges(keys=True)),
            sorted(sorted(c) for c in components(graph)),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("key", [0, -1, "bridge"])
@pytest.mark.parametrize("endpoints", [(1, 2), (2, 1), (1, 1)])
def test_explicit_edge_invalidates_outstanding_neighbor_iterator(key, endpoints):
    for lib in (nx, fnx):
        graph = lib.MultiGraph()
        graph.add_edge(0, 1)
        neighbors = graph.neighbors(1)
        assert next(neighbors) == 0
        graph.add_edge(*endpoints, key=key)
        with pytest.raises(RuntimeError, match="dictionary changed size"):
            next(neighbors)


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("shape", ["pair", "data", "key", "key-data", "weighted", "update"])
def test_bulk_insert_updates_observed_empty_rows(class_name, shape):
    def observe(lib):
        graph = getattr(lib, class_name)()
        graph.add_nodes_from(range(11))
        targets = range(1, 11)
        row = graph.neighbors(0)
        reverse_row = graph.predecessors(1) if graph.is_directed() else graph.neighbors(1)
        if shape == "weighted":
            graph.add_weighted_edges_from([(0, v, 2) for v in targets])
        elif shape == "update":
            graph.update(edges=[(0, v, {"w": 2}) for v in targets])
        else:
            suffix = {
                "pair": (),
                "data": ({"w": 2},),
                "key": ("k",),
                "key-data": (7, {"w": 2}),
            }[shape]
            graph.add_edges_from([(0, v, *suffix) for v in targets])
        # Reading a fresh row before this mutation would refresh its cache
        # generation and mask the missing neighbors.
        graph.add_edge(20, 21)
        for iterator in (row, reverse_row):
            with pytest.raises(RuntimeError, match="dictionary changed size"):
                next(iterator)
        return (
            list(graph.neighbors(0)),
            list(graph.predecessors(1) if graph.is_directed() else graph.neighbors(1)),
            sorted(graph.subgraph(list(graph)).copy().edges(keys=True)),
        )

    assert observe(fnx) == observe(nx)
