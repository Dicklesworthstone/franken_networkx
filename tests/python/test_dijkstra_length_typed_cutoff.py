import math

import franken_networkx as fnx
import networkx as nx
import pytest


def _rows(result):
    return [(repr(node), type(distance).__name__, distance) for node, distance in result.items()]


def _type_name(value):
    return value.__class__.__name__


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


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_dijkstra_path_length_target_only_raw_matches_nx_types(
    monkeypatch, fnx_factory, nx_factory
):
    gf, gn = _build_graphs(fnx_factory, nx_factory)

    def fail_path_build(*args, **kwargs):
        raise AssertionError("dijkstra_path_length should not construct a path")

    monkeypatch.setattr(fnx, "_raw_dijkstra_path", fail_path_build)

    for target in ("z", "mix", "s"):
        public = fnx.dijkstra_path_length(gf, "s", target, weight="weight")
        raw = fnx._raw_dijkstra_path_length(gf, "s", target, weight="weight")
        expected = nx.dijkstra_path_length(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected
        assert _type_name(public) == _type_name(expected)
        assert _type_name(raw) == _type_name(expected)


def _build_weighted_multidigraphs():
    gf = fnx.MultiDiGraph()
    gn = nx.MultiDiGraph()
    for graph in (gf, gn):
        graph.add_edge("s", "a", key=0, weight=7)
        graph.add_edge("s", "a", key=1, weight=1)
        graph.add_edge("a", "z", key=0, weight=2)
        graph.add_edge("s", "z", key=0, weight=10.0)
        graph.add_edge("s", "flag", key=0, weight=True)
        graph.add_edge("flag", "tail", key=0, weight=2)
    return gf, gn


def test_multidigraph_dijkstra_path_length_target_raw_skips_projection(monkeypatch):
    gf, gn = _build_weighted_multidigraphs()

    def fail_collapse(*args, **kwargs):
        raise AssertionError("directed multigraph target query should not collapse")

    monkeypatch.setattr(fnx, "_multigraph_collapse_min_weight", fail_collapse)

    for target in ("z", "tail", "s"):
        public = fnx.dijkstra_path_length(gf, "s", target, weight="weight")
        raw = fnx._raw_multidigraph_dijkstra_path_length_target(
            gf, "s", target, weight="weight"
        )
        expected = nx.dijkstra_path_length(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected
        assert _type_name(public) == _type_name(expected)
        assert _type_name(raw) == _type_name(expected)


def test_multidigraph_dijkstra_path_target_raw_skips_projection(monkeypatch):
    gf, gn = _build_weighted_multidigraphs()

    def fail_collapse(*args, **kwargs):
        raise AssertionError("directed multigraph target path should not collapse")

    monkeypatch.setattr(fnx, "_multigraph_collapse_min_weight", fail_collapse)

    for target in ("z", "tail", "s"):
        public = fnx.dijkstra_path(gf, "s", target, weight="weight")
        raw = fnx._raw_multidigraph_dijkstra_path_target(
            gf, "s", target, weight="weight"
        )
        expected = nx.dijkstra_path(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected


def test_multidigraph_dijkstra_path_length_target_raw_delegates_nonnumeric():
    gf = fnx.MultiDiGraph()
    gf.add_edge("s", "a", weight="bad")
    gf.add_edge("a", "z", weight=1)

    assert (
        fnx._raw_multidigraph_dijkstra_path_length_target(
            gf, "s", "z", weight="weight"
        )
        is None
    )


def test_multidigraph_dijkstra_path_target_raw_delegates_nonnumeric():
    gf = fnx.MultiDiGraph()
    gf.add_edge("s", "a", weight="bad")
    gf.add_edge("a", "z", weight=1)

    assert (
        fnx._raw_multidigraph_dijkstra_path_target(
            gf, "s", "z", weight="weight"
        )
        is None
    )
