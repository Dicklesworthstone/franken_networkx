"""Conformance tests: graph measures — fnx vs nx oracle."""

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
