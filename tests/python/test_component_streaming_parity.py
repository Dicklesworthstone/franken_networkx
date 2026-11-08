"""Component iterators preserve live inputs and do only requested DFS/BFS work."""

from __future__ import annotations

import copy
import gc
import random
import types
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx
import franken_networkx.backend as backend


ALGORITHMS = (
    "connected_components",
    "weakly_connected_components",
    "strongly_connected_components",
    "biconnected_components",
    "biconnected_component_edges",
    "articulation_points",
)
DIRECTED = {"weakly_connected_components", "strongly_connected_components"}


def _graph(lib, name, multi=False, nodes=(0, 1, 2, 3), edges=((0, 1), (1, 0))):
    cls = (
        lib.MultiDiGraph if multi else lib.DiGraph
    ) if name in DIRECTED else (lib.MultiGraph if multi else lib.Graph)
    graph = cls()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("lib", [fnx, nx], ids=["native", "foreign"])
@pytest.mark.parametrize("multi", [False, True], ids=["simple", "parallel"])
@pytest.mark.parametrize("view_kind", ["graph", "subgraph", "filter"])
def test_mutations_before_first_advance_are_visible(name, lib, multi, view_kind):
    graph = _graph(lib, name, multi)
    oracle = _graph(nx, name, multi)
    enabled = {"later": False}

    def view(library, source):
        if view_kind == "subgraph":
            return source.subgraph([0, 1, 2])
        if view_kind == "filter":
            return library.subgraph_view(
                source,
                filter_edge=lambda u, v, *key: enabled["later"] or max(u, v) < 2,
            )
        return source

    actual = getattr(fnx, name)(view(lib, graph))
    expected = getattr(nx, name)(view(nx, oracle))
    assert isinstance(actual, types.GeneratorType)
    graph.add_edges_from([(1, 2), (2, 1)])
    oracle.add_edges_from([(1, 2), (2, 1)])
    enabled["later"] = True
    assert list(actual) == list(expected)


