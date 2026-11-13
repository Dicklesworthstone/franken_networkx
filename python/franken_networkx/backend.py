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
import weakref
from contextvars import ContextVar

import franken_networkx as fnx

# br-r37-c1-xykjs: bulk native adjacency+attrs dump for the _fnx_to_nx parity
# conversion — one PyO3 crossing instead of per-edge AtlasView access.
try:
    from franken_networkx._fnx import (
        fnx_to_nx_adjacency as _native_fnx_to_nx_adjacency,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_fnx_to_nx_adjacency = None
try:
    from franken_networkx._fnx import (
        graph_has_any_attrs as _native_graph_has_any_attrs,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_graph_has_any_attrs = None

from franken_networkx._fnx import (
    nx_adjacency_edge_batch as _native_nx_adjacency_edge_batch,
)

log = logging.getLogger("franken_networkx.backend")

# should_run's ski-rental thresholds (sfq4w.2): k = ceil(B / (r - w)), the calls
# on one unmutated graph after which converting it pays off, where B is one
# conversion, r networkx's time per call and w fnx's once converted. Measured
# 2026-09-24 on a 20k-node / 80k-edge Barabasi-Albert graph (weighted for
# dijkstra, an oriented copy for the directed kernels). None: fnx is not faster
# once converted, so these calls never pay for a conversion. Anything absent
# converts on first use (heavier kernels, where one call recovers the cost).
_CONVERT_AFTER_USES = {
    "bfs_edges": 13,
    "bfs_tree": 3,
    "dfs_edges": 6,
    "dfs_preorder_nodes": 5,
    "number_connected_components": 10,
    "is_connected": 11,
    "node_connected_component": 12,
    "single_source_shortest_path_length": 8,
    "single_source_shortest_path": 144,
    "has_path": None,
    "single_source_dijkstra_path_length": 5,
    "pagerank": 3,
    "degree_centrality": 50,
    "core_number": 2,
    "descendants": 8,
    # Also dispatched from inside networkx's own pagerank and other matrix
    # routines: without an entry, a declined pagerank converted anyway.
    "to_scipy_sparse_array": 4,
}
_RENT_KEY = "franken_networkx: conversion rent"

# Component iterators are part of the owned live-input surface below.
_COMPONENT_ITERATORS = frozenset(
    {
        "connected_components",
        "weakly_connected_components",
        "strongly_connected_components",
        "biconnected_components",
        "biconnected_component_edges",
        "articulation_points",
    }
)
_COMMUNITY_ITERATOR_ALGORITHMS = frozenset(
    {
        "asyn_lpa_communities",
        "fast_label_propagation_communities",
        "girvan_newman",
        "k_clique_communities",
    }
)
_BETWEENNESS_INPUT_ALGORITHMS = frozenset(
    {"betweenness_centrality", "edge_betweenness_centrality"}
)
_SUBSET_BETWEENNESS_INPUT_ALGORITHMS = frozenset(
    {"betweenness_centrality_subset", "edge_betweenness_centrality_subset"}
)
_CONNECTIVITY_BATCH_INPUT_ALGORITHMS = frozenset(
    {"all_pairs_node_connectivity", "average_node_connectivity", "gomory_hu_tree"}
)
# Core decomposition graph restrictions are part of the algorithm contract.
_CORE_DECOMPOSITION_ALGORITHMS = frozenset(
    {"core_number", "k_core", "k_shell", "k_crust", "k_corona", "k_truss", "onion_layers"}
)
_BIPARTITE_MATCHING_ALGORITHMS = frozenset(
    {
        "hopcroft_karp_matching", "eppstein_matching", "to_vertex_cover",
        "minimum_weight_full_matching",
    }
)
_BIPARTITE_PROJECTION_ALGORITHMS = frozenset(
    {
        "projected_graph", "weighted_projected_graph",
        "collaboration_weighted_projected_graph", "generic_weighted_projected_graph",
        "overlap_weighted_projected_graph",
    }
)
_RESIDUAL_FLOW_ALGORITHMS = frozenset(
    {
        "edmonds_karp", "dinitz", "shortest_augmenting_path",
        "preflow_push", "boykov_kolmogorov",
    }
)

# These iterators read the caller's graph as they advance. NetworkX's conversion
# cache is shared by algorithms, so this choice belongs at invocation time,
# including when an eager algorithm populated the cache first.
_LIVE_INPUT_ALGORITHMS = frozenset(
    {
        "lexicographical_topological_sort",
        "topological_generations",
        "topological_sort",
        "bfs_edges",
        "bfs_predecessors",
        "bfs_successors",
        "bfs_layers",
        "dfs_edges",
        "dfs_preorder_nodes",
        "dfs_postorder_nodes",
        "edge_bfs",
        "edge_dfs",
        "all_pairs_shortest_path",
        "all_pairs_shortest_path_length",
        "all_pairs_dijkstra",
        "all_pairs_dijkstra_path",
        "all_pairs_dijkstra_path_length",
        "all_pairs_bellman_ford_path",
        "all_pairs_bellman_ford_path_length",
        "all_simple_paths",
        "all_simple_edge_paths",
        "shortest_simple_paths",
        "single_source_all_shortest_paths",
        "all_pairs_all_shortest_paths",
        "minimum_spanning_edges",
        "maximum_spanning_edges",
        "find_cliques",
        "enumerate_all_cliques",
        "all_triangles",
        "simple_cycles",
        "antichains",
        "bridges",
        "local_bridges",
    }
) | _COMPONENT_ITERATORS | _COMMUNITY_ITERATOR_ALGORITHMS

# User callbacks must receive the original attribute dictionaries and observe
# their own mutations. The ordinary string-weight/eager calls keep using the
# cached native graph. Bind the signature so positional callbacks work too.
_CALLBACK_INPUT_ALGORITHMS = frozenset(
    {
        "bfs_tree",
        "dfs_tree",
        "dfs_predecessors",
        "dfs_successors",
        "shortest_path",
        "shortest_path_length",
        "all_shortest_paths",
        "average_shortest_path_length",
        "average_degree_connectivity",
        "average_neighbor_degree",
        "transitive_closure_dag",
        "number_of_spanning_trees",
        "quotient_graph",
        "greedy_modularity_communities",
        "minimum_spanning_tree",
        "maximum_spanning_tree",
        "greedy_color",
        "eccentricity",
        "diameter",
        "radius",
        "center",
        "periphery",
        "barycenter",
        "closeness_centrality",
        "harmonic_centrality",
        "group_betweenness_centrality",
        "group_closeness_centrality",
        "constraint",
        "local_constraint",
        "effective_size",
        "wiener_index",
        "closeness_vitality",
        "eigenvector_centrality",
        "katz_centrality",
        "betweenness_centrality",
        "edge_betweenness_centrality",
        "pagerank",
        "maximum_flow",
        "maximum_flow_value",
        "minimum_cut",
        "minimum_cut_value",
        "stoer_wagner",
        "capacity_scaling",
        "cost_of_flow",
        "flow_hierarchy",
        "max_flow_min_cost",
        "min_cost_flow",
        "min_cost_flow_cost",
        "network_simplex",
        "node_connectivity",
        "edge_connectivity",
        "minimum_node_cut",
        "minimum_edge_cut",
        "all_pairs_node_connectivity",
        "average_node_connectivity",
        "gomory_hu_tree",
        "dijkstra_path",
        "dijkstra_path_length",
        "floyd_warshall",
        "floyd_warshall_predecessor_and_distance",
        "bellman_ford_path",
        "bellman_ford_path_length",
        "bellman_ford_predecessor_and_distance",
        "goldberg_radzik",
        "johnson",
        "find_negative_cycle",
        "negative_edge_cycle",
        "single_source_dijkstra",
        "single_source_dijkstra_path",
        "single_source_dijkstra_path_length",
        "single_source_bellman_ford",
        "single_source_bellman_ford_path",
        "single_source_bellman_ford_path_length",
        "multi_source_dijkstra",
        "multi_source_dijkstra_path",
        "multi_source_dijkstra_path_length",
        "dijkstra_predecessor_and_distance",
        "bidirectional_dijkstra",
        "astar_path",
        "astar_path_length",
    }
) | (
    _BIPARTITE_MATCHING_ALGORITHMS
    | _BIPARTITE_PROJECTION_ALGORITHMS
    | _SUBSET_BETWEENNESS_INPUT_ALGORITHMS
    | _RESIDUAL_FLOW_ALGORITHMS
)
_LIVE_CALLBACK_PARAMETERS = (
    "sort_neighbors", "weight", "distance", "heuristic", "key", "flow_func"
)
_SPECTRAL_INPUT_ALGORITHMS = frozenset({"eigenvector_centrality", "katz_centrality"})
_FLOW_SOLVER_INPUT_ALGORITHMS = frozenset(
    {"maximum_flow", "maximum_flow_value", "minimum_cut", "minimum_cut_value"}
)
_MULTI_SOURCE_DIJKSTRA_ALGORITHMS = frozenset(
    {"multi_source_dijkstra", "multi_source_dijkstra_path", "multi_source_dijkstra_path_length"}
)
_DIJKSTRA_INPUT_ALGORITHMS = _MULTI_SOURCE_DIJKSTRA_ALGORITHMS | {
    "dijkstra_predecessor_and_distance", "bidirectional_dijkstra"
}
_WEIGHTED_PATH_INPUT_ALGORITHMS = _DIJKSTRA_INPUT_ALGORITHMS | {
    "dijkstra_path", "dijkstra_path_length",
    "single_source_dijkstra", "single_source_dijkstra_path", "single_source_dijkstra_path_length",
    "bellman_ford_path", "bellman_ford_path_length",
    "single_source_bellman_ford", "single_source_bellman_ford_path", "single_source_bellman_ford_path_length",
    "shortest_path", "shortest_path_length", "all_shortest_paths",
    "astar_path", "astar_path_length",
}
_FLOW_INPUT_ALGORITHMS = frozenset(
    {
        "capacity_scaling", "cost_of_flow", "flow_hierarchy", "max_flow_min_cost",
        "min_cost_flow", "min_cost_flow_cost", "network_simplex",
    }
)
_CONNECTIVITY_INPUT_ALGORITHMS = frozenset(
    {"node_connectivity", "edge_connectivity", "minimum_node_cut", "minimum_edge_cut"}
)
_STRUCTURAL_HOLES_INPUT_ALGORITHMS = frozenset(
    {"constraint", "local_constraint", "effective_size"}
)
_PROVIDER_INPUT_ALGORITHMS = (
    _SPECTRAL_INPUT_ALGORITHMS | _FLOW_INPUT_ALGORITHMS | _CONNECTIVITY_INPUT_ALGORITHMS
    | _STRUCTURAL_HOLES_INPUT_ALGORITHMS
    | _FLOW_SOLVER_INPUT_ALGORITHMS
    | _RESIDUAL_FLOW_ALGORITHMS
    | _COMMUNITY_ITERATOR_ALGORITHMS
    | _WEIGHTED_PATH_INPUT_ALGORITHMS
    | _BETWEENNESS_INPUT_ALGORITHMS
    | _SUBSET_BETWEENNESS_INPUT_ALGORITHMS
    | _CONNECTIVITY_BATCH_INPUT_ALGORITHMS
    | _BIPARTITE_MATCHING_ALGORITHMS
    | _BIPARTITE_PROJECTION_ALGORITHMS
    | {
        "johnson", "quotient_graph", "pagerank", "greedy_modularity_communities",
        "greedy_color",
        "floyd_warshall", "floyd_warshall_predecessor_and_distance",
        "bellman_ford_predecessor_and_distance", "goldberg_radzik",
        "harmonic_centrality", "average_shortest_path_length",
        "average_degree_connectivity", "average_neighbor_degree",
        "group_betweenness_centrality", "group_closeness_centrality",
        "minimum_spanning_tree", "maximum_spanning_tree",
        "stoer_wagner", "transitive_closure_dag", "number_of_spanning_trees",
    }
)
_PROVIDER_CALL_INPUTS = ContextVar("franken_networkx_provider_inputs", default=None)


def _primary_graph_parameter(name):
    """Use the public graph parameter when binding or restoring an input."""
    if name in _BIPARTITE_PROJECTION_ALGORITHMS:
        return "B"
    return "flowG" if name in _FLOW_SOLVER_INPUT_ALGORITHMS else "G"


def _provider_dispatch_uses_original_graph(name, graph, arguments):
    """Preserve providers only on routes that read the caller's graph protocol."""
    if name in _BIPARTITE_PROJECTION_ALGORITHMS:
        # Projection preserves graph and node metadata and can invoke a
        # weight function with B itself. Keep these providers intact even
        # when a previous query populated the conversion cache.
        return True
    if name in _RESIDUAL_FLOW_ALGORITHMS:
        # The owned solvers validate G before constructing a residual. A
        # supplied residual avoids input topology reads entirely; otherwise
        # the builder must observe G's original node and edge providers.
        return True
    if name == "transitive_closure_dag":
        # Ordering and copy providers own the closure's snapshot boundary.
        # A cached conversion loses copy hooks and changes later graph reads.
        return True
    if name == "number_of_spanning_trees":
        # Matrix construction reads the caller's edge providers and literal
        # attribute keys, including None. Conversion can discard that state.
        return True
    if name in {"group_betweenness_centrality", "group_closeness_centrality"}:
        # Resolving groups can mutate the graph before searches begin. The
        # owned entry points also retain live weights and admit their native
        # routes themselves. Keep these boundaries even after cached queries.
        return True
    if name in {"minimum_spanning_tree", "maximum_spanning_tree"}:
        # Eager tree wrappers must still inspect the caller's rows and
        # metadata, including when a prior algorithm cached a conversion.
        return fnx._spanning_uses_live_python_rows(
            graph, arguments.get("weight", "weight"), copy_attributes=True
        )
    if name == "stoer_wagner":
        # The algorithm snapshots weights once, then invokes the selected
        # heap. Conversion beforehand can consume a weight provider or read
        # stale cached attributes, changing both the cut and callback effects.
        return True
    if name in _BIPARTITE_MATCHING_ALGORITHMS:
        return _bipartite_matching_dispatch_uses_live_providers(name, graph, arguments)
    if name in {"average_degree_connectivity", "average_neighbor_degree"}:
        return _degree_connectivity_dispatch_uses_live_providers(graph, arguments)
    if name in {"bellman_ford_predecessor_and_distance", "goldberg_radzik"}:
        # Their owned relaxations read live edge dictionaries, and Bellman-Ford
        # evaluates the heuristic protocol during relaxation. Preserve those
        # inputs before conversion, including when another query cached one.
        return True
    if name == "harmonic_centrality":
        # Resolving node selectors can mutate the graph. Inspect presence only;
        # the algorithm owns their truth, membership, and iteration protocols.
        return arguments.get("nbunch") is not None or arguments.get("sources") is not None
    if name in _BETWEENNESS_INPUT_ALGORITHMS:
        return fnx._betweenness_uses_live_python_rows(
            graph, arguments.get("weight"), arguments.get("seed"), arguments.get("k")
        )
    if name in _SUBSET_BETWEENNESS_INPUT_ALGORITHMS:
        return fnx._subset_betweenness_uses_live_python_rows(
            graph, arguments["sources"], arguments["targets"], arguments.get("weight")
        )
    if name in _CONNECTIVITY_BATCH_INPUT_ALGORITHMS:
        # Node iterables and capacity/flow providers can change later pairs
        # or cuts. The owned algorithms choose their native route themselves.
        return True
    if name in _FLOW_INPUT_ALGORITHMS:
        return True
    if name in _COMMUNITY_ITERATOR_ALGORITHMS:
        # Random sources, clique iterables and edge-selection callbacks can
        # mutate inputs when iteration advances. Keep those reads on the
        # caller and invalidate conversions around every resume and close.
        return True
    if name in _WEIGHTED_PATH_INPUT_ALGORITHMS:
        if (
            name in _MULTI_SOURCE_DIJKSTRA_ALGORITHMS
            and fnx._dijkstra_sources_use_live_graph(arguments["sources"])
        ):
            # Inspect only the source collection's admissible types here.
            # Truth testing or materializing a user iterable can mutate G.
            return True
        weight = arguments.get("weight", "weight")
        return (
            type(weight) is not str
            or not fnx._dijkstra_cutoff_uses_native_comparisons(arguments.get("cutoff"))
            or fnx._weighted_query_uses_live_python_rows(graph, weight)
        )
    if name in _FLOW_SOLVER_INPUT_ALGORITHMS:
        # Explicit solvers own validation and residual reuse. Their writes
        # must reach the caller, including when conversion is already cached.
        # Default solvers also need original views and capacity providers;
        # only ordinary concrete storage may use a converted native graph.
        return (
            arguments.get("flow_func") is not None
            or bool(arguments.get("kwargs"))
            or fnx._flow_uses_live_python_rows(graph, arguments.get("capacity", "capacity"))
        )
    if name == "johnson":
        return _johnson_dispatch_uses_live_providers(graph, arguments.get("weight"))
    if name == "quotient_graph":
        # Block attributes contain live induced views of the original graph.
        # Node and edge providers can also mutate later block computations.
        return True
    if name == "greedy_modularity_communities":
        # The owned merge iterator reads live weight and resolution providers;
        # conversion would detach those reads from the caller's graph.
        return True
    if name == "greedy_color":
        return _coloring_dispatch_uses_live_providers(graph, arguments)
    if name == "pagerank":
        return _pagerank_dispatch_uses_live_providers(graph, arguments)
    if name in {"floyd_warshall", "floyd_warshall_predecessor_and_distance"}:
        # Owned dictionary and matrix routes already admit the original
        # graph. Conversion can discard edge readers and their live writes.
        return True
    if name == "average_shortest_path_length":
        # Floyd-Warshall already admits live edge readers. Explicit weighted
        # methods also accept non-string attribute keys, including None.
        method = arguments.get("method")
        weight = arguments.get("weight")
        return (
            method in ("floyd-warshall", "floyd-warshall-numpy")
            or (
                method != "unweighted"
                and (weight is not None or method in ("dijkstra", "bellman-ford"))
                and (
                    any(name in vars(graph) for name in (
                        "is_directed", "is_multigraph", "__iter__", "__len__",
                        "number_of_nodes", "number_of_edges", "neighbors", "adjacency",
                    ))
                    or _johnson_dispatch_uses_live_providers(graph, weight)
                )
            )
        )
    if name in _STRUCTURAL_HOLES_INPUT_ALGORITHMS:
        # A requested-node iterator or edge-data provider can change later
        # ego networks. The owned scalar and sparse routes select their own
        # read boundary; dispatch must not replace it with a cached graph.
        return True
    if name in _CONNECTIVITY_INPUT_ALGORITHMS:
        # A solver can read or mutate the original graph while the algorithm
        # constructs its auxiliary or selects later source/target pairs.
        # Cutoff numeric protocols have the same observable boundary.
        return arguments.get("flow_func") is not None or (
            name == "edge_connectivity" and arguments.get("cutoff") is not None
        )
    return name in _SPECTRAL_INPUT_ALGORITHMS and _spectral_dispatch_uses_live_providers(
        name, graph, arguments
    )


def _bipartite_matching_dispatch_uses_live_providers(name, graph, arguments):
    """Keep partition and matching providers on the graph they can change.

    The owned Eppstein, vertex-cover and assignment routines already read the
    supplied graph directly. Hopcroft--Karp can convert plain storage for its
    native kernel, but admission must not consume a partition iterable or
    flatten an observable adjacency provider, even on a conversion-cache hit.
    """
    import networkx as nx

    if name != "hopcroft_karp_matching" or type(graph) is not nx.Graph:
        return True
    top_nodes = arguments.get("top_nodes")
    if top_nodes is not None and not fnx.bipartite._matching_plain_partition(top_nodes):
        return True
    storage = vars(graph)
    if "_graph" in storage or any(
        name in storage for name in (
            "is_directed", "is_multigraph", "number_of_nodes", "number_of_edges",
            "nbunch_iter", "neighbors", "adjacency", "get_edge_data",
            "__iter__", "__getitem__", "__len__", "__contains__",
        )
    ):
        return True
    nodes = storage.get("_node")
    adjacency = storage.get("_adj")
    plain_keys = (str, int, float, bool)
    if type(nodes) is not dict or type(adjacency) is not dict:
        return True
    if any(type(node) not in plain_keys for node in nodes):
        return True
    if any(type(node) not in plain_keys for node in adjacency):
        return True
    if nodes.keys() != adjacency.keys():
        return True
    representatives = {node: node for node in nodes}
    same_label = fnx.bipartite._matching_same_node_representation
    if any(not same_label(representatives[node], node) for node in adjacency):
        return True
    if top_nodes is not None and any(
        node not in representatives or not same_label(representatives[node], node)
        for node in top_nodes
    ):
        return True
    for row in adjacency.values():
        if type(row) is not dict or any(
            type(neighbor) not in plain_keys or neighbor not in nodes or type(attrs) is not dict
            for neighbor, attrs in row.items()
        ):
            return True
        if any(not same_label(representatives[neighbor], neighbor) for neighbor in row):
            return True
    if any(
        adjacency[neighbor].get(node) is not attrs
        for node, row in adjacency.items() for neighbor, attrs in row.items()
    ):
        return True
    if "adj" in storage:
        view = storage["adj"]
        if type(view) is not nx.classes.coreviews.AdjacencyView or view._atlas is not adjacency:
            return True
    if "nodes" in storage:
        view = storage["nodes"]
        if type(view) is not nx.classes.reportviews.NodeView or view._nodes is not nodes:
            return True
    if "edges" in storage:
        view = storage["edges"]
        if (
            type(view) is not nx.classes.reportviews.EdgeView
            or view._graph is not graph
            or view._adjdict is not adjacency
        ):
            return True
    return False


def _coloring_dispatch_uses_live_providers(graph, arguments):
    """Keep coloring callbacks and observable graph providers on their source.

    Canonical deterministic strategies can reuse a plain native conversion.
    Callable strategies receive the original graph plus the result dictionary
    as each color is assigned. Random and interchange paths retain their own
    input boundary too. Admission must not consume any of these providers.
    """
    import networkx as nx

    strategy = arguments.get("strategy", "largest_first")
    strategies = fnx.coloring.STRATEGIES
    if (
        type(strategy) is not str
        or strategy == "random_sequential"
        or arguments.get("interchange", False) is not False
        or type(strategies) is not dict
        or any(type(key) is not str for key in strategies)
    ):
        return True
    strategy_name = "strategy_saturation_largest_first" if strategy == "DSATUR" else f"strategy_{strategy}"
    canonical = fnx.coloring._FNX_STRATEGY_OVERRIDES.get(strategy_name)
    if canonical is None or strategies.get(strategy) is not canonical:
        return True
    if any(
        getattr(fnx.coloring, name) is not function
        for name, function in fnx.coloring._FNX_STRATEGY_OVERRIDES.items()
        if name.startswith("strategy_")
    ):
        return True
    if type(graph) not in (nx.Graph, nx.DiGraph):
        return True
    storage = vars(graph)
    if "_graph" in storage or any(
        name in storage for name in (
            "is_directed", "is_multigraph", "number_of_nodes", "number_of_edges",
            "nbunch_iter", "neighbors", "adjacency", "get_edge_data", "copy", "subgraph",
            "__iter__", "__getitem__", "__len__", "__contains__",
        )
    ):
        return True
    nodes = storage.get("_node")
    adjacency = storage.get("_adj")
    directed = type(graph) is nx.DiGraph
    predecessors = storage.get("_pred") if directed else adjacency
    if (
        type(nodes) is not dict
        or type(adjacency) is not dict
        or type(predecessors) is not dict
        or type(graph.graph) is not dict
        or (directed and storage.get("_succ") is not adjacency)
        or any(type(node) not in (str, int, float, bool) for node in nodes)
        or any(type(attrs) is not dict for attrs in nodes.values())
    ):
        return True
    for rows in (adjacency, predecessors):
        if any(type(node) not in (str, int, float, bool) for node in rows):
            return True
        if nodes.keys() != rows.keys():
            return True
        for row in rows.values():
            if type(row) is not dict or any(
                type(neighbor) not in (str, int, float, bool)
                or neighbor not in nodes
                or type(attrs) is not dict
                for neighbor, attrs in row.items()
            ):
                return True
    for node, row in adjacency.items():
        if any(predecessors[neighbor].get(node) is not attrs for neighbor, attrs in row.items()):
            return True
    if directed and any(
        adjacency[neighbor].get(node) is not attrs
        for node, row in predecessors.items()
        for neighbor, attrs in row.items()
    ):
        return True
    for name, rows in (("adj", adjacency), ("succ", adjacency), ("pred", predecessors)):
        if name in storage:
            view = storage[name]
            if type(view) is not nx.classes.coreviews.AdjacencyView or view._atlas is not rows:
                return True
    if "nodes" in storage:
        view = storage["nodes"]
        if type(view) is not nx.classes.reportviews.NodeView or view._nodes is not nodes:
            return True
    if "edges" in storage:
        view = storage["edges"]
        edge_type = nx.classes.reportviews.OutEdgeView if directed else nx.classes.reportviews.EdgeView
        if type(view) is not edge_type or view._graph is not graph or view._adjdict is not adjacency:
            return True
    if "degree" in storage:
        degree = storage["degree"]
        degree_type = nx.classes.reportviews.DiDegreeView if directed else nx.classes.reportviews.DegreeView
        if (
            type(degree) is not degree_type
            or degree._graph is not graph
            or degree._succ is not adjacency
            or degree._pred is not predecessors
            or degree._nodes is not adjacency
            or degree._weight is not None
        ):
            return True
    return False


def _pagerank_dispatch_uses_live_providers(graph, arguments):
    """Inspect plain inputs without consuming PageRank's edge/vector providers."""
    import networkx as nx

    if type(graph) not in (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph):
        return True
    storage = vars(graph)
    if (
        "_graph" in storage
        or any(name in storage for name in (
            "is_directed", "is_multigraph", "number_of_nodes", "number_of_edges",
            "nbunch_iter", "subgraph",
        ))
        or type(graph._node) is not dict
        or type(graph._adj) is not dict
    ):
        return True
    if type(graph.graph) is not dict or any(
        type(attrs) is not dict for attrs in graph._node.values()
    ):
        # Matrix construction does not read graph or node metadata. Preserve
        # custom mappings here so conversion cannot copy or invoke them.
        return True
    if "edges" in storage:
        edge_view_type = {
            nx.Graph: nx.classes.reportviews.EdgeView,
            nx.DiGraph: nx.classes.reportviews.OutEdgeView,
            nx.MultiGraph: nx.classes.reportviews.MultiEdgeView,
            nx.MultiDiGraph: nx.classes.reportviews.OutMultiEdgeView,
        }[type(graph)]
        view = storage["edges"]
        if type(view) is not edge_view_type or view._graph is not graph:
            return True
    if "nodes" in storage:
        view = storage["nodes"]
        if type(view) is not nx.classes.reportviews.NodeView or view._nodes is not graph._node:
            return True
    weight = arguments.get("weight", "weight")
    if weight is not None and type(weight) is not str:
        return True
    if type(arguments.get("max_iter", 100)) not in (int, bool):
        return True
    for parameter in ("alpha", "tol"):
        if type(arguments[parameter]) not in (int, float, bool):
            return True
    plain_keys = (str, int, float, bool, type(None))
    if any(type(node) not in plain_keys for node in graph._node):
        return True
    for parameter in ("personalization", "nstart", "dangling"):
        vector = arguments.get(parameter)
        if vector is None:
            continue
        if type(vector) is not dict or any(
            type(node) not in plain_keys or type(value) not in (int, float, bool)
            for node, value in vector.items()
        ):
            return True
    multi = graph.is_multigraph()
    for row in graph._adj.values():
        if type(row) is not dict:
            return True
        for data in row.values():
            if type(data) is not dict:
                return True
            for attrs in data.values() if multi else (data,):
                if type(attrs) is not dict or any(type(key) not in plain_keys for key in attrs):
                    return True
                # A None conversion hint drops all edge attributes. The
                # sparse algorithm nevertheless reads a real None key.
                if weight is None and None in attrs:
                    return True
                if type(attrs.get(weight, 1)) not in (int, float, bool):
                    return True
    return False


def _degree_connectivity_dispatch_uses_live_providers(graph, arguments):
    """Keep observable degree, selector and weight providers on their owner.

    Ordinary Graph/DiGraph dictionaries and builtin selectors can retain the
    cached native conversion. Check types before consuming an iterable or
    reading a custom mapping: those actions belong to the algorithm itself.
    """
    import networkx as nx
    from networkx.classes import coreviews, reportviews

    plain_keys = (str, int, float, bool, bytes, type(None))
    nodes = arguments.get("nodes")
    if nodes is not None and type(nodes) not in plain_keys:
        if type(nodes) is range:
            pass
        elif type(nodes) in (list, tuple, set, frozenset):
            if any(type(node) not in plain_keys for node in nodes):
                return True
        else:
            return True
    if any(type(arguments.get(name, "in+out")) is not str for name in ("source", "target")):
        return True
    if type(graph) not in (nx.Graph, nx.DiGraph):
        return True
    storage = vars(graph)
    if "_graph" in storage or any(name in storage for name in (
        "is_directed", "is_multigraph", "neighbors", "predecessors", "successors",
        "nbunch_iter", "__iter__", "__getitem__", "__len__", "number_of_nodes",
    )):
        return True

    directed = type(graph) is nx.DiGraph
    degree_types = {
        "degree": reportviews.DiDegreeView if directed else reportviews.DegreeView,
    }
    if directed:
        degree_types.update(in_degree=reportviews.InDegreeView, out_degree=reportviews.OutDegreeView)
    for name, view_type in degree_types.items():
        if name in storage and (
            type(storage[name]) is not view_type or storage[name]._graph is not graph
        ):
            return True
    if "nodes" in storage and (
        type(storage["nodes"]) is not reportviews.NodeView
        or storage["nodes"]._nodes is not graph._node
    ):
        return True
    for name, rows in (("adj", graph._adj),) + (
        (("succ", graph._succ), ("pred", graph._pred)) if directed else ()
    ):
        if name in storage and (
            type(storage[name]) is not coreviews.AdjacencyView
            or storage[name]._atlas is not rows
        ):
            return True

    if type(graph._node) is not dict or type(graph._adj) is not dict:
        return True
    if any(type(node) not in plain_keys for node in graph._node):
        return True
    if any(type(node) not in plain_keys for node in graph._adj):
        return True
    if list(graph._adj) != list(graph._node):
        return True
    reverse = graph._pred if directed else graph._adj
    if type(reverse) is not dict or any(type(node) not in plain_keys for node in reverse):
        return True
    if list(reverse) != list(graph._node):
        return True
    if any(type(row) is not dict for row in reverse.values()):
        return True
    for node, row in graph._adj.items():
        if type(row) is not dict:
            return True
        for neighbor, attrs in row.items():
            if type(neighbor) not in plain_keys or type(attrs) is not dict:
                return True
            if neighbor not in reverse or reverse[neighbor].get(node) is not attrs:
                # Assigned asymmetric rows cannot be represented by a native
                # graph with one shared edge dictionary or coherent pred/succ.
                return True
    if directed and sum(map(len, reverse.values())) != sum(map(len, graph._adj.values())):
        return True

    weight = arguments.get("weight")
    return weight is not None and _johnson_dispatch_uses_live_providers(graph, weight)


def _johnson_dispatch_uses_live_providers(graph, weight):
    """Keep Johnson callbacks and exact numeric protocols on the source graph."""
    from math import isfinite
    import networkx as nx

    if type(weight) is not str:
        return True
    if type(graph) not in (nx.Graph, nx.DiGraph) or "_graph" in vars(graph):
        return True
    if type(graph._node) is not dict or type(graph._adj) is not dict:
        return True
    if any(type(node) not in (str, int, float, bool) for node in graph._node):
        return True
    for row in graph._adj.values():
        if type(row) is not dict:
            return True
        for attrs in row.values():
            if type(attrs) is not dict:
                return True
            if any(type(key) not in (str, int, float, bool, type(None)) for key in attrs):
                return True
            # Empty strings are literal selectors too. Inspect only plain
            # dictionaries so deciding whether to convert invokes no providers.
            value = attrs.get(weight, 1)
            if type(value) not in (int, float, bool):
                return True
            if type(value) is float and not isfinite(value):
                return True
    return False


def _spectral_dispatch_uses_live_providers(name, graph, arguments):
    """Recover input providers that can affect an iterative ranking query.

    Ordinary NetworkX dictionaries and numeric vectors can reuse a cached
    native conversion. Custom vector, graph or numeric protocols must act on
    the original graph, even if another algorithm populated that cache first.
    Inspect types before reading a provider so admission has no side effects.
    """
    import networkx as nx

    if type(graph) not in (nx.Graph, nx.DiGraph) or "_graph" in vars(graph):
        return True
    if type(graph._node) is not dict or type(graph._adj) is not dict:
        return True
    for parameter in ("max_iter", "tol", "alpha", "normalized"):
        if parameter in arguments and type(arguments[parameter]) not in (int, float, bool):
            return True
    for parameter in ("nstart", "beta"):
        value = arguments.get(parameter)
        if value is None or type(value) in (int, float, bool):
            continue
        if type(value) is not dict or any(
            type(item) not in (int, float, bool) for item in value.values()
        ):
            return True
    weight = arguments.get("weight")
    if weight is not None and type(weight) is not str:
        return True
    reads_weights = name == "katz_centrality" or bool(weight)
    for row in graph._adj.values():
        if type(row) is not dict:
            return True
        if reads_weights:
            for attrs in row.values():
                if type(attrs) is not dict:
                    return True
                if any(type(key) not in (str, int, float, bool, type(None)) for key in attrs):
                    return True
                # NetworkX's weight=None conversion hint drops edge attrs,
                # but iterative Katz still looks up the literal None key.
                if weight is None and None in attrs:
                    return True
                if type(attrs.get(weight, 1)) not in (int, float, bool):
                    return True
    return False

# These APIs have two independently observable graph inputs. A converted
# graph can also be supplied explicitly as the auxiliary, so its weak source
# marker cannot identify both arguments' owners. NetworkX calls can_run with
# original arguments, then looks up the callable before converting anything.
# Capture that single invocation in the returned wrapper; nested conversions
# and other execution contexts cannot replace its original inputs.
_DISJOINT_ALGORITHMS = frozenset({"edge_disjoint_paths", "node_disjoint_paths"})
_DISJOINT_CALL_INPUTS = ContextVar("franken_networkx_disjoint_inputs", default=None)


def _refresh_dispatch_source(graph):
    """Associate cached conversions with the graph used for this invocation."""
    if isinstance(graph, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)):
        # An explicitly supplied native graph is an independent input, even if
        # it was originally produced by convert_from_nx and then modified.
        vars(graph).pop("_fnx_networkx_source", None)
        return
    cache = getattr(graph, "__networkx_cache__", None)
    if cache is None:
        return
    conversions = cache.get("backends", {}).get("franken_networkx", {})
    for converted in conversions.values():
        if isinstance(converted, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)):
            # Graph copying/pickling deliberately drops native private fields.
            # can_run receives the caller's graph even on conversion-cache hits.
            converted._fnx_networkx_source = weakref.ref(graph)


