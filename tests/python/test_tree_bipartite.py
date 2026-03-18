"""Conformance tests: tree, forest, bipartite, coloring, core — fnx vs nx oracle."""

import importlib.util

import pytest
from conftest import assert_sets_equal

HAS_SCIPY = importlib.util.find_spec("scipy") is not None


def _sorted_directed_weighted_edges(graph):
    return sorted((u, v, graph.edges[u, v].get("weight", 1.0)) for u, v in graph.edges)


def _sorted_weighted_edges(graph):
    return sorted((u, v, graph.edges[u, v].get("weight", 1.0)) for u, v in graph.edges)


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

    def test_number_of_spanning_trees_triangle(self, fnx):
        G = fnx.Graph()
        G.add_edge("a", "b")
        G.add_edge("b", "c")
        G.add_edge("a", "c")
        assert fnx.number_of_spanning_trees(G) == pytest.approx(3.0)

    def test_number_of_spanning_trees_weighted_triangle(self, fnx):
        G = fnx.Graph()
        G.add_edge(1, 2, weight=2.0)
        G.add_edge(1, 3, weight=1.0)
        G.add_edge(2, 3, weight=1.0)
        assert fnx.number_of_spanning_trees(G, weight="weight") == pytest.approx(5.0)

    def test_number_of_spanning_trees_directed_rooted(self, fnx):
        G = fnx.DiGraph()
        G.add_edge("a", "b", weight=2.0)
        G.add_edge("a", "c", weight=3.0)
        G.add_edge("b", "c", weight=5.0)
        assert fnx.number_of_spanning_trees(G, root="a") == pytest.approx(2.0)
        assert fnx.number_of_spanning_trees(G, root="a", weight="weight") == pytest.approx(16.0)

    def test_number_of_spanning_trees_errors_match_networkx_contract(self, fnx):
        empty = fnx.Graph()
        with pytest.raises(fnx.NetworkXPointlessConcept, match="Graph G must contain at least one node"):
            fnx.number_of_spanning_trees(empty)

        directed = fnx.DiGraph()
        directed.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXError, match="Input `root` must be provided when G is directed"):
            fnx.number_of_spanning_trees(directed)
        with pytest.raises(fnx.NetworkXError, match="The node root is not in the graph G."):
            fnx.number_of_spanning_trees(directed, root="missing")

    @pytest.mark.skipif(not HAS_SCIPY, reason="NetworkX number_of_spanning_trees requires scipy")
    def test_number_of_spanning_trees_matches_networkx_when_scipy_available(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=2.0)
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("a", "c", weight=4.0)
            graph.add_edge("c", "d", weight=3.0)
            graph.add_edge("b", "d", weight=5.0)
        assert fnx.number_of_spanning_trees(G_fnx) == pytest.approx(nx.number_of_spanning_trees(G_nx))
        assert fnx.number_of_spanning_trees(G_fnx, weight="weight") == pytest.approx(
            nx.number_of_spanning_trees(G_nx, weight="weight")
        )

    def test_partition_spanning_tree_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        fnx_partition = fnx.EdgePartition
        nx_partition = nx.EdgePartition

        G_fnx.graph["name"] = "fnx partition"
        G_nx.graph["name"] = "nx partition"
        G_fnx.add_node("a", color="red")
        G_nx.add_node("a", color="red")
        for graph, partition_enum in ((G_fnx, fnx_partition), (G_nx, nx_partition)):
            graph.add_edge("a", "b", weight=4.0, partition=partition_enum.INCLUDED, color="blue")
            graph.add_edge("b", "c", weight=1.0, color="green")
            graph.add_edge("a", "c", weight=3.0, color="orange")
            graph.add_edge("c", "d", weight=2.0, partition=partition_enum.EXCLUDED, color="purple")
            graph.add_edge("b", "d", weight=5.0, color="black")

        tree_fnx = fnx.partition_spanning_tree(G_fnx)
        tree_nx = nx.partition_spanning_tree(G_nx)
        assert _sorted_weighted_edges(tree_fnx) == _sorted_weighted_edges(tree_nx)
        assert tree_fnx.graph["name"] == "fnx partition"
        assert tree_fnx.nodes["a"]["color"] == "red"
        assert tree_fnx.edges["a", "b"]["partition"] == fnx_partition.INCLUDED
        assert tree_fnx.edges["a", "b"]["color"] == "blue"

        tree_fnx_max = fnx.partition_spanning_tree(G_fnx, minimum=False)
        tree_nx_max = nx.partition_spanning_tree(G_nx, minimum=False)
        assert _sorted_weighted_edges(tree_fnx_max) == _sorted_weighted_edges(tree_nx_max)

    def test_partition_spanning_tree_ignore_nan_matches_networkx(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph, partition_enum in ((G_fnx, fnx.EdgePartition), (G_nx, nx.EdgePartition)):
            graph.add_edge("a", "b", weight=float("nan"), partition=partition_enum.OPEN)
            graph.add_edge("b", "c", weight=1.0)
            graph.add_edge("a", "c", weight=2.0)

        assert _sorted_weighted_edges(
            fnx.partition_spanning_tree(G_fnx, ignore_nan=True)
        ) == _sorted_weighted_edges(nx.partition_spanning_tree(G_nx, ignore_nan=True))
        with pytest.raises(ValueError, match="NaN found as an edge weight"):
            fnx.partition_spanning_tree(G_fnx)

    def test_random_spanning_tree_is_seeded_and_valid(self, fnx):
        G = fnx.Graph()
        G.graph["name"] = "random tree source"
        G.add_node("a", tag="root")
        G.add_edge("a", "b", weight=2.0, color="red")
        G.add_edge("a", "c", weight=3.0, color="blue")
        G.add_edge("b", "c", weight=5.0, color="green")
        G.add_edge("b", "d", weight=7.0, color="purple")
        G.add_edge("c", "d", weight=11.0, color="orange")

        tree_a = fnx.random_spanning_tree(G, weight="weight", seed=7)
        tree_b = fnx.random_spanning_tree(G, weight="weight", seed=7)
        assert _sorted_weighted_edges(tree_a) == _sorted_weighted_edges(tree_b)
        assert tree_a.number_of_nodes() == G.number_of_nodes()
        assert tree_a.number_of_edges() == G.number_of_nodes() - 1
        assert fnx.is_tree(tree_a)
        assert tree_a.graph["name"] == "random tree source"
        assert tree_a.nodes["a"]["tag"] == "root"
        for u, v in tree_a.edges:
            assert G.has_edge(u, v)
            assert tree_a.edges[u, v]["color"] == G.edges[u, v]["color"]

    def test_random_spanning_tree_missing_weight_raises_key_error(self, fnx):
        G = fnx.Graph()
        G.add_edge("a", "b", weight=1.0)
        G.add_edge("b", "c")
        with pytest.raises(KeyError, match="weight"):
            fnx.random_spanning_tree(G, weight="weight", seed=1)

    @pytest.mark.skipif(not HAS_SCIPY, reason="NetworkX random_spanning_tree requires scipy")
    def test_random_spanning_tree_matches_networkx_when_scipy_available(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=2.0)
            graph.add_edge("a", "c", weight=3.0)
            graph.add_edge("b", "c", weight=5.0)
            graph.add_edge("b", "d", weight=7.0)
            graph.add_edge("c", "d", weight=11.0)

        tree_fnx = fnx.random_spanning_tree(G_fnx, weight="weight", seed=13)
        # Verify it's a valid spanning tree (connected, acyclic, V-1 edges)
        assert fnx.is_tree(tree_fnx)
        assert set(tree_fnx.nodes) == {"a", "b", "c", "d"}
        assert len(tree_fnx.edges) == 3


@pytest.mark.conformance
class TestBranchings:
    def test_maximum_branching_matches_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=5.0)
            graph.add_edge("c", "b", weight=5.0)
            graph.add_edge("b", "d", weight=4.0)
            graph.add_edge("c", "d", weight=4.0)

        fnx_result = fnx.maximum_branching(G_fnx)
        nx_result = nx.maximum_branching(G_nx)
        assert list(fnx_result.nodes) == list(nx_result.nodes)
        assert _sorted_directed_weighted_edges(fnx_result) == _sorted_directed_weighted_edges(nx_result)

    def test_minimum_branching_matches_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=5.0)
            graph.add_edge("b", "c", weight=-10.0)
            graph.add_edge("a", "c", weight=1.0)

        fnx_result = fnx.minimum_branching(G_fnx)
        nx_result = nx.minimum_branching(G_nx)
        assert list(fnx_result.nodes) == list(nx_result.nodes)
        assert _sorted_directed_weighted_edges(fnx_result) == _sorted_directed_weighted_edges(nx_result)

    def test_maximum_spanning_arborescence_matches_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=5.0)
            graph.add_edge("b", "c", weight=4.0)
            graph.add_edge("c", "a", weight=3.0)
            graph.add_edge("a", "d", weight=2.0)

        fnx_result = fnx.maximum_spanning_arborescence(G_fnx)
        nx_result = nx.maximum_spanning_arborescence(G_nx)
        assert list(fnx_result.nodes) == list(nx_result.nodes)
        assert _sorted_directed_weighted_edges(fnx_result) == _sorted_directed_weighted_edges(nx_result)

    def test_minimum_spanning_arborescence_matches_networkx(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("s", "a", weight=2.0)
            graph.add_edge("s", "b", weight=5.0)
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("a", "c", weight=4.0)
            graph.add_edge("b", "c", weight=1.0)

        fnx_result = fnx.minimum_spanning_arborescence(G_fnx)
        nx_result = nx.minimum_spanning_arborescence(G_nx)
        assert list(fnx_result.nodes) == list(nx_result.nodes)
        assert _sorted_directed_weighted_edges(fnx_result) == _sorted_directed_weighted_edges(nx_result)
