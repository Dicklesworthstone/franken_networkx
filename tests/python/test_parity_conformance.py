"""Conformance tests verifying fnx algorithm outputs match NetworkX exactly.

These tests systematically compare fnx and nx outputs across algorithms,
edge cases, and graph types. They serve as regression guards against
parity drift.

br-r37-c1-y5y7i follow-up: added after scipy.sparse pagerank optimization.
"""

import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


class TestCentralityParity:
    """Verify centrality algorithm outputs match NetworkX."""

    def test_pagerank_undirected(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_pr = fnx.pagerank(G, alpha=0.85)
        nx_pr = nx.pagerank(nxG, alpha=0.85)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_directed(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        fnx_pr = fnx.pagerank(DG)
        nx_pr = nx.pagerank(nxDG)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_dangling_nodes(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2)])
        DG.add_node(3)  # dangling - no outgoing
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2)])
        nxDG.add_node(3)
        fnx_pr = fnx.pagerank(DG)
        nx_pr = nx.pagerank(nxDG)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_weighted(self):
        random.seed(42)
        G = fnx.DiGraph()
        for i in range(10):
            for j in range(10):
                if i != j and random.random() < 0.3:
                    G.add_edge(i, j, weight=random.uniform(0.5, 2.0))
        nxG = nx.DiGraph()
        for u, v, d in G.edges(data=True):
            nxG.add_edge(u, v, weight=d["weight"])
        fnx_pr = fnx.pagerank(G, weight="weight")
        nx_pr = nx.pagerank(nxG, weight="weight")
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_empty(self):
        assert fnx.pagerank(fnx.Graph()) == {}
        assert nx.pagerank(nx.Graph()) == {}

    def test_betweenness_centrality_large(self):
        G = fnx.barabasi_albert_graph(200, 5, seed=42)
        nxG = nx.barabasi_albert_graph(200, 5, seed=42)
        fnx_bc = fnx.betweenness_centrality(G)
        nx_bc = nx.betweenness_centrality(nxG)
        max_diff = max(abs(fnx_bc[n] - nx_bc[n]) for n in fnx_bc)
        assert max_diff < 1e-10

    def test_closeness_centrality(self):
        G = fnx.cycle_graph(20)
        nxG = nx.cycle_graph(20)
        fnx_cc = fnx.closeness_centrality(G)
        nx_cc = nx.closeness_centrality(nxG)
        max_diff = max(abs(fnx_cc[n] - nx_cc[n]) for n in fnx_cc)
        assert max_diff < 1e-10

    def test_clustering_coefficient(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_cl = fnx.clustering(G)
        nx_cl = nx.clustering(nxG)
        max_diff = max(abs(fnx_cl[n] - nx_cl[n]) for n in fnx_cl)
        assert max_diff < 1e-10


class TestShortestPathParity:
    """Verify shortest path algorithm outputs match NetworkX."""

    def test_single_source_shortest_path_length(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_sp = dict(fnx.single_source_shortest_path_length(G, 0))
        nx_sp = dict(nx.single_source_shortest_path_length(nxG, 0))
        assert fnx_sp == nx_sp

    def test_all_pairs_shortest_path_length(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_apsp = dict(fnx.all_pairs_shortest_path_length(G))
        nx_apsp = dict(nx.all_pairs_shortest_path_length(nxG))
        assert fnx_apsp == nx_apsp

    def test_dijkstra_directed(self):
        DG = fnx.gnm_random_graph(50, 200, directed=True, seed=42)
        nxDG = nx.gnm_random_graph(50, 200, directed=True, seed=42)
        fnx_sp = dict(fnx.single_source_dijkstra_path_length(DG, 0))
        nx_sp = dict(nx.single_source_dijkstra_path_length(nxDG, 0))
        assert fnx_sp == nx_sp


class TestComponentsParity:
    """Verify component algorithm outputs match NetworkX."""

    def test_connected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3), (4, 5), (5, 6)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (2, 3), (4, 5), (5, 6)])
        fnx_cc = sorted([tuple(sorted(c)) for c in fnx.connected_components(G)])
        nx_cc = sorted([tuple(sorted(c)) for c in nx.connected_components(nxG)])
        assert fnx_cc == nx_cc

    def test_strongly_connected_components(self):
        DG = fnx.gnm_random_graph(50, 200, directed=True, seed=42)
        nxDG = nx.gnm_random_graph(50, 200, directed=True, seed=42)
        fnx_scc = sorted([tuple(sorted(c)) for c in fnx.strongly_connected_components(DG)])
        nx_scc = sorted([tuple(sorted(c)) for c in nx.strongly_connected_components(nxDG)])
        assert fnx_scc == nx_scc

    def test_number_connected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        G.add_node(99)  # isolated
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (2, 3)])
        nxG.add_node(99)
        assert fnx.number_connected_components(G) == nx.number_connected_components(nxG)


class TestMatchingParity:
    """Verify matching algorithm outputs match NetworkX."""

    def test_max_weight_matching(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1)
        G.add_edge(1, 2, weight=5)
        G.add_edge(2, 3, weight=1)
        G.add_edge(0, 3, weight=5)
        nxG = nx.Graph()
        for u, v, d in G.edges(data=True):
            nxG.add_edge(u, v, **d)
        fnx_match = set(tuple(sorted(e)) for e in fnx.max_weight_matching(G))
        nx_match = set(tuple(sorted(e)) for e in nx.max_weight_matching(nxG))
        assert fnx_match == nx_match