def _clear_callback_conversions(graph):
    cache = getattr(graph, "__networkx_cache__", None)
    if cache is not None:
        # A callback may change attributes in place, without a graph mutator
        # clearing conversions. Discard every backend's potentially stale copy.
        cache.pop("backends", None)


def _discard_component_passthrough(graph):
    """Do not let a live-input dispatch cache a foreign graph as native."""
    cache = getattr(graph, "__networkx_cache__", None)
    if cache is None:
        return
    conversions = cache.get("backends", {}).get("franken_networkx", {})
    for key, converted in tuple(conversions.items()):
        if converted is graph:
            del conversions[key]


def _iterate_callback_result(iterator, graph):
    """Invalidate conversions after each lazy callback-driven advancement."""
    try:
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                return
            finally:
                _clear_callback_conversions(graph)
            yield item
    finally:
        iterator.close()
        _clear_callback_conversions(graph)


def _call_disjoint_with_original_inputs(fn, signature, inputs, args, kwargs):
    bound = signature.bind(*args, **kwargs)
    originals = []
    for parameter, source_ref in inputs:
        source = source_ref()
        if source is None or not _is_dispatch_conversion(
            bound.arguments.get(parameter), source
        ):
            # A standalone backend call may follow an unrelated can_run
            # probe. Never substitute that probe's graph into a new call.
            return fn(*args, **kwargs)
        originals.append((parameter, source))
    graphs = []
    for parameter, source in originals:
        bound.arguments[parameter] = source
        if not any(source is graph for graph in graphs):
            graphs.append(source)
    if not callable(bound.arguments.get("flow_func")):
        return fn(*bound.args, **bound.kwargs)

    for graph in graphs:
        _clear_callback_conversions(graph)
    try:
        result = fn(*bound.args, **bound.kwargs)
    finally:
        for graph in graphs:
            _clear_callback_conversions(graph)
    if inspect.isgenerator(result):
        for graph in graphs:
            result = _iterate_callback_result(result, graph)
    return result


