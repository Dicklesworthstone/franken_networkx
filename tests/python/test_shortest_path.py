"""Conformance tests: shortest path algorithms — fnx vs nx oracle."""

import pytest


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

    def test_dijkstra_path(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert fnx.dijkstra_path(G_fnx, "a", "d") == nx.dijkstra_path(G_nx, "a", "d")

    def test_bellman_ford_path(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert fnx.bellman_ford_path(G_fnx, "a", "d") == nx.bellman_ford_path(G_nx, "a", "d")

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
