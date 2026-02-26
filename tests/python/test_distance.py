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
