"""Parity tests for sort_neighbors parameter on BFS/DFS traversal (bead 0i2)."""
import pytest
import franken_networkx as fnx
import networkx as nx


@pytest.fixture
def tree_graph():
    G = fnx.Graph()
    G.add_edges_from([(0, 3), (0, 2), (0, 1), (1, 4), (2, 5)])
    return G


@pytest.fixture
def nx_tree_graph():
    G = nx.Graph()
    G.add_edges_from([(0, 3), (0, 2), (0, 1), (1, 4), (2, 5)])
    return G


class TestBFSSortNeighbors:
    def test_bfs_edges_sorted(self, tree_graph, nx_tree_graph):
        be = list(fnx.bfs_edges(tree_graph, 0, sort_neighbors=sorted))
        nbe = list(nx.bfs_edges(nx_tree_graph, 0, sort_neighbors=sorted))
        assert be == nbe

    def test_bfs_edges_none_unchanged(self, tree_graph, nx_tree_graph):
        be = list(fnx.bfs_edges(tree_graph, 0))
        nbe = list(nx.bfs_edges(nx_tree_graph, 0))
        assert be == nbe

    def test_bfs_edges_custom_reverse(self, tree_graph, nx_tree_graph):
        rev = lambda x: sorted(x, reverse=True)
        be = list(fnx.bfs_edges(tree_graph, 0, sort_neighbors=rev))
        nbe = list(nx.bfs_edges(nx_tree_graph, 0, sort_neighbors=rev))
        assert be == nbe

    def test_bfs_predecessors_sorted(self, tree_graph, nx_tree_graph):
        bp = fnx.bfs_predecessors(tree_graph, 0, sort_neighbors=sorted)
        nbp = dict(nx.bfs_predecessors(nx_tree_graph, 0, sort_neighbors=sorted))
        assert bp == nbp

    def test_bfs_successors_sorted(self, tree_graph, nx_tree_graph):
        bs = fnx.bfs_successors(tree_graph, 0, sort_neighbors=sorted)
        nbs = dict(nx.bfs_successors(nx_tree_graph, 0, sort_neighbors=sorted))
        assert bs == nbs

    def test_bfs_tree_sorted(self, tree_graph, nx_tree_graph):
        bt = fnx.bfs_tree(tree_graph, 0, sort_neighbors=sorted)
        nbt = nx.bfs_tree(nx_tree_graph, 0, sort_neighbors=sorted)
        assert sorted(bt.edges()) == sorted(nbt.edges())


class TestDFSSortNeighbors:
    def test_dfs_edges_sorted(self, tree_graph, nx_tree_graph):
        de = list(fnx.dfs_edges(tree_graph, source=0, sort_neighbors=sorted))
        nde = list(nx.dfs_edges(nx_tree_graph, source=0, sort_neighbors=sorted))
        assert de == nde

    def test_dfs_predecessors_sorted(self, tree_graph, nx_tree_graph):
        dp = fnx.dfs_predecessors(tree_graph, source=0, sort_neighbors=sorted)
        ndp = dict(nx.dfs_predecessors(nx_tree_graph, source=0, sort_neighbors=sorted))
        assert dp == ndp

    def test_dfs_successors_sorted(self, tree_graph, nx_tree_graph):
        ds = fnx.dfs_successors(tree_graph, source=0, sort_neighbors=sorted)
        nds = dict(nx.dfs_successors(nx_tree_graph, source=0, sort_neighbors=sorted))
        assert ds == nds

    def test_dfs_preorder_sorted(self, tree_graph, nx_tree_graph):
        dpre = list(fnx.dfs_preorder_nodes(tree_graph, source=0, sort_neighbors=sorted))
        ndpre = list(nx.dfs_preorder_nodes(nx_tree_graph, source=0, sort_neighbors=sorted))
        assert dpre == ndpre

    def test_dfs_postorder_sorted(self, tree_graph, nx_tree_graph):
        dpost = list(fnx.dfs_postorder_nodes(tree_graph, source=0, sort_neighbors=sorted))
        ndpost = list(nx.dfs_postorder_nodes(nx_tree_graph, source=0, sort_neighbors=sorted))
        assert dpost == ndpost

    def test_dfs_tree_sorted(self, tree_graph, nx_tree_graph):
        dt = fnx.dfs_tree(tree_graph, source=0, sort_neighbors=sorted)
        ndt = nx.dfs_tree(nx_tree_graph, source=0, sort_neighbors=sorted)
        assert sorted(dt.edges()) == sorted(ndt.edges())