class _PrefixRows(dict):
    """Fail if traversal touches an unrequested disconnected component."""

    def __init__(self, rows, reads):
        super().__init__(rows)
        self.reads = reads

    def __getitem__(self, node):
        self.reads.append(node)
        assert node < 100, "read an unrequested component"
        return super().__getitem__(node)

    def items(self):
        for node in self:
            yield node, self[node]


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("dispatch", ["direct", "explicit", "automatic"])
def test_prefix_does_not_copy_or_visit_later_components(name, dispatch, monkeypatch):
    edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
    edges += [(node, node + 1) for node in range(100, 120)]
    graph = _graph(nx, name, nodes=range(3), edges=edges)
    reads = []
    graph._adj = _PrefixRows(graph._adj, reads)
    if graph.is_directed():
        graph._pred = _PrefixRows(graph._pred, reads)
    called = []
    original = backend._SUPPORTED_ALGORITHMS[name]

    def record(G):
        called.append(G)
        return original(G)

    monkeypatch.setitem(backend._SUPPORTED_ALGORITHMS, name, record)

    def no_materialization(*args, **kwargs):
        raise AssertionError("a component iterator materialized its input")

    monkeypatch.setattr(backend, "_nx_to_fnx_for_dispatch", no_materialization)
    if dispatch == "direct":
        iterator = getattr(fnx, name)(graph)
    elif dispatch == "explicit":
        iterator = getattr(nx, name)(graph, backend="franken_networkx")
    else:
        monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
        iterator = getattr(nx, name)(graph)
    assert reads == []
    if dispatch != "direct":
        assert called == [graph]
    expected = {
        "connected_components": {0, 1, 2},
        "weakly_connected_components": {0, 1, 2},
        "strongly_connected_components": {0, 1, 2},
        "biconnected_components": {1, 2},
        "biconnected_component_edges": [(1, 2)],
        "articulation_points": 1,
    }[name]
    assert next(iterator) == expected
    assert set(reads) <= {0, 1, 2}
    iterator.close()


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("cached", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("keyword", [False, True], ids=["positional", "keyword"])
def test_public_backend_live_input_with_cold_and_warm_caches(name, cached, keyword, monkeypatch):
    graph = _graph(nx, name)
    if cached:
        nx.degree_centrality(graph, backend="franken_networkx")
    conversions = graph.__networkx_cache__.get("backends", {}).get("franken_networkx", {})
    before = dict(conversions)

    def no_materialization(*args, **kwargs):
        raise AssertionError("component dispatch should use the original graph")

    monkeypatch.setattr(backend, "_nx_to_fnx_for_dispatch", no_materialization)
    call = getattr(nx, name)
    iterator = (
        call(G=graph, backend="franken_networkx")
        if keyword else call(graph, backend="franken_networkx")
    )
    assert graph.__networkx_backend__ == "networkx"
    assert "_fnx_networkx_source" not in vars(graph)
    after = graph.__networkx_cache__.get("backends", {}).get("franken_networkx", {})
    assert all(after[key] is converted for key, converted in before.items())
    assert all(converted is not graph for converted in after.values())
    graph.add_edges_from([(1, 2), (2, 1)])
    assert list(iterator) == list(call(graph, backend="networkx"))


@pytest.mark.parametrize("name", ALGORITHMS)
def test_cold_component_does_not_poison_following_native_dispatch(name, monkeypatch):
    graph = _graph(nx, name)
    iterator = getattr(nx, name)(graph, backend="franken_networkx")
    conversions = graph.__networkx_cache__.get("backends", {}).get("franken_networkx", {})
    assert all(converted is not graph for converted in conversions.values())
    list(iterator)
    seen = []
    original = backend._SUPPORTED_ALGORITHMS["degree_centrality"]

    def record(G):
        seen.append(G)
        return original(G)

    monkeypatch.setitem(backend._SUPPORTED_ALGORITHMS, "degree_centrality", record)
    expected = nx.degree_centrality(graph, backend="networkx")
    assert nx.degree_centrality(graph, backend="franken_networkx") == expected
    assert len(seen) == 1 and isinstance(seen[0], (fnx.Graph, fnx.DiGraph))
    list(getattr(nx, name)(graph, backend="franken_networkx"))
    assert nx.degree_centrality(graph, backend="franken_networkx") == expected
    assert seen[1] is seen[0]


@pytest.mark.parametrize("name", ALGORITHMS)
def test_explicit_native_conversion_keeps_its_own_changes(name):
    source = _graph(nx, name)
    converted = backend.BackendInterface.convert_from_nx(source, name="degree_centrality")
    converted.add_edges_from([(1, 2), (2, 1)])
    expected = _graph(nx, name)
    expected.add_edges_from([(1, 2), (2, 1)])
    assert list(getattr(nx, name)(converted, backend="franken_networkx")) == list(
        getattr(nx, name)(expected)
    )


@pytest.mark.parametrize("name", ALGORITHMS)
def test_copied_warm_backend_cache_recovers_the_copied_source(name):
    graph = _graph(nx, name)
    nx.degree_centrality(graph, backend="franken_networkx")
    copied = copy.deepcopy(graph)
    iterator = getattr(nx, name)(copied, backend="franken_networkx")
    copied.add_edges_from([(1, 2), (2, 1)])
    assert list(iterator) == list(getattr(nx, name)(copied, backend="networkx"))
    assert not graph.has_edge(1, 2)


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("multi", [False, True])
def test_random_ordered_decompositions_match_networkx(name, multi):
    for seed in range(24):
        rng = random.Random(seed)
        nodes = list(range(10))
        rng.shuffle(nodes)
        edges = [(u, v) for u in nodes for v in nodes if rng.random() < 0.16]
        if multi:
            edges += edges[::3]
        graph = _graph(fnx, name, multi, nodes, edges)
        oracle = _graph(nx, name, multi, nodes, edges)
        assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(oracle)), seed


