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

# br-r37-c1-xykjs: bulk native adjacency+attrs dump for the _fnx_to_nx parity
# conversion — one PyO3 crossing instead of per-edge AtlasView access.
try:
    from franken_networkx._fnx import (
        fnx_to_nx_adjacency as _native_fnx_to_nx_adjacency,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_fnx_to_nx_adjacency = None

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
    # br-r37-c1-bipx-removed: bipartite_sets is at fnx.bipartite.sets
    # in nx, not at top level.  Backend dispatch uses the underlying
    # nx-style namespaced function.
    "bipartite_sets": fnx.bipartite.sets,
    "greedy_color": fnx.greedy_color,
    "core_number": fnx.core_number,
    "number_of_spanning_trees": fnx.number_of_spanning_trees,
    "partition_spanning_tree": fnx.partition_spanning_tree,
    "random_spanning_tree": fnx.random_spanning_tree,
    "maximum_branching": fnx.maximum_branching,
    "maximum_spanning_arborescence": fnx.maximum_spanning_arborescence,
    "minimum_spanning_edges": fnx.minimum_spanning_edges,
    "minimum_branching": fnx.minimum_branching,
    # br-r37-c1-0epvo: minimal_branching is registered using the private
    # backend-only implementation so ``fnx.algorithms.tree.branchings.minimal_branching`` stays
    # AttributeError (matching nx's namespace contract — see
    # test_branching_weight_minimal_branching_only_at_branchings_namespace).
    "minimal_branching": fnx._minimal_branching_backend_impl,
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
    # br-r37-c1-yrtsz: fnx.lexicographical_topological_sort was a typo
    # alias removed from top level (br-r37-c1-hoqqp). nx's canonical
    # name is ``lexicographical_topological_sort`` (with the trailing
    # "al"); use the correctly-spelled fnx wrapper.
    "lexicographical_topological_sort": fnx.lexicographical_topological_sort,
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
    "min_weighted_vertex_cover": fnx.approximation.min_weighted_vertex_cover,
    "maximal_independent_set": fnx.maximal_independent_set,
    "maximum_independent_set": fnx.approximation.maximum_independent_set,
    "max_clique": fnx.approximation.max_clique,
    "clique_removal": fnx.approximation.clique_removal,
    "large_clique_size": fnx.approximation.large_clique_size,
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
    # Dispatchable I/O and conversion helpers. NetworkX does not dispatch
    # write_* helpers, node_link_data, or to_dict_of_dicts, so they are
    # intentionally absent from the backend registry.
    "read_edgelist": fnx.read_edgelist,
    "read_adjlist": fnx.read_adjlist,
    "read_graphml": fnx.read_graphml,
    "node_link_graph": fnx.node_link_graph,
    "to_numpy_array": fnx.to_numpy_array,
    "from_numpy_array": fnx.from_numpy_array,
    "to_scipy_sparse_array": fnx.to_scipy_sparse_array,
    "from_scipy_sparse_array": fnx.from_scipy_sparse_array,
    "from_dict_of_dicts": fnx.from_dict_of_dicts,
    "from_dict_of_lists": fnx.from_dict_of_lists,
    "to_dict_of_lists": fnx.to_dict_of_lists,
    "from_edgelist": fnx.from_edgelist,
    "to_edgelist": fnx.to_edgelist,
    "convert_node_labels_to_integers": fnx.convert_node_labels_to_integers,
    "from_pandas_edgelist": fnx.from_pandas_edgelist,
    "to_pandas_edgelist": fnx.to_pandas_edgelist,
    # Classic graph generators
    "path_graph": fnx.path_graph,
    "cycle_graph": fnx.cycle_graph,
    "star_graph": fnx.star_graph,
    "complete_graph": fnx.complete_graph,
    "empty_graph": fnx.empty_graph,
    "gnp_random_graph": fnx.gnp_random_graph,
    "watts_strogatz_graph": fnx.watts_strogatz_graph,
    "barabasi_albert_graph": fnx.barabasi_albert_graph,
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
    "louvain_communities": fnx.community.louvain_communities,
    # br-r37-c1-ecua7: registered using the private backend-only impl
    # so ``fnx.community.modularity`` stays AttributeError (matching nx's namespace
    # — nx exposes modularity only at nx.community.modularity).
    "modularity": fnx._modularity_backend_impl,
    # br-r37-c1-cy2me: These three community algorithms previously
    # registered to top-level fnx functions that have since been
    # hidden (br-r37-c1-02sx1 / br-r37-c1-uwm5v). Routing through
    # fnx.community.X here causes recursion (the nx dispatcher
    # ping-pongs between nx → fnx → nx) because the submodule entry
    # resolves to the same nx function via __getattr__ fallback.
    # ``label_propagation_communities`` has a native fnx-side
    # conversion+dispatch wrapper in community.py — but registering
    # it in the dispatch table would still recurse on nx-side calls
    # that don't go through that wrapper. Drop the entries entirely
    # and let the nx dispatcher fall through to its pure-Python
    # implementation.
    # Attribute setters / getters. br-r37-c1-l2j31: nx flags
    # ``set_*_attributes`` as mutation-preserving so the dispatcher
    # refuses to auto-convert fnx graphs to nx (the mutation would
    # land on a throwaway copy). Register fnx's wrappers so the
    # dispatcher routes the fnx graph in directly and the user's
    # in-place mutation reaches the underlying graph.
    "set_node_attributes": fnx.set_node_attributes,
    "set_edge_attributes": fnx.set_edge_attributes,
    "get_node_attributes": fnx.get_node_attributes,
    "get_edge_attributes": fnx.get_edge_attributes,
    # br-r37-c1-tq78w: same mutation-preserving dispatch family.
    # ``copy=False`` paths mutate the input graph; without these
    # entries the dispatcher raises NotImplementedError.
    "relabel_nodes": fnx.relabel_nodes,
    "contracted_nodes": fnx.contracted_nodes,
    "contracted_edge": fnx.contracted_edge,
    "identified_nodes": fnx.identified_nodes,
    # br-r37-c1-frbgb: edge-swap helpers mutate the input graph in
    # place; same dispatch-gap family as the entries above.
    "double_edge_swap": fnx.double_edge_swap,
    "connected_double_edge_swap": fnx.connected_double_edge_swap,
    # br-r37-c1-pq52x: more mutating dispatchables flagged by nx.
    "directed_edge_swap": fnx.directed_edge_swap,
    "incremental_closeness_centrality": fnx.incremental_closeness_centrality,
    "recursive_simple_cycles": fnx.recursive_simple_cycles,
    "remove_edge_attributes": fnx.remove_edge_attributes,
    "remove_node_attributes": fnx.remove_node_attributes,
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


def _topo_emit_edges_by_adj(fg, adj=None):
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
    # ``deque`` gives O(1) ``popleft``; ``list.pop(0)`` is O(N).  On a
    # 200-node 1000-edge graph the old list-pop emit ran in ~11ms
    # (dominated _fnx_to_nx); deque + a ready-queue (br-r37-c1-toposeq)
    # brings it under 1ms.
    from collections import deque as _deque
    # br-r37-c1-xykjs: ``adj`` (a ``{node: [neighbors]}`` dict in node-insertion
    # order, neighbors in adj-insertion order) lets the caller pre-fetch the
    # whole adjacency in one native crossing; the emit algorithm is unchanged so
    # the output order is identical to the per-node ``fg.adj[u]`` build.
    if adj is None:
        queues = {u: _deque(fg.adj[u]) for u in fg.nodes()}
        nodes_order = list(fg.nodes())
    else:
        queues = {u: _deque(nbrs) for u, nbrs in adj.items()}
        nodes_order = list(adj.keys())

    if is_directed:
        # Directed: emit each u's out-edges in adj order. No
        # cross-node constraint.
        for u in nodes_order:
            for v in queues[u]:
                yield (u, v)
        return

    # br-r37-c1-toposeq: the old algorithm did a full O(N) pass through
    # nodes_order for every edge emitted, giving O(N·E) worst case.
    # Replace with a "ready" queue: a node u is ready when (queues[u]
    # is a self-loop) OR (queues[v][0] == u where v = queues[u][0]).
    # Initial scan is O(N); after each emit we re-check at most two
    # nodes whose front-of-queue changed.  Total: O(N + E).
    def _is_ready(u):
        q = queues[u]
        if not q:
            return False
        v = q[0]
        if u == v:
            return True
        v_q = queues.get(v)
        return v_q is not None and bool(v_q) and v_q[0] == u

    ready = _deque(u for u in nodes_order if _is_ready(u))
    emitted = 0
    # Track an upper bound on emits to detect malformed inputs.
    # Total emitted edges ≤ sum(len(queues[u])) // 2 + (selfloop_count
    # bias is irrelevant since selfloops pop only their own queue once).
    edge_budget = sum(len(q) for q in queues.values())

    while ready:
        u = ready.popleft()
        # ``u`` may have been queued multiple times; check freshness.
        q_u = queues[u]
        if not q_u:
            continue
        v = q_u[0]
        if u == v:
            # Self-loop: pops once from u's queue.
            q_u.popleft()
            yield (u, v)
            emitted += 1
            if _is_ready(u):
                ready.append(u)
            continue
        v_q = queues.get(v)
        if v_q is None or not v_q or v_q[0] != u:
            # Stale entry — u's front no longer matches v.  Will be
            # re-queued when whoever pops v's front exposes u again.
            continue
        q_u.popleft()
        v_q.popleft()
        yield (u, v)
        emitted += 1
        if _is_ready(u):
            ready.append(u)
        if _is_ready(v):
            ready.append(v)
        if emitted > edge_budget:
            break

    # Drain any remainder if the ready-queue logic missed an edge
    # (shouldn't happen on valid undirected adj lists; defensive
    # fallback matching the old behavior for malformed inputs).
    drained_any = False
    for u in nodes_order:
        while queues[u]:
            v = queues[u].popleft()
            if v != u:
                v_q = queues.get(v)
                if v_q is not None:
                    try:
                        v_q.remove(u)
                    except ValueError:
                        pass
            yield (u, v)
            drained_any = True
    del drained_any  # silence linter if unused later


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
        # br-r37-c1-qpykd: emit parallel edges in adj-insertion order (the same
        # per-node-queue topological order used for simple graphs above) so the
        # converted multigraph's ``edges(u, keys=True)`` iteration is byte-
        # identical to a directly-built nx multigraph. The previous loop grouped
        # all of ``u``'s edges together in node-iteration order, which reordered
        # parallel edges across neighbours and silently diverged the yield order
        # of every adj-dependent delegated multigraph algorithm (all_simple_paths,
        # BFS/DFS variants, ...). ``_topo_emit_edges_by_adj`` yields each {u, v}
        # exactly once (undirected) / each u->v (directed) in adj order; for each
        # we emit all parallel keys in their stored (insertion) order.
        for u, v in _topo_emit_edges_by_adj(fg):
            G.add_edges_from(
                (u, v, key, dict(attrs)) for key, attrs in fg[u][v].items()
            )
    else:
        # Use 3-tuple attrs form so attr names that collide with nx's
        # positional ``u_of_edge`` / ``v_of_edge`` parameters don't
        # raise ``multiple values for argument`` (franken_networkx-yr7kf).
        # Directed graphs must key on the ordered (u, v) tuple — collapsing
        # (0,1) and (1,0) via frozenset would corrupt asymmetric edges
        # (mutual_weight, directed PageRank, etc.).  Undirected graphs key on
        # frozenset so the lookup is orientation-agnostic and safe across
        # non-comparable node types (nx allows mixing int / str / tuple nodes).
        directed = fg.is_directed()
        # br-r37-c1-xykjs: pull the whole (node, [(neighbor, attrs)]) structure
        # in one native crossing (reads the fresh edge_py_attrs) instead of two
        # per-edge AtlasView passes (attrs_by_pair + the topo queues build).
        #
        # Gate on the EXACT concrete type: the native helper reads the underlying
        # Rust ``inner`` adjacency, which bypasses node/edge filtering on a
        # SubgraphView (``type(view) is not Graph`` though it reports as one).
        # Views and any subclass fall to the AtlasView Python path, which honours
        # the filtered ``fg._adj``. (See reference_subgraph_view_coerce.)
        bulk = (
            _native_fnx_to_nx_adjacency(fg)
            if (
                _native_fnx_to_nx_adjacency is not None
                and type(fg) in (fnx.Graph, fnx.DiGraph)
            )
            else None
        )
        if bulk is not None:
            # br-r37-c1-fnx2nx-lazykey: ``_native_fnx_to_nx_adjacency`` returns
            # the canonical (interned) node keys (e.g. the string "0"), which the
            # lazy display-key path (br-r37-c1-17ucl) can make DIVERGE from the
            # original Python node objects yielded by ``for node in fg`` (e.g.
            # the int 0). Adding nodes from one form and edges from the other
            # makes networkx treat them as DISTINCT nodes — duplicating the graph
            # (e.g. karate 34 -> 68 nodes, every original node left at degree 0),
            # silently breaking every nx-delegated algorithm that converts.
            # The bulk and ``list(fg)`` iterate nodes in the same order, so zip
            # them to map each canonical key back to its original object.
            display_nodes = list(fg)
            canon_to_obj = {
                canon: obj for (canon, _nbrs), obj in zip(bulk, display_nodes)
            }
            adj_neighbors = {
                canon_to_obj[node]: [canon_to_obj[nbr] for nbr, _a in nbrs]
                for node, nbrs in bulk
            }
            attrs_by_pair = {}
            if directed:
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        attrs_by_pair[(onode, canon_to_obj[nbr])] = attrs
            else:
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        attrs_by_pair[frozenset((onode, canon_to_obj[nbr]))] = attrs
            edges_in_order = []
            for u, v in _topo_emit_edges_by_adj(fg, adj=adj_neighbors):
                key = (u, v) if directed else frozenset((u, v))
                edges_in_order.append((u, v, dict(attrs_by_pair.get(key, {}))))
        else:
            # Defensive fallback (e.g. native helper unavailable): the
            # per-node AtlasView path.
            attrs_by_pair = {}
            for u, nbrs in fg._adj.items():
                for v, attrs in nbrs.items():
                    attrs_by_pair[(u, v) if directed else frozenset((u, v))] = attrs
            edges_in_order = []
            for u, v in _topo_emit_edges_by_adj(fg):
                key = (u, v) if directed else frozenset((u, v))
                edges_in_order.append((u, v, dict(attrs_by_pair.get(key, {}))))
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
