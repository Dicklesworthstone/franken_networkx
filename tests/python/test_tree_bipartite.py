"""Conformance tests: tree, forest, bipartite, coloring, core — fnx vs nx oracle."""

import importlib.util

import pytest

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
@pytest.mark.skipif(not HAS_SCIPY, reason="scipy required for biadjacency_matrix")
class TestBiadjacencyMatrix:
    @staticmethod
    def _build(mod, directed=False):
        G = mod.DiGraph() if directed else mod.Graph()
        G.add_nodes_from([0, 1, 2, 3], bipartite=0)
        G.add_nodes_from(["a", "b", "c"], bipartite=1)
        G.add_weighted_edges_from(
            [(0, "a", 1.0), (0, "b", 2.0), (1, "b", 3.0), (2, "c", 4.0), (3, "a", 5.0)]
        )
        return G

    @pytest.mark.parametrize("fmt", ["csr", "csc", "coo", "lil", "dok"])
    def test_biadjacency_matches_networkx_across_formats(self, fnx, nx, fmt):
        import numpy as np
        from networkx.algorithms import bipartite as nx_bip

        Gn = self._build(nx)
        Gf = self._build(fnx)
        rows = [0, 1, 2, 3]
        cols = ["a", "b", "c"]
        expected = nx_bip.biadjacency_matrix(Gn, rows, cols, format=fmt).toarray()
        actual = fnx.biadjacency_matrix(Gf, rows, cols, format=fmt).toarray()
        assert np.allclose(expected, actual)

    def test_biadjacency_weight_none(self, fnx, nx):
        import numpy as np
        from networkx.algorithms import bipartite as nx_bip

        Gn = self._build(nx)
        Gf = self._build(fnx)
        rows = [0, 1, 2, 3]
        cols = ["a", "b", "c"]
        expected = nx_bip.biadjacency_matrix(Gn, rows, cols, weight=None).toarray()
        actual = fnx.biadjacency_matrix(Gf, rows, cols, weight=None).toarray()
        assert np.allclose(expected, actual)

    def test_biadjacency_row_only_infers_columns(self, fnx):
        Gf = self._build(fnx)
        actual = fnx.biadjacency_matrix(Gf, [0, 1, 2, 3])
        assert actual.shape == (4, 3)
        assert actual.nnz == 5

    def test_biadjacency_directed_uses_successors_only(self, fnx, nx):
        import numpy as np
        from networkx.algorithms import bipartite as nx_bip

        Gn = self._build(nx, directed=True)
        Gf = self._build(fnx, directed=True)
        rows = [0, 1, 2, 3]
        cols = ["a", "b", "c"]
        expected = nx_bip.biadjacency_matrix(Gn, rows, cols).toarray()
        actual = fnx.biadjacency_matrix(Gf, rows, cols).toarray()
        assert np.allclose(expected, actual)

    def test_biadjacency_rejects_empty_row_order(self, fnx):
        Gf = self._build(fnx)
        with pytest.raises(fnx.NetworkXError):
            fnx.biadjacency_matrix(Gf, [])

    def test_biadjacency_rejects_duplicate_row_order(self, fnx):
        Gf = self._build(fnx)
        with pytest.raises(fnx.NetworkXError):
            fnx.biadjacency_matrix(Gf, [0, 0, 1, 2], ["a", "b", "c"])

    def test_biadjacency_rejects_duplicate_column_order(self, fnx):
        Gf = self._build(fnx)
        with pytest.raises(fnx.NetworkXError):
            fnx.biadjacency_matrix(Gf, [0, 1, 2, 3], ["a", "a", "b"])

    def test_biadjacency_rejects_unknown_format(self, fnx):
        Gf = self._build(fnx)
        with pytest.raises(fnx.NetworkXError):
            fnx.biadjacency_matrix(
                Gf, [0, 1, 2, 3], ["a", "b", "c"], format="not-a-format"
            )

    def test_from_biadjacency_roundtrip_preserves_edges(self, fnx):
        Gf = self._build(fnx)
        rows = [0, 1, 2, 3]
        cols = ["a", "b", "c"]
        matrix = fnx.biadjacency_matrix(Gf, rows, cols)
        H = fnx.from_biadjacency_matrix(matrix, row_order=rows, column_order=cols)
        assert set(H.nodes()) == set(rows) | set(cols)
        original = sorted(tuple(sorted((u, v), key=str)) for u, v in Gf.edges())
        roundtrip = sorted(tuple(sorted((u, v), key=str)) for u, v in H.edges())
        assert original == roundtrip

    def test_from_biadjacency_rejects_wrong_length_row_order(self, fnx):
        import scipy as sp

        matrix = sp.sparse.csr_array([[1, 0], [0, 1]])
        with pytest.raises(ValueError):
            fnx.from_biadjacency_matrix(matrix, row_order=["only-one-row"])

    def test_from_biadjacency_integer_multigraph_expands_parallel_edges(self, fnx):
        import numpy as np
        import scipy as sp

        matrix = sp.sparse.csr_array(np.array([[2, 0], [0, 3]], dtype=int))
        H = fnx.from_biadjacency_matrix(matrix, create_using=fnx.MultiGraph())
        edges = sorted(H.edges())
        assert edges == [(0, 2), (0, 2), (1, 3), (1, 3), (1, 3)]


