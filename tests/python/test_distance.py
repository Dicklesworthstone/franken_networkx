"""Conformance tests: distance measure algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_sets_equal


@pytest.mark.conformance
class TestDistance:
    def test_density(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert abs(fnx.density(G_fnx) - nx.density(G_nx)) < 1e-9

    def test_density_complete(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert abs(fnx.density(G_fnx) - 1.0) < 1e-9
        assert abs(fnx.density(G_fnx) - nx.density(G_nx)) < 1e-9

    def test_diameter(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.diameter(G_fnx) == nx.diameter(G_nx)

    def test_radius(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.radius(G_fnx) == nx.radius(G_nx)

    def test_center(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_sets_equal(fnx.center(G_fnx), nx.center(G_nx), label="center")

    def test_periphery(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_sets_equal(fnx.periphery(G_fnx), nx.periphery(G_nx), label="periphery")

    def test_eccentricity(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ecc = fnx.eccentricity(G_fnx)
        nx_ecc = nx.eccentricity(G_nx)
        for node in nx_ecc:
            assert fnx_ecc[node] == nx_ecc[node], f"eccentricity[{node}]"

    def test_disconnected_raises(self, fnx, disconnected_graph):
        G_fnx, _ = disconnected_graph
        with pytest.raises(fnx.NetworkXError):
            fnx.diameter(G_fnx)

    def test_tree_broadcast_example_tree(self, fnx, nx):
        edge_list = [
            (0, 1),
            (1, 2),
            (2, 7),
            (3, 4),
            (5, 4),
            (4, 7),
            (6, 7),
            (7, 9),
            (8, 9),
            (9, 13),
            (13, 14),
            (14, 15),
            (14, 16),
            (14, 17),
            (13, 11),
            (11, 10),
            (11, 12),
            (13, 18),
            (18, 19),
            (18, 20),
        ]
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for u, v in edge_list:
            G_fnx.add_edge(u, v)
            G_nx.add_edge(u, v)

        fnx_time, fnx_center = fnx.tree_broadcast_center(G_fnx)
        nx_time, nx_center = nx.tree_broadcast_center(G_nx)

        assert fnx_time == nx_time
        assert_sets_equal(fnx_center, nx_center, label="tree_broadcast_center")
        assert fnx.tree_broadcast_time(G_fnx) == nx.tree_broadcast_time(G_nx)
        assert fnx.tree_broadcast_time(G_fnx, 17) == nx.tree_broadcast_time(G_nx, 17)
        assert fnx.tree_broadcast_time(G_fnx, 3) == nx.tree_broadcast_time(G_nx, 3)
