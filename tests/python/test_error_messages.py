"""Verify FrankenNetworkX error messages match NetworkX conventions.

Every exception FrankenNetworkX raises should be indistinguishable from
what NetworkX would raise in the same situation.
"""

import pytest

try:
    import franken_networkx as fnx

    FNX_AVAILABLE = True
except ImportError:
    FNX_AVAILABLE = False

pytestmark = pytest.mark.skipif(not FNX_AVAILABLE, reason="fnx not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_disconnected():
    """Return a disconnected graph with nodes a-b and isolated c."""
    G = fnx.Graph()
    G.add_edge("a", "b")
    G.add_node("c")
    return G


def _make_path():
    """Return a simple path a-b-c."""
    G = fnx.Graph()
    G.add_edge("a", "b")
    G.add_edge("b", "c")
    return G


def _make_triangle():
    """Return a triangle a-b-c."""
    G = fnx.Graph()
    G.add_edge("a", "b")
    G.add_edge("b", "c")
    G.add_edge("a", "c")
    return G


# ---------------------------------------------------------------------------
# NodeNotFound
# ---------------------------------------------------------------------------

class TestNodeNotFound:
    """NodeNotFound messages must include the missing node identifier."""

    def test_remove_node_message(self):
        G = fnx.Graph()
        G.add_node("a")
        with pytest.raises(fnx.NodeNotFound, match=r"The node.*is not in the graph"):
            G.remove_node("z")

    def test_shortest_path_source_not_found(self):
        G = _make_path()
        with pytest.raises(fnx.NodeNotFound, match=r"Node.*is not in G"):
            fnx.shortest_path(G, "z", "b")

    def test_shortest_path_target_not_found(self):
        G = _make_path()
        with pytest.raises(fnx.NodeNotFound, match=r"Node.*is not in G"):
            fnx.shortest_path(G, "a", "z")


# ---------------------------------------------------------------------------
# NetworkXNoPath
# ---------------------------------------------------------------------------

class TestNetworkXNoPath:
    """NetworkXNoPath messages must follow 'No path between X and Y.' format."""

    def test_shortest_path_no_path(self):
        G = _make_disconnected()
        with pytest.raises(fnx.NetworkXNoPath, match=r"No path between.*and"):
            fnx.shortest_path(G, "a", "c")

    def test_dijkstra_path_no_path(self):
        G = _make_disconnected()
        with pytest.raises(fnx.NetworkXNoPath, match=r"No path between.*and"):
            fnx.dijkstra_path(G, "a", "c")

    def test_bellman_ford_path_no_path(self):
        G = _make_disconnected()
        with pytest.raises(fnx.NetworkXNoPath, match=r"No path between.*and"):
            fnx.bellman_ford_path(G, "a", "c")

    def test_has_path_returns_false(self):
        """has_path should return False (not raise) for disconnected nodes."""
        G = _make_disconnected()
        assert fnx.has_path(G, "a", "c") is False


# ---------------------------------------------------------------------------
# NetworkXError — graph structure
# ---------------------------------------------------------------------------

class TestNetworkXError:
    """NetworkXError for structural issues must match NX wording."""

    def test_remove_edge_not_in_graph(self):
        G = _make_path()
        with pytest.raises(fnx.NetworkXError, match=r"The edge.*is not in the graph"):
            G.remove_edge("a", "z")

    def test_diameter_disconnected(self):
        G = _make_disconnected()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Found infinite path length because the graph is not connected",
        ):
            fnx.diameter(G)

    def test_radius_disconnected(self):
        G = _make_disconnected()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Found infinite path length because the graph is not connected",
        ):
            fnx.radius(G)

    def test_center_disconnected(self):
        G = _make_disconnected()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Found infinite path length because the graph is not connected",
        ):
            fnx.center(G)

    def test_periphery_disconnected(self):
        G = _make_disconnected()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Found infinite path length because the graph is not connected",
        ):
            fnx.periphery(G)

    def test_average_shortest_path_length_disconnected(self):
        G = _make_disconnected()
        with pytest.raises(
            fnx.NetworkXError, match=r"Graph is not connected\."
        ):
            fnx.average_shortest_path_length(G)

    def test_bipartite_sets_non_bipartite(self):
        G = _make_triangle()
        with pytest.raises(fnx.NetworkXError, match=r"Graph is not bipartite"):
            fnx.bipartite_sets(G)

    def test_min_edge_cover_isolated_node(self):
        G = fnx.Graph()
        G.add_node("a")
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Graph has a node with no edge incident on it",
        ):
            fnx.min_edge_cover(G)

    def test_tree_broadcast_center_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(fnx.NetworkXPointlessConcept, match=r"G has no nodes\."):
            fnx.tree_broadcast_center(G)

    def test_tree_broadcast_center_not_tree(self):
        G = _make_triangle()
        with pytest.raises(fnx.NotATree, match=r"G is not a tree"):
            fnx.tree_broadcast_center(G)

    def test_tree_broadcast_time_missing_node(self):
        G = _make_path()
        with pytest.raises(fnx.NodeNotFound, match=r"node z not in G"):
            fnx.tree_broadcast_time(G, node="z")


