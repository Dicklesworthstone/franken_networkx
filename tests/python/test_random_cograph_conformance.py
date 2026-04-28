"""NetworkX conformance tests for random_cograph."""

import networkx as nx

import franken_networkx as fnx


def _graph_signature(graph):
    return {
        "class": type(graph).__name__,
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph": dict(graph.graph),
        "nodes": sorted((node, dict(attrs)) for node, attrs in graph.nodes(data=True)),
        "edges": sorted((u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)),
    }


def test_random_cograph_seeded_output_matches_networkx():
    for order, seed in [(-1, 1), (0, 1), (1, 1), (2, 1), (3, 7), (4, 11)]:
        actual = fnx.random_cograph(order, seed=seed)
        expected = nx.random_cograph(order, seed=seed)

        assert _graph_signature(actual) == _graph_signature(expected)


def test_random_cograph_repeated_seed_is_stable_and_uses_power_of_two_order():
    first = fnx.random_cograph(5, seed=19)
    second = fnx.random_cograph(5, seed=19)
    expected = nx.random_cograph(5, seed=19)

    assert first.number_of_nodes() == 2**5
    assert _graph_signature(first) == _graph_signature(second)
    assert _graph_signature(first) == _graph_signature(expected)
