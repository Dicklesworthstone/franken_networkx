"""Tests for BFS, DFS, DAG, all_shortest_paths, and complement."""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def diamond():
    """Diamond graph: 0-1, 0-2, 1-3, 2-3."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(0, 2)
    G.add_edge(1, 3)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def path5():
    """Path graph: 0-1-2-3-4."""
    G = fnx.Graph()
    for i in range(4):
        G.add_edge(i, i + 1)
    return G


@pytest.fixture
def dag():
    """DAG: 0->1, 0->2, 1->3, 2->3."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(1, 3)
    D.add_edge(2, 3)
    return D


# ---------------------------------------------------------------------------
# BFS tests
# ---------------------------------------------------------------------------


class TestBFS:
    def test_bfs_edges_basic(self, diamond):
        edges = list(fnx.bfs_edges(diamond, 0))
        assert len(edges) == 3
        # First two edges must start from 0
        assert edges[0][0] == 0
        assert edges[1][0] == 0

    def test_bfs_edges_depth_limit(self, path5):
        edges = list(fnx.bfs_edges(path5, 0, depth_limit=2))
        nodes_reached = {0}
        for u, v in edges:
            nodes_reached.add(v)
        assert 2 in nodes_reached
        assert 3 not in nodes_reached

    def test_bfs_tree(self, diamond):
        tree = fnx.bfs_tree(diamond, 0)
        assert tree.number_of_nodes() == 4
        # BFS tree is a directed tree
        assert tree.number_of_edges() == 3

    def test_bfs_predecessors(self, diamond):
        preds = list(fnx.bfs_predecessors(diamond, 0))
        pred_dict = dict(preds)
        assert pred_dict[1] == 0
        assert pred_dict[2] == 0

    def test_bfs_successors(self, diamond):
        succs = list(fnx.bfs_successors(diamond, 0))
        succ_dict = dict(succs)
        assert set(succ_dict[0]) == {1, 2}

    def test_bfs_layers(self, diamond):
        layers = list(fnx.bfs_layers(diamond, 0))
        assert layers[0] == [0]
        assert set(layers[1]) == {1, 2}
        assert layers[2] == [3]

    def test_descendants_at_distance(self, diamond):
        d0 = fnx.descendants_at_distance(diamond, 0, 0)
        assert d0 == frozenset({0})
        d1 = fnx.descendants_at_distance(diamond, 0, 1)
        assert d1 == frozenset({1, 2})
        d2 = fnx.descendants_at_distance(diamond, 0, 2)
        assert d2 == frozenset({3})

    def test_bfs_edges_on_digraph(self, dag):
        edges = list(fnx.bfs_edges(dag, 0))
        assert len(edges) == 3
        nodes = {0}
        for u, v in edges:
            nodes.add(v)
        assert nodes == {0, 1, 2, 3}

    def test_bfs_edges_reverse_on_digraph(self, dag):
        edges = list(fnx.bfs_edges(dag, 3, reverse=True))
        assert edges == [(3, 1), (3, 2), (1, 0)]

    def test_bfs_tree_reverse_on_digraph(self, dag):
        tree = fnx.bfs_tree(dag, 3, reverse=True)
        assert set(tree.edges()) == {(3, 1), (3, 2), (1, 0)}

    def test_bfs_node_not_found(self, diamond):
        with pytest.raises(fnx.NodeNotFound):
            list(fnx.bfs_edges(diamond, 99))


# ---------------------------------------------------------------------------
# DFS tests
# ---------------------------------------------------------------------------