def _is_dispatch_conversion(graph, source):
    if graph is source:
        return True
    source_ref = getattr(graph, "__dict__", {}).get("_fnx_networkx_source")
    if isinstance(source_ref, weakref.ReferenceType) and source_ref() is source:
        return True
    cache = getattr(source, "__networkx_cache__", None)
    if cache is None:
        return False
    # Deepcopy and pickle discard private fields on native cached graphs.
    # Their source's cache still establishes the conversion's owner.
    conversions = cache.get("backends", {}).get("franken_networkx", {})
    return any(graph is converted for converted in conversions.values())

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
    "johnson": fnx.johnson,
    # Graph transformations
    "quotient_graph": fnx.quotient_graph,
    # Connectivity
    "is_connected": fnx.is_connected,
    "connected_components": fnx.connected_components,
    "number_connected_components": fnx.number_connected_components,
    "node_connectivity": fnx.node_connectivity,
    "minimum_node_cut": fnx.minimum_node_cut,
    "edge_connectivity": fnx.edge_connectivity,
    "minimum_edge_cut": fnx.minimum_edge_cut,
    "all_pairs_node_connectivity": fnx.all_pairs_node_connectivity,
    "average_node_connectivity": fnx.average_node_connectivity,
    "gomory_hu_tree": fnx.gomory_hu_tree,
    "edge_disjoint_paths": fnx.edge_disjoint_paths,
    "node_disjoint_paths": fnx.node_disjoint_paths,
    "articulation_points": fnx.articulation_points,
    "bridges": fnx.bridges,
    "local_bridges": fnx.local_bridges,
    # Centrality
    "degree_centrality": fnx.degree_centrality,
    "closeness_centrality": fnx.closeness_centrality,
    "harmonic_centrality": fnx.harmonic_centrality,
    "constraint": fnx.constraint,
    "local_constraint": fnx.local_constraint,
    "effective_size": fnx.effective_size,
    "katz_centrality": fnx.katz_centrality,
    "betweenness_centrality": fnx.betweenness_centrality,
    "edge_betweenness_centrality": fnx.edge_betweenness_centrality,
    "betweenness_centrality_subset": fnx.betweenness_centrality_subset,
    "edge_betweenness_centrality_subset": fnx.edge_betweenness_centrality_subset,
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
    # NetworkX's maximum_matching is an alias of hopcroft_karp_matching and
    # dispatches under that canonical name.
    "hopcroft_karp_matching": fnx.bipartite.hopcroft_karp_matching,
    "eppstein_matching": fnx.bipartite.eppstein_matching,
    "to_vertex_cover": fnx.bipartite.to_vertex_cover,
    "minimum_weight_full_matching": fnx.bipartite.minimum_weight_full_matching,
    # Bipartite projections
    "projected_graph": fnx.bipartite.projected_graph,
    "weighted_projected_graph": fnx.bipartite.weighted_projected_graph,
    "collaboration_weighted_projected_graph": fnx.bipartite.collaboration_weighted_projected_graph,
    "generic_weighted_projected_graph": fnx.bipartite.generic_weighted_projected_graph,
    "overlap_weighted_projected_graph": fnx.bipartite.overlap_weighted_projected_graph,
    # Flow
    "edmonds_karp": fnx.flow.edmonds_karp,
    "dinitz": fnx.flow.dinitz,
    "shortest_augmenting_path": fnx.flow.shortest_augmenting_path,
    "preflow_push": fnx.flow.preflow_push,
    "boykov_kolmogorov": fnx.flow.boykov_kolmogorov,
    "maximum_flow": fnx.maximum_flow,
    "maximum_flow_value": fnx.maximum_flow_value,
    "capacity_scaling": fnx.capacity_scaling,
    "cost_of_flow": fnx._cost_of_flow_backend_impl,
    "flow_hierarchy": fnx.flow_hierarchy,
    "max_flow_min_cost": fnx.max_flow_min_cost,
    "min_cost_flow": fnx.min_cost_flow,
    "min_cost_flow_cost": fnx.min_cost_flow_cost,
    "network_simplex": fnx.network_simplex,
    "minimum_cut": fnx.minimum_cut,
    "minimum_cut_value": fnx.minimum_cut_value,
    "stoer_wagner": fnx.stoer_wagner,
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
    "k_core": fnx.k_core,
    "k_shell": fnx.k_shell,
    "k_crust": fnx.k_crust,
    "k_corona": fnx.k_corona,
    "k_truss": fnx.k_truss,
    "onion_layers": fnx.onion_layers,
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
    "all_simple_edge_paths": fnx.all_simple_edge_paths,
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
    "closeness_vitality": fnx.closeness_vitality,
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
    # br-r37-c1-egjfn: ``maximum_independent_set``, ``max_clique`` and
    # ``clique_removal`` are deliberately NOT registered. There is no native
    # kernel behind those names — ``approximation.py`` obtains them from a
    # wildcard re-export of ``networkx.algorithms.approximation``, so
    # registering them would name nx's own ``@_dispatchable`` as this backend's
    # implementation of the same algorithm. Under
    # ``nx.config.backend_priority = ["franken_networkx"]`` that is a pure
    # dispatch cycle with no fnx frame in it, and it recurses until
    # ``RecursionError``. Pinning ``backend="networkx"`` at the call site does
    # not help: nx's own ``max_clique`` body calls ``clique_removal()``
    # unpinned, so the cycle re-forms one frame deeper. Leaving them out lets
    # ``fallback_to_nx`` route both nx and fnx graphs to nx's kernel, which is
    # what the registration was delegating to anyway.
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
    "transitive_closure_dag": fnx.transitive_closure_dag,
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
    # br-r37-c1-81vo1: the native levels; the fallback is pinned to networkx.
    "louvain_partitions": fnx.community.louvain_partitions,
    # br-r37-c1-epic-native-algorithms-1g0lj.3: networkx's CNM loop natively. Its
    # fallback calls networkx with backend="networkx", so this cannot ping-pong.
    "greedy_modularity_communities": fnx.community.greedy_modularity_communities,
    # br-r37-c1-ecua7: registered using the private backend-only impl
    # so ``fnx.community.modularity`` stays AttributeError (matching nx's namespace
    # — nx exposes modularity only at nx.community.modularity).
    "modularity": fnx._modularity_backend_impl,
    # These exports now have owned implementations in community.py. Lazy
    # algorithms retain the caller's graph until their first advancement.
    "label_propagation_communities": fnx.community.label_propagation_communities,
    "asyn_lpa_communities": fnx.community.asyn_lpa_communities,
    "fast_label_propagation_communities": fnx.community.fast_label_propagation_communities,
    "girvan_newman": fnx.community.girvan_newman,
    "k_clique_communities": fnx.community.k_clique_communities,
    "kernighan_lin_bisection": fnx.community.kernighan_lin_bisection,
    "asyn_fluidc": fnx.community.asyn_fluidc,
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
    "dijkstra_predecessor_and_distance": fnx.dijkstra_predecessor_and_distance,
    "bidirectional_dijkstra": fnx.bidirectional_dijkstra,
    "multi_source_dijkstra_path": fnx.multi_source_dijkstra_path,
    "multi_source_dijkstra_path_length": fnx.multi_source_dijkstra_path_length,
    "bellman_ford_path_length": fnx.bellman_ford_path_length,
    "bellman_ford_predecessor_and_distance": fnx.bellman_ford_predecessor_and_distance,
    "goldberg_radzik": fnx.goldberg_radzik,
    "single_source_dijkstra": fnx.single_source_dijkstra,
    "single_source_dijkstra_path": fnx.single_source_dijkstra_path,
    "single_source_dijkstra_path_length": fnx.single_source_dijkstra_path_length,
    "single_source_bellman_ford": fnx.single_source_bellman_ford,
    "single_source_bellman_ford_path": fnx.single_source_bellman_ford_path,
    "single_source_bellman_ford_path_length": fnx.single_source_bellman_ford_path_length,
    "single_target_shortest_path": fnx.single_target_shortest_path,
    "single_target_shortest_path_length": fnx.single_target_shortest_path_length,
    "all_pairs_dijkstra": fnx.all_pairs_dijkstra,
    "all_pairs_dijkstra_path": fnx.all_pairs_dijkstra_path,
    "all_pairs_dijkstra_path_length": fnx.all_pairs_dijkstra_path_length,
    "all_pairs_bellman_ford_path": fnx.all_pairs_bellman_ford_path,
    "all_pairs_bellman_ford_path_length": fnx.all_pairs_bellman_ford_path_length,
    "single_source_all_shortest_paths": fnx.single_source_all_shortest_paths,
    "all_pairs_all_shortest_paths": fnx.all_pairs_all_shortest_paths,
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
    "group_betweenness_centrality": fnx.group_betweenness_centrality,
    "group_closeness_centrality": fnx.group_closeness_centrality,
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


