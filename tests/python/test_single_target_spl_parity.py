"""Parity for the undirected single_target_shortest_path_length routing (br-r37-c1-sptlen).

For undirected graphs the distance from every node TO target equals the distance
FROM target, so single_target_shortest_path_length now routes to the native
single_source kernel (~2.5x faster than networkx) instead of a per-node Python
reverse BFS (~6x slower). Hop counts are integers and both build the dict in
BFS-from-target order, so the result is byte-identical (value + key order).
Directed graphs use native reverse BFS while preserving NetworkX discovery order.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G, directed=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def test_parity_value_and_order():
    for seed in range(250):
        rnd = random.Random(seed)
        m = rnd.randint(1, 70)
        directed = seed % 2 == 0
        G = nx.gnp_random_graph(m, rnd.uniform(0.03, 0.45), seed=seed, directed=directed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        F = _cp(G, directed)
        for tgt in list(G)[:3]:
            for cutoff in [None, 1, 2, 3]:
                a = dict(nx.single_target_shortest_path_length(G, tgt, cutoff))
                b = fnx.single_target_shortest_path_length(F, tgt, cutoff)
                assert a == b, (seed, tgt, cutoff)
                assert list(a.keys()) == list(b.keys()), (seed, tgt, cutoff)


def test_missing_target_raises():
    F = _cp(nx.path_graph(5))
    with pytest.raises(nx.NodeNotFound):
        fnx.single_target_shortest_path_length(F, 99)


def test_directed_uses_reverse_distances():
    # Directed star inward: every leaf reaches center at distance 1.
    G = nx.DiGraph()
    G.add_edges_from([(i, 0) for i in range(1, 6)])
    F = _cp(G, directed=True)
    assert fnx.single_target_shortest_path_length(F, 0) == dict(
        nx.single_target_shortest_path_length(G, 0)
    )


def test_multidigraph_value_and_order():
    edges = []
    for node in range(11):
        edges.append((node, node + 1, None))
        edges.append((node, node + 1, f"p{node}"))
    edges.extend((u, v, None) for u, v in [(0, 5), (2, 8), (4, 8), (7, 11), (3, 10)])

    G = nx.MultiDiGraph()
    G.add_nodes_from(range(12))
    F = fnx.MultiDiGraph()
    F.add_nodes_from(G.nodes())
    for u, v, key in edges:
        if key is None:
            G.add_edge(u, v)
            F.add_edge(u, v)
        else:
            G.add_edge(u, v, key=key)
            F.add_edge(u, v, key=key)

    for cutoff in (None, 0, 1, 2, 4):
        assert list(
            fnx.single_target_shortest_path_length(F, 11, cutoff=cutoff).items()
        ) == list(nx.single_target_shortest_path_length(G, 11, cutoff=cutoff).items())
        assert list(fnx.single_target_shortest_path(F, 11, cutoff=cutoff).items()) == list(
            nx.single_target_shortest_path(G, 11, cutoff=cutoff).items()
        )


def test_subgraphview():
    G = nx.gnp_random_graph(30, 0.2, seed=3)
    F = _cp(G)
    keep = list(range(12))
    sub = F.subgraph(keep)
    gsub = nx.subgraph(G, keep)
    assert fnx.single_target_shortest_path_length(sub, 2) == dict(
        nx.single_target_shortest_path_length(gsub, 2)
    )


def _target_fixture(library, graph_type):
    graph = getattr(library, graph_type)()
    graph.add_nodes_from(["root", "a", "b", "target", "outside"])
    # Predecessor order deliberately differs from node/successor-major order.
    graph.add_edges_from([("b", "target"), ("a", "target"), ("root", "a"),
                          ("root", "b"), ("outside", "target")])
    if graph.is_multigraph():
        graph.add_edge("b", "target", key="parallel")
    return graph


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("cutoff", [None, -1, 0, 1, 1.5, 2, float("inf")])
def test_foreign_target_queries_preserve_public_bfs_order(graph_type, filtered, cutoff):
    graph = _target_fixture(nx, graph_type)
    if filtered:
        graph = nx.subgraph_view(graph, filter_node=lambda node: node != "outside")
    for name in ("single_target_shortest_path", "single_target_shortest_path_length"):
        actual = getattr(fnx, name)(graph, "target", cutoff=cutoff)
        expected = getattr(nx, name)(graph, "target", cutoff=cutoff)
        assert list(actual.items()) == list(expected.items())


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cutoff", [None, -1, 0, 1, 1.5, 2, float("inf")])
def test_reversed_target_queries_preserve_orientation_and_cutoff(graph_type, cutoff):
    foreign = _target_fixture(nx, graph_type).reverse(copy=False)
    native = _target_fixture(fnx, graph_type).reverse(copy=False)
    for name in ("single_target_shortest_path", "single_target_shortest_path_length"):
        expected = getattr(nx, name)(foreign, "root", cutoff=cutoff)
        assert list(getattr(fnx, name)(foreign, "root", cutoff=cutoff).items()) == list(expected.items())
        assert list(getattr(fnx, name)(native, "root", cutoff=cutoff).items()) == list(expected.items())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_target_queries_accept_graph_subclasses_without_conversion(graph_type):
    class NativeSubclass(getattr(fnx, graph_type)):
        pass

    graph = NativeSubclass()
    graph.add_edges_from([(0, 1), (1, 2)])
    foreign = getattr(nx, graph_type)([(0, 1), (1, 2)])
    for name in ("single_target_shortest_path", "single_target_shortest_path_length"):
        assert getattr(fnx, name)(graph, 2) == getattr(nx, name)(foreign, 2)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_foreign_target_queries_keep_missing_target_error_contract(graph_type):
    graph = _target_fixture(nx, graph_type)
    for name in ("single_target_shortest_path", "single_target_shortest_path_length"):
        with pytest.raises(nx.NodeNotFound) as expected:
            getattr(nx, name)(graph, "missing")
        with pytest.raises(fnx.NodeNotFound) as actual:
            getattr(fnx, name)(graph, "missing")
        assert str(actual.value) == str(expected.value)


def test_foreign_target_paths_keep_original_target_object():
    class Label:
        def __init__(self, value):
            self.value = value

        def __hash__(self):
            return hash(self.value)

        def __eq__(self, other):
            return isinstance(other, Label) and self.value == other.value

    stored, target = Label("target"), Label("target")
    graph = nx.DiGraph()
    graph.add_edge("source", stored)
    paths = fnx.single_target_shortest_path(graph, target)
    assert all(path[-1] is target for path in paths.values())