class TestDFS:
    def test_dfs_edges_basic(self, diamond):
        edges = list(fnx.dfs_edges(diamond, 0))
        assert len(edges) == 3
        # All nodes visited
        nodes = {0}
        for u, v in edges:
            nodes.add(v)
        assert nodes == {0, 1, 2, 3}

    def test_dfs_edges_depth_limit(self, path5):
        edges = list(fnx.dfs_edges(path5, 0, depth_limit=2))
        nodes_reached = {0}
        for u, v in edges:
            nodes_reached.add(v)
        assert 2 in nodes_reached
        assert 3 not in nodes_reached

    def test_dfs_tree(self, diamond):
        tree = fnx.dfs_tree(diamond, 0)
        assert tree.number_of_nodes() == 4
        assert tree.number_of_edges() == 3

    def test_dfs_predecessors(self, diamond):
        preds = dict(fnx.dfs_predecessors(diamond, 0))
        # Every non-root node has exactly one predecessor
        assert 0 not in preds
        assert len(preds) == 3

    def test_dfs_successors(self, diamond):
        succs = dict(fnx.dfs_successors(diamond, 0))
        # Root has successors
        assert 0 in succs

    def test_dfs_preorder_nodes(self, path5):
        nodes = list(fnx.dfs_preorder_nodes(path5, 0))
        assert nodes[0] == 0
        assert set(nodes) == {0, 1, 2, 3, 4}

    def test_dfs_postorder_nodes(self, path5):
        nodes = list(fnx.dfs_postorder_nodes(path5, 0))
        # Root should be last in postorder
        assert nodes[-1] == 0
        assert set(nodes) == {0, 1, 2, 3, 4}

    def test_dfs_on_digraph(self, dag):
        edges = list(fnx.dfs_edges(dag, 0))
        nodes = {0}
        for u, v in edges:
            nodes.add(v)
        assert nodes == {0, 1, 2, 3}

    def test_dfs_source_none_traverses_all_components(self):
        g = fnx.Graph()
        g.add_edge(0, 1)
        g.add_edge(2, 3)
        g.add_node(4)

        edges = list(fnx.dfs_edges(g))
        assert len(edges) == 2

        preds = dict(fnx.dfs_predecessors(g))
        succs = dict(fnx.dfs_successors(g))
        assert len(preds) == 2
        assert len(succs) == 2

        preorder = list(fnx.dfs_preorder_nodes(g))
        postorder = list(fnx.dfs_postorder_nodes(g))
        assert set(preorder) == {0, 1, 2, 3, 4}
        assert set(postorder) == {0, 1, 2, 3, 4}

        tree = fnx.dfs_tree(g)
        assert tree.number_of_nodes() == 5
        assert tree.number_of_edges() == 2

    def test_dfs_source_none_on_digraph(self):
        d = fnx.DiGraph()
        d.add_edge(0, 1)
        d.add_edge(2, 3)
        d.add_node(4)

        edges = list(fnx.dfs_edges(d))
        assert len(edges) == 2

        preorder = list(fnx.dfs_preorder_nodes(d))
        postorder = list(fnx.dfs_postorder_nodes(d))
        assert set(preorder) == {0, 1, 2, 3, 4}
        assert set(postorder) == {0, 1, 2, 3, 4}

    def test_dfs_source_none_respects_prior_visits_on_digraph(self):
        d = fnx.DiGraph()
        d.add_node(0)
        d.add_node(1)
        d.add_edge(1, 0)

        edges = list(fnx.dfs_edges(d))
        assert edges == []


# ---------------------------------------------------------------------------
# DAG tests
# ---------------------------------------------------------------------------


