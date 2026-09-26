"""Verify FrankenNetworkX error messages match NetworkX conventions.

Every exception FrankenNetworkX raises should be indistinguishable from
what NetworkX would raise in the same situation.
"""

import networkx as nx
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
        """NetworkX raises NetworkXError (not NodeNotFound) for remove_node."""
        G = fnx.Graph()
        G.add_node("a")
        with pytest.raises(fnx.NetworkXError, match=r"The node.*is not in the graph"):
            G.remove_node("z")

    def test_shortest_path_source_not_found(self):
        G = _make_path()
        with pytest.raises(fnx.NodeNotFound, match=r"Source.*is not in G"):
            fnx.shortest_path(G, "z", "b")

    def test_shortest_path_target_not_found(self):
        G = _make_path()
        with pytest.raises(fnx.NodeNotFound, match=r"Target.*is not in G"):
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
        # Upstream nx.dijkstra_path raises NetworkXNoPath with the message
        # "No path to <target>." — not the "between ... and" wording used
        # by shortest_path. Accept either wording for parity.
        with pytest.raises(
            fnx.NetworkXNoPath, match=r"No path (between.*and|to)"
        ):
            fnx.dijkstra_path(G, "a", "c")

    def test_bellman_ford_path_no_path(self):
        G = _make_disconnected()
        # bellman_ford raises NetworkXNoPath with a different wording
        # than dijkstra: "Target {t} cannot be reached from given sources".
        with pytest.raises(
            fnx.NetworkXNoPath,
            match=r"(No path (between.*and|to)|cannot be reached)",
        ):
            fnx.bellman_ford_path(G, "a", "c")

    def test_has_path_returns_false(self):
        """has_path should return False (not raise) for disconnected nodes."""
        G = _make_disconnected()
        assert not fnx.has_path(G, "a", "c")


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

    def test_average_shortest_path_length_directed_not_strongly_connected(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        with pytest.raises(
            fnx.NetworkXError, match=r"Graph is not strongly connected\."
        ):
            fnx.average_shortest_path_length(DG)

    def test_bipartite_sets_non_bipartite(self):
        G = _make_triangle()
        with pytest.raises(fnx.NetworkXError, match=r"Graph is not bipartite"):
            fnx.bipartite.sets(G)

    def test_min_edge_cover_isolated_node(self):
        # br-r37-c1-mec-iso: nx raises NetworkXException (not
        # NetworkXError) here.  NetworkXError is a subclass of
        # NetworkXException, so the previous assertion was
        # narrower than nx's contract — fnx now matches the
        # exact typed-error class.
        G = fnx.Graph()
        G.add_node("a")
        with pytest.raises(
            fnx.NetworkXException,
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
            list(fnx.connected_components(DG))

    def test_bridges_digraph(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        # bridges returns a generator; NetworkXNotImplemented only fires
        # on iteration.
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for directed type",
        ):
            list(fnx.bridges(DG))

    def test_is_arborescence_undirected(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for undirected type",
        ):
            fnx.is_arborescence(G)

    def test_is_branching_undirected(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXNotImplemented,
            match=r"not implemented for undirected type",
        ):
            fnx.is_branching(G)


# ---------------------------------------------------------------------------
# Euler errors
# ---------------------------------------------------------------------------

class TestEulerErrors:
    """Euler error messages must match NX: 'G is not Eulerian.' / 'G has no Eulerian path.'"""

    def test_eulerian_circuit_not_eulerian(self):
        G = _make_path()  # a-b-c is not Eulerian
        # eulerian_circuit returns a generator; the NetworkXError is
        # raised on iteration, not at call time.
        with pytest.raises(fnx.NetworkXError, match=r"G is not Eulerian"):
            list(fnx.eulerian_circuit(G))

    def test_eulerian_path_not_semi_eulerian(self):
        """Graph with 4 odd-degree nodes has no Eulerian path."""
        G = fnx.Graph()
        G.add_edge("a", "b")
        G.add_edge("c", "d")
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Graph has no Eulerian paths\.",
        ):
            list(fnx.eulerian_path(G))


# ---------------------------------------------------------------------------
# NetworkXPointlessConcept — null graph cases
# ---------------------------------------------------------------------------

class TestPointlessConceptNullGraph:
    """Null-graph error messages must match NetworkX."""

    def test_is_eulerian_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"Connectivity is undefined for the null graph",
        ):
            fnx.is_eulerian(G)

    def test_eulerian_circuit_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"Connectivity is undefined for the null graph",
        ):
            list(fnx.eulerian_circuit(G))

    def test_eulerian_path_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"Connectivity is undefined for the null graph",
        ):
            list(fnx.eulerian_path(G))

    def test_has_eulerian_path_empty_digraph(self):
        DG = fnx.DiGraph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"Connectivity is undefined for the null graph",
        ):
            fnx.has_eulerian_path(DG)

    def test_is_semieulerian_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"Connectivity is undefined for the null graph",
        ):
            fnx.is_semieulerian(G)

    def test_is_arborescence_empty_digraph(self):
        DG = fnx.DiGraph()
        with pytest.raises(fnx.NetworkXPointlessConcept, match=r"G has no nodes\."):
            fnx.is_arborescence(DG)

    def test_is_branching_empty_digraph(self):
        DG = fnx.DiGraph()
        with pytest.raises(fnx.NetworkXPointlessConcept, match=r"G has no nodes\."):
            fnx.is_branching(DG)

    def test_average_shortest_path_length_empty_graph(self):
        G = fnx.Graph()
        with pytest.raises(
            fnx.NetworkXPointlessConcept,
            match=r"the null graph has no paths, thus there is no average shortest path length",
        ):
            fnx.average_shortest_path_length(G)