def _hinted_attrs(data, wanted, preserve):
    """networkx's dispatch conversion rule for one node or edge dict."""
    if preserve:
        return dict(data)
    if wanted:
        return {
            attr: data.get(attr, default)
            for attr, default in wanted.items()
            if default is not None or attr in data
        }
    return {}


def _restore_nx_row_order(source, result):
    """Keep every adjacency row when materializing the same graph shape.

    Edge insertion order alone cannot reproduce both successor and
    predecessor rows of a directed graph. Likewise, walking a multigraph's
    edge view changes its reverse adjacency rows. These orders determine
    traversal and shortest-path ties, so restore them before any destination
    row escapes to the caller. Parallel-edge dictionaries are moved intact.

    ``create_using`` may request a different graph kind or an upstream graph;
    those conversions retain their own construction semantics.
    """
    if (
        type(result) not in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)
        or source.is_directed() != result.is_directed()
        or source.is_multigraph() != result.is_multigraph()
    ):
        return
    nodes = list(result)
    if result.is_directed():
        rows = (
            [list(source.succ[node]) for node in nodes],
            [list(source.pred[node]) for node in nodes],
        )
    else:
        rows = ([list(source.adj[node]) for node in nodes],)
    if result.is_multigraph():
        rows = tuple(zip(nodes, side) for side in rows)
    if not result._fnx_set_row_orders(*rows):
        raise RuntimeError("Cannot preserve adjacency order during graph conversion")


