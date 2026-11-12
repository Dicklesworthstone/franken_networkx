

from contextlib import contextmanager as _contextmanager


@_contextmanager
def compatibility_mode(mode: str):
    """Context manager setting the thread-local compatibility mode ('strict' or 'hardened')."""
    old_mode = _rust_get_thread_compatibility_mode()
    _rust_set_thread_compatibility_mode(mode)
    try:
        yield
    finally:
        _rust_set_thread_compatibility_mode(old_mode)


def get_compatibility_mode() -> str:
    """Return the active compatibility mode ('strict' or 'hardened')."""
    return _rust_get_compatibility_mode()


def set_compatibility_mode(mode: str) -> None:
    """Set the global compatibility mode ('strict' or 'hardened')."""
    _rust_set_compatibility_mode(mode)


def decision_records(G) -> list:
    """Return audit ledger decision records for graph `G`."""
    return _rust_decision_records(G)


def drain_decision_records(G) -> list:
    """Drain and return audit ledger decision records for graph `G`."""
    return _rust_drain_decision_records(G)
approximation = _approx_ns
# br-r37-c1-2poe6: concrete native methods on _ApproximationNamespace bypass the
# __getattr__ wrapper's functools.wraps, so mirror nx's docstring for
# introspection parity (test_approximation_wrapper_carries_nx_docstring).
def _sync_approximation_docstrings():
    for apx_attr, apx_val in _ApproximationNamespace.__dict__.items():
        if not apx_attr.startswith("_") and callable(apx_val):
            nx_apx_fn = getattr(_nx.approximation, apx_attr, None)
            if nx_apx_fn is not None and getattr(apx_val, "__doc__", None) is None:
                apx_val.__doc__ = nx_apx_fn.__doc__


_sync_approximation_docstrings()

from networkx.exception import AmbiguousSolution as _AmbiguousSolution


# br-Gsigbulk: bulk-rename the first parameter of Rust-bindings that
# name the graph arg lowercase ``g`` to the nx-standard ``G`` so
# kwarg-style drop-in calls like ``fnx.is_empty(G=g)`` work. The wrapper
# forwards positionally so the Rust side still sees the graph as its
# first positional argument. This mops up the long tail of
# Rust-native-imports that Round 19 left behind.
def _bulk_rename_first_param_to_G():
    import functools as _ft
    import inspect as _insp

    targets = [
        "bfs_layers",
        "biconnected_component_edges",
        "bidirectional_shortest_path",
        "core_number",
        "descendants_at_distance",
        "dominance_frontiers",
        "enumerate_all_cliques",
        "is_arborescence",
        "is_bipartite",
        "is_branching",
        "is_connected",
        "is_dominating_set",
        "is_edge_cover",
        "is_empty",
        "is_eulerian",
        "is_isolate",
        "is_k_edge_connected",
        "is_k_regular",
        "is_matching",
        "is_maximal_matching",
        "is_perfect_matching",
        "is_semieulerian",
        "is_simple_path",
        "is_weakly_connected",
        "isolates",
        "kosaraju_strongly_connected_components",
        "max_weight_clique",
        "max_weight_matching",
        "maximal_independent_set",
        "maximal_matching",
        "min_weight_matching",
        "node_connected_component",
        "number_connected_components",
        "number_of_isolates",
        "number_of_spanning_trees",
        "number_strongly_connected_components",
        "number_weakly_connected_components",
        "tree_broadcast_center",
        "tree_broadcast_time",
    ]
    ns = globals()
    for name in targets:
        raw = ns.get(name)
        if raw is None:
            continue
        try:
            raw_sig = _insp.signature(raw)
        except (ValueError, TypeError):
            continue
        params = list(raw_sig.parameters.values())
        if not params or params[0].name != "g":
            continue

        def _make_wrapper(raw_fn, raw_params):
            # Build a new signature renaming first positional to 'G'.
            new_first = raw_params[0].replace(name="G")
            new_sig = _insp.Signature([new_first] + list(raw_params[1:]))

            @_ft.wraps(raw_fn)
            def wrapper(*args, **kwargs):
                if "G" in kwargs and "g" not in kwargs:
                    kwargs["g"] = kwargs.pop("G")
                return raw_fn(*args, **kwargs)

            wrapper.__signature__ = new_sig
            return wrapper

        ns[name] = _make_wrapper(raw, params)


_bulk_rename_first_param_to_G()


def _bulk_promote_to_generator():
    """br-bulkgen: nx returns generators for these functions; fnx's
    bindings returned materialised lists. Wrap each so the contract
    matches (lazy, exhausts after iteration, user code calling
    ``next(it)`` works).
    """
    import functools as _ft

    targets = [
        "find_cliques",
        "find_cliques_recursive",
        "enumerate_all_cliques",
        "all_simple_paths",
        "all_shortest_paths",
        "bfs_edges",
        "dfs_edges",
        "bfs_layers",
        "isolates",
        "minimum_spanning_edges",
        "maximum_spanning_edges",
    ]

    ns = globals()
    for name in targets:
        raw = ns.get(name)
        if raw is None:
            continue

        def _make_wrapper(raw_fn):
            @_ft.wraps(raw_fn)
            def wrapper(*args, **kwargs):
                result = raw_fn(*args, **kwargs)
                if hasattr(result, "__next__"):
                    return result
                return iter(result)

            return wrapper

        ns[name] = _make_wrapper(raw)


_bulk_promote_to_generator()


