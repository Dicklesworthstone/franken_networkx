"""Tests for DAG extra functions: dag_longest_path, dag_longest_path_length,
lexicographic_topological_sort, topological_generations."""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def diamond_dag():
    """DAG: 0->1, 0->2, 1->3, 2->3."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(1, 3)
    D.add_edge(2, 3)
    return D


@pytest.fixture
def chain_dag():
    """Linear DAG: 0->1->2->3->4."""
    D = fnx.DiGraph()
    for i in range(4):
        D.add_edge(i, i + 1)
    return D


@pytest.fixture
def wide_dag():
    """Wide DAG: 0->1, 0->2, 0->3, 1->4, 2->4, 3->4."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(0, 3)
    D.add_edge(1, 4)
    D.add_edge(2, 4)
    D.add_edge(3, 4)
    return D


# ---------------------------------------------------------------------------
# dag_longest_path
# ---------------------------------------------------------------------------


class TestDagLongestPath:
    def test_chain(self, chain_dag):
        path = fnx.dag_longest_path(chain_dag)
        assert path == [0, 1, 2, 3, 4]

    def test_diamond(self, diamond_dag):
        path = fnx.dag_longest_path(diamond_dag)
        assert len(path) == 3
        assert path[0] == 0
        assert path[-1] == 3

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(0)
        path = fnx.dag_longest_path(D)
        assert path == [0]

    def test_two_nodes(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        path = fnx.dag_longest_path(D)
        assert path == [0, 1]

    # br-r37-c1-sn6tm: nx's tie-breaking returns the FIRST predecessor in
    # G.pred[v] iteration order when two paths have equal length. Pre-fix
    # fnx delegated to nx via _fnx_to_nx, but the conversion emits edges in
    # source-node-iteration (adj) order — which scrambles G.pred[v] order
    # in the converted graph. nx then chose the wrong tie-break and fnx
    # returned a different (but equally-valid) longest path. Implementing
    # the algorithm natively on fnx.G.pred restores exact parity.
    def test_tie_break_matches_nx_with_reordered_node_set(self):
        import networkx as nx

        # Construct so adj-order would scramble pred[4]:
        # nodes added [5,1,3,2,4,6] → adj-iteration of source 3 comes
        # before source 2, but pred[4] insertion order is 2 then 3 (because
        # add_edge(2,4) happens before add_edge(3,4)).
        edges = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (4, 6)]
        node_order = [5, 1, 3, 2, 4, 6]

        D = fnx.DiGraph()
        D.add_nodes_from(node_order)
        for u, v in edges:
            D.add_edge(u, v)

        Dn = nx.DiGraph()
        Dn.add_nodes_from(node_order)
        for u, v in edges:
            Dn.add_edge(u, v)

        # Both must agree on tie-break — first predecessor inserted wins.
        assert fnx.dag_longest_path(D) == nx.dag_longest_path(Dn) == [1, 2, 4, 5]

    def test_weighted_tie_break_matches_nx(self):
        import networkx as nx

        D = fnx.DiGraph()
        Dn = nx.DiGraph()
        for u, v, w in [(0, 1, 1), (1, 2, 1), (0, 2, 42), (2, 3, 1)]:
            D.add_edge(u, v, cost=w)
            Dn.add_edge(u, v, cost=w)
        assert fnx.dag_longest_path(D, weight="cost") == nx.dag_longest_path(
            Dn, weight="cost"
        ) == [0, 2, 3]

    def test_topo_order_param_changes_tie_break(self):
        import networkx as nx

        D = fnx.DiGraph([(0, 1), (0, 2)])
        Dn = nx.DiGraph([(0, 1), (0, 2)])
        # With explicit topo_order, nx picks the second-in-order child.
        assert fnx.dag_longest_path(D, topo_order=[0, 1, 2]) == nx.dag_longest_path(
            Dn, topo_order=[0, 1, 2]
        )
        assert fnx.dag_longest_path(D, topo_order=[0, 2, 1]) == nx.dag_longest_path(
            Dn, topo_order=[0, 2, 1]
        )

    def test_empty_graph_returns_empty_list(self):
        assert fnx.dag_longest_path(fnx.DiGraph()) == []

    def test_undirected_raises_not_implemented(self):
        import pytest

        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.dag_longest_path(fnx.Graph([(1, 2)]))

    def test_cyclic_raises_unfeasible(self):
        import pytest

        D = fnx.DiGraph()
        D.add_edge(1, 2)
        D.add_edge(2, 1)
        with pytest.raises(fnx.NetworkXUnfeasible):
            fnx.dag_longest_path(D)


# ---------------------------------------------------------------------------
# dag_longest_path_length
# ---------------------------------------------------------------------------