class TestDAG:
    def test_is_directed_acyclic_graph_true(self, dag):
        assert fnx.is_directed_acyclic_graph(dag) is True

    def test_is_directed_acyclic_graph_cycle(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        D.add_edge(2, 0)
        assert fnx.is_directed_acyclic_graph(D) is False

    def test_is_directed_acyclic_graph_undirected(self, diamond):
        # Undirected graphs always return False
        assert fnx.is_directed_acyclic_graph(diamond) is False

    def test_topological_sort(self, dag):
        order = list(fnx.topological_sort(dag))
        assert set(order) == {0, 1, 2, 3}
        # 0 must come before 1 and 2
        assert order.index(0) < order.index(1)
        assert order.index(0) < order.index(2)
        # 1 and 2 must come before 3
        assert order.index(1) < order.index(3)
        assert order.index(2) < order.index(3)

    def test_topological_sort_cycle_raises(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        with pytest.raises(fnx.HasACycle):
            list(fnx.topological_sort(D))

    def test_ancestors(self, dag):
        anc = fnx.ancestors(dag, 3)
        assert anc == frozenset({0, 1, 2})

    def test_ancestors_root(self, dag):
        anc = fnx.ancestors(dag, 0)
        assert anc == frozenset()

    def test_descendants(self, dag):
        desc = fnx.descendants(dag, 0)
        assert desc == frozenset({1, 2, 3})

    def test_descendants_leaf(self, dag):
        desc = fnx.descendants(dag, 3)
        assert desc == frozenset()


# ---------------------------------------------------------------------------
# all_shortest_paths tests
# ---------------------------------------------------------------------------


class TestAllShortestPaths:
    def test_diamond_two_paths(self, diamond):
        paths = list(fnx.all_shortest_paths(diamond, 0, 3))
        assert len(paths) == 2
        assert [0, 1, 3] in paths
        assert [0, 2, 3] in paths

    def test_single_path(self, path5):
        paths = list(fnx.all_shortest_paths(path5, 0, 4))
        assert len(paths) == 1
        assert paths[0] == [0, 1, 2, 3, 4]

    def test_same_node(self, diamond):
        paths = list(fnx.all_shortest_paths(diamond, 0, 0))
        assert paths == [[0]]

    def test_no_path_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        with pytest.raises(fnx.NetworkXNoPath):
            list(fnx.all_shortest_paths(G, 0, 1))

    def test_node_not_found_raises(self, diamond):
        with pytest.raises(fnx.NodeNotFound):
            list(fnx.all_shortest_paths(diamond, 0, 99))

    def test_directed_diamond(self, dag):
        paths = list(fnx.all_shortest_paths(dag, 0, 3))
        assert len(paths) == 2
        assert [0, 1, 3] in paths
        assert [0, 2, 3] in paths

    def test_directed_no_reverse_path(self, dag):
        with pytest.raises(fnx.NetworkXNoPath):
            list(fnx.all_shortest_paths(dag, 3, 0))

    def test_weighted_equal(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(0, 2, weight=1.0)
        G.add_edge(1, 3, weight=1.0)
        G.add_edge(2, 3, weight=1.0)
        paths = list(fnx.all_shortest_paths(G, 0, 3, weight="weight"))
        assert len(paths) == 2

    def test_weighted_unique(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=1.0)
        G.add_edge(0, 2, weight=10.0)
        paths = list(fnx.all_shortest_paths(G, 0, 2, weight="weight"))
        assert len(paths) == 1
        assert paths[0] == [0, 1, 2]


# ---------------------------------------------------------------------------
# complement tests
# ---------------------------------------------------------------------------


class TestComplement:
    def test_complement_triangle(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(0, 2)
        G.add_edge(1, 2)
        C = fnx.complement(G)
        assert C.number_of_nodes() == 3
        assert C.number_of_edges() == 0

    def test_complement_empty(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        G.add_node(2)
        C = fnx.complement(G)
        assert C.number_of_nodes() == 3
        assert C.number_of_edges() == 3
        assert C.has_edge(0, 1)
        assert C.has_edge(0, 2)
        assert C.has_edge(1, 2)

    def test_complement_path(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        C = fnx.complement(G)
        assert C.number_of_nodes() == 3
        assert C.number_of_edges() == 1
        assert C.has_edge(0, 2)
        assert not C.has_edge(0, 1)
        assert not C.has_edge(1, 2)

    def test_complement_involution(self, diamond):
        C2 = fnx.complement(fnx.complement(diamond))
        assert C2.number_of_edges() == diamond.number_of_edges()
        for u, v in diamond.edges():
            assert C2.has_edge(u, v)

    def test_complement_preserves_type(self, diamond):
        C = fnx.complement(diamond)
        assert isinstance(C, fnx.Graph)

    def test_complement_digraph(self, dag):
        C = fnx.complement(dag)
        assert isinstance(C, fnx.DiGraph)
        # Original has 4 edges, complete digraph has 4*3=12 edges
        # Complement should have 12-4=8 edges
        assert C.number_of_edges() == 8
