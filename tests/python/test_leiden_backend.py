"""Dispatch contracts for the owned Leiden community implementation."""

import inspect
import random

import franken_networkx as fnx
import franken_networkx.backend as fnx_backend
import networkx as nx
import pytest


_APIS = ("leiden_communities", "leiden_partitions")


def _warm(graph):
    nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _input(graph, route):
    if route == "native":
        result = getattr(fnx, type(graph).__name__)()
        result.add_nodes_from(graph.nodes(data=True))
        if graph.is_multigraph():
            result.add_edges_from(graph.edges(keys=True, data=True))
        else:
            result.add_edges_from(graph.edges(data=True))
        return result
    if route == "warm":
        _warm(graph)
    return graph


def _groups(partition):
    assert isinstance(partition, list)
    assert all(isinstance(group, set) for group in partition)
    return {frozenset(group) for group in partition}


def _levels(name, result):
    if name == "leiden_partitions":
        assert inspect.isgenerator(result)
        return [_groups(partition) for partition in result]
    return [_groups(result)]


def _disjoint_cliques(multigraph=False):
    graph = nx.MultiGraph() if multigraph else nx.Graph()
    graph.add_nodes_from(range(9))
    graph.add_edges_from(nx.complete_graph(4).edges(), strength=3)
    graph.add_edges_from(
        ((u + 4, v + 4) for u, v in nx.complete_graph(4).edges()), strength=5
    )
    if multigraph:
        graph.add_edge(0, 1, strength=2)
    return graph


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_leiden_finds_disconnected_cliques(name, multigraph, route):
    graph = _disjoint_cliques(multigraph)
    expected = {frozenset(range(4)), frozenset(range(4, 8)), frozenset({8})}
    result = getattr(nx.community, name)(
        G=_input(graph, route), weight="strength", seed=11, backend="franken_networkx"
    )
    levels = _levels(name, result)
    assert levels[-1] == expected
    for partition in levels:
        assert set().union(*partition) == set(graph)
        assert sum(map(len, partition)) == len(graph)
        assert all(nx.is_connected(graph.subgraph(group)) for group in partition)


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("weight", [None, "strength"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_leiden_preserves_seed_resolution_and_weight_options(name, weight, route):
    graph = nx.path_graph(20)
    for index, (u, v) in enumerate(graph.edges()):
        graph[u][v]["strength"] = 1 if index % 4 == 3 else 8
    expected = _levels(name, getattr(fnx.community, name)(
        graph, weight=weight, resolution=0.4, seed=random.Random(19)
    ))
    actual = _levels(name, getattr(nx.community, name)(
        _input(graph.copy(), route), weight, 0.4,
        seed=random.Random(19), backend="franken_networkx"
    ))
    assert actual == expected


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("prewarm", [False, True])
def test_backend_leiden_reads_original_edge_provider_at_snapshot(name, prewarm):
    graph = _disjoint_cliques()
    if prewarm:
        _warm(graph)
    original_edges = graph.edges
    reads = []

    def edges(*args, **kwargs):
        reads.append((args, kwargs))
        return original_edges(*args, **kwargs)

    graph.edges = edges
    result = getattr(nx.community, name)(graph, seed=0, backend="franken_networkx")
    if name == "leiden_partitions":
        assert reads == []
    levels = _levels(name, result)
    assert reads == [((), {"data": True})]
    assert levels[-1] == {frozenset(range(4)), frozenset(range(4, 8)), frozenset({8})}


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("prewarm", [False, True])
def test_backend_leiden_cached_view_keeps_current_filter(name, prewarm):
    graph = _disjoint_cliques()
    visible = set(range(4))
    view = nx.subgraph_view(graph, filter_node=visible.__contains__)
    if prewarm:
        _warm(view)
    visible.update(range(4, 9))
    result = getattr(nx.community, name)(view, seed=0, backend="franken_networkx")
    assert _levels(name, result)[-1] == {
        frozenset(range(4)), frozenset(range(4, 8)), frozenset({8})
    }


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_leiden_partitions_snapshot_at_first_resume_and_copy_results(route):
    graph = nx.path_graph(32)
    supplied = _input(graph.copy(), route)
    iterator = nx.community.leiden_partitions(
        supplied, resolution=0.1, seed=0, backend="franken_networkx"
    )
    supplied.add_node("before-first-resume")
    graph.add_node("before-first-resume")
    expected = _levels("leiden_partitions", fnx.community.leiden_partitions(
        graph, resolution=0.1, seed=0
    ))
    assert len(expected) > 1
    first = next(iterator)
    assert _groups(first) == expected[0]
    first[0].add("edited-yielded-set")
    first.clear()
    supplied.clear()
    supplied.add_node("after-first-resume")
    assert [_groups(partition) for partition in iterator] == expected[1:]


@pytest.mark.parametrize("prewarm", [False, True])
def test_backend_leiden_rng_is_retained_and_draws_begin_on_resume(prewarm):
    class RecordingRandom(random.Random):
        def __init__(self):
            super().__init__(7)
            self.shuffles = []

        def shuffle(self, values):
            self.shuffles.append(tuple(values))
            return super().shuffle(values)

    graph = nx.path_graph(10)
    if prewarm:
        _warm(graph)
    rng = RecordingRandom()
    state = rng.getstate()
    iterator = nx.community.leiden_partitions(graph, seed=rng, backend="franken_networkx")
    assert rng.shuffles == []
    assert rng.getstate() == state
    next(iterator)
    assert rng.shuffles
    assert rng.getstate() != state
    iterator.close()


@pytest.mark.parametrize("route", ["cold", "warm", "native"])
@pytest.mark.parametrize("max_level", [1, 2, None])
def test_backend_leiden_communities_respects_level_limit(route, max_level):
    graph = nx.path_graph(32)
    levels = list(fnx.community.leiden_partitions(graph, resolution=0.1, seed=0))
    expected = levels[-1] if max_level is None else levels[min(max_level, len(levels)) - 1]
    actual = nx.community.leiden_communities(
        _input(graph.copy(), route), resolution=0.1,
        max_level=max_level, seed=0, backend="franken_networkx"
    )
    assert _groups(actual) == _groups(expected)


@pytest.mark.parametrize("name", _APIS)
def test_backend_leiden_explicit_native_graph_has_independent_origin(name):
    graph = nx.empty_graph(4)
    converted = fnx_backend.backend_interface.convert_from_nx(graph, name="pagerank")
    converted.add_edges_from(nx.complete_graph(4).edges())
    actual = _levels(name, getattr(nx.community, name)(
        converted, seed=0, backend="franken_networkx"
    ))
    assert actual[-1] == {frozenset(range(4))}
    assert graph.number_of_edges() == 0


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_leiden_empty_graph_returns_one_empty_partition(name, route):
    actual = _levels(name, getattr(nx.community, name)(
        _input(nx.Graph(), route), seed=0, backend="franken_networkx"
    ))
    assert actual == [set()]


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_backend_leiden_rejects_directed_graph(name, graph_type):
    graph = getattr(nx, graph_type)([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented, match="directed"):
        getattr(nx.community, name)(graph, seed=0, backend="franken_networkx")


@pytest.mark.parametrize("name", _APIS)
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_backend_leiden_rejects_bad_seed_at_call(name, graph_type):
    # NetworkX's compiled decorators resolve the seed before directedness.
    graph = getattr(nx, graph_type)([(0, 1), (1, 2)])
    with pytest.raises(ValueError):
        getattr(nx.community, name)(graph, seed=object(), backend="franken_networkx")


def test_backend_leiden_partitions_validates_weight_on_resume():
    graph = nx.Graph([(0, 1, {"weight": -1})])
    iterator = nx.community.leiden_partitions(graph, seed=0, backend="franken_networkx")
    with pytest.raises(nx.NetworkXError, match="finite nonnegative"):
        next(iterator)


def test_backend_leiden_communities_validates_weight_during_call():
    graph = nx.Graph([(0, 1, {"weight": -1})])
    with pytest.raises(nx.NetworkXError, match="finite nonnegative"):
        nx.community.leiden_communities(graph, seed=0, backend="franken_networkx")
