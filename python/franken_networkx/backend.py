"""NetworkX backend dispatch interface.

When installed alongside NetworkX 3.0+, FrankenNetworkX can accelerate
supported algorithms transparently via the backend dispatch protocol.

Usage::

    import networkx as nx
    nx.config.backend_priority = ["franken_networkx"]
    # All supported algorithms now dispatch to Rust.
"""

import logging
import inspect

import franken_networkx as fnx

log = logging.getLogger("franken_networkx.backend")

# ---------------------------------------------------------------------------
# Supported algorithm registry
# ---------------------------------------------------------------------------

# Maps NetworkX function name -> FrankenNetworkX callable.
# Add new entries here as more algorithms are bound.
_SUPPORTED_ALGORITHMS = {
    # Shortest path
    "shortest_path": fnx.shortest_path,
    "shortest_path_length": fnx.shortest_path_length,
    "has_path": fnx.has_path,
    "average_shortest_path_length": fnx.average_shortest_path_length,
    "dijkstra_path": fnx.dijkstra_path,
    "bellman_ford_path": fnx.bellman_ford_path,
    # Connectivity
    "is_connected": fnx.is_connected,
    "connected_components": fnx.connected_components,
    "number_connected_components": fnx.number_connected_components,
    "node_connectivity": fnx.node_connectivity,
    "minimum_node_cut": fnx.minimum_node_cut,
    "edge_connectivity": fnx.edge_connectivity,
    "articulation_points": fnx.articulation_points,
    "bridges": fnx.bridges,
    "local_bridges": fnx.local_bridges,
    # Centrality
    "degree_centrality": fnx.degree_centrality,
    "closeness_centrality": fnx.closeness_centrality,
    "harmonic_centrality": fnx.harmonic_centrality,
    "katz_centrality": fnx.katz_centrality,
    "betweenness_centrality": fnx.betweenness_centrality,
    "edge_betweenness_centrality": fnx.edge_betweenness_centrality,
    "eigenvector_centrality": fnx.eigenvector_centrality,
    "pagerank": fnx.pagerank,
    "hits": fnx.hits,
    "voterank": fnx.voterank,
    "average_neighbor_degree": fnx.average_neighbor_degree,
    "degree_assortativity_coefficient": fnx.degree_assortativity_coefficient,
    # Clustering
    "clustering": fnx.clustering,
    "average_clustering": fnx.average_clustering,
    "transitivity": fnx.transitivity,
    "triangles": fnx.triangles,
    "square_clustering": fnx.square_clustering,
    # Cliques
    "find_cliques": fnx.find_cliques,
    # Matching
    "maximal_matching": fnx.maximal_matching,
    "max_weight_matching": fnx.max_weight_matching,
    "min_weight_matching": fnx.min_weight_matching,
    "min_edge_cover": fnx.min_edge_cover,
    # Flow
    "maximum_flow": fnx.maximum_flow,
    "maximum_flow_value": fnx.maximum_flow_value,
    "minimum_cut": fnx.minimum_cut,
    "minimum_cut_value": fnx.minimum_cut_value,
    # Distance / measures
    "density": fnx.density,
    "eccentricity": fnx.eccentricity,
    "diameter": fnx.diameter,
    "radius": fnx.radius,
    "center": fnx.center,
    "periphery": fnx.periphery,
    # Tree / forest / bipartite / coloring / core
    "is_tree": fnx.is_tree,
    "is_forest": fnx.is_forest,
    "is_bipartite": fnx.is_bipartite,
    "bipartite_sets": fnx.bipartite_sets,
    "greedy_color": fnx.greedy_color,
    "core_number": fnx.core_number,
    "number_of_spanning_trees": fnx.number_of_spanning_trees,
    "partition_spanning_tree": fnx.partition_spanning_tree,
    "random_spanning_tree": fnx.random_spanning_tree,
    "maximum_branching": fnx.maximum_branching,
    "maximum_spanning_arborescence": fnx.maximum_spanning_arborescence,
    "minimum_spanning_edges": fnx.minimum_spanning_edges,
    "minimum_branching": fnx.minimum_branching,
    "minimum_spanning_arborescence": fnx.minimum_spanning_arborescence,
    "minimum_spanning_tree": fnx.minimum_spanning_tree,
    # Euler
    "is_eulerian": fnx.is_eulerian,
    "has_eulerian_path": fnx.has_eulerian_path,
    "is_semieulerian": fnx.is_semieulerian,
    "eulerian_circuit": fnx.eulerian_circuit,
    "eulerian_path": fnx.eulerian_path,
    # Paths / cycles
    "all_shortest_paths": fnx.all_shortest_paths,
    "all_simple_paths": fnx.all_simple_paths,
    "cycle_basis": fnx.cycle_basis,
    # Operators
    "complement": fnx.complement,
    # Efficiency
    "efficiency": fnx.efficiency,
    "global_efficiency": fnx.global_efficiency,
    "local_efficiency": fnx.local_efficiency,
    # Broadcasting
    "tree_broadcast_center": fnx.tree_broadcast_center,
    "tree_broadcast_time": fnx.tree_broadcast_time,
    # Shortest path — additional
    "multi_source_dijkstra": fnx.multi_source_dijkstra,
    # Traversal — BFS
    "bfs_edges": fnx.bfs_edges,
    "bfs_tree": fnx.bfs_tree,
    "bfs_predecessors": fnx.bfs_predecessors,
    "bfs_successors": fnx.bfs_successors,
    "bfs_layers": fnx.bfs_layers,
    "descendants_at_distance": fnx.descendants_at_distance,
    # Traversal — DFS
    "dfs_edges": fnx.dfs_edges,
    "dfs_tree": fnx.dfs_tree,
    "dfs_predecessors": fnx.dfs_predecessors,
    "dfs_successors": fnx.dfs_successors,
    "dfs_preorder_nodes": fnx.dfs_preorder_nodes,
    "dfs_postorder_nodes": fnx.dfs_postorder_nodes,
    # DAG
    "topological_sort": fnx.topological_sort,
    "topological_generations": fnx.topological_generations,
    "dag_longest_path": fnx.dag_longest_path,
    "dag_longest_path_length": fnx.dag_longest_path_length,
    "lexicographic_topological_sort": fnx.lexicographic_topological_sort,
    "is_directed_acyclic_graph": fnx.is_directed_acyclic_graph,
    "ancestors": fnx.ancestors,
    "descendants": fnx.descendants,
    # Link prediction
    "common_neighbors": fnx.common_neighbors,
    "jaccard_coefficient": fnx.jaccard_coefficient,
    "adamic_adar_index": fnx.adamic_adar_index,
    "preferential_attachment": fnx.preferential_attachment,
    "resource_allocation_index": fnx.resource_allocation_index,
    # Reciprocity
    "overall_reciprocity": fnx.overall_reciprocity,
    "reciprocity": fnx.reciprocity,
    # Wiener index
    "wiener_index": fnx.wiener_index,
    # Graph metrics
    "average_degree_connectivity": fnx.average_degree_connectivity,
    "rich_club_coefficient": fnx.rich_club_coefficient,
    "s_metric": fnx.s_metric,
    # Graph isomorphism
    "is_isomorphic": fnx.is_isomorphic,
    "could_be_isomorphic": fnx.could_be_isomorphic,
    "fast_could_be_isomorphic": fnx.fast_could_be_isomorphic,
    "faster_could_be_isomorphic": fnx.faster_could_be_isomorphic,
    # Planarity
    "is_planar": fnx.is_planar,
    # Barycenter
    "barycenter": fnx.barycenter,
    # A* shortest path
    "astar_path": fnx.astar_path,
    "astar_path_length": fnx.astar_path_length,
    "shortest_simple_paths": fnx.shortest_simple_paths,
    # Approximation algorithms
    "min_weighted_vertex_cover": fnx.min_weighted_vertex_cover,
    "maximal_independent_set": fnx.maximal_independent_set,
    "maximum_independent_set": fnx.maximum_independent_set,
    "max_clique": fnx.max_clique,
    "clique_removal": fnx.clique_removal,
    "large_clique_size": fnx.large_clique_size,
    "spanner": fnx.spanner,
    # Strongly connected components
    "strongly_connected_components": fnx.strongly_connected_components,
    "number_strongly_connected_components": fnx.number_strongly_connected_components,
    "is_strongly_connected": fnx.is_strongly_connected,
    # Weakly connected components
    "weakly_connected_components": fnx.weakly_connected_components,
    "number_weakly_connected_components": fnx.number_weakly_connected_components,
    "is_weakly_connected": fnx.is_weakly_connected,
    # Transitive closure/reduction
    "transitive_closure": fnx.transitive_closure,
    "transitive_reduction": fnx.transitive_reduction,
    # Maximum spanning tree
    "maximum_spanning_edges": fnx.maximum_spanning_edges,
    "maximum_spanning_tree": fnx.maximum_spanning_tree,
    # Condensation
    "condensation": fnx.condensation,
    # All-pairs shortest paths
    "all_pairs_shortest_path": fnx.all_pairs_shortest_path,
    "all_pairs_shortest_path_length": fnx.all_pairs_shortest_path_length,
    # Graph predicates & utilities
    "is_empty": fnx.is_empty,
    "non_neighbors": fnx.non_neighbors,
    "number_of_cliques": fnx.number_of_cliques,
    "all_triangles": fnx.all_triangles,
    "node_clique_number": fnx.node_clique_number,
    "enumerate_all_cliques": fnx.enumerate_all_cliques,
    "find_cliques_recursive": fnx.find_cliques_recursive,
    "chordal_graph_cliques": fnx.chordal_graph_cliques,
    "chordal_graph_treewidth": fnx.chordal_graph_treewidth,
    "make_max_clique_graph": fnx.make_max_clique_graph,
    "ring_of_cliques": fnx.ring_of_cliques,
    # Classic graph generators
    "balanced_tree": fnx.balanced_tree,
    "barbell_graph": fnx.barbell_graph,
    "bull_graph": fnx.bull_graph,
    "chvatal_graph": fnx.chvatal_graph,
    "cubical_graph": fnx.cubical_graph,
    "desargues_graph": fnx.desargues_graph,
    "diamond_graph": fnx.diamond_graph,
    "dodecahedral_graph": fnx.dodecahedral_graph,
    "frucht_graph": fnx.frucht_graph,
    "heawood_graph": fnx.heawood_graph,
    "house_graph": fnx.house_graph,
    "house_x_graph": fnx.house_x_graph,
    "icosahedral_graph": fnx.icosahedral_graph,
    "krackhardt_kite_graph": fnx.krackhardt_kite_graph,
    "moebius_kantor_graph": fnx.moebius_kantor_graph,
    "octahedral_graph": fnx.octahedral_graph,
    "pappus_graph": fnx.pappus_graph,
    "petersen_graph": fnx.petersen_graph,
    "sedgewick_maze_graph": fnx.sedgewick_maze_graph,
    "tetrahedral_graph": fnx.tetrahedral_graph,
    "truncated_cube_graph": fnx.truncated_cube_graph,
    "truncated_tetrahedron_graph": fnx.truncated_tetrahedron_graph,
    "tutte_graph": fnx.tutte_graph,
    "hoffman_singleton_graph": fnx.hoffman_singleton_graph,
    "generalized_petersen_graph": fnx.generalized_petersen_graph,
    "wheel_graph": fnx.wheel_graph,
    "ladder_graph": fnx.ladder_graph,
    "circular_ladder_graph": fnx.circular_ladder_graph,
    "lollipop_graph": fnx.lollipop_graph,
    "tadpole_graph": fnx.tadpole_graph,
    "turan_graph": fnx.turan_graph,
    "windmill_graph": fnx.windmill_graph,
    "hypercube_graph": fnx.hypercube_graph,
    "complete_bipartite_graph": fnx.complete_bipartite_graph,
    "complete_multipartite_graph": fnx.complete_multipartite_graph,
    "grid_2d_graph": fnx.grid_2d_graph,
    "null_graph": fnx.null_graph,
    "trivial_graph": fnx.trivial_graph,
    "binomial_tree": fnx.binomial_tree,
    "full_rary_tree": fnx.full_rary_tree,
    "circulant_graph": fnx.circulant_graph,
    "kneser_graph": fnx.kneser_graph,
    "paley_graph": fnx.paley_graph,
    "chordal_cycle_graph": fnx.chordal_cycle_graph,
    # Single-source shortest paths
    "single_source_shortest_path": fnx.single_source_shortest_path,
    "single_source_shortest_path_length": fnx.single_source_shortest_path_length,
    # Dominating set
    "dominating_set": fnx.dominating_set,
    "is_dominating_set": fnx.is_dominating_set,
    # Community detection
    "louvain_communities": fnx.louvain_communities,
    "modularity": fnx.modularity,
    "label_propagation_communities": fnx.label_propagation_communities,
    "asyn_lpa_communities": fnx.asyn_lpa_communities,
    "greedy_modularity_communities": fnx.greedy_modularity_communities,
    # Graph operators
    "union": fnx.union,
    "intersection": fnx.intersection,
    "compose": fnx.compose,
    "difference": fnx.difference,
    "symmetric_difference": fnx.symmetric_difference,
    "degree_histogram": fnx.degree_histogram,
    # Tree recognition
    "is_arborescence": fnx.is_arborescence,
    "is_branching": fnx.is_branching,
    # Isolates
    "is_isolate": fnx.is_isolate,
    "isolates": fnx.isolates,
    "number_of_isolates": fnx.number_of_isolates,
    # Boundary
    "cut_size": fnx.cut_size,
    "edge_boundary": fnx.edge_boundary,
    "node_boundary": fnx.node_boundary,
    "normalized_cut_size": fnx.normalized_cut_size,
    # Path validation
    "is_simple_path": fnx.is_simple_path,
    # Matching validators
    "is_matching": fnx.is_matching,
    "is_maximal_matching": fnx.is_maximal_matching,
    "is_perfect_matching": fnx.is_perfect_matching,
    # Cycles
    "simple_cycles": fnx.simple_cycles,
    "find_cycle": fnx.find_cycle,
    "girth": fnx.girth,
    "find_negative_cycle": fnx.find_negative_cycle,
    # Graph predicates
    "is_graphical": fnx.is_graphical,
    "is_digraphical": fnx.is_digraphical,
    "is_multigraphical": fnx.is_multigraphical,
    "is_pseudographical": fnx.is_pseudographical,
    "is_regular": fnx.is_regular,
    "is_k_regular": fnx.is_k_regular,
    "is_tournament": fnx.is_tournament,
    "is_weighted": fnx.is_weighted,
    "is_negatively_weighted": fnx.is_negatively_weighted,
    "is_path": fnx.is_path,
    "is_distance_regular": fnx.is_distance_regular,
    # DAG algorithms — additional
    "is_aperiodic": fnx.is_aperiodic,
    # Traversal algorithms — additional
    "edge_bfs": fnx.edge_bfs,
    "edge_dfs": fnx.edge_dfs,
    # Matching algorithms — additional
    "is_edge_cover": fnx.is_edge_cover,
    "max_weight_clique": fnx.max_weight_clique,
    "antichains": fnx.antichains,
    "immediate_dominators": fnx.immediate_dominators,
    "dominance_frontiers": fnx.dominance_frontiers,
    # Additional shortest path algorithms
    "dijkstra_path_length": fnx.dijkstra_path_length,
    "bellman_ford_path_length": fnx.bellman_ford_path_length,
    "single_source_dijkstra": fnx.single_source_dijkstra,
    "single_source_dijkstra_path": fnx.single_source_dijkstra_path,
    "single_source_dijkstra_path_length": fnx.single_source_dijkstra_path_length,
    "single_source_bellman_ford": fnx.single_source_bellman_ford,
    "single_source_bellman_ford_path": fnx.single_source_bellman_ford_path,
    "single_source_bellman_ford_path_length": fnx.single_source_bellman_ford_path_length,
    "single_target_shortest_path": fnx.single_target_shortest_path,
    "single_target_shortest_path_length": fnx.single_target_shortest_path_length,
    "all_pairs_dijkstra_path": fnx.all_pairs_dijkstra_path,
    "all_pairs_dijkstra_path_length": fnx.all_pairs_dijkstra_path_length,
    "all_pairs_bellman_ford_path": fnx.all_pairs_bellman_ford_path,
    "all_pairs_bellman_ford_path_length": fnx.all_pairs_bellman_ford_path_length,
    "floyd_warshall": fnx.floyd_warshall,
    "floyd_warshall_predecessor_and_distance": fnx.floyd_warshall_predecessor_and_distance,
    "bidirectional_shortest_path": fnx.bidirectional_shortest_path,
    "negative_edge_cycle": fnx.negative_edge_cycle,
    "predecessor": fnx.predecessor,
    "path_weight": fnx.path_weight,
    # Additional centrality
    "in_degree_centrality": fnx.in_degree_centrality,
    "out_degree_centrality": fnx.out_degree_centrality,
    "local_reaching_centrality": fnx.local_reaching_centrality,
    "global_reaching_centrality": fnx.global_reaching_centrality,
    "group_degree_centrality": fnx.group_degree_centrality,
    "group_in_degree_centrality": fnx.group_in_degree_centrality,
    "group_out_degree_centrality": fnx.group_out_degree_centrality,
    # Component algorithms
    "node_connected_component": fnx.node_connected_component,
    "is_biconnected": fnx.is_biconnected,
    "biconnected_components": fnx.biconnected_components,
    "biconnected_component_edges": fnx.biconnected_component_edges,
    "is_semiconnected": fnx.is_semiconnected,
    "kosaraju_strongly_connected_components": fnx.kosaraju_strongly_connected_components,
    "attracting_components": fnx.attracting_components,
    "number_attracting_components": fnx.number_attracting_components,
    "is_attracting_component": fnx.is_attracting_component,
}