def _nx_to_fnx_for_dispatch(
    G, *, edge_attrs, node_attrs, preserve_edge_attrs, preserve_node_attrs, preserve_graph_attrs
):
    """Convert a networkx graph for a dispatched call, carrying only what it needs (sfq4w.2).

    networkx tells ``convert_from_nx`` which attributes the algorithm reads
    (``edge_attrs`` / ``node_attrs`` as {name: default}) or that it keeps them
    all (``preserve_*_attrs``); its own loopback backend converts exactly
    that. Copying every attribute dict regardless was most of the conversion
    toll. The edges of a simple graph come from ``nx_adjacency_edge_batch``,
    the native port of ``_topo_emit_edges_by_adj`` (same order, so every
    node's neighbor order is kept) that builds the ``add_edges_from`` tuples
    in the same pass. Anything but networkx's own four classes (a view, a
    subclass that reinterprets ``_adj`` such as the approximation module's
    ``_AntiGraph``) keeps the full ``_from_nx_graph`` conversion.
    """
    import networkx as nx

    adj = getattr(G, "_adj", None)
    if type(G) not in (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph) or type(adj) is not dict:
        return _nx_to_fnx(G)
    from franken_networkx.readwrite import _empty_like_nx_graph

    result = _empty_like_nx_graph(G)
    if preserve_graph_attrs:
        result.graph.update(G.graph)
    if preserve_node_attrs or node_attrs:
        result.add_nodes_from(
            (n, _hinted_attrs(d, node_attrs, preserve_node_attrs)) for n, d in G._node.items()
        )
    else:
        result.add_nodes_from(G._node)
    if G.is_multigraph():
        result.add_edges_from(
            (u, v, key, _hinted_attrs(d, edge_attrs, preserve_edge_attrs))
            for u, v, key, d in G.edges(keys=True, data=True)
        )
    else:
        result.add_edges_from(
            _native_nx_adjacency_edge_batch(
                adj, G.is_directed(), edge_attrs or None, bool(preserve_edge_attrs)
            )
        )
    _restore_nx_row_order(G, result)
    return result


