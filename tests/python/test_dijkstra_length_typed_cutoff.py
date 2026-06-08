import math

import franken_networkx as fnx
import networkx as nx
import pytest


def _rows(result):
    return [(repr(node), type(distance).__name__, distance) for node, distance in result.items()]


def _build_graphs(graph_factory_f, graph_factory_n):
    gf = graph_factory_f()
    gn = graph_factory_n()
    for u, v, weight in (
        ("s", "a", 1),
        ("s", "b", 1),
        ("a", "c", 1),
        ("b", "d", 1),
        ("c", "z", 1),
        ("d", "z", 1),
        ("s", "flag", True),
        ("flag", "tail", 2),
        ("s", "float", 1.5),
        ("float", "mix", 2),
    ):
        gf.add_edge(u, v, weight=weight)
        gn.add_edge(u, v, weight=weight)
    return gf, gn


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
@pytest.mark.parametrize("cutoff", [None, 1, 2, -1, math.nan, math.inf])
def test_single_source_dijkstra_path_length_raw_matches_nx_types_and_cutoff(
    fnx_factory, nx_factory, cutoff
):
    gf, gn = _build_graphs(fnx_factory, nx_factory)

    public = fnx.single_source_dijkstra_path_length(
        gf, "s", cutoff=cutoff, weight="weight"
    )
    raw = fnx._raw_single_source_dijkstra_path_length(
        gf, "s", weight="weight", cutoff=cutoff
    )
    expected = nx.single_source_dijkstra_path_length(
        gn, "s", cutoff=cutoff, weight="weight"
    )

    assert _rows(public) == _rows(expected)
    assert _rows(raw) == _rows(expected)


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_single_source_dijkstra_path_length_large_int_sum_does_not_saturate(
    fnx_factory, nx_factory
):
    weight = 1 << 62
    expected_distance = 1 << 63
    gf = fnx_factory()
    gn = nx_factory()
    for graph in (gf, gn):
        graph.add_edge("s", "a", weight=weight)
        graph.add_edge("a", "z", weight=weight)

    public = fnx.single_source_dijkstra_path_length(gf, "s", weight="weight")
    raw = fnx._raw_single_source_dijkstra_path_length(gf, "s", weight="weight")
    expected = nx.single_source_dijkstra_path_length(gn, "s", weight="weight")

    assert public["z"] == expected_distance
    assert raw["z"] == expected_distance
    assert _rows(public) == _rows(expected)
    assert _rows(raw) == _rows(expected)
