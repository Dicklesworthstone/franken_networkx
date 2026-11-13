"""Owned Leiden phases, modularity invariants, and public API boundaries."""

import math
import random
from dataclasses import dataclass
from fractions import Fraction

import franken_networkx as fnx
import networkx as nx
import pytest

from franken_networkx import _leiden


@dataclass(frozen=True)
class _Node:
    value: int


def _canonical(partition):
    return frozenset(frozenset(block) for block in partition)


def _result(name, graph, **options):
    result = getattr(fnx.community, name)(graph, **options)
    return list(result)[-1] if name == "leiden_partitions" else result


def _articulation_graph():
    graph = nx.Graph()
    graph.add_nodes_from(range(12))
    graph.add_weighted_edges_from(
        [(0, 1, 2), (0, 4, 2), (1, 2, 1), (1, 3, 1), (4, 5, 1), (4, 6, 1)]
    )
    graph.add_edges_from((u, v, {"weight": 1}) for u in range(7, 12) for v in range(u + 1, 12))
    graph.add_edges_from((0, node, {"weight": 1}) for node in range(7, 12))
    degrees = dict(graph.degree(weight="weight"))
    graph.add_edges_from((node, node, {"weight": (10 - degrees[node]) / 2}) for node in graph)
    return graph


@pytest.mark.parametrize("name", ["leiden_communities", "leiden_partitions"])
@pytest.mark.parametrize("graph_type", [nx.Graph, nx.MultiGraph, fnx.Graph, fnx.MultiGraph])
@pytest.mark.parametrize("weight", ["weight", "strength", None])
def test_separated_cliques_keep_custom_labels_and_isolated_nodes(name, graph_type, weight):
    nodes = [_Node(index) for index in range(10)]
    graph = graph_type()
    graph.add_nodes_from(nodes)
    for group in (nodes[:4], nodes[4:9]):
        for index, node in enumerate(group):
            for neighbor in group[index + 1:]:
                attributes = {"weight": 1, "strength": Fraction(3, 2)}
                graph.add_edge(node, neighbor, **attributes)
                if graph.is_multigraph():
                    graph.add_edge(node, neighbor, **attributes)
    result = _result(name, graph, weight=weight, seed=13)
    assert _canonical(result) == _canonical([set(nodes[:4]), set(nodes[4:9]), {nodes[9]}])
    assert all(any(node is original for original in nodes) for block in result for node in block)


def test_refinement_repairs_articulation_partition_and_improves_modularity():
    graph = _articulation_graph()
    resolution = Fraction(6, 35)
    disconnected = [{1, 2, 3, 4, 5, 6}, {0, 7, 8, 9, 10, 11}]
    assert not nx.is_connected(graph.subgraph(disconnected[0]))
    assert nx.community.modularity(graph, disconnected, resolution=resolution) == pytest.approx(Fraction(89, 105))

    partitions = list(fnx.community.leiden_partitions(graph, resolution=resolution, seed=0))
    expected = [{1, 2, 3}, {4, 5, 6}, {0, 7, 8, 9, 10, 11}]
    assert _canonical(partitions[-1]) == _canonical(expected)
    assert all(nx.is_connected(graph.subgraph(block)) for level in partitions for block in level)
    assert nx.community.modularity(graph, partitions[-1], resolution=resolution) == pytest.approx(Fraction(73, 84))