# ---------------------------------------------------------------------------
# HasACycle — cycle detection errors
# ---------------------------------------------------------------------------

class TestHasACycle:
    """Cycle-detection error class parity with upstream NetworkX.

    br-zzcm7: nx.topological_sort raises NetworkXUnfeasible on cyclic
    input (NOT HasACycle — in nx's hierarchy HasACycle is a separate
    sibling class, not a subclass of NetworkXUnfeasible). fnx now
    matches.
    """

    def test_topological_sort_cyclic_graph(self):
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        DG.add_edge("b", "c")
        DG.add_edge("c", "a")  # Creates cycle
        with pytest.raises(fnx.NetworkXUnfeasible):
            list(fnx.topological_sort(DG))


# ---------------------------------------------------------------------------
# NetworkXNoCycle — no cycle found
# ---------------------------------------------------------------------------

class TestNetworkXNoCycle:
    """NetworkXNoCycle messages must indicate no cycle exists."""

    def test_find_cycle_acyclic_graph(self):
        """find_cycle on DAG must raise NetworkXNoCycle."""
        DG = fnx.DiGraph()
        DG.add_edge("a", "b")
        DG.add_edge("b", "c")
        with pytest.raises(fnx.NetworkXNoCycle, match=r"No cycle found"):
            fnx.find_cycle(DG)


# ---------------------------------------------------------------------------
# NetworkXUnfeasible — infeasible operations
# ---------------------------------------------------------------------------

