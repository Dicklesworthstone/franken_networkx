"""Tests for newly-added Python bindings: tree recognition, isolates,
boundary and cuts, is_simple_path, matching validators, simple_cycles, find_cycle."""

import pytest
import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as _fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def triangle():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def path4():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def arborescence():
    """Directed rooted tree: 0 -> 1, 0 -> 2, 1 -> 3."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(1, 3)
    return D


@pytest.fixture
def directed_cycle():
    """Directed cycle: 0 -> 1 -> 2 -> 0."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    D.add_edge(2, 0)
    return D


# ---------------------------------------------------------------------------
# is_arborescence
# ---------------------------------------------------------------------------


class TestIsArborescence:
    def test_arborescence(self, arborescence):
        assert fnx.is_arborescence(arborescence) is True

    def test_cycle_not_arborescence(self, directed_cycle):
        assert fnx.is_arborescence(directed_cycle) is False

    def test_undirected_returns_false(self, triangle):
        assert fnx.is_arborescence(triangle) is False

    def test_empty_digraph(self):
        D = fnx.DiGraph()
        assert fnx.is_arborescence(D) is False

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(0)
        assert fnx.is_arborescence(D) is True

    def test_forest_not_arborescence(self):
        """A forest with two trees is not an arborescence."""
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(2, 3)
        assert fnx.is_arborescence(D) is False


# ---------------------------------------------------------------------------
# is_branching
# ---------------------------------------------------------------------------


