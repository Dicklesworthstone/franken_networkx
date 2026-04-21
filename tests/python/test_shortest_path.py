"""Conformance tests: shortest path algorithms — fnx vs nx oracle."""

import importlib.util
from functools import lru_cache
from pathlib import Path
import sys
from collections.abc import Iterator

import pytest


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _negative_weight_graph_pair(fnx, nx, *, directed=False):
    graph_type = fnx.DiGraph if directed else fnx.Graph
    nx_graph_type = nx.DiGraph if directed else nx.Graph
    G_fnx = graph_type()
    G_nx = nx_graph_type()
    for u, v, weight in [
        ("a", "b", 2.0),
        ("b", "c", -5.0),
        ("a", "c", 1.0),
    ]:
        G_fnx.add_edge(u, v, weight=weight)
        G_nx.add_edge(u, v, weight=weight)
    return G_fnx, G_nx


def _strongly_connected_negative_weight_digraph_pair(fnx, nx):
    D_fnx = fnx.DiGraph()
    D_nx = nx.DiGraph()
    for u, v, weight in [
        ("a", "b", 1.0),
        ("b", "c", -1.0),
        ("c", "a", 2.0),
        ("a", "c", 4.0),
        ("c", "b", 1.0),
        ("b", "a", 3.0),
    ]:
        D_fnx.add_edge(u, v, weight=weight)
        D_nx.add_edge(u, v, weight=weight)
    return D_fnx, D_nx


def _negative_cycle_digraph_pair(fnx, nx):
    D_fnx = fnx.DiGraph()
    D_nx = nx.DiGraph()
    for u, v, weight in [
        ("a", "b", 1.0),
        ("b", "c", -3.0),
        ("c", "a", 1.0),
    ]:
        D_fnx.add_edge(u, v, weight=weight)
        D_nx.add_edge(u, v, weight=weight)
    return D_fnx, D_nx


def _assert_same_result_or_exception(fnx_call, nx_call):
    try:
        nx_result = nx_call()
    except Exception as nx_exc:
        with pytest.raises(Exception) as fnx_exc_info:
            fnx_call()
        fnx_exc = fnx_exc_info.value
        assert type(fnx_exc).__name__ == type(nx_exc).__name__
        assert str(fnx_exc) == str(nx_exc)
        return

    fnx_result = fnx_call()
    assert fnx_result == nx_result