def get_backend_info():
    """Return NetworkX backend metadata for dispatch registration."""
    return {
        "short_summary": "Rust-backed graph algorithms and generators with NetworkX parity goals.",
        "functions": {name: {} for name in _SUPPORTED_ALGORITHMS},
    }


# ---------------------------------------------------------------------------
# Graph conversion helpers
# ---------------------------------------------------------------------------


def _nx_to_fnx(G):
    """Convert a NetworkX graph to the matching FrankenNetworkX graph type."""
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(G)


def _convert_result_to_nx(value):
    """Recursively convert fnx graphs to nx graphs inside common containers.

    Returns non-graph values unchanged. Preserves container type for
    list / tuple / set. For dict, converts values only (keys are left
    alone since graph-typed keys are pathological).
    """
    if isinstance(value, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)):
        return _fnx_to_nx(value)
    if isinstance(value, dict):
        return {k: _convert_result_to_nx(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_result_to_nx(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_convert_result_to_nx(v) for v in value)
    if isinstance(value, set):
        # Graphs aren't hashable so a set of fnx graphs is unusual; recurse
        # only if elements are themselves non-graph (sets of nodes etc.).
        return value
    return value


def _topo_emit_edges_by_adj(fg):
    """Yield ``(u, v)`` pairs in an order consistent with each node's
    ``fg.adj[u]`` insertion order (br-r37-c1-sgnab).

    Used by :func:`_fnx_to_nx` so the converted nx graph's per-node
    adjacency order matches what nx would have built if the user had
    called the same sequence of ``add_edge`` calls. Without this,
    iterating ``fg.edges`` (which canonicalises endpoints) feeds nx
    edges in the wrong order and silently flips adj[u] orientation
    for any node whose first ``add_edge`` call had it as the second
    argument.

    The algorithm is a per-node-queue topological sort: an edge ``{u,
    v}`` is emitted when both ``queues[u][0] == v`` and
    ``queues[v][0] == u`` simultaneously — i.e. it's the next edge
    expected by both endpoints. For directed graphs the constraint is
    one-sided (``queues[u][0] == v`` only).
    """
    is_directed = fg.is_directed()
    queues = {u: list(fg.adj[u]) for u in fg.nodes()}
    nodes_order = list(fg.nodes())

    if is_directed:
        # Directed: emit each u's out-edges in adj order. No
        # cross-node constraint.
        for u in nodes_order:
            for v in queues[u]:
                yield (u, v)
        return

    # Self-loops appear only once in adj[u] (as 'u' itself); count
    # accordingly when computing total edge budget.
    total_edges = (
        sum(len(q) for q in queues.values())
        - sum(1 for u, q in queues.items() if u in q)
    ) // 2 + sum(1 for u, q in queues.items() if u in q)
    emitted_count = 0

    while emitted_count < total_edges:
        progress = False
        for u in nodes_order:
            if not queues[u]:
                continue
            v = queues[u][0]
            if u == v:
                # Self-loop — only appears once in queues[u].
                yield (u, v)
                queues[u].pop(0)
                emitted_count += 1
                progress = True
                break
            # Match: u is also at front of v's queue?
            if queues[v] and queues[v][0] == u:
                yield (u, v)
                queues[u].pop(0)
                queues[v].pop(0)
                emitted_count += 1
                progress = True
                break
        if not progress:
            # Constraint cycle: shouldn't happen for valid adj lists.
            # Fall back to draining whatever's at the front of each queue.
            for u in nodes_order:
                while queues[u]:
                    v = queues[u].pop(0)
                    if v != u and queues[v]:
                        try:
                            queues[v].remove(u)
                        except ValueError:
                            pass
                    yield (u, v)
                    emitted_count += 1
            break


def _fnx_to_nx(fg):
    """Convert a FrankenNetworkX graph to the matching NetworkX graph type.

    Uses ``add_nodes_from`` / ``add_edges_from`` with attrs passed
    positionally in the tuple so attr names that collide with nx's
    positional parameters (``node_for_adding`` on nodes;
    ``u_of_edge`` / ``v_of_edge`` on edges) don't raise the
    ``multiple values for argument`` TypeError
    (franken_networkx-yr7kf, same class as -uphdr / -9x7r0).

    br-r37-c1-sgnab: emit edges in an order that preserves per-node
    adj insertion order so the converted graph's adj[u] matches what
    a directly-constructed nx graph would have. Critical for any
    delegated algorithm whose result depends on adj iteration
    (greedy_color BFS strategies, ego_graph, BFS/DFS variants).
    """
    import networkx as nx

    if fg.is_multigraph():
        if fg.is_directed():
            G = nx.MultiDiGraph()
        else:
            G = nx.MultiGraph()
    elif fg.is_directed():
        G = nx.DiGraph()
    else:
        G = nx.Graph()
    node_view = getattr(fg, "nodes", None)
    if node_view is not None:
        G.add_nodes_from((node, dict(node_view[node])) for node in fg)
    else:
        G.add_nodes_from(fg)
    if fg.is_multigraph():
        seen = set()
        for u in fg:
            for v, keyed_attrs in fg[u].items():
                if not fg.is_directed():
                    edge_id = frozenset((u, v))
                    if edge_id in seen:
                        continue
                    seen.add(edge_id)
                G.add_edges_from(
                    (u, v, key, dict(attrs))
                    for key, attrs in keyed_attrs.items()
                )
    else:
        # Use 3-tuple attrs form so attr names that collide with nx's
        # positional ``u_of_edge`` / ``v_of_edge`` parameters don't
        # raise ``multiple values for argument`` (franken_networkx-yr7kf).
        edges_in_order = [
            (u, v, dict(fg.edges[u, v]))
            for u, v in _topo_emit_edges_by_adj(fg)
        ]
        G.add_edges_from(edges_in_order)
    G.graph.update(dict(fg.graph))
    return G


# ---------------------------------------------------------------------------
# BackendInterface
# ---------------------------------------------------------------------------


class BackendInterface:
    """NetworkX backend interface for FrankenNetworkX.

    This class implements the dispatch protocol so that NetworkX can
    transparently delegate supported algorithm calls to FrankenNetworkX's
    Rust backend.
    """

    @staticmethod
    def convert_from_nx(
        G,
        edge_attrs=None,
        node_attrs=None,
        preserve_edge_attrs=False,
        preserve_node_attrs=False,
        preserve_graph_attrs=False,
        preserve_all_attrs=False,
        name=None,
        graph_name=None,
    ):
        """Convert a NetworkX graph to a FrankenNetworkX graph."""
        return _nx_to_fnx(G)

    @staticmethod
    def convert_to_nx(result, *, name=None):
        """Convert a FrankenNetworkX result back to NetworkX types.

        br-convnest: previously only unwrapped a top-level fnx graph.
        If a dispatched algorithm returned a dict/list/tuple/set
        containing fnx graphs (e.g. a dict of subgraphs), the inner
        values stayed as fnx types — ``isinstance(g, nx.DiGraph)``
        returned False on those results, breaking callers that rely
        on the dispatcher's convert_to_nx contract. Recurse into
        common containers so nested fnx graphs are converted too.
        """
        return _convert_result_to_nx(result)

    @staticmethod
    def can_run(name, args, kwargs):
        """Return True if this backend can run the named algorithm."""
        fn = _SUPPORTED_ALGORITHMS.get(name)
        if fn is None:
            return False
        try:
            bound = inspect.signature(fn).bind(*args, **kwargs)
        except TypeError:
            return False
        if name == "average_shortest_path_length" and kwargs.get("method") is not None:
            return False
        # Reject custom flow-function callables — fnx's native
        # connectivity/flow implementations don't honour them, so the nx
        # dispatcher needs to fall back to the upstream pure-Python path.
        if name in {"node_connectivity", "edge_connectivity", "minimum_node_cut", "minimum_edge_cut"}:
            bound.apply_defaults()
            if bound.arguments.get("flow_func") is not None:
                return False
        return True

    @staticmethod
    def should_run(name, args, kwargs):
        """Return True if this backend should run (performance heuristic)."""
        return BackendInterface.can_run(name, args, kwargs)

    # Make algorithm functions available as attributes for dispatch
    def __getattr__(self, name):
        if name in _SUPPORTED_ALGORITHMS:
            import franken_networkx as fnx
            import functools

            fn = _SUPPORTED_ALGORITHMS[name]

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except fnx.NetworkXNotImplemented as e:
                    # NetworkX's dispatcher strictly requires the builtin NotImplementedError
                    # to correctly trigger its fallback sequence.
                    raise NotImplementedError(str(e)) from e

            return wrapper
        raise AttributeError(f"BackendInterface has no attribute '{name}'")


backend_interface = BackendInterface()