def _bulk_add_backend_dispatch_kwargs():
    """br-r37-c1-spbk-bulk: nx's ``@_dispatchable`` decorator adds
    ``*, backend=None, **backend_kwargs`` to every dispatchable
    function's signature. fnx's wrappers had this surface on ~40
    functions but ~20 high-traffic ones were missed
    (br-r37-c1-0z6fh fixed 4 of them; this bulk pass covers the
    rest). Drop-in code that uses ``fn(G, ..., backend='networkx')``
    crashed on the missed ones with `TypeError: got an unexpected
    keyword argument 'backend'`.

    Wrap each missed function so its signature reflects
    ``backend`` and ``backend_kwargs``, validates them via
    ``_validate_backend_dispatch_keywords`` (raises ImportError
    for unknown backends, TypeError for unexpected kwargs), and
    forwards the rest to the original implementation.
    """
    import functools as _ft
    import inspect as _inspect

    targets = (
        "find_cycle", "simple_cycles", "diameter", "radius", "eccentricity",
        "average_shortest_path_length", "cycle_basis", "topological_sort",
        "descendants", "ancestors", "single_source_shortest_path",
        "has_path", "is_directed_acyclic_graph", "is_simple_path",
        "minimum_spanning_tree", "maximum_spanning_tree",
        "is_strongly_connected", "strongly_connected_components",
        "weakly_connected_components", "is_weakly_connected",
        # br-r37-c1-trav-bk: 11 BFS/DFS/topology traversal entry
        # points missed the backend dispatch surface — same family
        # as the prior pass.  Drop-in code that uses
        # ``fn(G, ..., backend='networkx')`` crashed.
        "bfs_labeled_edges", "dfs_labeled_edges", "bfs_layers",
        "descendants_at_distance", "bfs_predecessors", "bfs_successors",
        "bfs_tree", "dfs_tree", "topological_generations",
        "all_topological_sorts", "lexicographical_topological_sort",
        # br-r37-c1-bulk2-bk: 50-function audit found another batch
        # of high-traffic dispatchable APIs missing the backend
        # surface.  Same root cause + same fix shape as the prior
        # bulk pass.
        # Distance / path
        "shortest_path_length", "dijkstra_path", "dijkstra_path_length",
        "all_pairs_dijkstra", "floyd_warshall", "johnson",
        # Connectivity
        "biconnected_components", "is_biconnected", "bridges",
        "has_bridges", "local_bridges", "articulation_points",
        "node_connectivity", "edge_connectivity", "minimum_edge_cut",
        "all_node_cuts",
        # DAG
        "condensation", "transitive_closure", "transitive_closure_dag",
        "transitive_reduction", "antichains", "dag_to_branching",
        "dag_longest_path", "dag_longest_path_length",
        # Cycles / trees
        "recursive_simple_cycles", "minimum_cycle_basis",
        "is_arborescence", "is_branching",
        # Coloring
        "greedy_color", "equitable_color",
        # Clustering
        "clustering", "average_clustering", "transitivity",
        "triangles", "square_clustering",
        # Matching
        "max_weight_matching", "min_weight_matching", "is_matching",
        "is_perfect_matching", "is_maximal_matching",
        # Operators
        "union", "compose", "intersection", "difference",
        "symmetric_difference", "disjoint_union",
        "cartesian_product", "tensor_product", "lexicographic_product",
        "strong_product",
        # br-r37-c1-bulk3-bk: 59 more high-traffic dispatchable APIs
        # missing the backend surface — second sweep finished after
        # br-r37-c1-bulk2-bk (50 functions).
        # Path / SSSP / multi-source variants
        "estrada_index",
        "all_pairs_dijkstra_path", "all_pairs_dijkstra_path_length",
        "all_pairs_bellman_ford_path", "all_pairs_bellman_ford_path_length",
        "single_source_dijkstra", "single_source_dijkstra_path",
        "single_source_dijkstra_path_length",
        "single_source_bellman_ford", "single_source_bellman_ford_path",
        "single_source_bellman_ford_path_length",
        "multi_source_dijkstra", "multi_source_dijkstra_path",
        "multi_source_dijkstra_path_length",
        "bellman_ford_path", "bellman_ford_path_length",
        "bellman_ford_predecessor_and_distance",
        "astar_path", "astar_path_length",
        "shortest_simple_paths",
        # Components / branching
        "attracting_components", "kosaraju_strongly_connected_components",
        "minimum_spanning_edges", "maximum_spanning_edges",
        "maximum_branching", "minimum_branching",
        "maximum_spanning_arborescence", "minimum_spanning_arborescence",
        # Distance measures
        "periphery", "center", "resistance_distance",
        "effective_graph_resistance",
        # Misc
        "flow_hierarchy", "global_efficiency", "local_efficiency",
        "algebraic_connectivity", "fiedler_vector", "spectral_ordering",
        # Eulerian
        "is_eulerian", "has_eulerian_path", "is_semieulerian",
        "eulerian_path", "eulerian_circuit", "eulerize",
        # Domination / k-core
        "is_dominating_set", "dominating_set",
        "core_number", "k_core", "k_shell", "k_crust", "k_corona", "k_truss",
        # Chordal
        "is_chordal", "chordal_graph_cliques", "chordal_graph_treewidth",
        "find_induced_nodes", "complete_to_chordal_graph",
        # Regularity
        "is_strongly_regular", "is_distance_regular",
        # br-r37-c1-bk-residue: 2 dispatchable APIs slipped past
        # bulk2/bulk3/bulk4 audits.
        "graph_edit_distance", "reverse",
        # br-r37-c1-bk-matrix: 17 matrix / spectrum functions —
        # first batch of the multi-tick br-r37-c1-xc9no epic.
        "adjacency_matrix", "adjacency_spectrum",
        "attr_matrix", "attr_sparse_matrix",
        "bethe_hessian_matrix", "bethe_hessian_spectrum",
        "directed_combinatorial_laplacian_matrix",
        "directed_laplacian_matrix", "directed_modularity_matrix",
        "google_matrix", "incidence_matrix",
        "laplacian_matrix", "laplacian_spectrum",
        "modularity_matrix", "modularity_spectrum",
        "normalized_laplacian_matrix", "normalized_laplacian_spectrum",
        # br-r37-c1-bk-algo: 128 algorithm-variant functions —
        # batch 2/5 of the br-r37-c1-xc9no epic.  SSSP/all-pairs
        # variants, traversal generators, attribute setters/getters,
        # is-* predicates, k-* connectivity variants, triad/trophic
        # measures, vf2pp helpers, similarity hashing, etc.
        "all_pairs_all_shortest_paths", "all_pairs_node_connectivity",
        "all_triads", "all_triangles", "average_node_connectivity",
        "bfs_beam_edges", "bfs_edges", "biconnected_component_edges",
        "bidirectional_dijkstra", "bidirectional_shortest_path",
        "cd_index", "chain_decomposition", "chordless_cycles",
        "complement", "connected_double_edge_swap",
        "contracted_edge", "contracted_nodes",
        "convert_node_labels_to_integers", "dedensify",
        "dfs_edges", "dfs_postorder_nodes", "dfs_predecessors",
        "dfs_preorder_nodes", "dfs_successors",
        "dijkstra_predecessor_and_distance", "double_edge_swap",
        "edge_disjoint_paths", "efficiency", "enumerate_all_cliques",
        "find_asteroidal_triple", "find_cliques", "find_cliques_recursive",
        "find_minimal_d_separator", "find_negative_cycle",
        "floyd_warshall_numpy", "floyd_warshall_predecessor_and_distance",
        "from_nested_tuple", "from_prufer_sequence", "from_sparse6_bytes",
        "full_join", "generalized_degree", "generic_bfs_edges",
        "geometric_edges", "get_edge_attributes", "get_node_attributes",
        "girth", "goldberg_radzik", "harmonic_diameter",
        "hyper_wiener_index", "identified_nodes", "intersection_array",
        "is_at_free", "is_attracting_component", "is_bipartite",
        "is_connected_dominating_set", "is_d_separator", "is_digraphical",
        "is_empty", "is_k_edge_connected", "is_k_regular",
        "is_kl_connected", "is_minimal_d_separator", "is_multigraphical",
        "is_negatively_weighted", "is_pseudographical", "is_regular",
        "is_regular_expander", "is_semiconnected", "is_triad",
        "is_valid_joint_degree", "is_weighted",
        "k_components", "k_edge_augmentation", "k_edge_components",
        "k_edge_subgraphs", "k_factor", "kl_connected_subgraph",
        "make_clique_bipartite", "max_weight_clique",
        "maximal_independent_set", "maximal_matching", "min_edge_cover",
        "negative_edge_cycle", "node_attribute_xy", "node_clique_number",
        "node_connected_component", "node_degree_xy",
        "node_disjoint_paths", "node_expansion", "non_randomness",
        "number_attracting_components", "number_of_selfloops",
        "number_strongly_connected_components",
        "number_weakly_connected_components",
        "onion_layers", "optimal_edit_paths", "optimize_edit_paths",
        "panther_vector_similarity", "predecessor", "prominent_group",
        "reconstruct_path", "relabel_nodes",
        "remove_edge_attributes", "remove_node_attributes",
        "set_edge_attributes", "set_node_attributes",
        "single_source_all_shortest_paths",
        "single_source_shortest_path_length",
        "single_target_shortest_path",
        "single_target_shortest_path_length",
        "snap_aggregation", "spanner", "spectral_bisection",
        "stoer_wagner", "to_nested_tuple", "to_prufer_sequence",
        "tree_broadcast_center", "tree_broadcast_time",
        "triad_type", "triadic_census", "triads_by_type",
        "trophic_differences", "trophic_incoherence_parameter",
        "trophic_levels",
        "vf2pp_all_isomorphisms", "vf2pp_is_isomorphic", "vf2pp_isomorphism",
        "weisfeiler_lehman_subgraph_hashes",
        # br-r37-c1-bk-final: 176 remaining functions across
        # generators, IO, conversions, and submodule re-exports —
        # batches 3-5 of the br-r37-c1-xc9no epic, bundled.
        # Generators (special graphs)
        "LCF_graph", "LFR_benchmark_graph", "balanced_tree", "barbell_graph",
        "binomial_tree", "bull_graph", "caveman_graph", "chordal_cycle_graph",
        "chvatal_graph", "circulant_graph", "circular_ladder_graph",
        "complete_bipartite_graph", "complete_multipartite_graph",
        "configuration_model", "connected_caveman_graph",
        "connected_watts_strogatz_graph", "corona_product",
        "cubical_graph", "cycle_graph", "davis_southern_women_graph",
        "degree_sequence_tree", "dense_gnm_random_graph", "desargues_graph",
        "diamond_graph", "directed_configuration_model",
        "directed_edge_swap", "directed_havel_hakimi_graph",
        "directed_joint_degree_graph", "dodecahedral_graph",
        "dorogovtsev_goltsev_mendes_graph", "ego_graph", "empty_graph",
        "florentine_families_graph", "frucht_graph", "full_rary_tree",
        "generalized_petersen_graph", "generate_random_paths",
        "geographical_threshold_graph", "geometric_soft_configuration_graph",
        "gn_graph", "gnc_graph", "gnm_random_graph", "gnr_graph",
        "graph_atlas", "graph_atlas_g",
        "grid_2d_graph", "grid_graph", "havel_hakimi_graph",
        "heawood_graph", "hexagonal_lattice_graph",
        "hkn_harary_graph", "hnm_harary_graph", "hoffman_singleton_graph",
        "house_graph", "house_x_graph", "hypercube_graph",
        "icosahedral_graph", "interval_graph", "inverse_line_graph",
        "join_trees", "joint_degree_graph", "junction_tree",
        "k_random_intersection_graph", "karate_club_graph",
        "kneser_graph", "krackhardt_kite_graph", "ladder_graph",
        "lattice_reference", "les_miserables_graph", "line_graph",
        "lollipop_graph", "make_max_clique_graph",
        "margulis_gabber_galil_graph", "maybe_regular_expander_graph",
        "modular_product", "moebius_kantor_graph", "moral_graph",
        "mycielski_graph", "mycielskian", "navigable_small_world_graph",
        "nonisomorphic_trees", "null_graph",
        "number_of_nonisomorphic_trees", "number_of_spanning_trees",
        "octahedral_graph", "optimize_graph_edit_distance",
        "paley_graph", "pappus_graph", "partition_spanning_tree",
        "petersen_graph", "planted_partition_graph", "power",
        "prefix_tree", "prefix_tree_recursive", "projected_graph",
        "quotient_graph", "random_clustered_graph", "random_cograph",
        "random_degree_sequence_graph", "random_geometric_graph",
        "random_internet_as_graph", "random_k_out_graph",
        "random_labeled_rooted_forest", "random_labeled_rooted_tree",
        "random_labeled_tree", "random_partition_graph",
        "random_powerlaw_tree_sequence", "random_reference",
        "random_regular_expander_graph", "random_spanning_tree",
        "random_unlabeled_rooted_forest", "random_unlabeled_rooted_tree",
        "random_unlabeled_tree", "relaxed_caveman_graph",
        "ring_of_cliques", "rooted_product", "scale_free_graph",
        "sedgewick_maze_graph", "soft_random_geometric_graph",
        "spectral_graph_forge", "star_graph", "stochastic_block_model",
        "stochastic_graph", "sudoku_graph", "tadpole_graph",
        "tetrahedral_graph", "thresholded_random_geometric_graph",
        "tree_graph", "triad_graph", "triangular_lattice_graph",
        "trivial_graph", "truncated_cube_graph",
        "truncated_tetrahedron_graph", "turan_graph", "tutte_graph",
        "visibility_graph", "waxman_graph", "weisfeiler_lehman_graph_hash",
        "wheel_graph", "windmill_graph",
        # IO / conversion functions
        "adjacency_graph", "cytoscape_graph", "from_dict_of_lists",
        "from_edgelist", "from_graph6_bytes", "from_numpy_array",
        "from_pandas_adjacency", "from_scipy_sparse_array",
        "node_link_graph", "parse_adjlist", "parse_edgelist",
        "parse_gml", "parse_graphml", "parse_leda",
        "parse_multiline_adjlist", "parse_pajek", "read_adjlist",
        "read_gexf", "read_gml", "read_graph6", "read_graphml",
        "read_leda", "read_multiline_adjlist", "read_pajek",
        "read_sparse6", "read_weighted_edgelist",
        "to_numpy_array", "to_pandas_adjacency",
        "to_pandas_edgelist", "to_scipy_sparse_array",
        # Predicates
        "is_graphical", "is_perfect_graph", "is_tournament",
        "is_valid_degree_sequence_erdos_gallai",
        "is_valid_degree_sequence_havel_hakimi",
        "is_valid_directed_joint_degree",
        # br-r37-c1-bulk4-bk: 64 more high-traffic dispatchable
        # APIs missing the backend surface — third / final sweep
        # covering communicability, assortativity, cuts, isolates,
        # link prediction, isomorphism, polynomials, flows, and
        # boundary measures.
        # Communicability
        "communicability", "communicability_exp",
        # Isolates / aperiodic
        "is_aperiodic", "is_isolate", "number_of_isolates", "isolates",
        # Voronoi / sequence-driven
        "voronoi_cells", "expected_degree_graph",
        # Assortativity
        "degree_assortativity_coefficient",
        "degree_pearson_correlation_coefficient",
        "attribute_assortativity_coefficient",
        "numeric_assortativity_coefficient",
        "attribute_mixing_dict", "attribute_mixing_matrix",
        "degree_mixing_dict", "degree_mixing_matrix",
        # Cuts / expansion
        "mixing_expansion", "cut_size", "normalized_cut_size",
        "volume", "boundary_expansion", "edge_expansion", "conductance",
        # Edge traversals
        "edge_dfs", "edge_bfs",
        # *_all operators
        "compose_all", "union_all", "intersection_all", "disjoint_union_all",
        # Link prediction
        "jaccard_coefficient", "adamic_adar_index",
        "preferential_attachment", "cn_soundarajan_hopcroft",
        "ra_index_soundarajan_hopcroft", "within_inter_cluster",
        "resource_allocation_index",
        # Isomorphism (top-level)
        "is_isomorphic", "could_be_isomorphic",
        "fast_could_be_isomorphic", "faster_could_be_isomorphic",
        # Similarity
        "simrank_similarity", "panther_similarity",
        # Edge cover
        "is_edge_cover",
        # Conversions
        "to_dict_of_lists", "to_edgelist", "from_dict_of_dicts",
        # Boundaries
        "edge_boundary", "node_boundary",
        # Dominance
        "immediate_dominators", "dominance_frontiers",
        # Polynomials
        "chromatic_polynomial", "tutte_polynomial",
        # Flows
        "minimum_cut_value", "maximum_flow_value", "maximum_flow",
        "minimum_cut", "min_cost_flow", "min_cost_flow_cost",
        "max_flow_min_cost", "cost_of_flow", "gomory_hu_tree",
        "capacity_scaling", "network_simplex",
    )

    ns = globals()

    for name in targets:
        raw = ns.get(name)
        if raw is None:
            continue
        try:
            orig_sig = _inspect.signature(raw)
        except (TypeError, ValueError):
            continue
        if "backend" in orig_sig.parameters:
            continue  # Already has the surface — leave alone.

        def _make_wrapper(raw_fn, fn_name, base_sig):
            orig_param_names = set(base_sig.parameters)
            # br-r37-c1-bulk4-bk: when the original already has
            # ``**kwargs`` it is *intended* to forward unknown kwargs
            # downstream (e.g. flow_func dispatch on minimum_cut_value).
            # Don't strip-and-validate in that case — just pass through.
            has_var_keyword = any(
                p.kind == _inspect.Parameter.VAR_KEYWORD
                for p in base_sig.parameters.values()
            )

            @_ft.wraps(raw_fn)
            def wrapper(*args, backend=None, **kwargs):
                if has_var_keyword:
                    # The original consumes **kwargs; only validate
                    # ``backend`` and forward the rest unchanged.
                    _validate_backend_dispatch_keywords(fn_name, backend, {})
                    return raw_fn(*args, **kwargs)
                bk = {k: kwargs.pop(k) for k in list(kwargs) if k not in orig_param_names}
                _validate_backend_dispatch_keywords(fn_name, backend, bk)
                return raw_fn(*args, **kwargs)

            # Synthesize a signature with backend / backend_kwargs added
            # so inspect.signature parity matches nx exactly.
            # br-r37-c1-bulk4-bk: when the original signature already
            # had a VAR_KEYWORD param (``**kwargs``), inserting another
            # one was rejected with ValueError and the synthesis was
            # skipped — leaving ``inspect.signature(wrapper)`` showing
            # the original (no ``backend``).  Fix: insert ``backend``
            # *before* the existing var-keyword and reuse the existing
            # var-keyword (rather than adding a duplicate).
            base_params = list(base_sig.parameters.values())
            existing_var_keyword = next(
                (p for p in base_params
                 if p.kind == _inspect.Parameter.VAR_KEYWORD),
                None,
            )
            if existing_var_keyword is None:
                new_params = base_params + [
                    _inspect.Parameter(
                        "backend",
                        kind=_inspect.Parameter.KEYWORD_ONLY,
                        default=None,
                    ),
                    _inspect.Parameter(
                        "backend_kwargs",
                        kind=_inspect.Parameter.VAR_KEYWORD,
                    ),
                ]
            else:
                # Insert ``backend`` keyword-only just before the
                # existing **kwargs.  Reuse the existing var-keyword
                # name (matching nx's pattern of ``**kwargs`` rather
                # than ``**backend_kwargs`` for these flow APIs).
                new_params = [p for p in base_params if p is not existing_var_keyword]
                new_params.append(_inspect.Parameter(
                    "backend",
                    kind=_inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                ))
                new_params.append(existing_var_keyword)
            try:
                wrapper.__signature__ = base_sig.replace(parameters=new_params)
            except (TypeError, ValueError):
                # If signature reconstruction fails (e.g. duplicate VAR_*),
                # fall back to no-signature; the kwargs still work.
                pass
            return wrapper

        ns[name] = _make_wrapper(raw, name, orig_sig)


