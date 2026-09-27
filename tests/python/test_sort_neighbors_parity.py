"""Parity tests for sort_neighbors parameter on BFS/DFS traversal (bead 0i2)."""
from collections.abc import Iterator
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


@pytest.fixture
def forest_graph():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (2, 3)])
    return G


@pytest.fixture
def nx_forest_graph():
    G = nx.Graph()
    G.add_edges_from([(0, 1), (2, 3)])
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
        def rev(x): return sorted(x, reverse=True)
        be = list(fnx.bfs_edges(tree_graph, 0, sort_neighbors=rev))
        nbe = list(nx.bfs_edges(nx_tree_graph, 0, sort_neighbors=rev))
        assert be == nbe

    def test_bfs_predecessors_sorted(self, tree_graph, nx_tree_graph):
        bp = fnx.bfs_predecessors(tree_graph, 0, sort_neighbors=sorted)
        nbp = nx.bfs_predecessors(nx_tree_graph, 0, sort_neighbors=sorted)
        assert isinstance(bp, Iterator)
        assert list(bp) == list(nbp)

    def test_bfs_predecessors_unsorted_is_iterator(self, tree_graph, nx_tree_graph):
        bp = fnx.bfs_predecessors(tree_graph, 0)
        nbp = nx.bfs_predecessors(nx_tree_graph, 0)
        assert isinstance(bp, Iterator)
        assert list(bp) == list(nbp)

    def test_bfs_successors_sorted(self, tree_graph, nx_tree_graph):
        bs = dict(fnx.bfs_successors(tree_graph, 0, sort_neighbors=sorted))
        nbs = dict(nx.bfs_successors(nx_tree_graph, 0, sort_neighbors=sorted))
        assert bs == nbs

    def test_bfs_tree_sorted(self, tree_graph, nx_tree_graph):
        bt = fnx.bfs_tree(tree_graph, 0, sort_neighbors=sorted)
        nbt = nx.bfs_tree(nx_tree_graph, 0, sort_neighbors=sorted)
        assert list(bt.edges()) == list(nbt.edges())

    def test_bfs_tree_unsorted_preserves_edge_order(self, tree_graph, nx_tree_graph):
        bt = fnx.bfs_tree(tree_graph, 0)
        nbt = nx.bfs_tree(nx_tree_graph, 0)
        assert list(bt.edges()) == list(nbt.edges())

    def test_bfs_tree_reverse_preserves_edge_order(self):
        graph = fnx.DiGraph()
        nx_graph = nx.DiGraph()
        for G in (graph, nx_graph):
            G.add_edge(0, 1)
            G.add_edge(2, 1)
            G.add_edge(1, 3)
        bt = fnx.bfs_tree(graph, 3, reverse=True)
        nbt = nx.bfs_tree(nx_graph, 3, reverse=True)
        assert list(bt.edges()) == list(nbt.edges())


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

    def test_dfs_edges_forest_sorted(self, forest_graph, nx_forest_graph):
        de = list(fnx.dfs_edges(forest_graph, sort_neighbors=sorted))
        nde = list(nx.dfs_edges(nx_forest_graph, sort_neighbors=sorted))
        assert de == nde

    def test_dfs_tree_forest_sorted(self, forest_graph, nx_forest_graph):
        dt = fnx.dfs_tree(forest_graph, sort_neighbors=sorted)
        ndt = nx.dfs_tree(nx_forest_graph, sort_neighbors=sorted)
        assert sorted(dt.edges()) == sorted(ndt.edges())
        assert sorted(dt.nodes()) == sorted(ndt.nodes())

    def test_dfs_preorder_forest_sorted(self, forest_graph, nx_forest_graph):
        dpre = list(fnx.dfs_preorder_nodes(forest_graph, sort_neighbors=sorted))
        ndpre = list(nx.dfs_preorder_nodes(nx_forest_graph, sort_neighbors=sorted))
        assert dpre == ndpre

    def test_dfs_postorder_forest_sorted(self, forest_graph, nx_forest_graph):
        dpost = list(fnx.dfs_postorder_nodes(forest_graph, sort_neighbors=sorted))
        ndpost = list(nx.dfs_postorder_nodes(nx_forest_graph, sort_neighbors=sorted))
        assert dpost == ndpost


# br-r37-c1-mub4s: networkx calls sort_neighbors on a node's row ITERATOR when
# the node is discovered - before that node's edge is yielded, including for
# the last level a depth_limit allows - and stops once every node is seen. The
# event log interleaves those calls with the yields, so a walk that sorts at
# expansion time (the level queue this replaced) or hands over a list fails it.
_BFS_EDGES = [(0, 3), (0, 2), (0, 1), (1, 4), (2, 5), (4, 6), (5, 6), (3, 7)]
_DEPTHS = [None, 0, 1, 2, 2.5, float("nan"), float("inf"), -1]


def _bfs_event_log(lib, directed, call):
    G = (lib.DiGraph if directed else lib.Graph)(_BFS_EDGES)
    log = []

    def sort_neighbors(row):
        ordered = sorted(row, reverse=True)
        log.append(("sort", isinstance(row, Iterator), tuple(ordered)))
        return ordered

    for item in call(lib, G, sort_neighbors):
        log.append(("yield", item))
    return log


@pytest.mark.parametrize("depth_limit", _DEPTHS)
@pytest.mark.parametrize(
    ("directed", "reverse", "source"), [(False, False, 0), (True, False, 0), (True, True, 6)]
)
def test_bfs_edges_sort_neighbors_calls_match_networkx(depth_limit, directed, reverse, source):
    def call(lib, G, sort_neighbors):
        return lib.bfs_edges(G, source, reverse=reverse, depth_limit=depth_limit, sort_neighbors=sort_neighbors)

    assert _bfs_event_log(fnx, directed, call) == _bfs_event_log(nx, directed, call)


@pytest.mark.parametrize("depth_limit", [None, 1, 2])
def test_bfs_successors_and_tree_sort_neighbors_calls_match_networkx(depth_limit):
    for call in (
        lambda lib, G, s: lib.bfs_successors(G, 0, depth_limit=depth_limit, sort_neighbors=s),
        lambda lib, G, s: lib.bfs_predecessors(G, 0, depth_limit=depth_limit, sort_neighbors=s),
        lambda lib, G, s: lib.bfs_tree(G, 0, depth_limit=depth_limit, sort_neighbors=s).edges(),
    ):
        assert _bfs_event_log(fnx, False, call) == _bfs_event_log(nx, False, call)


@pytest.mark.parametrize("depth_limit", [None, 1, 2])
def test_generic_bfs_edges_calls_neighbors_on_discovery_like_networkx(depth_limit):
    def call(lib, G, sort_neighbors):
        return lib.generic_bfs_edges(
            G, 0, lambda node: iter(sort_neighbors(G.neighbors(node))), depth_limit
        )

    assert _bfs_event_log(fnx, False, call) == _bfs_event_log(nx, False, call)


@pytest.mark.parametrize("sort_neighbors", [sorted, None])
@pytest.mark.parametrize("depth_limit", [None, -1, float("nan")])
def test_bfs_edges_absent_source_raises_like_networkx(sort_neighbors, depth_limit):
    raised = []
    for lib in (fnx, nx):
        edges = lib.bfs_edges(lib.Graph(_BFS_EDGES), 99, depth_limit=depth_limit, sort_neighbors=sort_neighbors)
        with pytest.raises(nx.NetworkXError) as error:
            next(edges)
        raised.append(error.value.args)
    assert raised[0] == raised[1]