class TestNetworkXUnfeasible:
    """NetworkXUnfeasible for operations that cannot be completed."""

    def test_min_cost_flow_unsatisfiable_demand(self):
        """min_cost_flow with unsatisfiable demand must raise NetworkXUnfeasible."""
        DG = fnx.DiGraph()
        DG.add_node("s", demand=-10)  # Source supplies 10
        DG.add_node("t", demand=10)   # Sink demands 10
        # No edges, so demand can't be satisfied
        with pytest.raises(fnx.NetworkXUnfeasible, match=r"no flow satisfies all node demands"):
            fnx.min_cost_flow(DG)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """Exception types must form the same inheritance tree as NetworkX."""

    def test_exported_exceptions_are_networkx_classes(self):
        # (top-level-name, nx-class)
        toplevel_pairs = [
            ("NetworkXException", nx.NetworkXException),
            ("NetworkXError", nx.NetworkXError),
            ("NetworkXPointlessConcept", nx.NetworkXPointlessConcept),
            ("NetworkXAlgorithmError", nx.NetworkXAlgorithmError),
            ("NetworkXUnfeasible", nx.NetworkXUnfeasible),
            ("NetworkXNoPath", nx.NetworkXNoPath),
            ("NetworkXNoCycle", nx.NetworkXNoCycle),
            ("NetworkXUnbounded", nx.NetworkXUnbounded),
            ("NetworkXNotImplemented", nx.NetworkXNotImplemented),
            ("NotATree", nx.NotATree),
            ("NodeNotFound", nx.NodeNotFound),
            ("HasACycle", nx.HasACycle),
            ("PowerIterationFailedConvergence", nx.PowerIterationFailedConvergence),
        ]
        for name, nx_class in toplevel_pairs:
            assert getattr(fnx, name) is nx_class

        # br-r37-c1-esvs4: NotAPartition is namespaced in nx
        # (nx.community.quality.NotAPartition; nx top-level does
        # not expose it). fnx mirrors that — reach it via the
        # community.quality submodule.
        assert (
            fnx.community.quality.NotAPartition
            is nx.community.quality.NotAPartition
        )

    def test_native_raises_are_caught_by_networkx_handlers(self):
        with pytest.raises(nx.NetworkXNoPath):
            fnx.shortest_path(fnx.Graph([(0, 1), (2, 3)]), 0, 3)

        with pytest.raises(nx.NetworkXNotImplemented):
            list(fnx.bridges(fnx.DiGraph([(0, 1)])))


# br-r37-c1-ct24s: which check fires FIRST is part of the contract. networkx's
# @not_implemented_for runs before any argument check; is_eulerian /
# has_eulerian_path run before the source is looked at; s / t are checked
# before the null graph can raise; a v given on the null graph is still checked.
_ORDER_GRAPHS = {
    "null": lambda m: m.Graph(),
    "null_directed": lambda m: m.DiGraph(),
    "path": lambda m: m.path_graph(3),
    "cycle": lambda m: m.cycle_graph(3),
    "directed_cycle": lambda m: m.DiGraph([(0, 1), (1, 2), (2, 0)]),
    "directed_path": lambda m: m.DiGraph([(0, 1), (1, 2)]),
    "star": lambda m: m.star_graph(3),
}
_ORDER_CALLS = {
    "immediate_dominators_missing_start": lambda m, G: m.immediate_dominators(G, 9),
    "dominance_frontiers_missing_start": lambda m, G: m.dominance_frontiers(G, 9),
    "eccentricity_missing_v": lambda m, G: m.eccentricity(G, v=12),
    "eccentricity_v_list": lambda m, G: m.eccentricity(G, v=[12]),
    "eulerian_circuit_source_0": lambda m, G: list(m.eulerian_circuit(G, source=0)),
    "eulerian_circuit_missing_source": lambda m, G: list(m.eulerian_circuit(G, source=9)),
    "eulerian_path_source_0": lambda m, G: list(m.eulerian_path(G, source=0)),
    "eulerian_path_missing_source": lambda m, G: list(m.eulerian_path(G, source=9)),
    "node_connectivity_st": lambda m, G: m.node_connectivity(G, 0, 1),
    "node_connectivity_s_only": lambda m, G: m.node_connectivity(G, 0),
    "edge_connectivity_st": lambda m, G: m.edge_connectivity(G, 0, 1),
    "minimum_node_cut_st": lambda m, G: m.minimum_node_cut(G, 0, 1),
    "google_matrix_shape": lambda m, G: m.google_matrix(G).shape,
}


def _order_outcome(module, graph, call):
    try:
        return ("ok", repr(_ORDER_CALLS[call](module, _ORDER_GRAPHS[graph](module))))
    except Exception as exc:  # noqa: BLE001 - the raise is the answer
        return ("raise", type(exc).__name__, str(exc))


@pytest.mark.parametrize("graph", sorted(_ORDER_GRAPHS))
@pytest.mark.parametrize("call", sorted(_ORDER_CALLS))
def test_first_failing_check_matches_networkx(graph, call):
    assert _order_outcome(fnx, graph, call) == _order_outcome(nx, graph, call)