def _convert_result_to_nx(value):
    """Recursively convert fnx graphs to nx graphs inside common containers.

    Returns non-graph values unchanged. Preserves container type for
    list / tuple / set. For dict, converts values only (keys are left
    alone since graph-typed keys are pathological).
    """
    if isinstance(value, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)):
        return _fnx_to_nx(value)
    # br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.7: rebuild only the
    # exact builtin containers, and only when a graph inside was converted.
    # Subclasses come back as the same object: scipy's dok_array IS a dict
    # and was flattened into a plain one (losing .todense()), namedtuples
    # are tuples. Sets are returned as-is (graphs are not hashable).
    kind = type(value)
    if kind is dict:
        converted = {k: _convert_result_to_nx(v) for k, v in value.items()}
        changed = any(converted[k] is not v for k, v in value.items())
        return converted if changed else value
    if kind is list or kind is tuple:
        converted = [_convert_result_to_nx(v) for v in value]
        if any(c is not v for c, v in zip(converted, value)):
            return kind(converted)
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
    # Assigned _node/_adj/_succ/_pred mappings own the public graph, even
    # when its concrete class still has native bulk methods. Those methods
    # read the old Rust storage and can silently relabel nodes or drop edges.
    native_storage = (
        type(fg) in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)
        and not fnx._has_networkx_private_storage(fg)
    )
    node_view = getattr(fg, "nodes", None)
    if node_view is not None:
        G.add_nodes_from((node, dict(node_view[node])) for node in fg)
    else:
        G.add_nodes_from(fg)
    bulk_row_order = None
    if fg.is_multigraph():
        # br-r37-c1-i5cf1: the previous multigraph path walked AtlasViews per edge
        # (``_topo_emit_edges_by_adj`` + ``fg[u][v]``) and then ``_align_rows``
        # re-walked ``fg.adj`` / ``fg.pred`` per node — O(V*deg) Python-wrapper
        # round-trips that made a multigraph conversion pathologically slow (a
        # 500-node MultiDiGraph ~12s), so EVERY delegated multigraph algorithm was
        # many-x slower than nx (wcc 126x, scc 19x, connected_components 9.9x, ...).
        # Build from the fast NATIVE bulk edge view (``edges(keys=True, data=True)``
        # — node-major adj order, fresh Python-visible attrs) and realign rows from
        # cheap native bulk snapshots: succ/adj from ``adjacency()`` and (directed)
        # ``_pred`` from ``_native_predecessor_keys_bulk`` (fg.pred / edge-insertion
        # order — required so bidirectional-search tie-breaks aren't poisoned, see
        # test_fnx_to_nx_row_parity / br-r37-c1-w7nn3). Edge tuples, parallel-key
        # order, node/graph attrs and every row order stay byte-identical to the
        # old path.
        G.add_edges_from(
            (u, v, key, dict(attrs))
            for u, v, key, attrs in fg.edges(keys=True, data=True)
        )

        def _align_inline(nx_rows, source_rows):
            for x in fg:
                src = source_rows[x]
                row = nx_rows[x]
                if len(row) != len(src) or any(
                    a is not b for a, b in zip(row, src)
                ):
                    nx_rows[x] = {o: row[o] for o in src}

        pred_bulk = (
            getattr(fg, "_native_predecessor_keys_bulk", None)
            if native_storage else None
        )
        if not fg.is_directed() and native_storage:
            _align_inline(G._adj, {n: list(nbrs) for n, nbrs in fg.adjacency()})
            G.graph.update(dict(fg.graph))
            return G
        if pred_bulk is not None:
            _align_inline(G._succ, {n: list(nbrs) for n, nbrs in fg.adjacency()})
            _align_inline(G._pred, {n: preds for n, preds in pred_bulk()})
            G.graph.update(dict(fg.graph))
            return G
        # Private storage and views, or an unavailable native pred reader,
        # keep their logical rows through the generic alignment below.
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
        # The native helper reads Rust ``inner`` adjacency. Views, subclasses,
        # and assigned private storage must use their public rows instead.
        bulk = (
            _native_fnx_to_nx_adjacency(fg)
            if (
                _native_fnx_to_nx_adjacency is not None
                and native_storage
            )
            else None
        )
        if bulk is not None:
            # br-r37-c1-fnx2nx-lazyattr: a freshly batch-built (``add_edges_from``)
            # INT-node graph leaves ``edge_py_attrs`` UNMATERIALIZED while the inner
            # Rust AttrMaps hold the weights, and the bulk read above reads ONLY that
            # lazy mirror -> it SILENTLY DROPS every edge attr, so the converted graph
            # is unweighted and EVERY nx-delegated weighted algorithm (multi_source_
            # dijkstra ...) runs wrong. Detect it precisely: the inner reports edge
            # attrs (``graph_has_any_attrs``) yet the bulk came back with NONE. Only
            # then force the mirror to materialise from the inner (``edges(data=True)``
            # uses the display-key path get_edge_data/dijkstra read correctly) and
            # re-read. The ``any(attrs ...)`` probe EARLY-EXITS on the first non-empty
            # attr, so an already-materialised (normal) graph pays O(1) and the fast
            # path is untouched; attr-less graphs skip the gate entirely.
            if (
                _native_graph_has_any_attrs is not None
                and fg.number_of_edges()
                and _native_graph_has_any_attrs(fg)
                and not any(attrs for _n, _nbrs in bulk for _v, attrs in _nbrs)
            ):
                for _ in fg.edges(data=True):
                    pass
                bulk = _native_fnx_to_nx_adjacency(fg)
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
            # br-r37-c1-fnx2nx-fastemit: emit edges in plain node-major (bulk)
            # order. The previous path rebuilt ``adj_neighbors`` via a per-node
            # ``fg[obj]`` AdjacencyView pass AND ran the ``_topo_emit_edges_by_adj``
            # topological walk solely to make the INITIAL nx adjacency-row order
            # match fg — but ``_align_rows`` below unconditionally reorders every
            # row into fg's exact order (reusing the datadicts via hash-equal
            # lookup), so the emission order is irrelevant. Dropping both (~14ms
            # of a ~30ms / 600-node conversion) makes check_planarity and every
            # cheap-nx-compute delegated function ~2.5x faster. Undirected edges
            # appear in both endpoints' bulk rows; ``seen`` emits each once.
            bulk_row_order = {
                canon_to_obj[node]: [canon_to_obj[nbr] for nbr, _attrs in nbrs]
                for node, nbrs in bulk
            }
            edges_in_order = []
            if directed:
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        edges_in_order.append((onode, canon_to_obj[nbr], dict(attrs)))
            else:
                seen_undirected = set()
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        onbr = canon_to_obj[nbr]
                        pair = frozenset((onode, onbr))
                        if pair in seen_undirected:
                            continue
                        seen_undirected.add(pair)
                        edges_in_order.append((onode, onbr, dict(attrs)))
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
    # br-r37-c1-w7nn3: edge-sequence emission cannot reproduce every row
    # family of the source at once — the succ-major walk fills directed
    # PRED rows in walk order (an nx-native graph's pred rows follow edge
    # insertion; the mismatch made delegated bidirectional searches pick
    # the WRONG tie-break path), and reverse-direction cells take the
    # emitted endpoint object instead of the source's row display object
    # (z6uka overrides for mixed hash-equal keys). Rebuild every adjacency
    # inner dict in the source's row order with the source's row objects.
    # The inner datadicts are REUSED (hash-equal lookup), so nx's
    # _adj/_succ/_pred sharing invariant holds.
    def _align_rows(nx_rows, fg_rows, source_rows=None):
        for x in fg:
            if source_rows is None:
                src = list(fg_rows[x])
            else:
                src = source_rows.get(x)
                if src is None:
                    src = list(fg_rows[x])
            row = nx_rows[x]
            if len(row) != len(src) or any(
                a is not b for a, b in zip(row, src)
            ):
                nx_rows[x] = {o: row[o] for o in src}
        if not native_storage:
            # Assigning only _node can reorder node iteration without
            # reordering _adj/_succ/_pred. Edge iteration follows those
            # outer adjacency rows, independently of the node dictionary.
            order = list(fg_rows)
            if len(nx_rows) != len(order) or any(
                actual is not source for actual, source in zip(nx_rows, order)
            ):
                ordered_rows = [(node, nx_rows[node]) for node in order]
                nx_rows.clear()
                nx_rows.update(ordered_rows)

    if fg.is_directed():
        succ_source_rows = None
        has_succ_overrides = getattr(fg, "_native_has_succ_py_keys", None)
        if (
            bulk_row_order is not None
            and has_succ_overrides is not None
            and not has_succ_overrides()
        ):
            succ_source_rows = bulk_row_order
        _align_rows(G._succ, fg.adj, succ_source_rows)
        _align_rows(G._pred, fg.pred)
    else:
        adj_source_rows = None
        has_adj_overrides = getattr(fg, "_native_has_adj_py_keys", None)
        if (
            bulk_row_order is not None
            and has_adj_overrides is not None
            and not has_adj_overrides()
        ):
            adj_source_rows = bulk_row_order
        _align_rows(G._adj, fg.adj, adj_source_rows)
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
        """Convert a NetworkX graph to a FrankenNetworkX graph.

        Normally cache a native graph: NetworkX keys conversions by attribute
        hints, not algorithm name. Remember the source weakly so lazy and
        callback-driven algorithms can recover it even from a conversion
        cached by another algorithm. A strong reference would create a cycle
        through the source's conversion cache and retain both graphs.

        Live-input iterators pass through without traversing the source. Their
        wrapper removes this temporary cache entry before invoking the owned
        traversal, so unrelated algorithms still receive native conversions.
        """
        pending_provider = _PROVIDER_CALL_INPUTS.get()
        if name in _LIVE_INPUT_ALGORITHMS or (
            pending_provider is not None
            and pending_provider[0] == name
            and pending_provider[1]() is G
        ):
            return G
        converted = _nx_to_fnx_for_dispatch(
            G,
            edge_attrs=edge_attrs,
            node_attrs=node_attrs,
            preserve_edge_attrs=preserve_edge_attrs or preserve_all_attrs,
            preserve_node_attrs=preserve_node_attrs or preserve_all_attrs,
            preserve_graph_attrs=preserve_graph_attrs or preserve_all_attrs,
        )
        if name is not None:
            converted._fnx_networkx_source = weakref.ref(G)
        return converted

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
        if name in _DISJOINT_ALGORITHMS:
            try:
                inputs = tuple(
                    (parameter, weakref.ref(bound.arguments[parameter]))
                    for parameter in ("G", "auxiliary")
                    if bound.arguments.get(parameter) is not None
                )
            except TypeError:
                _DISJOINT_CALL_INPUTS.set(None)
                return False
            _DISJOINT_CALL_INPUTS.set((name, inputs))
        elif name in _LIVE_INPUT_ALGORITHMS or name in _CALLBACK_INPUT_ALGORITHMS:
            graph_parameter = _primary_graph_parameter(name)
            _refresh_dispatch_source(bound.arguments.get(graph_parameter))
            if name in _PROVIDER_INPUT_ALGORITHMS:
                bound.apply_defaults()
                graph = bound.arguments.get(graph_parameter)
                if _provider_dispatch_uses_original_graph(name, graph, bound.arguments):
                    _PROVIDER_CALL_INPUTS.set((name, weakref.ref(graph)))
                else:
                    _PROVIDER_CALL_INPUTS.set(None)
        return True

    @staticmethod
    def should_run(name, args, kwargs):
        """Whether converting a networkx graph for this call pays off (sfq4w.2).

        networkx asks only when the call needs a conversion; declining makes
        networkx run the call itself. For the kernels in
        ``_CONVERT_AFTER_USES`` one conversion costs more than networkx
        running the kernel, so this is ski rental: each declined call adds
        1/k of a conversion's cost to the graph's running total, and the call
        that brings it to one converts. The conversion is then cached on the
        graph (networkx clears that cache, and this total, on every
        mutation), so later calls run at fnx's speed. A cold call is never
        slower than networkx, and total cost stays within twice the best
        choice made in hindsight. Other algorithms convert at once, as does
        any call once a conversion is already cached.
        """
        can_run = BackendInterface.can_run(name, args, kwargs)
        if can_run is not True or name not in _CONVERT_AFTER_USES:
            return can_run
        graph = args[0] if args else kwargs.get(_primary_graph_parameter(name))
        if not hasattr(graph, "__networkx_cache__"):
            return True
        import networkx as nx

        cache = graph.__networkx_cache__
        if cache is None or not nx.config.cache_converted_graphs:
            reason = f"conversion costs more than networkx running {name}, and caching is off"
            log.debug("declining %s: %s", name, reason)
            return reason
        if cache.get("backends", {}).get("franken_networkx"):
            return True
        uses = _CONVERT_AFTER_USES[name]
        rent = cache.get(_RENT_KEY, 0.0) + (1.0 / uses if uses else 0.0)
        if rent >= 1.0:
            log.debug("converting for %s: accumulated rent %.2f", name, rent)
            return True
        cache[_RENT_KEY] = rent
        reason = (
            f"one conversion costs more than networkx running {name}; converting once "
            f"this graph's calls have paid for it ({rent:.2f} of 1.0)"
        )
        log.debug("declining %s: %s", name, reason)
        return reason

    # Make algorithm functions available as attributes for dispatch
    def __getattr__(self, name):
        if name in _SUPPORTED_ALGORITHMS:
            import franken_networkx as fnx
            import functools

            fn = _SUPPORTED_ALGORITHMS[name]
            graph_parameter = _primary_graph_parameter(name)
            live_input = name in _LIVE_INPUT_ALGORITHMS
            callback_signature = (
                inspect.signature(fn)
                if live_input or name in _CALLBACK_INPUT_ALGORITHMS else None
            )
            disjoint_inputs = None
            if name in _DISJOINT_ALGORITHMS:
                pending = _DISJOINT_CALL_INPUTS.get()
                if pending is not None and pending[0] == name:
                    disjoint_inputs = pending[1]
                    disjoint_signature = inspect.signature(fn)

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    if live_input or name in _PROVIDER_INPUT_ALGORITHMS:
                        graph = args[0] if args else kwargs.get(graph_parameter)
                        _discard_component_passthrough(graph)
                    if name in _PROVIDER_INPUT_ALGORITHMS:
                        pending_provider = _PROVIDER_CALL_INPUTS.get()
                        if pending_provider is not None and pending_provider[0] == name:
                            _PROVIDER_CALL_INPUTS.set(None)
                    if disjoint_inputs is not None:
                        # hasattr probes may look up and discard wrappers.
                        # Capture before conversion, but consume only on call.
                        # A nested conversion may already have installed and
                        # consumed another record in this execution context.
                        if _DISJOINT_CALL_INPUTS.get() is pending:
                            _DISJOINT_CALL_INPUTS.set(None)
                        return _call_disjoint_with_original_inputs(
                            fn, disjoint_signature, disjoint_inputs, args, kwargs
                        )
                    source = None
                    has_callbacks = False
                    reads_lazily = live_input
                    if callback_signature is not None:
                        graph = args[0] if args else kwargs.get(graph_parameter)
                        source_ref = getattr(graph, "__dict__", {}).get("_fnx_networkx_source")
                        source = (
                            source_ref() if isinstance(source_ref, weakref.ReferenceType) else None
                        )
                        if (live_input or name in _PROVIDER_INPUT_ALGORITHMS) and not isinstance(
                            graph, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)
                        ):
                            source = graph
                        if source is not None:
                            bound = callback_signature.bind(*args, **kwargs)
                            bound.apply_defaults()
                            has_callbacks = any(
                                callable(bound.arguments.get(parameter))
                                for parameter in _LIVE_CALLBACK_PARAMETERS
                            )
                            uses_live_provider = _provider_dispatch_uses_original_graph(
                                name, source, bound.arguments
                            )
                            # Once the owned algorithm retains its provider,
                            # an extra weighted-route probe is unnecessary.
                            # It may call is_directed before the algorithm's
                            # edge snapshot and move a user's live mutation.
                            uses_live_weight = not (has_callbacks or uses_live_provider) and any(
                                parameter in bound.arguments
                                and fnx._weighted_query_uses_live_python_rows(
                                    source, bound.arguments[parameter]
                                )
                                for parameter in ("weight", "distance")
                            )
                            has_callbacks = has_callbacks or uses_live_provider or uses_live_weight
                            reads_supplied_distances = (
                                name == "eccentricity"
                                and bound.arguments.get("sp") is not None
                            )
                            reads_lazily = live_input or (
                                name in {"shortest_path", "shortest_path_length"}
                                and bound.arguments.get("source") is None
                                and bound.arguments.get("target") is None
                            )
                            if (
                                reads_lazily or has_callbacks or uses_live_weight
                                or reads_supplied_distances
                            ):
                                if args:
                                    args = (source, *args[1:])
                                else:
                                    kwargs = {**kwargs, graph_parameter: source}
                    if not has_callbacks:
                        return fn(*args, **kwargs)
                    _clear_callback_conversions(source)
                    try:
                        result = fn(*args, **kwargs)
                    finally:
                        _clear_callback_conversions(source)
                    if reads_lazily and inspect.isgenerator(result):
                        return _iterate_callback_result(result, source)
                    return result
                except fnx.NetworkXNotImplemented as e:
                    if name in _CORE_DECOMPOSITION_ALGORITHMS or name in {
                        "stoer_wagner", "minimum_spanning_tree", "maximum_spanning_tree"
                    }:
                        # Keep documented self-loop and graph-type errors intact.
                        raise
                    # NetworkX's dispatcher strictly requires the builtin NotImplementedError
                    # to correctly trigger its fallback sequence.
                    raise NotImplementedError(str(e)) from e

            return wrapper
        raise AttributeError(f"BackendInterface has no attribute '{name}'")


backend_interface = BackendInterface()
__all__ = ["BackendInterface", "backend_interface", "get_backend_info"]
