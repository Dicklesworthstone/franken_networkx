"""Conformance tests: graph measures — fnx vs nx oracle."""

import inspect
import math
from decimal import Decimal
from fractions import Fraction

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestMeasures:
    def test_average_neighbor_degree(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree",
        )

    def test_average_neighbor_degree_complete(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree_complete",
        )

    def test_average_neighbor_degree_signature_matches_networkx(self, fnx, nx):
        assert str(inspect.signature(fnx.average_neighbor_degree)) == str(
            inspect.signature(nx.average_neighbor_degree)
        )

    def test_average_neighbor_degree_directed_defaults_match_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        edges = [(0, 1), (1, 2), (0, 2), (2, 3)]
        G_fnx.add_edges_from(edges)
        G_nx.add_edges_from(edges)
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx),
            nx.average_neighbor_degree(G_nx),
            label="average_neighbor_degree_directed_defaults",
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"source": "in"}, id="source-in"),
            pytest.param({"target": "in"}, id="target-in"),
            pytest.param({"source": "in", "target": "in"}, id="source-in-target-in"),
            pytest.param({"nodes": [0, 2]}, id="nodes-subset"),
        ],
    )
    def test_average_neighbor_degree_directed_variants_match_networkx(self, fnx, nx, kwargs):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        edges = [(0, 1), (1, 2), (0, 2), (2, 3)]
        G_fnx.add_edges_from(edges)
        G_nx.add_edges_from(edges)
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx, **kwargs),
            nx.average_neighbor_degree(G_nx, **kwargs),
            label=f"average_neighbor_degree_directed_variants_{kwargs}",
        )

    def test_average_neighbor_degree_weighted_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(5)
        G_nx = nx.path_graph(5)
        for i, (u, v) in enumerate(G_fnx.edges()):
            G_fnx[u][v]["weight"] = i + 1
        for i, (u, v) in enumerate(G_nx.edges()):
            G_nx[u][v]["weight"] = i + 1
        assert_dicts_close(
            fnx.average_neighbor_degree(G_fnx, weight="weight"),
            nx.average_neighbor_degree(G_nx, weight="weight"),
            label="average_neighbor_degree_weighted",
        )

    def test_average_neighbor_degree_backend_keyword_surface_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert_dicts_close(
                fnx.average_neighbor_degree(G_fnx, backend=backend),
                nx.average_neighbor_degree(G_nx, backend=backend),
                label=f"average_neighbor_degree_backend_{backend}",
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.average_neighbor_degree(G_fnx, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.average_neighbor_degree(G_nx, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.average_neighbor_degree(G_fnx, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.average_neighbor_degree(G_nx, backend_kwargs={"x": 1})

    def test_average_neighbor_degree_invalid_mode_matches_networkx(self, fnx, nx):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)
        with pytest.raises((fnx.NetworkXError, nx.NetworkXError), match="only supported for directed graphs"):
            fnx.average_neighbor_degree(G_fnx, source="in")
        with pytest.raises(nx.NetworkXError, match="only supported for directed graphs"):
            nx.average_neighbor_degree(G_nx, source="in")


_NEIGHBOR_DEGREE_DIRECTIONS = [("Graph", "out", "out")] + [
    ("DiGraph", source, target)
    for source in ("in", "out", "in+out")
    for target in ("in", "out", "in+out")
]


def _assert_neighbor_degree_values(actual, expected):
    assert list(actual) == list(expected)
    for node, want in expected.items():
        got = actual[node]
        assert type(got) is type(want)
        if isinstance(want, float) and math.isnan(want):
            assert math.isnan(got)
        else:
            assert got == want


@pytest.mark.parametrize("graph_type,source,target", _NEIGHBOR_DEGREE_DIRECTIONS)
@pytest.mark.parametrize("weight", ["weight", "cost"])
def test_average_neighbor_degree_native_reads_retained_weight_mutations(
    fnx, nx, monkeypatch, graph_type, source, target, weight
):
    """A native measure must observe each write through an already held dict."""
    actual, expected = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (actual, expected):
        graph.add_nodes_from([3, 0, 2, 1, 99])
        for u, v, value in ((3, 0, 3), (0, 2, 2), (0, 1, 1), (2, 1, 5), (1, 1, 4)):
            graph.add_edge(u, v, **{weight: value})
    held = [graph.get_edge_data(0, 1) for graph in (actual, expected)]
    namespace = fnx.average_neighbor_degree.__globals__
    native = namespace["_raw_average_neighbor_degree"]
    native_calls = []

    def record_native(*args, **kwargs):
        result = native(*args, **kwargs)
        assert result is not None, "ordinary weights must retain the native measure"
        native_calls.append(result)
        return result

    monkeypatch.setitem(namespace, "_raw_average_neighbor_degree", record_native)
    options = {"source": source, "target": target, "weight": weight}

    def check():
        _assert_neighbor_degree_values(
            fnx.average_neighbor_degree(actual, **options),
            nx.average_neighbor_degree(expected, **options),
        )

    check()
    mutations = (
        lambda attrs: attrs.update({weight: 9}),
        lambda attrs: attrs.__setitem__(weight, 0),
        lambda attrs: dict.__setitem__(attrs, weight, 6),
        lambda attrs: attrs.pop(weight),
        lambda attrs: attrs.__setitem__(weight, 4),
        lambda attrs: attrs.clear(),
    )
    for mutate in mutations:
        for attrs in held:
            mutate(attrs)
        check()
    assert len(native_calls) == len(mutations) + 1


@pytest.mark.parametrize("graph_type,source,target", _NEIGHBOR_DEGREE_DIRECTIONS)
@pytest.mark.parametrize(
    "value",
    [Fraction(1, 3), Decimal("0.1"), 2**100, math.inf, -math.inf, math.nan, 1e308],
    ids=["fraction", "decimal", "wide-int", "inf", "negative-inf", "nan", "overflow"],
)
def test_average_neighbor_degree_preserves_weight_arithmetic(
    fnx, nx, graph_type, source, target, value
):
    actual, expected = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (actual, expected):
        graph.add_nodes_from([2, 0, 1, 3, 99])
        graph.add_edge(0, 1, cost=value)
        graph.add_edge(1, 2, cost=1)
        graph.add_edge(2, 3, cost=2)
    options = {"source": source, "target": target, "weight": "cost"}
    for _ in range(2):
        _assert_neighbor_degree_values(
            fnx.average_neighbor_degree(actual, **options),
            nx.average_neighbor_degree(expected, **options),
        )


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("nested", [False, True])
def test_average_neighbor_degree_keeps_asymmetric_view_rows(fnx, nx, graph_type, nested):
    results = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 0, 8), (1, 2, 1), (2, 1, 4)])
        graph.add_node(99)
        view = graph.to_undirected(as_view=True)
        if nested:
            view = lib.subgraph_view(view, filter_node=lambda node: node != 99)
        before = lib.average_neighbor_degree(view, weight="weight")
        data = graph[1][0][0] if graph.is_multigraph() else graph[1][0]
        data["weight"] = 3
        results.append((before, lib.average_neighbor_degree(view, weight="weight")))
    for actual, expected in zip(results[0], results[1]):
        _assert_neighbor_degree_values(actual, expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_average_neighbor_degree_respects_instance_degree_provider(fnx, nx, graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2)])
        events = []

        def degree_provider(nodes=None, weight=None):
            events.append((nodes, weight))
            return [(0, 7), (1, 11), (2, 13)]

        graph.degree = degree_provider
        if graph.is_directed():
            graph.out_degree = degree_provider
        return lib.average_neighbor_degree(graph), events

    actual, actual_events = run(fnx)
    expected, expected_events = run(nx)
    _assert_neighbor_degree_values(actual, expected)
    assert actual_events == expected_events