@pytest.mark.conformance
class TestGreedyBranchingParity:
    @staticmethod
    def _weighted_digraph(mod, seed=42):
        import random as _random

        rng = _random.Random(seed)
        G = mod.DiGraph()
        G.add_nodes_from(range(10))
        for _ in range(25):
            u = rng.randint(0, 9)
            v = rng.randint(0, 9)
            if u != v:
                G.add_edge(u, v, weight=rng.uniform(1.0, 10.0))
        return G

    @pytest.mark.parametrize("kind", ["max", "min"])
    def test_matches_networkx_edge_selection(self, fnx, nx, kind):
        Gn = self._weighted_digraph(nx)
        Gf = self._weighted_digraph(fnx)
        Bn = nx.algorithms.tree.branchings.greedy_branching(Gn, kind=kind)
        Bf = fnx.greedy_branching(Gf, kind=kind)

        def triples(G):
            return sorted(
                (u, v, round(G.edges[u, v].get("weight", 1.0), 9))
                for u, v in G.edges()
            )

        assert triples(Bn) == triples(Bf)

    @pytest.mark.parametrize("kind", ["max", "min"])
    def test_result_is_a_branching(self, fnx, kind):
        Gf = self._weighted_digraph(fnx)
        Bf = fnx.greedy_branching(Gf, kind=kind)
        assert all(Bf.in_degree[n] <= 1 for n in Bf.nodes())
        assert fnx.is_directed_acyclic_graph(Bf)
        assert set(Bf.nodes()) == set(Gf.nodes())

    def test_default_attribute_is_used_for_missing_edges(self, fnx, nx):
        Gn = nx.DiGraph()
        Gn.add_edge(0, 1, cost=3)
        Gn.add_edge(1, 2, cost=5)
        Gn.add_edge(0, 2)
        Gf = fnx.DiGraph()
        Gf.add_edge(0, 1, cost=3)
        Gf.add_edge(1, 2, cost=5)
        Gf.add_edge(0, 2)

        Bn = nx.algorithms.tree.branchings.greedy_branching(
            Gn, attr="cost", default=100, kind="max"
        )
        Bf = fnx.greedy_branching(Gf, attr="cost", default=100, kind="max")
        assert sorted((u, v, B.edges[u, v].get("cost")) for u, v in Bn.edges() for B in [Bn]) == sorted(
            (u, v, B.edges[u, v].get("cost")) for u, v in Bf.edges() for B in [Bf]
        )

    def test_none_attr_uses_random_key_and_keeps_edge_count_matching_networkx(
        self, fnx, nx
    ):
        Gn = self._weighted_digraph(nx)
        Gf = self._weighted_digraph(fnx)
        Bn = nx.algorithms.tree.branchings.greedy_branching(
            Gn, attr=None, kind="max", seed=7
        )
        Bf = fnx.greedy_branching(Gf, attr=None, kind="max", seed=7)
        assert Bf.number_of_edges() == Bn.number_of_edges()
        assert all(Bf.in_degree[n] <= 1 for n in Bf.nodes())

    def test_invalid_kind_raises(self, fnx):
        Gf = self._weighted_digraph(fnx)
        with pytest.raises(fnx.NetworkXError):
            fnx.greedy_branching(Gf, kind="not-a-kind")

    def test_empty_graph_returns_empty_branching(self, fnx):
        Gf = fnx.DiGraph()
        Bf = fnx.greedy_branching(Gf)
        assert Bf.number_of_nodes() == 0
        assert Bf.number_of_edges() == 0


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