# ---------------------------------------------------------------------------
# NetworkXNotImplemented — directed type
# ---------------------------------------------------------------------------

class TestNetworkXNotImplemented:
    """NetworkXNotImplemented on DiGraph must say 'not implemented for directed type'."""

    def test_is_connected_digraph(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for directed type",
        ):
            fnx.is_connected(DG)

    def test_connected_components_digraph(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for directed type",
        ):
            fnx.connected_components(DG)

    def test_bridges_digraph(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for directed type",
        ):
            fnx.bridges(DG)


# ---------------------------------------------------------------------------
# Euler errors
# ---------------------------------------------------------------------------

class TestEulerErrors:
    """Euler error messages must match NX: 'G is not Eulerian.' / 'G has no Eulerian path.'"""

    def test_eulerian_circuit_not_eulerian(self):
        G = _make_path()  # a-b-c is not Eulerian
        with pytest.raises(fnx.NetworkXError, match=r"G is not Eulerian"):
            fnx.eulerian_circuit(G)

    def test_eulerian_path_not_semi_eulerian(self):
        """Graph with 4 odd-degree nodes has no Eulerian path."""
        G = fnx.Graph()
        G.add_edge("a", "b")
        G.add_edge("c", "d")
        with pytest.raises(fnx.NetworkXError, match=r"G has no Eulerian path"):
            fnx.eulerian_path(G)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """Exception types must form the same inheritance tree as NetworkX."""

    def test_no_path_is_unfeasible(self):
        assert issubclass(fnx.NetworkXNoPath, fnx.NetworkXUnfeasible)

    def test_unfeasible_is_error(self):
        assert issubclass(fnx.NetworkXUnfeasible, fnx.NetworkXError)

    def test_not_implemented_is_error(self):
        assert issubclass(fnx.NetworkXNotImplemented, fnx.NetworkXError)

    def test_node_not_found_is_error(self):
        assert issubclass(fnx.NodeNotFound, fnx.NetworkXError)

    def test_has_a_cycle_is_error(self):
        assert issubclass(fnx.HasACycle, fnx.NetworkXError)

    def test_unbounded_is_error(self):
        assert issubclass(fnx.NetworkXUnbounded, fnx.NetworkXError)

    def test_pointless_concept_is_error(self):
        assert issubclass(fnx.NetworkXPointlessConcept, fnx.NetworkXError)

    def test_algorithm_error_is_error(self):
        assert issubclass(fnx.NetworkXAlgorithmError, fnx.NetworkXError)

    def test_not_a_tree_is_error(self):
        assert issubclass(fnx.NotATree, fnx.NetworkXError)
