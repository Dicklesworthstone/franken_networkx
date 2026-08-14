"""Numerical parity on larger graphs (precision at scale).

Small graphs can hide numerical-precision and scaling divergences. This runs
the precision-sensitive metrics on larger random graphs (n=40-60) and checks
fnx stays within tight tolerance of networkx — catching accumulation/precision
bugs that n<15 tests miss.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import math
import random

import franken_networkx as fnx
import networkx as nx
import pytest


def _identical_large(seed):
    r = random.Random(seed)
    n = r.randint(40, 60)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.18]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


def _maxdiff(fd, nd):
    return max(abs(fd[k] - nd[k]) for k in fd)


def _float_hex_differences(actual, expected):
    """Return only the bit-level map differences for a relabeling failure."""
    return {
        node: (actual[node].hex(), expected[node].hex())
        for node in expected
        if actual[node] != expected[node]
    }


@pytest.mark.parametrize("seed", range(10))
def test_large_graph_centrality_precision(seed):
    fg, ng, n = _identical_large(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _maxdiff(fnx.betweenness_centrality(fg), nx.betweenness_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.closeness_centrality(fg), nx.closeness_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.harmonic_centrality(fg), nx.harmonic_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.pagerank(fg), nx.pagerank(ng)) < 1e-6
    assert _maxdiff(
        fnx.eigenvector_centrality_numpy(fg), nx.eigenvector_centrality_numpy(ng)
    ) < 1e-5
    assert _maxdiff(
        fnx.katz_centrality_numpy(fg), nx.katz_centrality_numpy(ng)
    ) < 1e-5


@pytest.mark.parametrize("directed", [False, True], ids=["graph", "digraph"])
def test_harmonic_centrality_matches_networkx_float_bits(directed):
    """Source-order accumulation is observable in the low f64 bits."""
    fnx_type = fnx.DiGraph if directed else fnx.Graph
    nx_type = nx.DiGraph if directed else nx.Graph
    fg = fnx.path_graph(600, create_using=fnx_type)
    ng = nx.path_graph(600, create_using=nx_type)

    actual = fnx.harmonic_centrality(fg)
    expected = nx.harmonic_centrality(ng)

    assert list(actual) == list(expected)
    assert {
        node: (type(value), float(value).hex()) for node, value in actual.items()
    } == {
        node: (type(value), float(value).hex()) for node, value in expected.items()
    }


@pytest.mark.parametrize("seed", range(10))
def test_large_graph_scalar_precision(seed):
    fg, ng, n = _identical_large(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert abs(fnx.transitivity(fg) - nx.transitivity(ng)) < 1e-9
    assert abs(fnx.average_clustering(fg) - nx.average_clustering(ng)) < 1e-9
    assert abs(fnx.global_efficiency(fg) - nx.global_efficiency(ng)) < 1e-9
    assert fnx.diameter(fg) == nx.diameter(ng)
    assert _maxdiff(fnx.clustering(fg), nx.clustering(ng)) < 1e-9
    assert abs(fnx.estrada_index(fg) - nx.estrada_index(ng)) < 1e-3


def test_node_metric_maps_are_equivariant_under_relabeling():
    """Node-keyed centrality maps must move values with their node labels."""
    graph = fnx.Graph()
    graph.add_edges_from(
        [("a", "b"), ("b", "c"), ("c", "d"), ("b", "d"), ("d", "e")]
    )
    mapping = {node: f"renamed-{index}" for index, node in enumerate(graph)}
    relabeled = fnx.relabel_nodes(graph, mapping)

    for metric in (
        fnx.betweenness_centrality,
        fnx.closeness_centrality,
        fnx.harmonic_centrality,
    ):
        original = metric(graph)
        moved = metric(relabeled)
        assert set(moved) == {mapping[node] for node in original}
        expected = {mapping[node]: value for node, value in original.items()}
        assert moved.keys() == expected.keys()
        assert all(
            math.isclose(moved[node], value, rel_tol=1e-15)
            for node, value in expected.items()
        ), (
            f"{metric.__name__} relabeling drift: "
            f"{_float_hex_differences(moved, expected)}"
        )


def test_edge_betweenness_map_is_equivariant_under_relabeling():
    graph = fnx.Graph()
    graph.add_edges_from(
        [("a", "b"), ("b", "c"), ("c", "d"), ("b", "d"), ("d", "e")]
    )
    mapping = {node: f"renamed-{index}" for index, node in enumerate(graph)}
    relabeled = fnx.relabel_nodes(graph, mapping)

    original = fnx.edge_betweenness_centrality(graph)
    moved = fnx.edge_betweenness_centrality(relabeled)
    expected = {(mapping[u], mapping[v]): value for (u, v), value in original.items()}
    assert moved == expected


def test_component_outputs_are_equivariant_under_relabeling():
    graph = fnx.Graph()
    graph.add_edges_from(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    )
    mapping = {node: f"component-{node}" for node in graph}
    relabeled = fnx.relabel_nodes(graph, mapping)

    def mapped_components(components, node_mapping):
        return {
            frozenset(node_mapping[node] for node in component) for component in components
        }

    identity = {node: node for node in relabeled}
    assert mapped_components(fnx.connected_components(graph), mapping) == mapped_components(
        fnx.connected_components(relabeled), identity
    )
    assert mapped_components(fnx.biconnected_components(graph), mapping) == mapped_components(
        fnx.biconnected_components(relabeled), identity
    )
    assert {mapping[node] for node in fnx.articulation_points(graph)} == set(
        fnx.articulation_points(relabeled)
    )
    expected_bridges = {
        frozenset((mapping[u], mapping[v])) for u, v in fnx.bridges(graph)
    }
    assert expected_bridges == {frozenset(edge) for edge in fnx.bridges(relabeled)}

    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
    directed_mapping = {node: f"directed-{node}" for node in directed}
    directed_relabeled = fnx.relabel_nodes(directed, directed_mapping)
    for component_fn in (fnx.strongly_connected_components, fnx.weakly_connected_components):
        expected = {
            frozenset(directed_mapping[node] for node in component)
            for component in component_fn(directed)
        }
        actual = {
            frozenset(component) for component in component_fn(directed_relabeled)
        }
        assert expected == actual


def test_link_prediction_outputs_are_equivariant_under_relabeling():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3), (3, 4)])
    mapping = {node: f"candidate-{node}" for node in graph}
    relabeled = fnx.relabel_nodes(graph, mapping)
    ebunch = [(0, 2), (1, 4)]
    relabeled_ebunch = [(mapping[u], mapping[v]) for u, v in ebunch]

    def score_map(scores, node_mapping):
        return {(node_mapping[u], node_mapping[v]): score for u, v, score in scores}

    for predictor in (fnx.jaccard_coefficient, fnx.preferential_attachment):
        original = predictor(graph, ebunch)
        moved = predictor(relabeled, relabeled_ebunch)
        assert score_map(original, mapping) == score_map(
            moved, {value: value for value in mapping.values()}
        )

    original = fnx.common_neighbors(graph, 0, 2)
    moved = fnx.common_neighbors(relabeled, mapping[0], mapping[2])
    assert {mapping[node] for node in original} == set(moved)


def test_all_simple_paths_are_equivariant_under_relabeling():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 3), (0, 2), (2, 3), (1, 2)])
    mapping = {node: f"path-{node}" for node in graph}
    relabeled = fnx.relabel_nodes(graph, mapping)

    original = {
        tuple(path)
        for path in fnx.all_simple_paths(graph, 0, 3)
    }
    moved = {
        tuple(path)
        for path in fnx.all_simple_paths(relabeled, mapping[0], mapping[3])
    }
    expected = {tuple(mapping[node] for node in path) for path in original}
    assert moved == expected


def test_all_simple_edge_paths_are_equivariant_under_relabeling():
    graph = fnx.Graph([(0, 1), (1, 3), (0, 2), (2, 3), (1, 2)])
    mapping = {node: f"edge-path-{node}" for node in graph}
    relabeled = fnx.relabel_nodes(graph, mapping)
    original = {
        tuple(path) for path in fnx.all_simple_edge_paths(graph, 0, 3)
    }
    moved = {
        tuple(path)
        for path in fnx.all_simple_edge_paths(relabeled, mapping[0], mapping[3])
    }
    expected = {
        tuple((mapping[u], mapping[v]) for u, v in path) for path in original
    }
    assert moved == expected


def test_path_predicates_are_invariant_under_relabeling():
    graph = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    mapping = {node: f"predicate-{node}" for node in graph}
    relabeled = fnx.relabel_nodes(graph, mapping)
    assert fnx.has_path(graph, 0, 3) == fnx.has_path(relabeled, mapping[0], mapping[3])
    for path in ([0, 1, 2, 3], [0, 1, 0], [0, 2, 3]):
        moved = [mapping[node] for node in path if node in mapping]
        assert fnx.is_simple_path(graph, path) == fnx.is_simple_path(relabeled, moved)

    directed = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    directed_mapping = {node: f"directed-predicate-{node}" for node in directed}
    directed_relabeled = fnx.relabel_nodes(directed, directed_mapping)
    assert fnx.has_path(directed, 0, 3) == fnx.has_path(
        directed_relabeled, directed_mapping[0], directed_mapping[3]
    )
    assert fnx.is_simple_path(directed, [0, 1, 2, 3]) == fnx.is_simple_path(
        directed_relabeled, [directed_mapping[node] for node in [0, 1, 2, 3]]
    )

    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 3), (0, 2), (2, 3), (1, 2)])
    directed_mapping = {node: f"directed-path-{node}" for node in directed}
    directed_relabeled = fnx.relabel_nodes(directed, directed_mapping)
    original = {tuple(path) for path in fnx.all_simple_paths(directed, 0, 3)}
    moved = {
        tuple(path)
        for path in fnx.all_simple_paths(
            directed_relabeled, directed_mapping[0], directed_mapping[3]
        )
    }
    expected = {
        tuple(directed_mapping[node] for node in path) for path in original
    }
    assert moved == expected