@pytest.mark.conformance
class TestShortestPath:
    def test_shortest_path_source_target(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.shortest_path(G_fnx, "a", "e") == list(nx.shortest_path(G_nx, "a", "e"))

    def test_shortest_path_source_only(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_result = fnx.shortest_path(G_fnx, source="a")
        nx_result = dict(nx.shortest_path(G_nx, source="a"))
        for target in nx_result:
            assert fnx_result[target] == list(nx_result[target])

    def test_shortest_path_length(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.shortest_path_length(G_fnx, "a", "e") == nx.shortest_path_length(G_nx, "a", "e")

    @pytest.mark.parametrize(
        ("kwargs", "exc_type", "message"),
        [
            ({"source": "missing"}, "NodeNotFound", "Source missing is not in G"),
            ({"source": ["a", "b"]}, "NodeNotFound", "Source ['a', 'b'] is not in G"),
            ({"source": ("a", "b")}, "NodeNotFound", "Source ('a', 'b') is not in G"),
            (
                {"source": "missing", "weight": "weight", "method": "dijkstra"},
                "NodeNotFound",
                "Node missing not found in graph",
            ),
            (
                {"source": "missing", "weight": "weight", "method": "bellman-ford"},
                "NodeNotFound",
                "Source missing not in G",
            ),
            (
                {"source": ["a", "b"], "weight": "weight", "method": "dijkstra"},
                "TypeError",
                "unhashable type: 'list'",
            ),
            (
                {"source": ["a", "b"], "weight": "weight", "method": "bellman-ford"},
                "TypeError",
                "unhashable type: 'list'",
            ),
            (
                {"source": ("a", "b"), "weight": "weight", "method": "dijkstra"},
                "NodeNotFound",
                "Node ('a', 'b') not found in graph",
            ),
        ],
    )
    def test_shortest_path_length_source_only_networkx_34_source_validation(
        self, fnx, path_graph, kwargs, exc_type, message
    ):
        G_fnx, _ = path_graph
        with pytest.raises(Exception) as exc_info:
            fnx.shortest_path_length(G_fnx, **kwargs)

        assert type(exc_info.value).__name__ == exc_type
        assert str(exc_info.value) == message

    def test_shortest_path_length_all_pairs_returns_iterator(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph

        fnx_result = fnx.shortest_path_length(G_fnx)
        nx_result = nx.shortest_path_length(G_nx)

        assert isinstance(fnx_result, Iterator)
        assert list(fnx_result) == list(nx_result)

    def test_has_path_true(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.has_path(G_fnx, "a", "e") == nx.has_path(G_nx, "a", "e")

    def test_has_path_false(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.has_path(G_fnx, "a", "d") == nx.has_path(G_nx, "a", "d")

    def test_average_shortest_path_length(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_val = fnx.average_shortest_path_length(G_fnx)
        nx_val = nx.average_shortest_path_length(G_nx)
        assert abs(fnx_val - nx_val) < 1e-9

    def test_average_shortest_path_length_weighted_matches_networkx(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val = fnx.average_shortest_path_length(G_fnx, weight="weight")
        nx_val = nx.average_shortest_path_length(G_nx, weight="weight")
        assert fnx_val == pytest.approx(nx_val)

    def test_average_shortest_path_length_weighted_method_variants_match_networkx(
        self, fnx, nx
    ):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        edges = [
            ("a", "b", 2.0),
            ("b", "c", 1.0),
            ("c", "d", 3.0),
            ("a", "d", 10.0),
        ]
        for graph in (G_fnx, G_nx):
            for u, v, weight in edges:
                graph.add_edge(u, v, weight=weight)

        for method in ("dijkstra", "bellman-ford", "unweighted"):
            fnx_val = fnx.average_shortest_path_length(G_fnx, weight="weight", method=method)
            nx_val = nx.average_shortest_path_length(G_nx, weight="weight", method=method)
            assert fnx_val == pytest.approx(nx_val)

    def test_average_shortest_path_length_weighted_directed_matches_networkx(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        edges = [
            ("a", "b", 1.0),
            ("b", "c", 2.0),
            ("c", "a", 4.0),
            ("a", "c", 5.0),
            ("c", "b", 1.0),
            ("b", "a", 3.0),
        ]
        for graph in (D_fnx, D_nx):
            for u, v, weight in edges:
                graph.add_edge(u, v, weight=weight)

        for method in (None, "dijkstra", "bellman-ford"):
            kwargs = {"weight": "weight"}
            if method is not None:
                kwargs["method"] = method
            fnx_val = fnx.average_shortest_path_length(D_fnx, **kwargs)
            nx_val = nx.average_shortest_path_length(D_nx, **kwargs)
            assert fnx_val == pytest.approx(nx_val)

    def test_average_shortest_path_length_weighted_sparse_graph_matches_networkx(
        self, fnx, nx
    ):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()

        for graph in (G_fnx, G_nx):
            for node in range(128):
                graph.add_node(node)
            for node in range(127):
                graph.add_edge(node, node + 1, weight=float((node % 7) + 1))

        for method in ("dijkstra", "bellman-ford"):
            fnx_val = fnx.average_shortest_path_length(
                G_fnx, weight="weight", method=method
            )
            nx_val = nx.average_shortest_path_length(
                G_nx, weight="weight", method=method
            )
            assert fnx_val == pytest.approx(nx_val)

    def test_average_shortest_path_length_weighted_directed_not_strongly_connected(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        D_fnx.add_edge("a", "b", weight=1.0)
        D_nx.add_edge("a", "b", weight=1.0)

        with pytest.raises(fnx.NetworkXError, match="Graph is not strongly connected."):
            fnx.average_shortest_path_length(D_fnx, weight="weight")
        with pytest.raises(nx.NetworkXError, match="Graph is not strongly connected."):
            nx.average_shortest_path_length(D_nx, weight="weight")

    def test_dijkstra_path(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert fnx.dijkstra_path(G_fnx, "a", "d") == nx.dijkstra_path(G_nx, "a", "d")

    def test_bellman_ford_path(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert fnx.bellman_ford_path(G_fnx, "a", "d") == nx.bellman_ford_path(G_nx, "a", "d")

    def test_negative_weight_dijkstra_point_to_point_parity(self, fnx, nx):
        G_fnx, G_nx = _negative_weight_graph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_path(G_fnx, "a", "c", weight="weight"),
            lambda: nx.dijkstra_path(G_nx, "a", "c", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_path_length(G_fnx, "a", "c", weight="weight"),
            lambda: nx.dijkstra_path_length(G_nx, "a", "c", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.shortest_path(
                G_fnx, "a", "c", weight="weight", method="dijkstra"
            ),
            lambda: nx.shortest_path(
                G_nx, "a", "c", weight="weight", method="dijkstra"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.shortest_path_length(
                G_fnx, "a", "c", weight="weight", method="dijkstra"
            ),
            lambda: nx.shortest_path_length(
                G_nx, "a", "c", weight="weight", method="dijkstra"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.bidirectional_dijkstra(G_fnx, "a", "c", weight="weight"),
            lambda: nx.bidirectional_dijkstra(G_nx, "a", "c", weight="weight"),
        )

    def test_negative_weight_dijkstra_source_scoped_api_parity(self, fnx, nx):
        G_fnx, G_nx = _negative_weight_graph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: fnx.single_source_dijkstra(G_fnx, "a", weight="weight"),
            lambda: nx.single_source_dijkstra(G_nx, "a", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.single_source_dijkstra_path(G_fnx, "a", weight="weight"),
            lambda: nx.single_source_dijkstra_path(G_nx, "a", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.single_source_dijkstra_path_length(
                G_fnx, "a", weight="weight"
            ),
            lambda: nx.single_source_dijkstra_path_length(
                G_nx, "a", weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(G_fnx, {"a"}, weight="weight"),
            lambda: nx.multi_source_dijkstra(G_nx, {"a"}, weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path(G_fnx, {"a"}, weight="weight"),
            lambda: nx.multi_source_dijkstra_path(G_nx, {"a"}, weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path_length(
                G_fnx, {"a"}, weight="weight"
            ),
            lambda: nx.multi_source_dijkstra_path_length(
                G_nx, {"a"}, weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path(
                    G_fnx, source="a", weight="weight", method="dijkstra"
                )
            ),
            lambda: dict(
                nx.shortest_path(
                    G_nx, source="a", weight="weight", method="dijkstra"
                )
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path(
                    G_fnx, target="c", weight="weight", method="dijkstra"
                )
            ),
            lambda: dict(
                nx.shortest_path(
                    G_nx, target="c", weight="weight", method="dijkstra"
                )
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path_length(
                    G_fnx, source="a", weight="weight", method="dijkstra"
                )
            ),
            lambda: dict(
                nx.shortest_path_length(
                    G_nx, source="a", weight="weight", method="dijkstra"
                )
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path_length(
                    G_fnx, target="c", weight="weight", method="dijkstra"
                )
            ),
            lambda: dict(
                nx.shortest_path_length(
                    G_nx, target="c", weight="weight", method="dijkstra"
                )
            ),
        )

    def test_multi_source_dijkstra_cutoff_and_callable_weight_match_legacy_networkx_34(
        self, fnx
    ):
        legacy_nx = _legacy_networkx()
        G_fnx = fnx.Graph()
        G_legacy = legacy_nx.Graph()
        for graph in (G_fnx, G_legacy):
            graph.add_edge("a", "b", w=1)
            graph.add_edge("b", "d", w=2)
            graph.add_edge("c", "d", w=1)

        def weight_fn(u, v, data):
            return data.get("w", 1)

        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(
                G_fnx, ["a", "c"], cutoff=1, weight="w"
            ),
            lambda: legacy_nx.multi_source_dijkstra(
                G_legacy, ["a", "c"], cutoff=1, weight="w"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(
                G_fnx, ["a", "c"], weight=weight_fn
            ),
            lambda: legacy_nx.multi_source_dijkstra(
                G_legacy, ["a", "c"], weight=weight_fn
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path(
                G_fnx, ["a", "c"], cutoff=0, weight=weight_fn
            ),
            lambda: legacy_nx.multi_source_dijkstra_path(
                G_legacy, ["a", "c"], cutoff=0, weight=weight_fn
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path_length(
                G_fnx, ["a", "c"], cutoff=1, weight=weight_fn
            ),
            lambda: legacy_nx.multi_source_dijkstra_path_length(
                G_legacy, ["a", "c"], cutoff=1, weight=weight_fn
            ),
        )

    def test_multi_source_dijkstra_empty_sources_match_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0)

        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(G_fnx, set(), weight="weight"),
            lambda: nx.multi_source_dijkstra(G_nx, set(), weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(
                G_fnx, set(), target="a", weight="weight"
            ),
            lambda: nx.multi_source_dijkstra(
                G_nx, set(), target="a", weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path(G_fnx, set(), weight="weight"),
            lambda: nx.multi_source_dijkstra_path(G_nx, set(), weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra_path_length(
                G_fnx, set(), weight="weight"
            ),
            lambda: nx.multi_source_dijkstra_path_length(G_nx, set(), weight="weight"),
        )

    def test_single_source_dijkstra_target_and_cutoff_match_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1)
            graph.add_edge("b", "c", weight=1)
            graph.add_edge("c", "d", weight=1)
            graph.add_edge("a", "d", weight=5)

        cases = [
            (
                "target_reachable",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", target="d", weight="weight"
                ),
            ),
            (
                "target_cutoff_reachable",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", target="c", cutoff=2, weight="weight"
                ),
            ),
            (
                "target_cutoff_unreachable",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", target="d", cutoff=2, weight="weight"
                ),
            ),
            (
                "target_missing",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", target="missing", weight="weight"
                ),
            ),
            (
                "cutoff_filtered_dicts",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", cutoff=1, weight="weight"
                ),
            ),
            (
                "negative_cutoff_keeps_source",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", cutoff=-1, weight="weight"
                ),
            ),
            (
                "negative_cutoff_target_source",
                lambda mod, graph: mod.single_source_dijkstra(
                    graph, "a", target="a", cutoff=-1, weight="weight"
                ),
            ),
        ]

        for name, run in cases:
            _assert_same_result_or_exception(
                lambda run=run: run(fnx, G_fnx),
                lambda run=run: run(nx, G_nx),
            )

    def test_single_source_dijkstra_path_wrappers_cutoff_match_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1, length=2, penalty=0)
            graph.add_edge("a", "c", weight=4, length=1, penalty=5)
            graph.add_edge("b", "c", weight=1, length=1, penalty=0)
            graph.add_edge("c", "d", weight=1, length=2, penalty=0)

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        cases = [
            (
                "path_cutoff",
                lambda mod, graph: mod.single_source_dijkstra_path(
                    graph, "a", cutoff=2, weight="weight"
                ),
            ),
            (
                "path_length_cutoff",
                lambda mod, graph: mod.single_source_dijkstra_path_length(
                    graph, "a", cutoff=2, weight="weight"
                ),
            ),
            (
                "path_negative_cutoff_keeps_source",
                lambda mod, graph: mod.single_source_dijkstra_path(
                    graph, "a", cutoff=-1, weight="weight"
                ),
            ),
            (
                "path_length_negative_cutoff_keeps_source",
                lambda mod, graph: mod.single_source_dijkstra_path_length(
                    graph, "a", cutoff=-1, weight="weight"
                ),
            ),
            (
                "path_callable_weight_cutoff",
                lambda mod, graph: mod.single_source_dijkstra_path(
                    graph, "a", cutoff=2, weight=weight_fn
                ),
            ),
            (
                "path_length_callable_weight_cutoff",
                lambda mod, graph: mod.single_source_dijkstra_path_length(
                    graph, "a", cutoff=2, weight=weight_fn
                ),
            ),
        ]

        for name, run in cases:
            _assert_same_result_or_exception(
                lambda run=run: run(fnx, G_fnx),
                lambda run=run: run(nx, G_nx),
            )

    def test_callable_weight_dijkstra_wrapper_family_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", length=2, penalty=0)
            graph.add_edge("a", "c", length=1, penalty=5)
            graph.add_edge("b", "c", length=1, penalty=0)
            graph.add_edge("b", "d", length=5, penalty=0)
            graph.add_edge("c", "d", length=2, penalty=0)

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        cases = [
            ("dijkstra_path", lambda mod, graph: mod.dijkstra_path(graph, "a", "d", weight=weight_fn)),
            (
                "dijkstra_path_length",
                lambda mod, graph: mod.dijkstra_path_length(graph, "a", "d", weight=weight_fn),
            ),
            (
                "shortest_path_source_target",
                lambda mod, graph: mod.shortest_path(
                    graph, "a", "d", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_length_source_target",
                lambda mod, graph: mod.shortest_path_length(
                    graph, "a", "d", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_source",
                lambda mod, graph: mod.shortest_path(
                    graph, source="a", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_target",
                lambda mod, graph: mod.shortest_path(
                    graph, target="d", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_all_pairs",
                lambda mod, graph: dict(
                    mod.shortest_path(graph, weight=weight_fn, method="dijkstra")
                ),
            ),
            (
                "shortest_path_length_source",
                lambda mod, graph: mod.shortest_path_length(
                    graph, source="a", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_length_target",
                lambda mod, graph: mod.shortest_path_length(
                    graph, target="d", weight=weight_fn, method="dijkstra"
                ),
            ),
            (
                "shortest_path_length_all_pairs",
                lambda mod, graph: dict(
                    mod.shortest_path_length(graph, weight=weight_fn, method="dijkstra")
                ),
            ),
            (
                "single_source_dijkstra",
                lambda mod, graph: mod.single_source_dijkstra(graph, "a", weight=weight_fn),
            ),
            (
                "single_source_dijkstra_path",
                lambda mod, graph: mod.single_source_dijkstra_path(
                    graph, "a", weight=weight_fn
                ),
            ),
            (
                "single_source_dijkstra_path_length",
                lambda mod, graph: mod.single_source_dijkstra_path_length(
                    graph, "a", weight=weight_fn
                ),
            ),
            (
                "multi_source_dijkstra",
                lambda mod, graph: mod.multi_source_dijkstra(
                    graph, {"a", "c"}, weight=weight_fn
                ),
            ),
            (
                "multi_source_dijkstra_path",
                lambda mod, graph: mod.multi_source_dijkstra_path(
                    graph, {"a", "c"}, weight=weight_fn
                ),
            ),
            (
                "multi_source_dijkstra_path_length",
                lambda mod, graph: mod.multi_source_dijkstra_path_length(
                    graph, {"a", "c"}, weight=weight_fn
                ),
            ),
            (
                "all_pairs_dijkstra_path",
                lambda mod, graph: dict(mod.all_pairs_dijkstra_path(graph, weight=weight_fn)),
            ),
            (
                "all_pairs_dijkstra_path_length",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra_path_length(graph, weight=weight_fn)
                ),
            ),
        ]

        for name, run in cases:
            assert run(fnx, G_fnx) == run(nx, G_nx), name

    def test_callable_weight_bellman_ford_wrapper_family_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", length=2, penalty=0)
            graph.add_edge("a", "c", length=5, penalty=0)
            graph.add_edge("b", "c", length=1, penalty=0)
            graph.add_edge("b", "d", length=5, penalty=0)
            graph.add_edge("c", "d", length=1, penalty=0)

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        cases = [
            (
                "bellman_ford_path",
                lambda mod, graph: mod.bellman_ford_path(
                    graph, "a", "d", weight=weight_fn
                ),
            ),
            (
                "bellman_ford_path_length",
                lambda mod, graph: mod.bellman_ford_path_length(
                    graph, "a", "d", weight=weight_fn
                ),
            ),
            (
                "shortest_path_source_target",
                lambda mod, graph: mod.shortest_path(
                    graph, "a", "d", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_length_source_target",
                lambda mod, graph: mod.shortest_path_length(
                    graph, "a", "d", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_source",
                lambda mod, graph: mod.shortest_path(
                    graph, source="a", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_target",
                lambda mod, graph: mod.shortest_path(
                    graph, target="d", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_all_pairs",
                lambda mod, graph: dict(
                    mod.shortest_path(graph, weight=weight_fn, method="bellman-ford")
                ),
            ),
            (
                "shortest_path_length_source",
                lambda mod, graph: mod.shortest_path_length(
                    graph, source="a", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_length_target",
                lambda mod, graph: mod.shortest_path_length(
                    graph, target="d", weight=weight_fn, method="bellman-ford"
                ),
            ),
            (
                "shortest_path_length_all_pairs",
                lambda mod, graph: dict(
                    mod.shortest_path_length(
                        graph, weight=weight_fn, method="bellman-ford"
                    )
                ),
            ),
            (
                "single_source_bellman_ford",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", weight=weight_fn
                ),
            ),
            (
                "single_source_bellman_ford_path",
                lambda mod, graph: mod.single_source_bellman_ford_path(
                    graph, "a", weight=weight_fn
                ),
            ),
            (
                "single_source_bellman_ford_path_length",
                lambda mod, graph: mod.single_source_bellman_ford_path_length(
                    graph, "a", weight=weight_fn
                ),
            ),
            (
                "all_pairs_bellman_ford_path",
                lambda mod, graph: dict(
                    mod.all_pairs_bellman_ford_path(graph, weight=weight_fn)
                ),
            ),
            (
                "all_pairs_bellman_ford_path_length",
                lambda mod, graph: dict(
                    mod.all_pairs_bellman_ford_path_length(graph, weight=weight_fn)
                ),
            ),
        ]

        for name, run in cases:
            assert run(fnx, G_fnx) == run(nx, G_nx), name

    def test_callable_weight_floyd_warshall_wrappers_match_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", length=2, penalty=0)
            graph.add_edge("a", "c", length=5, penalty=0)
            graph.add_edge("b", "c", length=1, penalty=0)
            graph.add_edge("b", "d", length=5, penalty=0)
            graph.add_edge("c", "d", length=1, penalty=0)

        def weight_fn(u, v, data):
            return data["length"] + data.get("penalty", 0)

        cases = [
            (
                "floyd_warshall",
                lambda mod, graph: dict(mod.floyd_warshall(graph, weight=weight_fn)),
            ),
            (
                "floyd_warshall_predecessor_and_distance",
                lambda mod, graph: mod.floyd_warshall_predecessor_and_distance(
                    graph, weight=weight_fn
                ),
            ),
        ]

        for name, run in cases:
            assert run(fnx, G_fnx) == run(nx, G_nx), name

    @pytest.mark.parametrize(
        "nodelist",
        [
            ["a", "b", "b"],
            ["a", "b"],
            ["a", "b", "c", "x"],
        ],
    )
    def test_floyd_warshall_numpy_nodelist_contract_matches_networkx(
        self, fnx, nx, nodelist
    ):
        G_fnx = fnx.path_graph(["a", "b", "c"])
        G_nx = nx.path_graph(["a", "b", "c"])

        _assert_same_result_or_exception(
            lambda: fnx.floyd_warshall_numpy(G_fnx, nodelist=nodelist),
            lambda: nx.floyd_warshall_numpy(G_nx, nodelist=nodelist),
        )

    def test_single_source_bellman_ford_target_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)
            graph.add_edge("c", "d", weight=1.0)
            graph.add_edge("x", "y", weight=1.0)

        def weight_fn(u, v, data):
            return data["weight"]

        cases = [
            (
                "target_reachable",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", target="d", weight="weight"
                ),
            ),
            (
                "target_unreachable",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", target="y", weight="weight"
                ),
            ),
            (
                "target_missing",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", target="missing", weight="weight"
                ),
            ),
            (
                "target_source",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", target="a", weight="weight"
                ),
            ),
            (
                "source_missing",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "missing", target="other", weight="weight"
                ),
            ),
            (
                "source_missing_target_same",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "missing", target="missing", weight="weight"
                ),
            ),
            (
                "callable_weight_target",
                lambda mod, graph: mod.single_source_bellman_ford(
                    graph, "a", target="d", weight=weight_fn
                ),
            ),
        ]

        for name, run in cases:
            _assert_same_result_or_exception(
                lambda run=run: run(fnx, G_fnx),
                lambda run=run: run(nx, G_nx),
            )

    def test_negative_edge_cycle_heuristic_and_directed_match_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=-2.0)
            graph.add_edge("b", "c", weight=-3.0)
            graph.add_edge("c", "a", weight=-1.0)

        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=-3.0)
            graph.add_edge("c", "a", weight=1.0)

        D_acyclic_fnx = fnx.DiGraph()
        D_acyclic_nx = nx.DiGraph()
        for graph in (D_acyclic_fnx, D_acyclic_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)

        def weight_fn(u, v, data):
            return data.get("weight", 1.0)

        cases = [
            (
                "undirected_heuristic_false",
                lambda mod, graph: mod.negative_edge_cycle(
                    graph, weight="weight", heuristic=False
                ),
                G_fnx,
                G_nx,
            ),
            (
                "directed_default",
                lambda mod, graph: mod.negative_edge_cycle(graph, weight="weight"),
                D_fnx,
                D_nx,
            ),
            (
                "directed_heuristic_false",
                lambda mod, graph: mod.negative_edge_cycle(
                    graph, weight="weight", heuristic=False
                ),
                D_fnx,
                D_nx,
            ),
            (
                "directed_no_cycle_heuristic_false",
                lambda mod, graph: mod.negative_edge_cycle(
                    graph, weight="weight", heuristic=False
                ),
                D_acyclic_fnx,
                D_acyclic_nx,
            ),
            (
                "callable_weight_heuristic_false",
                lambda mod, graph: mod.negative_edge_cycle(
                    graph, weight=weight_fn, heuristic=False
                ),
                G_fnx,
                G_nx,
            ),
        ]

        for name, run, fnx_graph, nx_graph in cases:
            _assert_same_result_or_exception(
                lambda run=run, fnx_graph=fnx_graph: run(fnx, fnx_graph),
                lambda run=run, nx_graph=nx_graph: run(nx, nx_graph),
            )

    def test_multi_source_dijkstra_target_cutoff_matches_legacy_networkx_34(self, fnx):
        legacy_nx = _legacy_networkx()
        G_fnx = fnx.Graph()
        G_legacy = legacy_nx.Graph()
        for graph in (G_fnx, G_legacy):
            graph.add_edge("a", "b", w=1)
            graph.add_edge("c", "d", w=1)

        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(
                G_fnx, ["a"], target="b", cutoff=0, weight="w"
            ),
            lambda: legacy_nx.multi_source_dijkstra(
                G_legacy, ["a"], target="b", cutoff=0, weight="w"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.multi_source_dijkstra(
                G_fnx, ["a"], target="d", cutoff=10, weight="w"
            ),
            lambda: legacy_nx.multi_source_dijkstra(
                G_legacy, ["a"], target="d", cutoff=10, weight="w"
            ),
        )

    def test_negative_weight_dijkstra_all_pairs_api_parity(self, fnx, nx):
        G_fnx, G_nx = _negative_weight_graph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_dijkstra(G_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_dijkstra(G_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_dijkstra_path(G_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_dijkstra_path(G_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_dijkstra_path_length(G_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_dijkstra_path_length(G_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.shortest_path(G_fnx, weight="weight", method="dijkstra")),
            lambda: dict(nx.shortest_path(G_nx, weight="weight", method="dijkstra")),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path_length(G_fnx, weight="weight", method="dijkstra")
            ),
            lambda: dict(
                nx.shortest_path_length(G_nx, weight="weight", method="dijkstra")
            ),
        )

    def test_all_pairs_dijkstra_cutoff_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0, cost=1.0)
            graph.add_edge("a", "c", weight=4.0, cost=1.0)
            graph.add_edge("b", "c", weight=1.0, cost=1.0)
            graph.add_edge("c", "d", weight=1.0, cost=2.0)
            graph.add_edge("d", "e", weight=2.0, cost=1.0)
            graph.add_node("isolated")

        weight_fn = lambda u, v, data: data["cost"]

        cases = [
            (
                "all_pairs_dijkstra_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra(graph, cutoff=2.5, weight="weight")
                ),
            ),
            (
                "all_pairs_dijkstra_path_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra_path(graph, cutoff=2.5, weight="weight")
                ),
            ),
            (
                "all_pairs_dijkstra_path_length_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra_path_length(
                        graph, cutoff=2.5, weight="weight"
                    )
                ),
            ),
            (
                "all_pairs_dijkstra_callable_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra(graph, cutoff=2.5, weight=weight_fn)
                ),
            ),
            (
                "all_pairs_dijkstra_path_callable_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra_path(graph, cutoff=2.5, weight=weight_fn)
                ),
            ),
            (
                "all_pairs_dijkstra_path_length_callable_cutoff",
                lambda mod, graph: dict(
                    mod.all_pairs_dijkstra_path_length(
                        graph, cutoff=2.5, weight=weight_fn
                    )
                ),
            ),
        ]

        for _, run in cases:
            _assert_same_result_or_exception(
                lambda run=run: run(fnx, G_fnx),
                lambda run=run: run(nx, G_nx),
            )

    def test_all_pairs_all_shortest_paths_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0, cost=1.0)
            graph.add_edge("a", "c", weight=1.0, cost=1.0)
            graph.add_edge("b", "d", weight=1.0, cost=1.0)
            graph.add_edge("c", "d", weight=1.0, cost=1.0)
            graph.add_edge("b", "e", weight=2.0, cost=2.0)
            graph.add_edge("d", "e", weight=1.0, cost=1.0)
            graph.add_node("isolated")

        weight_fn = lambda u, v, data: data["cost"]

        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_all_shortest_paths(G_fnx)),
            lambda: dict(nx.all_pairs_all_shortest_paths(G_nx)),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_all_shortest_paths(G_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_all_shortest_paths(G_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: dict(
                fnx.all_pairs_all_shortest_paths(
                    G_fnx, weight="weight", method="dijkstra"
                )
            ),
            lambda: dict(
                nx.all_pairs_all_shortest_paths(
                    G_nx, weight="weight", method="dijkstra"
                )
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_all_shortest_paths(G_fnx, weight=weight_fn)),
            lambda: dict(nx.all_pairs_all_shortest_paths(G_nx, weight=weight_fn)),
        )

    def test_dijkstra_predecessor_and_distance_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0, cost=1.0)
            graph.add_edge("a", "c", weight=1.0, cost=1.0)
            graph.add_edge("b", "d", weight=1.0, cost=1.0)
            graph.add_edge("c", "d", weight=1.0, cost=1.0)
            graph.add_edge("d", "e", weight=2.0, cost=2.0)

        weight_fn = lambda u, v, data: data["cost"]

        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_predecessor_and_distance(G_fnx, "a", weight="weight"),
            lambda: nx.dijkstra_predecessor_and_distance(G_nx, "a", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_predecessor_and_distance(
                G_fnx, "a", cutoff=1.5, weight="weight"
            ),
            lambda: nx.dijkstra_predecessor_and_distance(
                G_nx, "a", cutoff=1.5, weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_predecessor_and_distance(G_fnx, "a", weight=weight_fn),
            lambda: nx.dijkstra_predecessor_and_distance(G_nx, "a", weight=weight_fn),
        )
        _assert_same_result_or_exception(
            lambda: fnx.dijkstra_predecessor_and_distance(
                G_fnx, "missing", weight="weight"
            ),
            lambda: nx.dijkstra_predecessor_and_distance(
                G_nx, "missing", weight="weight"
            ),
        )

    def test_predecessor_preserves_networkx_order(self, fnx, nx):
        G_fnx = fnx.path_graph(["a", "b", "c", "d"])
        G_nx = nx.path_graph(["a", "b", "c", "d"])

        assert list(fnx.predecessor(G_fnx, "a").items()) == list(
            nx.predecessor(G_nx, "a").items()
        )
        assert list(fnx.predecessor(G_fnx, "a", cutoff=2).items()) == list(
            nx.predecessor(G_nx, "a", cutoff=2).items()
        )

    def test_negative_weight_dijkstra_directed_api_parity(self, fnx, nx):
        D_fnx, D_nx = _negative_weight_graph_pair(fnx, nx, directed=True)

        _assert_same_result_or_exception(
            lambda: fnx.shortest_path(
                D_fnx, "a", "c", weight="weight", method="dijkstra"
            ),
            lambda: nx.shortest_path(
                D_nx, "a", "c", weight="weight", method="dijkstra"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.single_source_dijkstra_path_length(
                D_fnx, "a", weight="weight"
            ),
            lambda: nx.single_source_dijkstra_path_length(
                D_nx, "a", weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_dijkstra_path_length(D_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_dijkstra_path_length(D_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: list(fnx.all_shortest_paths(D_fnx, "a", "c", weight="weight")),
            lambda: list(nx.all_shortest_paths(D_nx, "a", "c", weight="weight")),
        )

    def test_negative_weight_average_shortest_path_length_parity(self, fnx, nx):
        G_fnx, G_nx = _negative_weight_graph_pair(fnx, nx)
        D_fnx, D_nx = _negative_weight_graph_pair(fnx, nx, directed=True)
        SD_fnx, SD_nx = _strongly_connected_negative_weight_digraph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: fnx.average_shortest_path_length(G_fnx, weight="weight"),
            lambda: nx.average_shortest_path_length(G_nx, weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.average_shortest_path_length(D_fnx, weight="weight"),
            lambda: nx.average_shortest_path_length(D_nx, weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.average_shortest_path_length(SD_fnx, weight="weight"),
            lambda: nx.average_shortest_path_length(SD_nx, weight="weight"),
        )

    def test_negative_cycle_average_shortest_path_length_bellman_ford_parity(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=-1.0)

        D_fnx, D_nx = _negative_cycle_digraph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: fnx.average_shortest_path_length(
                G_fnx, weight="weight", method="bellman-ford"
            ),
            lambda: nx.average_shortest_path_length(
                G_nx, weight="weight", method="bellman-ford"
            ),
        )
        _assert_same_result_or_exception(
            lambda: fnx.average_shortest_path_length(
                D_fnx, weight="weight", method="bellman-ford"
            ),
            lambda: nx.average_shortest_path_length(
                D_nx, weight="weight", method="bellman-ford"
            ),
        )

    def test_negative_cycle_directed_bellman_ford_source_and_all_pairs_api_parity(self, fnx, nx):
        D_fnx, D_nx = _negative_cycle_digraph_pair(fnx, nx)

        _assert_same_result_or_exception(
            lambda: fnx.single_source_bellman_ford(D_fnx, "a", weight="weight"),
            lambda: nx.single_source_bellman_ford(D_nx, "a", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.single_source_bellman_ford_path(D_fnx, "a", weight="weight"),
            lambda: nx.single_source_bellman_ford_path(D_nx, "a", weight="weight"),
        )
        _assert_same_result_or_exception(
            lambda: fnx.single_source_bellman_ford_path_length(
                D_fnx, "a", weight="weight"
            ),
            lambda: nx.single_source_bellman_ford_path_length(
                D_nx, "a", weight="weight"
            ),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_bellman_ford_path(D_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_bellman_ford_path(D_nx, weight="weight")),
        )
        _assert_same_result_or_exception(
            lambda: dict(fnx.all_pairs_bellman_ford_path_length(D_fnx, weight="weight")),
            lambda: dict(nx.all_pairs_bellman_ford_path_length(D_nx, weight="weight")),
        )

    def test_undirected_all_shortest_paths_bellman_ford_parity(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("a", "d", weight=1.0)
            graph.add_edge("d", "c", weight=1.0)
            graph.add_edge("c", "e", weight=1.0)
            graph.add_edge("b", "e", weight=2.0)

        _assert_same_result_or_exception(
            lambda: list(
                fnx.all_shortest_paths(
                    G_fnx, "a", "e", weight="weight", method="bellman-ford"
                )
            ),
            lambda: list(
                nx.all_shortest_paths(
                    G_nx, "a", "e", weight="weight", method="bellman-ford"
                )
            ),
        )

    @pytest.mark.parametrize("method", ["SPAM", "bogus", None])
    def test_all_shortest_paths_rejects_unsupported_weighted_method(self, fnx, nx, method):
        G_fnx = fnx.path_graph(["a", "b"])
        G_nx = nx.path_graph(["a", "b"])
        for graph in (G_fnx, G_nx):
            graph["a"]["b"]["weight"] = 1.0

        _assert_same_result_or_exception(
            lambda: list(
                fnx.all_shortest_paths(
                    G_fnx, "a", "b", weight="weight", method=method
                )
            ),
            lambda: list(
                nx.all_shortest_paths(G_nx, "a", "b", weight="weight", method=method)
            ),
        )

    def test_directed_target_only_bellman_ford_shortest_path_length_parity(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)
            graph.add_edge("a", "c", weight=10.0)
            graph.add_edge("x", "y", weight=4.0)

        _assert_same_result_or_exception(
            lambda: dict(
                fnx.shortest_path_length(
                    D_fnx, target="c", weight="weight", method="bellman-ford"
                )
            ),
            lambda: dict(
                nx.shortest_path_length(
                    D_nx, target="c", weight="weight", method="bellman-ford"
                )
            ),
        )

    def test_single_target_shortest_path_wrappers_preserve_networkx_order(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge("a", "d")
            graph.add_edge("b", "d")
            graph.add_edge("c", "b")
            graph.add_edge("e", "c")
            graph.add_edge("f", "e")

        for cutoff in (None, 2):
            fnx_paths = fnx.single_target_shortest_path(D_fnx, "d", cutoff=cutoff)
            nx_paths = nx.single_target_shortest_path(D_nx, "d", cutoff=cutoff)
            assert fnx_paths == nx_paths
            assert list(fnx_paths) == list(nx_paths)

            fnx_lengths = fnx.single_target_shortest_path_length(
                D_fnx, "d", cutoff=cutoff
            )
            nx_lengths = nx.single_target_shortest_path_length(
                D_nx, "d", cutoff=cutoff
            )
            assert fnx_lengths == nx_lengths
            assert list(fnx_lengths) == list(nx_lengths)

    def test_shortest_path_no_path_raises(self, fnx, disconnected_graph):
        G_fnx, _ = disconnected_graph
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.shortest_path(G_fnx, "a", "d")

    def test_node_not_found_raises(self, fnx, path_graph):
        G_fnx, _ = path_graph
        with pytest.raises(fnx.NodeNotFound):
            fnx.shortest_path(G_fnx, "a", "nonexistent")

    def test_directed_shortest_path_respects_edge_direction(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge("a", "b")
        D_nx = nx.DiGraph()
        D_nx.add_edge("a", "b")

        with pytest.raises(fnx.NetworkXNoPath):
            fnx.shortest_path(D_fnx, "b", "a")
        with pytest.raises(nx.NetworkXNoPath):
            nx.shortest_path(D_nx, "b", "a")

        assert not fnx.has_path(D_fnx, "b", "a")
        assert not nx.has_path(D_nx, "b", "a")

    def test_directed_weighted_paths_respect_edge_direction(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge("a", "b", weight=1.0)
        D_nx = nx.DiGraph()
        D_nx.add_edge("a", "b", weight=1.0)

        with pytest.raises(fnx.NetworkXNoPath):
            fnx.dijkstra_path(D_fnx, "b", "a", weight="weight")
        with pytest.raises(nx.NetworkXNoPath):
            nx.dijkstra_path(D_nx, "b", "a", weight="weight")

        with pytest.raises(fnx.NetworkXNoPath):
            fnx.bellman_ford_path(D_fnx, "b", "a", weight="weight")
        with pytest.raises(nx.NetworkXNoPath):
            nx.bellman_ford_path(D_nx, "b", "a", weight="weight")
