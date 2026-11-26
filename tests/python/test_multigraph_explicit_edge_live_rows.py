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
