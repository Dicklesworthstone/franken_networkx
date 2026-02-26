"""Conformance tests: connectivity algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_sets_equal


@pytest.mark.conformance
class TestConnectivity:
    def test_is_connected_true(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_connected(G_fnx) == nx.is_connected(G_nx)

    def test_is_connected_false(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.is_connected(G_fnx) == nx.is_connected(G_nx)

    def test_number_connected_components(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.number_connected_components(G_fnx) == nx.number_connected_components(G_nx)

    def test_connected_components_count(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        fnx_comps = fnx.connected_components(G_fnx)
        nx_comps = list(nx.connected_components(G_nx))
        assert len(fnx_comps) == len(nx_comps)

    def test_connected_components_content(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_comps = fnx.connected_components(G_fnx)
        nx_comps = list(nx.connected_components(G_nx))
        # Both should have one component with all nodes
        assert len(fnx_comps) == 1
        assert_sets_equal(fnx_comps[0], nx_comps[0])

    def test_node_connectivity(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert fnx.node_connectivity(G_fnx) == nx.node_connectivity(G_nx)

    def test_articulation_points(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ap = set(str(x) for x in fnx.articulation_points(G_fnx))
        nx_ap = set(str(x) for x in nx.articulation_points(G_nx))
        assert fnx_ap == nx_ap

    def test_bridges(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_br = set(tuple(sorted((str(u), str(v)))) for u, v in fnx.bridges(G_fnx))
        nx_br = set(tuple(sorted((str(u), str(v)))) for u, v in nx.bridges(G_nx))
        assert fnx_br == nx_br
