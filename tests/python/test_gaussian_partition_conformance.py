"""NetworkX conformance tests for gaussian_random_partition_graph."""

import pytest
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


@pytest.mark.parametrize("directed", [False, True])
def test_gaussian_random_partition_graph_seeded_output_matches_networkx(directed):
    actual = fnx.gaussian_random_partition_graph(
        12, 3, 1, 0.8, 0.2, directed=directed, seed=5
    )
    expected = nx.gaussian_random_partition_graph(
        12, 3, 1, 0.8, 0.2, directed=directed, seed=5
    )

    assert _graph_signature(actual) == _graph_signature(expected)


def test_gaussian_random_partition_graph_rejects_mean_larger_than_node_count():
    with pytest.raises(nx.NetworkXError) as expected:
        nx.gaussian_random_partition_graph(2, 3, 1, 0.8, 0.2, seed=5)
    with pytest.raises(fnx.NetworkXError) as actual:
        fnx.gaussian_random_partition_graph(2, 3, 1, 0.8, 0.2, seed=5)

    assert str(actual.value) == str(expected.value)
