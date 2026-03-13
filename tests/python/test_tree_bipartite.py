"""Conformance tests: tree, forest, bipartite, coloring, core — fnx vs nx oracle."""

import pytest
from conftest import assert_sets_equal


@pytest.mark.conformance
class TestTreeForest:
    def test_is_tree_path(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_tree(G_fnx) == nx.is_tree(G_nx)

    def test_is_tree_cycle(self, fnx, nx, cycle_graph):
        G_fnx, G_nx = cycle_graph
        assert fnx.is_tree(G_fnx) == nx.is_tree(G_nx)

    def test_is_forest_path(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_forest(G_fnx) == nx.is_forest(G_nx)

    def test_is_forest_disconnected(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.is_forest(G_fnx) == nx.is_forest(G_nx)


@pytest.mark.conformance
class TestBipartite:
    def test_is_bipartite_path(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_bipartite(G_fnx) == nx.is_bipartite(G_nx)

    def test_is_bipartite_triangle(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert fnx.is_bipartite(G_fnx) == nx.is_bipartite(G_nx)

    def test_bipartite_sets(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_a, fnx_b = fnx.bipartite_sets(G_fnx)
        # nx.bipartite_sets moved to nx.bipartite.sets in NetworkX 3.6
        from networkx.algorithms import bipartite as nx_bip
        nx_a, nx_b = nx_bip.sets(G_nx)
        # Sets might be swapped, so check both orderings
        fnx_pair = (set(str(x) for x in fnx_a), set(str(x) for x in fnx_b))
        nx_pair = (set(str(x) for x in nx_a), set(str(x) for x in nx_b))
        assert fnx_pair == nx_pair or fnx_pair == (nx_pair[1], nx_pair[0])

    def test_non_bipartite_raises(self, fnx, triangle_graph):
        G_fnx, _ = triangle_graph
        with pytest.raises(fnx.NetworkXError):
            fnx.bipartite_sets(G_fnx)


@pytest.mark.conformance
class TestColoring:
    def test_greedy_color_valid(self, fnx, path_graph):
        G_fnx, _ = path_graph
        coloring = fnx.greedy_color(G_fnx)
        # Verify proper coloring: no adjacent nodes share a color
        for u, v in G_fnx.edges:
            assert coloring[u] != coloring[v]

    def test_greedy_color_chromatic_bound(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_colors = len(set(fnx.greedy_color(G_fnx).values()))
        nx_colors = len(set(nx.greedy_color(G_nx).values()))
        assert fnx_colors == nx_colors


@pytest.mark.conformance
class TestCore:
    def test_core_number(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        fnx_cn = fnx.core_number(G_fnx)
        nx_cn = nx.core_number(G_nx)
        for node in nx_cn:
            assert fnx_cn[node] == nx_cn[node]

    def test_core_number_path(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_cn = fnx.core_number(G_fnx)
        nx_cn = nx.core_number(G_nx)
        for node in nx_cn:
            assert fnx_cn[node] == nx_cn[node]


@pytest.mark.conformance
class TestMST:
    def test_minimum_spanning_tree_edges(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        mst_fnx = fnx.minimum_spanning_tree(G_fnx, weight="weight")
        mst_nx = nx.minimum_spanning_tree(G_nx, algorithm="kruskal")
        # MST should have same number of edges
        assert mst_fnx.number_of_edges() == mst_nx.number_of_edges()
        # Total weight should match
        fnx_weight = sum(
            G_fnx.edges[u, v].get("weight", 1.0)
            for u, v in mst_fnx.edges
        )
        nx_weight = sum(mst_nx[u][v].get("weight", 1.0) for u, v in mst_nx.edges())
        assert abs(fnx_weight - nx_weight) < 1e-9

    def test_minimum_spanning_edges_matches_networkx(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert list(fnx.minimum_spanning_edges(G_fnx, weight="weight")) == list(
            nx.minimum_spanning_edges(G_nx, weight="weight")
        )

    def test_maximum_spanning_edges_data_false_matches_networkx(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        assert list(fnx.maximum_spanning_edges(G_fnx, weight="weight", data=False)) == list(
            nx.maximum_spanning_edges(G_nx, weight="weight", data=False)
        )

    def test_spanning_edges_ignore_nan_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=float("nan"))
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("c", "d", weight=2.0)

        assert list(fnx.minimum_spanning_edges(G_fnx, weight="weight", ignore_nan=True)) == list(
            nx.minimum_spanning_edges(G_nx, weight="weight", ignore_nan=True)
        )
        assert list(
            fnx.maximum_spanning_edges(G_fnx, weight="weight", ignore_nan=True, data=False)
        ) == list(nx.maximum_spanning_edges(G_nx, weight="weight", ignore_nan=True, data=False))

        with pytest.raises(ValueError, match="NaN found as an edge weight"):
            list(fnx.minimum_spanning_edges(G_fnx, weight="weight"))

        with pytest.raises(ValueError, match="NaN found as an edge weight"):
            list(fnx.maximum_spanning_edges(G_fnx, weight="weight"))