_bulk_add_backend_dispatch_kwargs()
_install_convert_matrix_native_aliases()


def _resync_isomorphism_module_exports():
    """br-r37-c1-bulk4-bk: the isomorphism submodule is built earlier
    by snapshotting globals().  When the later bulk backend-dispatch
    wrap replaces the wrapped names in globals(), the submodule's
    references go stale.  Re-sync after the wrap so
    ``fnx.isomorphism.is_isomorphic is fnx.is_isomorphic``."""
    if "isomorphism" not in globals():
        return
    iso_mod = globals()["isomorphism"]
    for export_name in _ISOMORPHISM_MODULE_EXPORTS:
        if export_name in globals():
            setattr(iso_mod, export_name, globals()[export_name])


def _resync_submodule_exports():
    """Re-sync submodules whose exports may have captured unwrapped functions
    before _bulk_add_backend_dispatch_kwargs ran, or whose references went stale."""
    _resync_isomorphism_module_exports()

    for mod_name in (
        "assortativity",
        "centrality",
        "coloring",
        "distance_measures",
        "link_analysis",
        "shortest_paths",
    ):
        for prefix in (f"{__name__}.{mod_name}", f"{__name__}.algorithms.{mod_name}"):
            mod = _sys.modules.get(prefix)
            if mod is not None and hasattr(mod, "_route_to_fnx_toplevel"):
                mod._route_to_fnx_toplevel()

    for mod_name, func_names in (
        ("boundary", ("edge_boundary", "node_boundary")),
        ("chains", ("chain_decomposition",)),
        ("communicability_alg", ("communicability", "communicability_exp")),
        ("asteroidal", ("is_at_free", "find_asteroidal_triple")),
        ("planar_drawing", ("combinatorial_embedding_to_pos",)),
        ("time_dependent", ("cd_index",)),
    ):
        for prefix in (f"{__name__}.{mod_name}", f"{__name__}.algorithms.{mod_name}"):
            mod = _sys.modules.get(prefix)
            if mod is not None:
                for fn in func_names:
                    if fn in globals():
                        setattr(mod, fn, globals()[fn])

    alg_mod = _sys.modules.get(f"{__name__}.algorithms")
    if alg_mod is not None and hasattr(alg_mod, "_install_fnx_native_algorithm_aliases"):
        alg_mod._install_fnx_native_algorithm_aliases()


