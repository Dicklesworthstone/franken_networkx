"""NetworkX conformance tests for random_internet_as_graph."""

from collections import Counter

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


def test_random_internet_as_graph_seeded_output_matches_networkx():
    for order, seed in [(-1, 4), (0, 4), (1, 4), (2, 4), (10, 4), (25, 7)]:
        actual = fnx.random_internet_as_graph(order, seed=seed)
        expected = nx.random_internet_as_graph(order, seed=seed)

        assert _graph_signature(actual) == _graph_signature(expected)


def test_random_internet_as_graph_preserves_as_attributes():
    graph = fnx.random_internet_as_graph(10, seed=4)
    node_attrs = Counter(
        tuple(sorted(attrs.items())) for _, attrs in graph.nodes(data=True)
    )
    edge_attrs = Counter(
        tuple(sorted(dict(attrs).items())) for _, _, attrs in graph.edges(data=True)
    )

    assert node_attrs == Counter(
        [
            (("type", "T"),),
            (("type", "T"),),
            (("type", "T"),),
            (("type", "T"),),
            (("peers", 1), ("type", "M")),
            (("peers", 1), ("type", "M")),
            (("peers", 0), ("type", "C")),
            (("peers", 0), ("type", "C")),
            (("peers", 0), ("type", "C")),
            (("peers", 0), ("type", "C")),
        ]
    )
    assert edge_attrs == Counter(
        [
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "none"), ("type", "peer")),
            (("customer", "4"), ("type", "transit")),
            (("customer", "5"), ("type", "transit")),
            (("customer", "6"), ("type", "transit")),
            (("customer", "7"), ("type", "transit")),
            (("customer", "8"), ("type", "transit")),
            (("customer", "9"), ("type", "transit")),
        ]
    )