class TestMultiGraphParity:
    """Verify MultiGraph/MultiDiGraph behaviors match NetworkX."""

    def test_multigraph_pagerank_weighted(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, weight=1.0)
        MG.add_edge(0, 1, weight=2.0)  # parallel edge
        MG.add_edge(1, 2, weight=1.0)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 1, weight=1.0)
        nxMG.add_edge(0, 1, weight=2.0)
        nxMG.add_edge(1, 2, weight=1.0)
        fnx_pr = fnx.pagerank(MG, weight="weight")
        nx_pr = nx.pagerank(nxMG, weight="weight")
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_multigraph_weighted_degree(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, weight=1.0)
        MG.add_edge(0, 1, weight=2.0)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 1, weight=1.0)
        nxMG.add_edge(0, 1, weight=2.0)
        assert dict(MG.degree(weight="weight")) == dict(nxMG.degree(weight="weight"))

    def test_multigraph_selfloops(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 0)
        MG.add_edge(0, 0)
        MG.add_edge(0, 1)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 0)
        nxMG.add_edge(0, 0)
        nxMG.add_edge(0, 1)
        assert fnx.number_of_selfloops(MG) == nx.number_of_selfloops(nxMG)


class TestEdgeCaseParity:
    """Verify edge case behaviors match NetworkX."""

    def test_k_core_isolated_nodes(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 3), (1, 3)])
        G.add_node(99)  # isolated
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 3), (1, 3)])
        nxG.add_node(99)
        assert set(fnx.k_core(G, k=2).nodes()) == set(nx.k_core(nxG, k=2).nodes())

    def test_density_various_graphs(self):
        # Empty
        assert fnx.density(fnx.Graph()) == nx.density(nx.Graph())
        # Single node
        g1 = fnx.Graph()
        g1.add_node(0)
        ng1 = nx.Graph()
        ng1.add_node(0)
        assert fnx.density(g1) == nx.density(ng1)
        # Path
        assert fnx.density(fnx.path_graph(5)) == nx.density(nx.path_graph(5))

    def test_is_bipartite_edge_cases(self):
        # Empty
        assert fnx.is_bipartite(fnx.Graph()) == nx.is_bipartite(nx.Graph())
        # Single node
        g1 = fnx.Graph()
        g1.add_node(0)
        ng1 = nx.Graph()
        ng1.add_node(0)
        assert fnx.is_bipartite(g1) == nx.is_bipartite(ng1)
        # Triangle (not bipartite)
        assert fnx.is_bipartite(fnx.cycle_graph(3)) == nx.is_bipartite(nx.cycle_graph(3))
        # Square (bipartite)
        assert fnx.is_bipartite(fnx.cycle_graph(4)) == nx.is_bipartite(nx.cycle_graph(4))

    def test_triangles(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
        assert fnx.triangles(G) == nx.triangles(nxG)

    def test_transitivity(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert abs(fnx.transitivity(G) - nx.transitivity(nxG)) < 1e-10


class TestCommunityParity:
    """Verify community detection outputs match NetworkX."""

    def test_louvain_communities(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_louvain = list(fnx.community.louvain_communities(G, seed=42))
        nx_louvain = list(nx.community.louvain_communities(nxG, seed=42))
        fnx_sets = set(frozenset(c) for c in fnx_louvain)
        nx_sets = set(frozenset(c) for c in nx_louvain)
        assert fnx_sets == nx_sets

    def test_greedy_modularity_communities(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_greedy = list(fnx.community.greedy_modularity_communities(G))
        nx_greedy = list(nx.community.greedy_modularity_communities(nxG))
        fnx_sets = set(frozenset(c) for c in fnx_greedy)
        nx_sets = set(frozenset(c) for c in nx_greedy)
        assert fnx_sets == nx_sets


class TestLinkAnalysisParity:
    """Verify link analysis algorithm outputs match NetworkX."""

    def test_eigenvector_centrality(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_ec = fnx.eigenvector_centrality(G, max_iter=1000)
        nx_ec = nx.eigenvector_centrality(nxG, max_iter=1000)
        max_diff = max(abs(fnx_ec[n] - nx_ec[n]) for n in fnx_ec)
        assert max_diff < 1e-6

    def test_hits(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_hubs, fnx_auth = fnx.hits(G, max_iter=1000)
        nx_hubs, nx_auth = nx.hits(nxG, max_iter=1000)
        max_hub_diff = max(abs(fnx_hubs[n] - nx_hubs[n]) for n in fnx_hubs)
        max_auth_diff = max(abs(fnx_auth[n] - nx_auth[n]) for n in fnx_auth)
        assert max_hub_diff < 1e-6
        assert max_auth_diff < 1e-6


class TestIsomorphismParity:
    """Verify isomorphism algorithm outputs match NetworkX."""

    def test_is_isomorphic_same(self):
        G1 = fnx.cycle_graph(5)
        G2 = fnx.cycle_graph(5)
        nxG1 = nx.cycle_graph(5)
        nxG2 = nx.cycle_graph(5)
        assert fnx.is_isomorphic(G1, G2) == nx.is_isomorphic(nxG1, nxG2)

    def test_is_isomorphic_different(self):
        G1 = fnx.cycle_graph(5)
        G2 = fnx.path_graph(5)
        nxG1 = nx.cycle_graph(5)
        nxG2 = nx.path_graph(5)
        assert fnx.is_isomorphic(G1, G2) == nx.is_isomorphic(nxG1, nxG2)

    def test_graph_edit_distance(self):
        G1 = fnx.path_graph(4)
        G2 = fnx.cycle_graph(4)
        nxG1 = nx.path_graph(4)
        nxG2 = nx.cycle_graph(4)
        assert fnx.graph_edit_distance(G1, G2) == nx.graph_edit_distance(nxG1, nxG2)