def test_refined_quotient_preserves_weight_loops_and_coarse_membership():
    graph = _articulation_graph()
    labels, level = _leiden._snapshot(graph, "weight")
    assert labels == list(range(12))
    assert level.total_weight == 60
    assert level.degrees == [10] * 12
    refined = [{1, 2, 3}, {4, 5, 6}, {0, 7, 8, 9, 10, 11}]
    coarse = [refined[0] | refined[1], refined[2]]
    quotient, membership = _leiden._aggregate(level, refined, coarse)
    assert quotient.total_weight == 60
    assert quotient.loops == [14, 14, 28]
    assert quotient.degrees == [30, 30, 60]
    assert quotient.adjacency == [{2: 2}, {2: 2}, {0: 2, 1: 2}]
    assert quotient.members == refined
    assert membership == [0, 0, 1]

    # Splitting either star out of its inherited coarse block gains 3/140 Q.
    # No original individual node could make that improving move.
    merge_score = _leiden._delta(quotient, 0, 30, 30, Fraction(6, 35))
    assert -merge_score / quotient.total_weight == pytest.approx(Fraction(3, 140))
    moved = _leiden._fast_local_move(quotient, membership, Fraction(6, 35), random.Random(0))
    assert _canonical(moved) == _canonical([{0}, {1}, {2}])


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_public_levels_are_nested_connected_and_modularity_nondecreasing(seed):
    graph = nx.path_graph(32)
    levels = list(fnx.community.leiden_partitions(graph, resolution=0.1, seed=seed))
    assert len(levels) >= 2
    previous = [{node} for node in graph]
    previous_score = nx.community.modularity(graph, previous, resolution=0.1)
    for partition in levels:
        assert len(partition) < len(previous)
        assert all(partition)
        assert set().union(*partition) == set(graph)
        assert sum(map(len, partition)) == len(graph)
        assert all(nx.is_connected(graph.subgraph(block)) for block in partition)
        assert all(any(block <= larger for larger in partition) for block in previous)
        score = nx.community.modularity(graph, partition, resolution=0.1)
        assert score >= previous_score - 1e-14
        previous, previous_score = partition, score


def test_snapshot_occurs_on_first_advance_and_yielded_sets_are_independent():
    graph = nx.path_graph(32)
    iterator = fnx.community.leiden_partitions(graph, resolution=0.1, seed=0)
    graph.add_node("added before first advance")
    expected = list(fnx.community.leiden_partitions(graph, resolution=0.1, seed=0))
    first = next(iterator)
    assert _canonical(first) == _canonical(expected[0])
    assert {"added before first advance"} in first
    assert len(expected) > 1
    for block in first:
        block.clear()
    graph.clear()
    assert [_canonical(level) for level in iterator] == [_canonical(level) for level in expected[1:]]


@pytest.mark.parametrize("max_level", [1, 2, 3, None])
def test_max_level_limits_public_refined_contractions(max_level):
    graph = nx.path_graph(32)
    levels = list(fnx.community.leiden_partitions(graph, resolution=0.1, seed=0))
    position = -1 if max_level is None else min(max_level, len(levels)) - 1
    result = fnx.community.leiden_communities(graph, resolution=0.1, max_level=max_level, seed=0)
    assert _canonical(result) == _canonical(levels[position])


@pytest.mark.parametrize("max_level", [0, -1, -100])
def test_nonpositive_max_level_is_rejected(max_level):
    with pytest.raises(ValueError, match="positive integer or None"):
        fnx.community.leiden_communities(nx.path_graph(2), max_level=max_level)


def test_noninteger_max_level_retains_islice_validation():
    with pytest.raises(ValueError, match="islice"):
        fnx.community.leiden_communities(nx.path_graph(2), max_level=1.5)


@pytest.mark.parametrize("name", ["leiden_communities", "leiden_partitions"])
@pytest.mark.parametrize("graph_type", [nx.DiGraph, nx.MultiDiGraph, fnx.DiGraph, fnx.MultiDiGraph])
def test_directed_graph_rejected_before_invalid_seed(name, graph_type):
    with pytest.raises(nx.NetworkXNotImplemented, match="directed"):
        getattr(fnx.community, name)(graph_type(), seed=object())


def test_seed_resolution_occurs_when_iterator_is_created():
    with pytest.raises(ValueError):
        fnx.community.leiden_partitions(nx.Graph(), seed=object())


def test_seed_is_repeatable_and_integer_seed_does_not_mutate_global_random():
    graph = nx.karate_club_graph()
    before = random.getstate()
    first = list(fnx.community.leiden_partitions(graph, seed=314))
    assert random.getstate() == before
    second = list(fnx.community.leiden_partitions(graph, seed=314))
    assert [_canonical(level) for level in first] == [_canonical(level) for level in second]
    supplied = random.Random(314)
    state = supplied.getstate()
    third = list(fnx.community.leiden_partitions(graph, seed=supplied))
    assert supplied.getstate() != state
    assert [_canonical(level) for level in first] == [_canonical(level) for level in third]


@pytest.mark.parametrize("seed_factory", ["default_rng", "RandomState"])
def test_numpy_random_sources_are_supported(seed_factory):
    import numpy as np

    graph = nx.path_graph(16)
    factory = getattr(np.random, seed_factory)
    first = fnx.community.leiden_communities(graph, seed=factory(19))
    second = fnx.community.leiden_communities(graph, seed=factory(19))
    assert _canonical(first) == _canonical(second)