@pytest.mark.parametrize("name", ALGORITHMS)
def test_long_chain_uses_an_iterative_search(name):
    nodes = range(1600)
    edges = [(node, node + 1) for node in range(1599)]
    graph = _graph(fnx, name, nodes=nodes, edges=edges)
    oracle = _graph(nx, name, nodes=nodes, edges=edges)
    assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(oracle))


@pytest.mark.parametrize("name", ALGORITHMS)
def test_non_reflexive_node_objects_do_not_break_dfs_completion(name):
    root = float("nan")
    graph = _graph(
        nx, name, nodes=(root, "first", ("second",)),
        edges=[(root, "first"), ("first", root), (root, ("second",)), (("second",), root)],
    )
    assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(graph))


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("lib", [fnx, nx])
def test_wrong_directedness_raises_when_called(name, lib):
    graph = lib.Graph() if name in DIRECTED else lib.DiGraph()
    with pytest.raises(fnx.NetworkXNotImplemented):
        getattr(fnx, name)(graph)


@pytest.mark.parametrize("name", ALGORITHMS)
@pytest.mark.parametrize("nodes,edges", [((), ()), ((0,), ()), ((0,), ((0, 0),))])
def test_empty_isolated_and_self_loop_cases(name, nodes, edges):
    graph = _graph(fnx, name, nodes=nodes, edges=edges)
    oracle = _graph(nx, name, nodes=nodes, edges=edges)
    assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(oracle))


@pytest.mark.parametrize("name", ALGORITHMS)
def test_assigned_logical_rows_override_native_topology(name):
    logical = _graph(nx, name, nodes=range(4), edges=[(0, 1), (1, 0), (1, 2), (2, 1)])
    graph = _graph(fnx, name, nodes=(100, 101), edges=[(100, 101)])
    graph._node = logical._node
    graph._adj = logical._adj
    if graph.is_directed():
        graph._succ = logical._succ
        graph._pred = logical._pred
    assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(logical))


@pytest.mark.parametrize("name", ["connected_components", "weakly_connected_components"])
@pytest.mark.parametrize("lib", [fnx, nx])
def test_assigned_node_storage_does_not_hide_reachable_adjacency(name, lib):
    oracle = _graph(nx, name, nodes=(0, 1), edges=[(1, 0)])
    oracle._node = {0: {}}
    graph = _graph(lib, name, nodes=(), edges=())
    graph._node = oracle._node
    graph._adj = oracle._adj
    if graph.is_directed():
        graph._succ = oracle._succ
        graph._pred = oracle._pred
    assert list(getattr(fnx, name)(graph)) == list(getattr(nx, name)(oracle)) == [{0, 1}]


@pytest.mark.parametrize("name", [name for name in ALGORITHMS if name != "articulation_points"])
def test_mutating_a_yielded_component_does_not_change_remaining_results(name):
    edges = [(0, 1), (1, 0), (10, 11), (11, 10)]
    graph = _graph(fnx, name, nodes=(0, 1, 10, 11), edges=edges)
    oracle = _graph(nx, name, nodes=(0, 1, 10, 11), edges=edges)
    actual = getattr(fnx, name)(graph)
    expected = list(getattr(nx, name)(oracle))
    first = next(actual)
    assert first == expected[0]
    first.clear()
    assert list(actual) == expected[1:]


@pytest.mark.parametrize("name", ALGORITHMS)
def test_closing_an_active_generator_releases_its_source(name):
    graph = _graph(nx, name, edges=[(0, 1), (1, 0), (1, 2), (2, 1)])
    reference = weakref.ref(graph)
    iterator = getattr(fnx, name)(graph)
    del graph
    next(iterator)
    assert reference() is not None
    iterator.close()
    gc.collect()
    assert reference() is None
