"""NetworkX conformance tests for duplication-family generators."""

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
        ("partial_duplication_graph", (8, 3, 0.5, 0.2), {"seed": 4}),
        ("partial_duplication_graph", (6, 6, 0.5, 0.2), {"seed": 7}),
        ("duplication_divergence_graph", (8, 0.5), {"seed": 4}),
        ("duplication_divergence_graph", (2, 0.5), {"seed": 7}),
    ],
)
def test_duplication_generators_seeded_output_matches_networkx(name, args, kwargs):
    actual = getattr(fnx, name)(*args, **kwargs)
    expected = getattr(nx, name)(*args, **kwargs)

    assert _graph_signature(actual) == _graph_signature(expected)


@pytest.mark.parametrize(
    "name,args",
    [
        ("partial_duplication_graph", (8, 3, 0.5, 0.2)),
        ("duplication_divergence_graph", (8, 0.5)),
    ],
)
@pytest.mark.parametrize("create_using", [fnx.DiGraph, fnx.MultiGraph])
def test_duplication_generators_reject_unsupported_create_using(name, args, create_using):
    nx_create_using = nx.DiGraph if create_using is fnx.DiGraph else nx.MultiGraph

    with pytest.raises(nx.NetworkXError) as expected:
        getattr(nx, name)(*args, seed=4, create_using=nx_create_using)
    with pytest.raises(fnx.NetworkXError) as actual:
        getattr(fnx, name)(*args, seed=4, create_using=create_using)

    assert str(actual.value) == str(expected.value)