def _bulk_coerce_negative_depth_to_zero():
    """br-r37-c1-trav-depth-bulk: same defect family as br-r37-c1-
    {w1smc, udsdu}. The Rust traversal bindings declare
    `depth_limit` / `cutoff` as unsigned int — negative values
    raise OverflowError. nx walks `range(depth)` / while-loop
    which trivially yields nothing on negatives, returning empty
    or source-only results.

    Wrap each affected function so a negative `depth_limit` /
    `cutoff` is coerced to 0 (nx-equivalent degenerate result)
    before the Rust binding sees it. Other arg shapes pass
    through unchanged.
    """
    import functools as _ft
    import inspect as _inspect

    # Map: function name -> kwarg name to coerce
    # br-r37-c1-cut-extend: extended in cycle 140 to cover two
    # more cutoff/depth_limit functions still raising
    # TypeError/OverflowError on NaN/+inf/float (same family as
    # br-r37-c1-bfs-cutfloat / -s86fd):
    #   * single_source_shortest_path
    #   * dfs_tree
    # ``predecessor`` is intentionally excluded — its cutoff
    # semantic ``if cutoff and cutoff <= level: break`` is
    # truthy-aware (``cutoff=-1`` IS truthy and breaks at level 0,
    # ``cutoff=0`` is falsy and acts as unbounded) so the
    # _DEPTH_EMPTY → 0 mapping the wrapper performs would change
    # behaviour.
    targets = {
        "dfs_edges": "depth_limit",
        "dfs_predecessors": "depth_limit",
        "dfs_successors": "depth_limit",
        "dfs_postorder_nodes": "depth_limit",
        "dfs_preorder_nodes": "depth_limit",
        "dfs_tree": "depth_limit",
        "single_source_shortest_path": "cutoff",
        "single_source_shortest_path_length": "cutoff",
        "single_target_shortest_path": "cutoff",
        "single_target_shortest_path_length": "cutoff",
        "all_pairs_shortest_path": "cutoff",
        "all_pairs_shortest_path_length": "cutoff",
    }

    ns = globals()

    for fn_name, kwarg_name in targets.items():
        raw = ns.get(fn_name)
        if raw is None:
            continue
        try:
            sig = _inspect.signature(raw)
        except (TypeError, ValueError):
            continue
        if kwarg_name not in sig.parameters:
            continue
        # Find the positional index of the kwarg (for *args support).
        param_names = list(sig.parameters)
        kwarg_idx = param_names.index(kwarg_name)

        def _coerce_cutoff_value(val):
            """br-r37-c1-bfs-cutfloat-sister: route through the
            ``_normalize_bfs_depth_limit`` helper so NaN / +inf /
            -inf / fractional float / negative int all map to
            nx-shaped behaviour before the Rust binding sees the
            value.  The previous ``int(val) < 0`` check raised
            OverflowError on +/-inf and TypeError on NaN/float —
            both diverging from nx's permissive numeric handling.
            Returns ``(replacement_or_unchanged, replaced_flag)``.
            """
            if val is None:
                return val, False
            normalized = _normalize_bfs_depth_limit(val)
            if normalized is _DEPTH_EMPTY:
                # nx-shaped "empty" — Rust binding accepts 0 as the
                # closest non-negative bound (yields nothing for
                # bfs/shortest-path-length style; for dfs the source
                # is still emitted with depth=0 which matches nx's
                # NaN/-inf behaviour).
                return 0, True
            return normalized, normalized is not val

        def _make_wrapper(raw_fn, idx, name):
            @_ft.wraps(raw_fn)
            def wrapper(*args, **kwargs):
                # Try keyword first, then positional.
                if name in kwargs:
                    new_val, changed = _coerce_cutoff_value(kwargs[name])
                    if changed:
                        kwargs[name] = new_val
                elif idx < len(args):
                    new_val, changed = _coerce_cutoff_value(args[idx])
                    if changed:
                        args = args[:idx] + (new_val,) + args[idx + 1:]
                return raw_fn(*args, **kwargs)
            return wrapper

        ns[fn_name] = _make_wrapper(raw, kwarg_idx, kwarg_name)


