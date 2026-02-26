"""Conformance tests: Euler algorithms — fnx vs nx oracle."""

import pytest


@pytest.mark.conformance
class TestEuler:
    def test_is_eulerian_k3(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert fnx.is_eulerian(G_fnx) == nx.is_eulerian(G_nx)

    def test_is_eulerian_path(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_eulerian(G_fnx) == nx.is_eulerian(G_nx)

    def test_has_eulerian_path_true(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.has_eulerian_path(G_fnx) == nx.has_eulerian_path(G_nx)

    def test_is_semieulerian(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_semieulerian(G_fnx) == nx.is_semieulerian(G_nx)

    def test_eulerian_circuit_k3(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        fnx_circuit = fnx.eulerian_circuit(G_fnx)
        nx_circuit = list(nx.eulerian_circuit(G_nx))
        # Same number of edges in circuit
        assert len(fnx_circuit) == len(nx_circuit)
        # Verify it actually forms a valid circuit
        for i in range(len(fnx_circuit) - 1):
            assert str(fnx_circuit[i][1]) == str(fnx_circuit[i + 1][0])

    def test_eulerian_path_simple(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_path = fnx.eulerian_path(G_fnx)
        nx_path = list(nx.eulerian_path(G_nx))
        assert len(fnx_path) == len(nx_path)

    def test_non_eulerian_raises(self, fnx, star_graph):
        G_fnx, _ = star_graph
        with pytest.raises(fnx.NetworkXError):
            fnx.eulerian_circuit(G_fnx)
