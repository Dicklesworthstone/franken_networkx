"""Conformance tests: clustering algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestClustering:
    def test_clustering(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert_dicts_close(fnx.clustering(G_fnx), nx.clustering(G_nx),
                           label="clustering")

    def test_average_clustering(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert abs(fnx.average_clustering(G_fnx) - nx.average_clustering(G_nx)) < 1e-9

    def test_transitivity(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert abs(fnx.transitivity(G_fnx) - nx.transitivity(G_nx)) < 1e-9

    def test_triangles(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        fnx_tri = fnx.triangles(G_fnx)
        nx_tri = nx.triangles(G_nx)
        for node in nx_tri:
            assert fnx_tri[node] == nx_tri[node], f"triangles[{node}]"

    def test_square_clustering(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert_dicts_close(fnx.square_clustering(G_fnx), nx.square_clustering(G_nx),
                           label="square_clustering")

    def test_find_cliques(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        fnx_cliques = fnx.find_cliques(G_fnx)
        nx_cliques = list(nx.find_cliques(G_nx))
        # K5 should have exactly one maximal clique of size 5
        assert len(fnx_cliques) == len(nx_cliques)
        fnx_sorted = sorted([sorted(str(n) for n in c) for c in fnx_cliques])
        nx_sorted = sorted([sorted(str(n) for n in c) for c in nx_cliques])
        assert fnx_sorted == nx_sorted

    def test_graph_clique_number(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert fnx.graph_clique_number(G_fnx) == nx.graph_clique_number(G_nx)

    def test_clustering_path_graph(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        # Path graph has 0 clustering everywhere
        assert abs(fnx.transitivity(G_fnx) - nx.transitivity(G_nx)) < 1e-9