class TestDagLongestPathLength:
    def test_chain(self, chain_dag):
        length = fnx.dag_longest_path_length(chain_dag)
        assert length == 4

    def test_diamond(self, diamond_dag):
        length = fnx.dag_longest_path_length(diamond_dag)
        assert length == 2

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(0)
        length = fnx.dag_longest_path_length(D)
        assert length == 0

    def test_wide(self, wide_dag):
        length = fnx.dag_longest_path_length(wide_dag)
        assert length == 2


# ---------------------------------------------------------------------------
# lexicographic_topological_sort
# ---------------------------------------------------------------------------


class TestLexicographicTopologicalSort:
    def test_diamond(self, diamond_dag):
        order = list(fnx.lexicographic_topological_sort(diamond_dag))
        assert set(order) == {0, 1, 2, 3}
        # Must be a valid topological order
        assert order.index(0) < order.index(1)
        assert order.index(0) < order.index(2)
        assert order.index(1) < order.index(3)
        assert order.index(2) < order.index(3)

    def test_lexicographic_tiebreak(self):
        """When multiple sources exist, smaller label should come first."""
        D = fnx.DiGraph()
        D.add_edge(0, 2)
        D.add_edge(1, 2)
        order = list(fnx.lexicographic_topological_sort(D))
        # Both 0 and 1 are sources; lexicographic means 0 before 1
        assert order.index(0) < order.index(1)

    def test_chain(self, chain_dag):
        order = list(fnx.lexicographic_topological_sort(chain_dag))
        assert order == [0, 1, 2, 3, 4]

    def test_cycle_raises(self):
        # br-zzcm7: matches nx which raises NetworkXUnfeasible (not HasACycle)
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        with pytest.raises(fnx.NetworkXUnfeasible):
            list(fnx.lexicographic_topological_sort(D))


# ---------------------------------------------------------------------------
# topological_generations
# ---------------------------------------------------------------------------


class TestTopologicalGenerations:
    def test_diamond(self, diamond_dag):
        gens = list(fnx.topological_generations(diamond_dag))
        assert len(gens) == 3
        assert set(gens[0]) == {0}
        assert set(gens[1]) == {1, 2}
        assert set(gens[2]) == {3}

    def test_chain(self, chain_dag):
        gens = list(fnx.topological_generations(chain_dag))
        assert len(gens) == 5
        for i, gen in enumerate(gens):
            assert gen == [i]

    def test_wide(self, wide_dag):
        gens = list(fnx.topological_generations(wide_dag))
        assert len(gens) == 3
        assert set(gens[0]) == {0}
        assert set(gens[1]) == {1, 2, 3}
        assert set(gens[2]) == {4}

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(42)
        gens = list(fnx.topological_generations(D))
        assert len(gens) == 1
        assert gens[0] == [42]

    def test_cycle_raises(self):
        # br-zzcm7: matches nx which raises NetworkXUnfeasible (not HasACycle)
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        with pytest.raises(fnx.NetworkXUnfeasible):
            list(fnx.topological_generations(D))


# ---------------------------------------------------------------------------
# antichains
# ---------------------------------------------------------------------------


class TestAntichains:
    def test_diamond_antichains(self, diamond_dag):
        """Diamond DAG should have antichains: [], [0], [1], [2], [3], [1, 2]."""
        antichains = list(fnx.antichains(diamond_dag))
        # Convert to frozensets for comparison (order doesn't matter)
        ac_sets = {frozenset(ac) for ac in antichains}
        expected = {
            frozenset(),
            frozenset([0]),
            frozenset([1]),
            frozenset([2]),
            frozenset([3]),
            frozenset([1, 2]),
        }
        assert ac_sets == expected

    def test_antichains_with_topo_order(self, diamond_dag):
        """antichains(topo_order=...) should match NetworkX behavior."""
        import networkx as nx

        # Get a topological order
        topo = list(fnx.topological_sort(diamond_dag))

        # Build equivalent NetworkX graph
        G_nx = nx.DiGraph()
        G_nx.add_edges_from(diamond_dag.edges)

        # Compare antichains with explicit topo_order
        fnx_ac = {frozenset(ac) for ac in fnx.antichains(diamond_dag, topo_order=topo)}
        nx_ac = {frozenset(ac) for ac in nx.antichains(G_nx, topo_order=topo)}
        assert fnx_ac == nx_ac

    def test_antichains_topo_order_affects_output_order(self):
        """Different topo_orders may produce antichains in different orders."""
        D = fnx.DiGraph()
        D.add_edge(0, 2)
        D.add_edge(1, 2)
        # Two valid topological orders: [0, 1, 2] or [1, 0, 2]
        topo1 = [0, 1, 2]
        topo2 = [1, 0, 2]

        ac1 = list(fnx.antichains(D, topo_order=topo1))
        ac2 = list(fnx.antichains(D, topo_order=topo2))

        # Same antichains, but possibly different order
        assert {frozenset(ac) for ac in ac1} == {frozenset(ac) for ac in ac2}