_bulk_coerce_negative_depth_to_zero()
_resync_submodule_exports()


def __getattr__(name):
    """Fallback to the NetworkX top-level namespace for missing public attrs."""
    # br-r37-c1-rt-removed: nx 3.4 removed ``random_tree`` and now
    # raises a deprecation AttributeError on attribute access pointing
    # callers at ``random_labeled_tree``.  fnx had a public
    # ``random_tree`` Python function that silently kept working,
    # masking the deprecation for drop-in callers.  Mirror nx's exact
    # error before the generic nx-fallback below.
    if name == "random_tree":
        raise AttributeError(
            "nx.random_tree was removed in version 3.4. Use "
            "`nx.random_labeled_tree` instead.\n"
            "See: https://networkx.org/documentation/latest/release/release_3.4.html"
        )
    # br-r37-c1-bia-removed: biadjacency_matrix /
    # from_biadjacency_matrix are nx.bipartite-only; nx never
    # exposed them at top level.  fnx had top-level Python
    # re-implementations (now removed) that masked nx's
    # AttributeError — emit nx's exact wording so drop-in
    # callers branching on the exception see identical behaviour.
    if name in ("biadjacency_matrix", "from_biadjacency_matrix"):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-m8ktl: nx removed top-level ``info`` in 3.0 (the
    # function lived only as a deprecation shim before that).
    # fnx kept a working ``info`` that masked nx's AttributeError
    # for drop-in callers branching on ``hasattr(nx, 'info')``.
    if name == "info":
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-42dos: nx removed top-level ``graph_clique_number``;
    # it lives only at nx.algorithms.clique. fnx exposed it through
    # the _fnx Rust binding, masking nx's AttributeError for drop-in
    # callers branching on ``hasattr(nx, 'graph_clique_number')``.
    if name == "graph_clique_number":
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-twl53: hamiltonian_path lives only at
    # nx.tournament.hamiltonian_path; nx top-level raises AttributeError.
    # fnx.tournament.hamiltonian_path still works via the auto-bound
    # nx.algorithms.tournament submodule fallback.
    if name == "hamiltonian_path":
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-j57zz: ``nodes_equal`` / ``edges_equal`` /
    # ``graphs_equal`` live only at nx.utils.X; ``average_degree``
    # doesn't exist in nx at all. Removed from fnx top-level for
    # drop-in parity (the three test helpers are still reachable
    # via fnx.utils.X through the submodule fallback).
    if name in ("nodes_equal", "edges_equal", "graphs_equal", "average_degree"):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-qy2r4: more leaked fnx top-level helpers nx doesn't
    # re-export at top level — make_list_of_ints / cumulative_distribution
    # / powerlaw_sequence / zipf_rv live at nx.utils.X (still reachable
    # via fnx.utils.X). frozen / flow_matrix_row / pseudo_peripheral_node
    # are fnx-only public aliases for deeply-nested nx internals — drop
    # them; callers can use the nx-qualified path directly.
    if name in (
        "make_list_of_ints", "cumulative_distribution",
        "powerlaw_sequence", "zipf_rv",
        "frozen", "flow_matrix_row", "pseudo_peripheral_node",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-xc6c2: greedy-coloring strategy callables live at
    # nx.coloring.X / nx.algorithms.coloring.X but not at nx top level.
    # fnx exposed all 8 — removed for drop-in parity; still reachable
    # via fnx.coloring.X (greedy_color also accepts the string names).
    if name in (
        "strategy_largest_first", "strategy_smallest_last",
        "strategy_random_sequential", "strategy_independent_set",
        "strategy_connected_sequential",
        "strategy_connected_sequential_bfs",
        "strategy_connected_sequential_dfs",
        "strategy_saturation_largest_first",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-32nso: 11 subgraph_view filter constructors live at
    # nx.classes.filters.X — nx top-level raises. fnx exposed all 11;
    # removed for drop-in parity. They remain reachable via
    # fnx.classes.filters.X through the auto-bound submodule fallback.
    if name in (
        "hide_nodes", "hide_edges", "hide_diedges",
        "hide_multiedges", "hide_multidiedges",
        "show_nodes", "show_edges", "show_diedges",
        "show_multiedges", "show_multidiedges",
        "no_filter",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-xgqo1: 18 nx.approximation helpers live at
    # nx.approximation.X but not at nx top level. fnx exposed all
    # 18 — removed for drop-in parity. They remain reachable via
    # fnx.approximation.X through the auto-bound submodule fallback.
    if name in (
        "christofides", "clique_removal", "densest_subgraph",
        "maximum_independent_set", "max_clique", "metric_closure",
        "min_edge_dominating_set", "min_maximal_matching",
        "min_weighted_dominating_set", "min_weighted_vertex_cover",
        "one_exchange", "randomized_partitioning", "ramsey_R2",
        "simulated_annealing_tsp", "threshold_accepting_tsp",
        "steiner_tree", "traveling_salesman_problem",
        "asadpour_atsp",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-uwm5v: 8 nx.community helpers live at nx.community.X
    # but not at nx top level. fnx exposed all 8 — removed for
    # drop-in parity. They remain reachable via fnx.community.X
    # through the auto-bound submodule fallback.
    if name in (
        "louvain_communities", "louvain_partitions",
        "leiden_partitions", "asyn_fluidc",
        "asyn_lpa_communities",
        "fast_label_propagation_communities",
        "edge_betweenness_partition", "girvan_newman",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-02sx1: 7 more nx.community helpers + nx.bipartite.
    # is_bipartite_node_set — none at nx top level. fnx exposed
    # all 8 — removed for drop-in parity. They remain reachable
    # via fnx.community.X / fnx.bipartite.X.
    if name in (
        "greedy_modularity_communities", "leiden_communities",
        "label_propagation_communities", "k_clique_communities",
        "greedy_source_expansion", "kernighan_lin_bisection",
        "is_partition", "is_bipartite_node_set",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-hoqqp: 9 dag / treewidth / node_classification
    # helpers at nx.algorithms.{dag,approximation,node_classification}.X
    # — none at nx top level. fnx exposed all 9 — removed for
    # drop-in parity. ``lexicographic_topological_sort`` is fnx-only
    # (nx never exposed it). Reachable via fnx.algorithms.X.
    if name in (
        "colliders", "v_structures", "has_cycle",
        "lexicographic_topological_sort", "root_to_leaf_paths",
        "treewidth_min_degree", "treewidth_min_fill_in",
        "harmonic_function", "local_and_global_consistency",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-3u5xk: 8 more nx-namespaced helpers — none at nx
    # top level. Removed for drop-in parity:
    #   nx.utils.rcm.X:           cuthill_mckee_ordering /
    #                             connected_cuthill_mckee_ordering /
    #                             reverse_cuthill_mckee_ordering
    #   nx.bipartite.X:           hopcroft_karp_matching / latapy_clustering
    #   nx.algorithms.matching.X: matching_dict_to_set
    #   nx.algorithms.connectivity.X: is_locally_k_edge_connected
    #   nx.algorithms.tournament.X:   is_reachable
    if name in (
        "cuthill_mckee_ordering", "connected_cuthill_mckee_ordering",
        "reverse_cuthill_mckee_ordering",
        "hopcroft_karp_matching", "latapy_clustering",
        "matching_dict_to_set",
        "is_locally_k_edge_connected", "is_reachable",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-dytcs: 10 more nx-namespaced helpers — none at nx
    # top level. Removed for drop-in parity:
    #   nx.readwrite.X (selective): parse_gexf / parse_graph6 / parse_sparse6
    #   nx.algorithms.bipartite.cluster.X: cc_dot / cc_max / cc_min
    #   nx.algorithms.tree.branchings.X:   greedy_branching
    #   nx.algorithms.approximation.X:     greedy_tsp / large_clique_size
    #   nx.algorithms.bipartite.X:         to_vertex_cover
    if name in (
        "parse_gexf", "parse_graph6", "parse_sparse6",
        "cc_dot", "cc_max", "cc_min",
        "greedy_branching", "greedy_tsp",
        "large_clique_size", "to_vertex_cover",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-luy4x: 6 more nx-namespaced helpers — none at nx
    # top level. Removed for drop-in parity:
    #   nx.algorithms.tree.mst.X: boruvka_mst_edges / kruskal_mst_edges /
    #                             prim_mst_edges
    #   nx.algorithms.structuralholes.X: mutual_weight /
    #                                    normalized_mutual_weight
    #   nx.algorithms.connectivity.X: local_node_connectivity
    if name in (
        "boruvka_mst_edges", "kruskal_mst_edges", "prim_mst_edges",
        "mutual_weight", "normalized_mutual_weight",
        "local_node_connectivity",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-ccr8k: 4 fnx-only helpers that don't exist anywhere
    # in nx. Removed from fnx top level for drop-in parity (callers
    # can use the closest nx equivalent or the _fnx Rust binding):
    #   global_node_connectivity     -> use node_connectivity
    #   is_valid_tree_degree_sequence
    #   number_of_spanning_arborescences (still in franken_networkx._fnx)
    #   random_uniform_k_out_graph
    if name in (
        "global_node_connectivity",
        "is_valid_tree_degree_sequence",
        "number_of_spanning_arborescences",
        "random_uniform_k_out_graph",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-yidw1: 8 nx.bipartite helpers live at nx.bipartite.X
    # but not at nx top level. fnx exposed all 8 — removed for
    # drop-in parity. They remain reachable via fnx.bipartite.X
    # through the auto-bound submodule fallback. Note ``color``,
    # ``sets``, and ``degrees`` use very generic names — drop-in
    # callers should reach them via the namespace.
    if name in (
        "eppstein_matching", "maximum_matching",
        "minimum_weight_full_matching", "node_redundancy",
        "color", "degrees", "robins_alexander_clustering", "sets",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-vt5fm: 4 nx.connectivity helpers live at
    # nx.algorithms.connectivity.X but not at nx top level. fnx
    # exposed all 4 — removed for drop-in parity. They remain
    # reachable via fnx.connectivity.X through the auto-bound
    # submodule fallback.
    if name in (
        "local_edge_connectivity", "minimum_st_edge_cut",
        "minimum_st_node_cut", "bridge_components",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-yrtsz: 5 nx.algorithms.flow primitives — none at nx
    # top level. fnx exposed all 5 + accepted them as
    # ``flow_func=fnx.X`` callable args in tests. Removed for
    # drop-in parity; tests migrated to ``flow_func=fnx.flow.X``.
    # Reachable via fnx.flow.X / fnx.algorithms.flow.X.
    if name in (
        "edmonds_karp", "preflow_push", "shortest_augmenting_path",
        "dinitz", "boykov_kolmogorov",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-4asgt: 3 nx.utils.heaps.X classes (BinaryHeap, MinHeap,
    # PairingHeap) + NotAPartition (nx.algorithms.community.quality.X).
    # All exposed at fnx top level but not at nx top level. Aliased
    # privately as _BinaryHeap / _NotAPartition / etc; reachable via
    # fnx.utils.X / fnx.community.X.
    if name in (
        "BinaryHeap", "MinHeap", "PairingHeap",
        "NotAPartition",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-dm5jl: 5 tournament + tree-isomorphism helpers
    # live at nx.tournament.X / nx.isomorphism.X but not at nx top
    # level. fnx exposed all 5 — removed for drop-in parity. They
    # remain reachable via fnx.tournament.X / fnx.isomorphism.X.
    if name in (
        "random_tournament", "tournament_matrix", "score_sequence",
        "rooted_tree_isomorphism", "tree_isomorphism",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-bipx-removed: bipartite_sets and bipartite_density
    # were exposed at fnx top-level as fnx-only convenience aliases.
    # nx exposes them only at nx.bipartite (sets / density).  Drop-
    # in callers writing nx.bipartite_sets get AttributeError on nx;
    # mirror that contract.
    if name in ("bipartite_sets", "bipartite_density"):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-iso-removed: nine isomorphism matcher constructors
    # (categorical/numerical/generic × node/edge/multiedge) live
    # only at ``nx.algorithms.isomorphism`` in nx.  fnx had top-
    # level aliases that masked the AttributeError nx raises for
    # drop-in callers.  Mirror nx's exact wording.
    if name in (
        "categorical_node_match", "categorical_edge_match",
        "categorical_multiedge_match",
        "numerical_node_match", "numerical_edge_match",
        "numerical_multiedge_match",
        "generic_node_match", "generic_edge_match",
        "generic_multiedge_match",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-bw-removed: branching_weight / minimal_branching live
    # only at nx.algorithms.tree.branchings; nx top-level raises.
    if name in ("branching_weight", "minimal_branching"):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    # br-r37-c1-plr-removed: planarity helpers live only at
    # nx.algorithms.planarity; nx top-level raises.
    if name in (
        "check_planarity_recursive", "get_counterexample",
        "get_counterexample_recursive",
    ):
        raise AttributeError(
            f"module 'networkx' has no attribute '{name}'"
        )
    import networkx as nx

    # br-r37-c1-als7z: for submodules that fnx has its own version of,
    # return the fnx submodule instead of nx's so fnx.generators.balanced_tree
    # returns fnx types instead of nx types.
    # br-r37-c1-2qsqf: a name missing from this set does NOT fall back to a
    # harmless nx module — it silently replaces the fnx submodule wholesale,
    # because the fallback below is `getattr(nx, name)` and networkx has a module
    # of the same name. `fnx.convert.from_edgelist` was returning
    # `networkx.convert.from_edgelist`, so the routing inside
    # `franken_networkx/convert.py` was dead on this access path while still
    # reachable via `from franken_networkx.convert import ...` (two spellings,
    # two implementations). The three added here each carry real overrides that
    # were unreachable: convert 7 names, distance_regular 5, relabel 2.
    #
    # Only these three are added because only these three are inside the audit
    # this bead covers. 36 further submodules are shadowed the same way and are
    # filed separately — adding them here is a bigger behavioural change than
    # this bead's evidence supports.
    _fnx_submodules = {
        "algorithms",
        "broadcasting",
        "classes",
        "connectivity",
        "convert",
        "convert_matrix",
        "distance_regular",
        "drawing",
        "generators",
        "linalg",
        "readwrite",
        "relabel",
        "utils",
        # br-r37-c1-t6z9m: the remaining 35 fnx-owned submodules that networkx
        # also has a module for. Without an entry here `getattr(nx, name)` wins
        # and `fnx.<ns>` IS networkx's module, so every name reached through it
        # is networkx's implementation whatever the fnx submodule contains.
        #
        # Each was checked individually rather than swept in, as the bead
        # required: for every one below, the fnx submodule genuinely overrides
        # at least one name that networkx also exports (counts ranged 1-4, e.g.
        # centrality 4, link_analysis 3 (pagerank/hits/google_matrix), boundary 2,
        # walks 1). `exception` is DELIBERATELY absent — it is a pure re-export,
        # so allowlisting it would change which module object is returned while
        # changing no behaviour.
        "assortativity",
        "asteroidal",
        "boundary",
        "centrality",
        "chains",
        "cluster",
        "coloring",
        "communicability_alg",
        "covering",
        "cuts",
        "cycles",
        "d_separation",
        "distance_measures",
        "dominance",
        "dominating",
        "efficiency_measures",
        "graph_hashing",
        "graphical",
        "hierarchy",
        "isolate",
        "link_analysis",
        "link_prediction",
        "lowest_common_ancestors",
        "matching",
        "mis",
        "perfect_graph",
        "planar_drawing",
        "polynomials",
        "richclub",
        "shortest_paths",
        "similarity",
        "simple_paths",
        "smetric",
        "structuralholes",
        "time_dependent",
        "vitality",
        "voronoi",
        "walks",
        "wiener",
    }
    if name in _fnx_submodules:
        import importlib
        try:
            return importlib.import_module(f"franken_networkx.{name}")
        except ImportError:
            pass  # Fall through to nx

    try:
        return getattr(nx, name)
    except AttributeError as exc:
        # br-r37-c1-aohtp: mirror nx's exact wording so drop-in callers
        # branching on the AttributeError message see identical text on
        # fnx and nx (siblings in this same handler already do).
        raise AttributeError(f"module 'networkx' has no attribute '{name}'") from exc


def __dir__():
    """Expose FrankenNetworkX globals plus NetworkX's public top-level namespace."""
    import networkx as nx

    return sorted(set(globals()) | set(dir(nx)))


# br-r37-c1-z0640: ``networkx`` declares no ``__all__``, so ``from networkx
# import *`` binds every public module-level name — including its subpackages.
# fnx declares an explicit ``__all__``, and these 27 subpackages were absent from
# it, so ``from franken_networkx import *; bipartite.sets(G)`` raised NameError
# where the nx spelling works. They were always reachable as ATTRIBUTES; only the
# star-export surface was short.
#
# Listed explicitly rather than derived: ``approximation`` is a
# ``_ApproximationNamespace`` instance, not a ``ModuleType``, and its ``__name__``
# is swallowed by its own ``__getattr__``, so any ``isinstance(v, ModuleType)``
# rule silently drops it (measured: such a rule selects 26 of the 27). The
# accompanying test asserts the property against the live nx surface, so a
# subpackage added later without being exported fails there.
__all__ += [
    "approximation",
    "bipartite",
    "chordal",
    "clique",
    "community",
    "components",
    "convert_matrix",
    "core",
    "dag",
    "drawing",
    "euler",
    "flow",
    "hybrid",
    "minors",
    "moral",
    "node_classification",
    "operators",
    "planarity",
    "readwrite",
    "regular",
    "smallworld",
    "sparsifiers",
    "summarization",
    "swap",
    "tournament",
    "traversal",
    "tree",
    "triads",
    "algorithms",
    "assortativity",
    "asteroidal",
    "boundary",
    "broadcasting",
    "centrality",
    "chains",
    "cluster",
    "coloring",
    "communicability_alg",
    "connectivity",
    "covering",
    "cuts",
    "cycles",
    "d_separation",
    "distance_measures",
    "distance_regular",
    "dominance",
    "dominating",
    "efficiency_measures",
    "graph_hashing",
    "graphical",
    "hierarchy",
    "isolate",
    "link_analysis",
    "link_prediction",
    "lowest_common_ancestors",
    "matching",
    "mis",
    "perfect_graph",
    "planar_drawing",
    "polynomials",
    "richclub",
    "shortest_paths",
    "similarity",
    "simple_paths",
    "smetric",
    "structuralholes",
    "time_dependent",
    "vitality",
    "voronoi",
    "walks",
    "wiener",
]


_fnx_public_bridges.bridges = _fnx_public_bridges
_fnx_public_bridges.has_bridges = has_bridges
_fnx_public_bridges.local_bridges = local_bridges

_fnx_public_reciprocity.reciprocity = _fnx_public_reciprocity
_fnx_public_reciprocity.overall_reciprocity = overall_reciprocity

# ``franken_networkx.bridges`` / ``.reciprocity`` are leaf SUBMODULES whose
# names collide with public functions — exactly like networkx, where
# ``nx.bridges`` is the function while ``sys.modules["networkx.algorithms.bridges"]``
# is the module. The import system binds a child module onto its parent the
# first time it is loaded, so load them NOW and bind the functions afterwards
# (networkx's own package init relies on the same ordering). This replaces the
# 07924ecdd module-class swap, whose Python-level ``__getattribute__`` made
# every ``fnx.<attr>`` lookup ~4x slower (br-r37-c1-rc0923-epic-honest-measurement-vbneu.1).
import importlib as _importlib_leaf

_importlib_leaf.import_module("franken_networkx.bridges")
_importlib_leaf.import_module("franken_networkx.reciprocity")
bridges = _fnx_public_bridges
reciprocity = _fnx_public_reciprocity