@pytest.mark.parametrize("value", [-1, math.inf, -math.inf, math.nan, "1", 1j, None])
@pytest.mark.parametrize("name", ["leiden_communities", "leiden_partitions"])
def test_invalid_edge_weights_are_rejected(name, value):
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=value)
    with pytest.raises(nx.NetworkXError, match="finite nonnegative"):
        _result(name, graph, seed=0)


@pytest.mark.parametrize("resolution", [0, -1, math.inf, -math.inf, math.nan, "1", 1j, None])
def test_invalid_resolution_is_rejected(resolution):
    with pytest.raises(nx.NetworkXError, match="finite positive"):
        fnx.community.leiden_communities(nx.path_graph(3), resolution=resolution)


@pytest.mark.parametrize("weights", [(1e308,), (9e307, 9e307)])
def test_nonfinite_total_degree_is_reported(weights):
    graph = nx.MultiGraph()
    for weight in weights:
        graph.add_edge(0, 1, weight=weight)
    with pytest.raises(nx.NetworkXError, match="not finite"):
        fnx.community.leiden_communities(graph)


def test_nonfinite_modularity_arithmetic_is_reported():
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=1e100)
    with pytest.raises(nx.NetworkXError, match="arithmetic is not finite"):
        fnx.community.leiden_communities(graph, resolution=1e300)


def test_subtract_max_refinement_handles_large_finite_scores():
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=1e100)
    assert fnx.community.leiden_communities(graph, seed=0) == [{0, 1}]


def test_unweighted_mode_ignores_stored_weight_values():
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=math.nan)
    graph.add_edge(1, 2, weight=-10)
    graph.add_edge(0, 2, weight="unweighted")
    assert fnx.community.leiden_communities(graph, weight=None, seed=0) == [{0, 1, 2}]


@pytest.mark.parametrize("graph_type", [nx.Graph, nx.MultiGraph, fnx.Graph, fnx.MultiGraph])
@pytest.mark.parametrize("empty", [False, True])
def test_zero_total_weight_yields_singletons_once(graph_type, empty):
    graph = graph_type()
    if not empty:
        graph.add_nodes_from(range(4))
        graph.add_edge(0, 1, weight=0)
        graph.add_edge(2, 2, weight=0)
    expected = [{node} for node in graph]
    assert list(fnx.community.leiden_partitions(graph, seed=0)) == [expected]
    assert fnx.community.leiden_communities(graph, seed=0) == expected


def test_loops_count_twice_in_degree_and_can_prevent_merging():
    graph = nx.Graph()
    graph.add_edge(0, 0, weight=2)
    graph.add_edge(0, 1, weight=1)
    assert fnx.community.leiden_communities(graph, resolution=2, seed=0) == [{0}, {1}]
    assert list(fnx.community.leiden_partitions(nx.path_graph(2), seed=0)) == [[{0, 1}]]


class _ScriptedRandom(random.Random):
    def __init__(self, draws):
        super().__init__(0)
        self.draws = iter(draws)
        self.calls = 0

    def shuffle(self, sequence):
        pass

    def random(self):
        self.calls += 1
        return next(self.draws)


def test_refinement_randomly_permits_staying_and_retries_failed_contraction():
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=0.001)
    _, level = _leiden._snapshot(graph, "weight")
    assert _leiden._refine(level, [{0, 1}], 1, _ScriptedRandom([0])) == [{0, 1}]
    assert _leiden._refine(level, [{0, 1}], 1, _ScriptedRandom([0.99, 0.99])) == [{0}, {1}]
    rng = _ScriptedRandom([0.99, 0.99, 0])
    assert list(fnx.community.leiden_partitions(graph, seed=rng)) == [[{0, 1}]]
    assert rng.calls == 3


def test_repeated_staying_is_reported_as_nonprogress_not_convergence():
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=1e-100)
    rng = _ScriptedRandom([0.75] * 128)
    with pytest.raises(nx.NetworkXError, match="no progress after 64 attempts"):
        list(fnx.community.leiden_partitions(graph, seed=rng))
    assert rng.calls == 128


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_tiny_weight_graph_progresses_with_normal_random_seeds(seed):
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=1e-100)
    assert fnx.community.leiden_communities(graph, seed=seed) == [{0, 1}]
