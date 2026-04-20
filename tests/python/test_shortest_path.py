"""Conformance tests: shortest path algorithms — fnx vs nx oracle."""

from collections.abc import Iterator

import pytest


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
