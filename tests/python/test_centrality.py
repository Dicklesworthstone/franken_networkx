"""Conformance tests: centrality algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestCentrality:
    def test_degree_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.degree_centrality(G_fnx), nx.degree_centrality(G_nx),
                           label="degree_centrality")

    def test_closeness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.closeness_centrality(G_fnx), nx.closeness_centrality(G_nx),
                           label="closeness_centrality")

    def test_harmonic_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.harmonic_centrality(G_fnx), nx.harmonic_centrality(G_nx),
                           label="harmonic_centrality")

    def test_betweenness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.betweenness_centrality(G_fnx), nx.betweenness_centrality(G_nx),
                           label="betweenness_centrality")

    def test_eigenvector_centrality(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        # K5 all nodes have equal eigenvector centrality
        fnx_ec = fnx.eigenvector_centrality(G_fnx)
        nx_ec = nx.eigenvector_centrality(G_nx)
        assert_dicts_close(fnx_ec, nx_ec, atol=1e-3, label="eigenvector_centrality")

    def test_pagerank(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        fnx_pr = fnx.pagerank(G_fnx)
        nx_pr = nx.pagerank(G_nx)
        assert_dicts_close(fnx_pr, nx_pr, atol=1e-3, label="pagerank")

    def test_pagerank_sum_to_one(self, fnx, path_graph):
        G_fnx, _ = path_graph
        pr = fnx.pagerank(G_fnx)
        assert abs(sum(pr.values()) - 1.0) < 0.01

    def test_pagerank_dangling(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        G_fnx.add_edge(0, 1)
        G_nx.add_edge(0, 1)
        G_fnx.add_node(2)
        G_nx.add_node(2)
        dangling = {0: 0.0, 1: 0.5, 2: 0.5}

        assert_dicts_close(
            fnx.pagerank(G_fnx, dangling=dangling),
            nx.pagerank(G_nx, dangling=dangling),
            atol=1e-6,
            label="pagerank_dangling",
        )

    def test_katz_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_kc = fnx.katz_centrality(G_fnx)
        nx_kc = nx.katz_centrality(G_nx)
        assert_dicts_close(fnx_kc, nx_kc, atol=1e-3, label="katz_centrality")

    def test_edge_betweenness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ebc = fnx.edge_betweenness_centrality(G_fnx)
        nx_ebc = nx.edge_betweenness_centrality(G_nx)
        # Normalize edge keys for comparison
        fnx_norm = {tuple(sorted((str(u), str(v)))): s for (u, v), s in fnx_ebc.items()}
        nx_norm = {tuple(sorted((str(u), str(v)))): s for (u, v), s in nx_ebc.items()}
        for key in nx_norm:
            assert abs(fnx_norm[key] - nx_norm[key]) < 1e-6, f"edge_betweenness[{key}]"

    def test_voterank(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_vr = fnx.voterank(G_fnx)
        nx_vr = nx.voterank(G_nx)
        # Voterank order should match
        assert [str(x) for x in fnx_vr] == [str(x) for x in nx_vr]

    def test_degree_assortativity(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_dac = fnx.degree_assortativity_coefficient(G_fnx)
        nx_dac = nx.degree_assortativity_coefficient(G_nx)
        assert abs(fnx_dac - nx_dac) < 1e-6