class TestIsBranching:
    def test_arborescence_is_branching(self, arborescence):
        assert fnx.is_branching(arborescence) is True

    def test_forest_is_branching(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(2, 3)
        assert fnx.is_branching(D) is True

    def test_cycle_not_branching(self, directed_cycle):
        assert fnx.is_branching(directed_cycle) is False

    def test_undirected_returns_false(self, triangle):
        assert fnx.is_branching(triangle) is False

    def test_empty_digraph(self):
        D = fnx.DiGraph()
        assert fnx.is_branching(D) is True


# ---------------------------------------------------------------------------
# branching and arborescence constructors
# ---------------------------------------------------------------------------


class TestBranchingConstructors:
    def test_graph_edge_view_preserves_insertion_order(self):
        graph = fnx.Graph()
        for edge in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]:
            graph.add_edge(*edge)

        assert list(graph.edges()) == [
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 2),
            (1, 3),
            (2, 3),
        ]

    def test_maximum_branching_preserve_attrs(self):
        D = fnx.DiGraph()
        D.add_edge("a", "b", weight=5.0, color="red")
        D.add_edge("c", "b", weight=4.0, color="blue")

        kept = fnx.maximum_branching(D, preserve_attrs=True)
        assert kept.edges["a", "b"]["weight"] == 5.0
        assert kept.edges["a", "b"]["color"] == "red"

        dropped = fnx.maximum_branching(D, preserve_attrs=False)
        assert dropped.edges["a", "b"]["weight"] == 5.0
        assert "color" not in dropped.edges["a", "b"]

    def test_empty_spanning_arborescence_raises(self):
        D = fnx.DiGraph()
        with pytest.raises(fnx.NetworkXPointlessConcept):
            fnx.maximum_spanning_arborescence(D)
        with pytest.raises(fnx.NetworkXPointlessConcept):
            fnx.minimum_spanning_arborescence(D)

    def test_spanning_arborescence_supports_partition_constraints(self):
        fnx_graph = fnx.DiGraph()
        nx_graph = nx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    fnx_graph.add_edge(u, v, weight=1)
                    nx_graph.add_edge(u, v, weight=1)

        fnx_graph.edges[0, 1]["partition"] = fnx.EdgePartition.INCLUDED
        fnx_graph.edges[0, 2]["partition"] = fnx.EdgePartition.EXCLUDED
        nx_graph.edges[0, 1]["partition"] = nx.EdgePartition.INCLUDED
        nx_graph.edges[0, 2]["partition"] = nx.EdgePartition.EXCLUDED

        assert sorted(
            fnx.minimum_spanning_arborescence(fnx_graph, partition="partition").edges()
        ) == sorted(
            nx.minimum_spanning_arborescence(nx_graph, partition="partition").edges()
        )
        assert sorted(
            fnx.maximum_spanning_arborescence(fnx_graph, partition="partition").edges()
        ) == sorted(
            nx.maximum_spanning_arborescence(nx_graph, partition="partition").edges()
        )

    def test_spanning_tree_iterator_rust_preserves_keys_and_attrs(self):
        graph = fnx.Graph()
        graph.graph["label"] = "demo"
        graph.add_node(10, color="red")
        graph.add_node(20, color="blue")
        graph.add_edge(10, 20, weight=7, tag="x")

        tree = next(_fnx.spanning_tree_iterator_rust(graph))

        assert list(tree.nodes()) == [10, 20]
        assert list(tree.edges()) == [(10, 20)]
        assert tree.nodes[10]["color"] == "red"
        assert tree.nodes[20]["color"] == "blue"
        assert tree.edges[10, 20]["weight"] == 7
        assert tree.edges[10, 20]["tag"] == "x"
        assert dict(tree.graph) == {"label": "demo"}

    def test_arborescence_iterator_rust_preserves_keys_and_attrs(self):
        digraph = fnx.DiGraph()
        digraph.graph["name"] = "demo"
        digraph.add_node(1, role="root")
        digraph.add_node(2, role="leaf")
        digraph.add_edge(1, 2, weight=3, tag="keep")

        arb = next(_fnx.arborescence_iterator_rust(digraph))

        assert list(arb.nodes()) == [1, 2]
        assert list(arb.edges()) == [(1, 2)]
        assert arb.nodes[1]["role"] == "root"
        assert arb.nodes[2]["role"] == "leaf"
        assert arb.edges[1, 2]["weight"] == 3
        assert arb.edges[1, 2]["tag"] == "keep"
        assert dict(arb.graph) == {"name": "demo"}

    def test_arborescence_iterator_honors_init_partition(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1, weight=1)
        digraph.add_edge(0, 2, weight=1)
        digraph.add_edge(1, 2, weight=1)
        digraph.add_edge(2, 1, weight=1)

        arbs = list(
            fnx.ArborescenceIterator(
                digraph,
                weight="weight",
                minimum=True,
                init_partition=([(0, 1)], []),
            )
        )

        assert [sorted(arb.edges()) for arb in arbs] == [
            [(0, 1), (0, 2)],
            [(0, 1), (1, 2)],
        ]

    def test_arborescence_iterator_honors_excluded_edges_in_init_partition(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1, weight=1)
        digraph.add_edge(0, 2, weight=1)
        digraph.add_edge(1, 2, weight=1)
        digraph.add_edge(2, 1, weight=1)

        arbs = list(
            fnx.ArborescenceIterator(
                digraph,
                weight="weight",
                minimum=True,
                init_partition=([], [(0, 1)]),
            )
        )

        assert [sorted(arb.edges()) for arb in arbs] == [[(0, 2), (2, 1)]]

    def test_arborescence_iterator_constructor_preserves_init_partition(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1, weight=1)
        digraph.add_edge(0, 2, weight=1)
        digraph.add_edge(1, 2, weight=1)
        digraph.add_edge(2, 1, weight=1)

        iterator = fnx.ArborescenceIterator(
            digraph,
            weight="weight",
            minimum=True,
            init_partition=([(0, 1)], []),
        )

        assert isinstance(iterator, fnx.ArborescenceIterator)
        assert [sorted(arb.edges()) for arb in iterator] == [
            [(0, 1), (0, 2)],
            [(0, 1), (1, 2)],
        ]

    def test_arborescence_iterator_rust_honors_init_partition_keyword(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1, weight=1)
        digraph.add_edge(0, 2, weight=1)
        digraph.add_edge(1, 2, weight=1)
        digraph.add_edge(2, 1, weight=1)

        arbs = list(
            _fnx.arborescence_iterator_rust(
                digraph,
                max_count=10,
                init_partition=([(0, 1)], []),
            )
        )

        assert [sorted(arb.edges()) for arb in arbs] == [
            [(0, 1), (0, 2)],
            [(0, 1), (1, 2)],
        ]

    def test_spanning_tree_iterator_honors_ignore_nan(self):
        graph = fnx.Graph()
        graph.add_edge("a", "b", weight=float("nan"))
        graph.add_edge("b", "c", weight=1.0)
        graph.add_edge("a", "c", weight=2.0)

        with pytest.raises(ValueError, match="NaN found as an edge weight"):
            list(fnx.SpanningTreeIterator(graph, weight="weight", ignore_nan=False))

        trees = list(fnx.SpanningTreeIterator(graph, weight="weight", ignore_nan=True))

        assert len(trees) == 1
        assert sorted(trees[0].edges()) == [("a", "c"), ("b", "c")]

    def test_spanning_tree_iterator_rejects_directed_graphs(self):
        digraph = fnx.DiGraph()
        digraph.add_edge("a", "b", weight=1)

        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            next(iter(fnx.SpanningTreeIterator(digraph)))

        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            _fnx.spanning_tree_iterator_rust(digraph)

    def test_spanning_tree_iterator_rejects_multigraphs(self):
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0, weight=1)
        multigraph.add_edge("a", "b", key=1, weight=2)

        with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph type"):
            next(iter(fnx.SpanningTreeIterator(multigraph)))

        with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph type"):
            _fnx.spanning_tree_iterator_rust(multigraph)
    def test_arborescence_iterator_rejects_undirected_graphs(self):
        graph = fnx.Graph()
        graph.add_edge("a", "b", weight=1)

        with pytest.raises(fnx.NetworkXNotImplemented, match="undirected type"):
            next(iter(fnx.ArborescenceIterator(graph)))

        with pytest.raises(fnx.NetworkXNotImplemented, match="undirected type"):
            _fnx.arborescence_iterator_rust(graph)
    def test_arborescence_iterator_rejects_null_digraph(self):
        digraph = fnx.DiGraph()

        with pytest.raises(fnx.NetworkXPointlessConcept, match="G has no nodes"):
            next(iter(fnx.ArborescenceIterator(digraph)))

        # The rust-level binding does not check node count; the python wrapper does.
        # So we no longer test that _fnx.arborescence_iterator_rust(digraph) raises it.

    def test_arborescence_iterator_rejects_multidigraphs(self):
        multidigraph = fnx.MultiDiGraph()
        multidigraph.add_edge("a", "b", key=0, weight=1)
        multidigraph.add_edge("a", "b", key=1, weight=2)

        with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph type"):
            next(iter(fnx.ArborescenceIterator(multidigraph)))

        with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph type"):
            _fnx.arborescence_iterator_rust(multidigraph)

    def test_spanning_tree_iterator_returns_spanning_forest_for_disconnected_graph(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1, weight=2, tag="keep")
        graph.add_node(2, color="solo")

        forests = list(fnx.SpanningTreeIterator(graph))
        raw_forests = list(_fnx.spanning_tree_iterator_rust(graph))

        assert len(forests) == 1
        assert len(raw_forests) == 1
        assert sorted(forests[0].edges()) == [(0, 1)]
        assert sorted(raw_forests[0].edges()) == [(0, 1)]
        assert sorted(forests[0].nodes()) == [0, 1, 2]
        assert sorted(raw_forests[0].nodes()) == [0, 1, 2]
        assert forests[0].edges[0, 1]["tag"] == "keep"

    def test_spanning_tree_iterator_rust_honors_max_count_keyword(self):
        graph = fnx.complete_graph(4)

        assert len(list(_fnx.spanning_tree_iterator_rust(graph, max_count=1))) == 1
        assert len(list(_fnx.spanning_tree_iterator_rust(graph, max_count=2))) == 2
        assert len(list(_fnx.spanning_tree_iterator_rust(graph, max_count=5))) == 5

    def test_arborescence_iterator_rust_honors_max_count_keyword(self):
        digraph = fnx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    digraph.add_edge(u, v, weight=1)

        assert len(list(_fnx.arborescence_iterator_rust(digraph, max_count=1))) == 1
        assert len(list(_fnx.arborescence_iterator_rust(digraph, max_count=2))) == 2
        assert len(list(_fnx.arborescence_iterator_rust(digraph, max_count=5))) == 5

    def test_arborescence_iterator_raises_for_disconnected_digraph(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1, weight=1)
        digraph.add_edge(2, 3, weight=2)

        with pytest.raises(fnx.NetworkXError, match="No minimum spanning arborescence"):
            list(fnx.ArborescenceIterator(digraph))
        with pytest.raises(fnx.NetworkXError, match="No minimum spanning arborescence"):
            _fnx.arborescence_iterator_rust(digraph)

        with pytest.raises(fnx.NetworkXError, match="No maximum spanning arborescence"):
            list(fnx.ArborescenceIterator(digraph, minimum=False))
        with pytest.raises(fnx.NetworkXError, match="No maximum spanning arborescence"):
            _fnx.arborescence_iterator_rust(digraph, minimum=False)

    def test_arborescence_iterator_complete_digraph_k4_count(self):
        digraph = fnx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    digraph.add_edge(u, v, weight=1)

        arbs = list(fnx.ArborescenceIterator(digraph))

        assert len(arbs) == 64
        assert len({tuple(sorted(arb.edges())) for arb in arbs}) == 64

    def test_arborescence_iterator_complete_digraph_k5_exceeds_old_wrapper_cap(self):
        digraph = fnx.DiGraph()
        for u in range(5):
            for v in range(5):
                if u != v:
                    digraph.add_edge(u, v, weight=1)

        assert sum(1 for _ in fnx.ArborescenceIterator(digraph)) == 625

    def test_complete_digraph_k4_branching_and_arborescences_match_networkx(self):
        nx_graph = nx.DiGraph()
        fnx_graph = fnx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    nx_graph.add_edge(u, v, weight=1)
                    fnx_graph.add_edge(u, v, weight=1)

        assert sorted(fnx.maximum_branching(fnx_graph).edges()) == sorted(
            nx.maximum_branching(nx_graph).edges()
        )
        assert sorted(fnx.maximum_spanning_arborescence(fnx_graph).edges()) == sorted(
            nx.maximum_spanning_arborescence(nx_graph).edges()
        )
        assert sorted(fnx.minimum_spanning_arborescence(fnx_graph).edges()) == sorted(
            nx.minimum_spanning_arborescence(nx_graph).edges()
        )

    def test_complete_digraph_k4_arborescence_iterator_matches_networkx_prefix(self):
        nx_graph = nx.DiGraph()
        fnx_graph = fnx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    nx_graph.add_edge(u, v, weight=1)
                    fnx_graph.add_edge(u, v, weight=1)

        nx_prefix = [sorted(tree.edges()) for _, tree in zip(range(12), nx.ArborescenceIterator(nx_graph))]
        fnx_prefix = [sorted(tree.edges()) for _, tree in zip(range(12), fnx.ArborescenceIterator(fnx_graph))]

        assert fnx_prefix == nx_prefix

    def test_complete_digraph_k4_arborescence_iterator_init_partition_matches_networkx(self):
        nx_graph = nx.DiGraph()
        fnx_graph = fnx.DiGraph()
        for u in range(4):
            for v in range(4):
                if u != v:
                    nx_graph.add_edge(u, v, weight=1)
                    fnx_graph.add_edge(u, v, weight=1)

        partition = ([(0, 1)], [(0, 2)])
        nx_prefix = [
            sorted(tree.edges())
            for _, tree in zip(
                range(5),
                nx.ArborescenceIterator(nx_graph, init_partition=partition),
            )
        ]
        fnx_prefix = [
            sorted(tree.edges())
            for _, tree in zip(
                range(5),
                fnx.ArborescenceIterator(fnx_graph, init_partition=partition),
            )
        ]

        assert fnx_prefix == nx_prefix

    def test_spanning_tree_iterator_matches_networkx_next_lifecycle(self):
        iterator = fnx.SpanningTreeIterator(fnx.path_graph(2))

        with pytest.raises(AttributeError, match="partition_queue"):
            next(iterator)

        iterator = iter(iterator)
        tree = next(iterator)
        assert sorted(tree.edges()) == [(0, 1)]

        with pytest.raises(StopIteration):
            next(iterator)
        with pytest.raises(AttributeError, match="partition_queue"):
            next(iterator)

    def test_arborescence_iterator_matches_networkx_next_lifecycle(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        iterator = fnx.ArborescenceIterator(digraph)

        with pytest.raises(AttributeError, match="partition_queue"):
            next(iterator)

        iterator = iter(iterator)
        arb = next(iterator)
        assert sorted(arb.edges()) == [(0, 1)]

        with pytest.raises(StopIteration):
            next(iterator)
        with pytest.raises(AttributeError, match="partition_queue"):
            next(iterator)


# ---------------------------------------------------------------------------
# is_isolate, isolates, number_of_isolates
# ---------------------------------------------------------------------------


class TestIsolates:
    def test_is_isolate_true(self):
        G = fnx.Graph()
        G.add_node(42)
        assert fnx.is_isolate(G, 42) is True

    def test_is_isolate_false(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        assert fnx.is_isolate(G, 0) is False

    def test_isolates_list(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        G.add_edge(2, 3)
        iso = list(fnx.isolates(G))
        assert set(iso) == {0, 1}

    def test_number_of_isolates(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        G.add_edge(2, 3)
        assert fnx.number_of_isolates(G) == 2

    def test_no_isolates(self, triangle):
        assert fnx.number_of_isolates(triangle) == 0
        assert list(fnx.isolates(triangle)) == []

    def test_directed_isolates(self):
        D = fnx.DiGraph()
        D.add_node(0)
        D.add_edge(1, 2)
        assert fnx.is_isolate(D, 0) is True
        assert fnx.is_isolate(D, 1) is False
        assert fnx.number_of_isolates(D) == 1

    def test_is_isolate_nonexistent_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        with pytest.raises(fnx.NodeNotFound):
            fnx.is_isolate(G, 99)


# ---------------------------------------------------------------------------
# edge_boundary, node_boundary
# ---------------------------------------------------------------------------


class TestBoundary:
    def test_edge_boundary(self, path4):
        edges = fnx.edge_boundary(path4, [0, 1])
        # Edges crossing from {0,1} to {2,3}: should be (1,2)
        assert len(edges) == 1
        assert set(edges[0]) == {1, 2}

    def test_edge_boundary_with_nbunch2(self, path4):
        edges = fnx.edge_boundary(path4, [0, 1], [2])
        assert len(edges) == 1
        assert set(edges[0]) == {1, 2}

    def test_edge_boundary_empty(self, triangle):
        edges = fnx.edge_boundary(triangle, [0, 1, 2])
        assert len(edges) == 0

    def test_node_boundary(self, path4):
        nodes = fnx.node_boundary(path4, [0, 1])
        assert set(nodes) == {2}

    def test_node_boundary_with_nbunch2(self, path4):
        nodes = fnx.node_boundary(path4, [0], [1, 2, 3])
        assert set(nodes) == {1}

    def test_node_boundary_empty(self, triangle):
        nodes = fnx.node_boundary(triangle, [0, 1, 2])
        assert len(nodes) == 0

    def test_cut_size_uses_complement(self, path4):
        assert fnx.cut_size(path4, [0, 1]) == 1.0

    def test_cut_size_directed_weighted_counts_both_directions(self):
        D = fnx.DiGraph()
        D.add_edge("a", "b", weight=-2)
        D.add_edge("b", "a", weight=5)
        assert abs(fnx.cut_size(D, ["a"], ["b"], weight="weight") - 3.0) < 1e-9

    def test_normalized_cut_size(self, path4):
        assert abs(fnx.normalized_cut_size(path4, [0, 1]) - (2.0 / 3.0)) < 1e-9

    def test_normalized_cut_size_directed_weighted(self):
        D = fnx.DiGraph()
        D.add_edge("a", "b", weight=-2)
        D.add_edge("b", "a", weight=5)
        assert abs(fnx.normalized_cut_size(D, ["a"], ["b"], weight="weight") + 0.9) < 1e-9

    def test_normalized_cut_size_zero_volume_raises(self, triangle):
        with pytest.raises(ZeroDivisionError):
            fnx.normalized_cut_size(triangle, [])


# ---------------------------------------------------------------------------
# is_simple_path
# ---------------------------------------------------------------------------


class TestIsSimplePath:
    def test_valid_path(self, path4):
        assert fnx.is_simple_path(path4, [0, 1, 2, 3]) is True

    def test_partial_path(self, path4):
        assert fnx.is_simple_path(path4, [0, 1, 2]) is True

    def test_not_a_path(self, path4):
        assert fnx.is_simple_path(path4, [0, 2]) is False

    def test_empty_path(self, path4):
        assert fnx.is_simple_path(path4, []) is False

    def test_single_node(self, path4):
        assert fnx.is_simple_path(path4, [0]) is True

    def test_repeated_node(self, triangle):
        assert fnx.is_simple_path(triangle, [0, 1, 0]) is False

    def test_directed(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        assert fnx.is_simple_path(D, [0, 1, 2]) is True
        assert fnx.is_simple_path(D, [2, 1, 0]) is False  # wrong direction


# ---------------------------------------------------------------------------
# is_matching, is_maximal_matching, is_perfect_matching
# ---------------------------------------------------------------------------


class TestMatchingValidators:
    def test_is_matching_valid(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(2, 3)
        assert fnx.is_matching(G, [(0, 1)]) is True

    def test_is_matching_invalid_overlap(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        # Both edges share node 1
        assert fnx.is_matching(G, [(0, 1), (1, 2)]) is False

    def test_is_matching_empty(self, triangle):
        assert fnx.is_matching(triangle, []) is True

    def test_is_maximal_matching(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(2, 3)
        # {(0,1)} alone is not maximal — could add (2,3)
        assert fnx.is_maximal_matching(G, [(0, 1)]) is False
        assert fnx.is_maximal_matching(G, [(0, 1), (2, 3)]) is True

    def test_is_perfect_matching(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(2, 3)
        assert fnx.is_perfect_matching(G, [(0, 1), (2, 3)]) is True
        assert fnx.is_perfect_matching(G, [(0, 1)]) is False

    def test_is_perfect_matching_odd_nodes(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        # 3 nodes — can't have a perfect matching
        assert fnx.is_perfect_matching(G, [(0, 1)]) is False


# ---------------------------------------------------------------------------
# simple_cycles
# ---------------------------------------------------------------------------


class TestSimpleCycles:
    def test_triangle_cycle(self, directed_cycle):
        cycles = fnx.simple_cycles(directed_cycle)
        assert len(cycles) == 1
        assert set(cycles[0]) == {0, 1, 2}

    def test_length_bound_matches_networkx(self, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge(1, 2)
            graph.add_edge(2, 3)
            graph.add_edge(3, 1)
            graph.add_edge(2, 4)
            graph.add_edge(4, 2)

        assert list(fnx.simple_cycles(D_fnx, length_bound=2)) == list(
            nx.simple_cycles(D_nx, length_bound=2)
        )
        assert list(fnx.simple_cycles(D_fnx, length_bound=3)) == list(
            nx.simple_cycles(D_nx, length_bound=3)
        )

    def test_no_cycles(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        cycles = fnx.simple_cycles(D)
        assert len(cycles) == 0

    def test_self_loop(self):
        D = fnx.DiGraph()
        D.add_edge(0, 0)
        cycles = fnx.simple_cycles(D)
        assert len(cycles) == 1

    def test_two_cycles(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_edge(1, 2)
        D.add_edge(2, 1)
        cycles = fnx.simple_cycles(D)
        assert len(cycles) == 2

    def test_order_matches_networkx(self, nx):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge(0, 3)
            graph.add_edge(3, 0)
            graph.add_edge(1, 2)
            graph.add_edge(2, 1)

        assert fnx.simple_cycles(D_fnx) == list(nx.simple_cycles(D_nx))

    def test_undirected_matches_networkx(self, nx):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge(0, 1)
            graph.add_edge(1, 2)
            graph.add_edge(2, 0)

        MG_fnx = fnx.MultiGraph()
        MG_nx = nx.MultiGraph()
        for graph in (MG_fnx, MG_nx):
            graph.add_edge("a", "b")
            graph.add_edge("b", "c")
            graph.add_edge("c", "a")

        assert list(fnx.simple_cycles(G_fnx)) == list(nx.simple_cycles(G_nx))
        assert list(fnx.simple_cycles(MG_fnx)) == list(nx.simple_cycles(MG_nx))


# ---------------------------------------------------------------------------
# find_cycle
# ---------------------------------------------------------------------------


class TestFindCycle:
    def test_finds_cycle_undirected(self, triangle):
        cycle = fnx.find_cycle(triangle)
        assert len(cycle) >= 3
        # Each element should be an edge tuple
        for u, v in cycle:
            assert triangle.has_edge(u, v)

    def test_finds_cycle_directed(self, directed_cycle):
        cycle = fnx.find_cycle(directed_cycle)
        assert len(cycle) >= 2

    def test_no_cycle_raises(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        with pytest.raises(fnx.NetworkXNoCycle):
            fnx.find_cycle(G)

    def test_source_and_orientation_match_networkx(self, nx):
        for graph_type in ("Graph", "DiGraph"):
            G_fnx = getattr(fnx, graph_type)()
            G_nx = getattr(nx, graph_type)()
            for u, v in ((0, 1), (1, 2), (2, 0)):
                G_fnx.add_edge(u, v)
                G_nx.add_edge(u, v)

            assert fnx.find_cycle(G_fnx, source=1) == nx.find_cycle(G_nx, source=1)
            assert fnx.find_cycle(G_fnx, orientation="original") == nx.find_cycle(
                G_nx, orientation="original"
            )
            assert fnx.find_cycle(G_fnx, orientation="ignore") == nx.find_cycle(
                G_nx, orientation="ignore"
            )
            assert fnx.find_cycle(
                G_fnx, source=1, orientation="original"
            ) == nx.find_cycle(G_nx, source=1, orientation="original")

    def test_multigraph_preserves_edge_keys(self, nx):
        for graph_type in ("MultiGraph", "MultiDiGraph"):
            G_fnx = getattr(fnx, graph_type)()
            G_nx = getattr(nx, graph_type)()
            for graph in (G_fnx, G_nx):
                graph.add_edge("a", "b", key="k1")
                graph.add_edge("b", "c", key="k2")
                graph.add_edge("c", "a", key="k3")

            assert fnx.find_cycle(G_fnx) == nx.find_cycle(G_nx)
            assert fnx.find_cycle(G_fnx, source="b") == nx.find_cycle(
                G_nx, source="b"
            )
