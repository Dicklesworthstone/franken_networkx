"""Tests for newly-added Python bindings: tree recognition, isolates,
boundary and cuts, is_simple_path, matching validators, simple_cycles, find_cycle."""

import pytest

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

    def test_spanning_tree_iterator_rust_preserves_keys_and_attrs(self):
        graph = fnx.Graph()
        graph.graph["label"] = "demo"
        graph.add_node(10, color="red")
        graph.add_node(20, color="blue")
        graph.add_edge(10, 20, weight=7, tag="x")

        tree = _fnx.spanning_tree_iterator_rust(graph, max_count=1)[0]

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

        arb = _fnx.arborescence_iterator_rust(digraph, max_count=1)[0]

        assert list(arb.nodes()) == [1, 2]
        assert list(arb.edges()) == [(1, 2)]
        assert arb.nodes[1]["role"] == "root"
        assert arb.nodes[2]["role"] == "leaf"
        assert arb.edges[1, 2]["weight"] == 3
        assert arb.edges[1, 2]["tag"] == "keep"
        assert dict(arb.graph) == {"name": "demo"}

    def test_arborescence_iterator_rejects_unsupported_init_partition(self):
        digraph = fnx.DiGraph()
        digraph.add_edge("a", "b", weight=1)
        digraph.add_edge("b", "a", weight=2)

        with pytest.raises(fnx.NetworkXNotImplemented, match="init_partition"):
            fnx.ArborescenceIterator(
                digraph,
                weight="weight",
                minimum=True,
                init_partition=([], [("a", "b")]),
            )

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

    def test_arborescence_iterator_rejects_undirected_graphs(self):
        graph = fnx.Graph()
        graph.add_edge("a", "b", weight=1)

        with pytest.raises(fnx.NetworkXNotImplemented, match="undirected type"):
            next(iter(fnx.ArborescenceIterator(graph)))


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

    def test_undirected_raises(self, triangle):
        with pytest.raises(fnx.NetworkXError):
            fnx.simple_cycles(triangle)


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

    def test_no_cycle_directed_raises(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        with pytest.raises(fnx.NetworkXNoCycle):
            fnx.find_cycle(D)

    def test_single_node_no_cycle(self):
        G = fnx.Graph()
        G.add_node(0)
        with pytest.raises(fnx.NetworkXNoCycle):
            fnx.find_cycle(G)
