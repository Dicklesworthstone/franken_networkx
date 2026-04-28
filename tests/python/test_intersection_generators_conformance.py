"""NetworkX conformance tests for random intersection graph generators."""

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


@pytest.mark.parametrize(
    "name,args,kwargs",
    [
        ("uniform_random_intersection_graph", (6, 5, 0.3), {"seed": 5}),
        (
            "general_random_intersection_graph",
            (6, 5, [0.1, 0.2, 0.3, 0.4, 0.5]),
            {"seed": 5},
        ),
    ],
)
def test_intersection_generators_seeded_output_matches_networkx(name, args, kwargs):
    actual = getattr(fnx, name)(*args, **kwargs)
    expected = getattr(nx, name)(*args, **kwargs)

    assert _graph_signature(actual) == _graph_signature(expected)


def test_general_random_intersection_graph_validates_probability_count():
    with pytest.raises(ValueError) as expected:
        nx.general_random_intersection_graph(3, 4, [0.2, 0.4], seed=1)
    with pytest.raises(ValueError) as actual:
        fnx.general_random_intersection_graph(3, 4, [0.2, 0.4], seed=1)

    assert str(actual.value) == str(expected.value)
