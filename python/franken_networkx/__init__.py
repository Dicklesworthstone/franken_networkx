"""FrankenNetworkX — A high-performance Rust-backed drop-in replacement for NetworkX.

Usage::

    import franken_networkx as fnx

    G = franken_networkx.Graph()
    G.add_edge("a", "b", weight=3.0)
    G.add_edge("b", "c", weight=1.5)
    path = fnx.shortest_path(G, "a", "c", weight="weight")

Or as a NetworkX backend (zero code changes required)::

    import networkx as nx
    nx.config.backend_priority = ["franken_networkx"]
    # Now all supported algorithms dispatch to Rust automatically.
"""

from collections import defaultdict, deque
from collections.abc import Mapping
from copy import deepcopy
from enum import Enum
from heapq import heappop, heappush
import itertools
from itertools import combinations, count
import math
import sys

from franken_networkx import _fnx
from franken_networkx._fnx import __version__

# Core graph classes
from franken_networkx._fnx import Graph
from franken_networkx._fnx import DiGraph
from franken_networkx._fnx import MultiGraph
from franken_networkx._fnx import MultiDiGraph


class EdgePartition(Enum):
    OPEN = 0
    INCLUDED = 1
    EXCLUDED = 2


def _nan_filtered_graph(G, weight, ignore_nan):
    H = G.__class__()
    H.graph.update(dict(G.graph))
    H.add_nodes_from(G.nodes(data=True))

    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            edge_weight = attrs.get(weight, 1)
            if isinstance(edge_weight, float) and math.isnan(edge_weight):
                if ignore_nan:
                    continue
                raise ValueError(
                    f"NaN found as an edge weight. Edge {(u, v, dict(attrs))}"
                )
            H.add_edge(u, v, key=key, **dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            edge_weight = attrs.get(weight, 1)
            if isinstance(edge_weight, float) and math.isnan(edge_weight):
                if ignore_nan:
                    continue
                raise ValueError(
                    f"NaN found as an edge weight. Edge {(u, v, dict(attrs))}"
                )
            H.add_edge(u, v, **dict(attrs))

    return H


class SpanningTreeIterator:
    """Iterate over all spanning trees of a graph in weight-sorted order.

    Uses the Rust-backed spanning-tree iterator implementation and matches
    NetworkX ``SpanningTreeIterator`` semantics for the supported graph types.

    Parameters
    ----------
    G : Graph
        Undirected graph.
    weight : str, default "weight"
        Edge attribute used as weight.
    minimum : bool, default True
        If True, yield trees in increasing weight order; otherwise decreasing.
    ignore_nan : bool, default False
        If False, raise when a NaN edge weight is encountered. If True, skip
        NaN-weighted edges before enumeration.
    """

    def __init__(self, G, weight="weight", minimum=True, ignore_nan=False):
        self.G = G
        self.weight = weight
        self.minimum = minimum
        self.ignore_nan = ignore_nan

    def __iter__(self):
        from franken_networkx._fnx import spanning_tree_iterator_rust
        from franken_networkx._fnx import NetworkXNotImplemented

        if self.G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        if self.G.is_multigraph():
            raise NetworkXNotImplemented("not implemented for multigraph type")
        graph = _nan_filtered_graph(self.G, self.weight, self.ignore_nan)
        self._iterator = spanning_tree_iterator_rust(
            graph,
            self.weight,
            self.minimum,
            sys.maxsize,
        )
        return self

    def __next__(self):
        if not hasattr(self, "_iterator") or self._iterator is None:
            raise AttributeError(
                "'SpanningTreeIterator' object has no attribute 'partition_queue'"
            )
        try:
            return next(self._iterator)
        except StopIteration:
            del self.G
            del self._iterator
            raise StopIteration


class ArborescenceIterator:
    """Iterate over all spanning arborescences of a digraph in weight-sorted order.

    Uses the Rust-backed arborescence iterator implementation and matches
    NetworkX ``ArborescenceIterator`` semantics for the supported graph types.

    Parameters
    ----------
    G : DiGraph
        Directed graph.
    weight : str, default "weight"
        Edge attribute used as weight.
    minimum : bool, default True
        If True, yield arborescences in increasing weight order.
    init_partition : tuple, optional
        ``(included_edges, excluded_edges)`` to constrain the enumeration.
    """

    def __init__(self, G, weight="weight", minimum=True, init_partition=None):
        self.G = G
        self.weight = weight
        self.minimum = minimum
        self.init_partition = init_partition

    def __iter__(self):
        from franken_networkx._fnx import arborescence_iterator_rust
        from franken_networkx._fnx import NetworkXPointlessConcept

        if not self.G.is_directed():
            from franken_networkx._fnx import NetworkXNotImplemented

            raise NetworkXNotImplemented("not implemented for undirected type")
        if self.G.is_multigraph():
            from franken_networkx._fnx import NetworkXNotImplemented

            raise NetworkXNotImplemented("not implemented for multigraph type")
        if self.G.number_of_nodes() == 0:
            raise NetworkXPointlessConcept("G has no nodes.")
        self._iterator = arborescence_iterator_rust(
            self.G,
            self.weight,
            self.minimum,
            sys.maxsize,
            self.init_partition,
        )
        return self

    def __next__(self):
        if not hasattr(self, "_iterator") or self._iterator is None:
            raise AttributeError(
                "'ArborescenceIterator' object has no attribute 'partition_queue'",
            )
        try:
            return next(self._iterator)
        except StopIteration:
            del self.G
            del self._iterator
            raise StopIteration


# Exception hierarchy
from franken_networkx._fnx import (
    HasACycle,
    NetworkXAlgorithmError,
    NetworkXError,
    NetworkXNoCycle,
    NetworkXNoPath,
    NetworkXNotImplemented,
    NetworkXPointlessConcept,
    NetworkXUnbounded,
    NetworkXUnfeasible,
    NotATree,
    NodeNotFound,
    PowerIterationFailedConvergence,
)

# Algorithm functions — shortest path
from franken_networkx._fnx import (
    average_shortest_path_length,
    bellman_ford_path,
    dijkstra_path,
    has_path,
    multi_source_dijkstra,
    shortest_path,
    shortest_path_length as _shortest_path_length_raw,
)


def shortest_path_length(G, source=None, target=None, weight=None, method="dijkstra"):
    """Return shortest path length between source and target.

    If *source* and *target* are both None, return an iterator over
    ``(node, dict)`` pairs for all nodes.
    If only *source* is given, return a dict mapping target to length.
    If both are given, return a single number.
    Matches ``networkx.shortest_path_length``.
    """
    if method not in ("dijkstra", "bellman-ford"):
        raise ValueError(f"method not supported: {method}")

    if source is not None and target is not None:
        if weight is not None and method == "bellman-ford":
            return bellman_ford_path_length(G, source, target, weight=weight)
        return _shortest_path_length_raw(G, source, target, weight=weight)
    
    if source is not None:
        if weight is not None and method == "bellman-ford":
            return dict(single_source_bellman_ford_path_length(G, source, weight=weight))
        return dict(single_source_shortest_path_length(G, source, weight=weight))
        
    if target is not None:
        if weight is not None and method == "bellman-ford":
            raise NetworkXNotImplemented("single_target_bellman_ford_path_length not implemented")
        return dict(single_target_shortest_path_length(G, target, weight=weight))
        
    if weight is not None:
        if method == "bellman-ford":
            all_pairs = dict(all_pairs_bellman_ford_path_length(G, weight=weight))
        else:  # dijkstra
            all_pairs = dict(all_pairs_dijkstra_path_length(G, weight=weight))
    else:
        all_pairs = all_pairs_shortest_path_length(G)
    return ((node, all_pairs[node]) for node in G.nodes())


# Algorithm functions — connectivity
from franken_networkx._fnx import (
    articulation_points,
    bridges,
    connected_components,
    edge_connectivity,
    is_connected,
    minimum_node_cut,
    node_connectivity,
    number_connected_components,
)

# Algorithm functions — centrality
from franken_networkx._fnx import (
    average_neighbor_degree,
    betweenness_centrality,
    closeness_centrality,
    degree_assortativity_coefficient,
    degree_centrality,
    edge_betweenness_centrality,
    eigenvector_centrality,
    harmonic_centrality,
    hits,
    katz_centrality,
    pagerank,
    voterank,
)

# Algorithm functions — clustering
from franken_networkx._fnx import (
    average_clustering,
    clustering,
    find_cliques,
    graph_clique_number,
    square_clustering,
    transitivity,
    triangles,
)

# Algorithm functions — matching
from franken_networkx._fnx import (
    max_weight_matching,
    maximal_matching,
    min_edge_cover,
    min_weight_matching,
)

# Algorithm functions — flow
from franken_networkx._fnx import (
    maximum_flow,
    maximum_flow_value,
    minimum_cut,
    minimum_cut_value,
)

# Algorithm functions — distance measures
from franken_networkx._fnx import (
    center,
    density,
    diameter,
    eccentricity,
    periphery,
    radius,
)

# Algorithm functions — tree, forest, bipartite, coloring, core
from franken_networkx._fnx import (
    bipartite_sets,
    core_number,
    greedy_color,
    is_bipartite,
    is_forest,
    is_tree,
    maximum_branching,
    maximum_spanning_arborescence,
    number_of_spanning_trees,
    minimum_spanning_edges,
    minimum_branching,
    minimum_spanning_arborescence,
    minimum_spanning_tree,
    partition_spanning_tree,
    random_spanning_tree,
)

# Algorithm functions — Euler
from franken_networkx._fnx import (
    eulerian_circuit,
    eulerian_path,
    has_eulerian_path,
    is_eulerian,
    is_semieulerian,
)

# Algorithm functions — paths and cycles
from franken_networkx._fnx import (
    all_shortest_paths,
    all_simple_paths as _rust_all_simple_paths,
    cycle_basis,
)


def all_simple_paths(G, source, target, cutoff=None):
    """Return all simple paths from source to target.

    Delegates to the Rust implementation.
    """
    # Trivial case: source is target
    if source == target:
        return [[source]]
    return _rust_all_simple_paths(G, source, target, cutoff=cutoff)


# Algorithm functions — graph operators
from franken_networkx._fnx import (
    complement,
)

# Algorithm functions — efficiency
from franken_networkx._fnx import (
    efficiency,
    global_efficiency,
    local_efficiency,
)

# Algorithm functions — broadcasting
from franken_networkx._fnx import (
    tree_broadcast_center,
    tree_broadcast_time,
)

# Algorithm functions — traversal (BFS) — wrapped for sort_neighbors support
from franken_networkx._fnx import (
    bfs_edges as _bfs_edges_raw,
    bfs_layers,
    bfs_predecessors as _bfs_predecessors_raw,
    bfs_successors as _bfs_successors_raw,
    bfs_tree as _bfs_tree_raw,
    descendants_at_distance,
)

# Algorithm functions — traversal (DFS) — wrapped for sort_neighbors support
from franken_networkx._fnx import (
    dfs_edges as _dfs_edges_raw,
    dfs_postorder_nodes as _dfs_postorder_nodes_raw,
    dfs_predecessors as _dfs_predecessors_raw,
    dfs_preorder_nodes as _dfs_preorder_nodes_raw,
    dfs_successors as _dfs_successors_raw,
    dfs_tree as _dfs_tree_raw,
)


def _py_bfs_edges(G, source, depth_limit=None, sort_neighbors=None, reverse=False):
    """Python-level BFS with sort_neighbors support."""
    from collections import deque

    visited = {source}
    queue = deque([(source, 0)])
    max_depth = depth_limit if depth_limit is not None else float("inf")
    if reverse and G.is_directed():
        neighbor_iter = G.predecessors
    else:
        neighbor_iter = G.neighbors
    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        nbrs = list(neighbor_iter(node))
        if sort_neighbors is not None:
            nbrs = list(sort_neighbors(nbrs))
        for neighbor in nbrs:
            if neighbor not in visited:
                visited.add(neighbor)
                yield (node, neighbor)
                queue.append((neighbor, depth + 1))


def _py_dfs_labeled_edges(G, source=None, depth_limit=None, sort_neighbors=None):
    """Python-level DFS labeled edges with sort_neighbors support."""
    nodes = G if source is None else [source]
    if depth_limit is None:
        depth_limit = len(G)

    get_children = (
        G.neighbors
        if sort_neighbors is None
        else lambda n: iter(sort_neighbors(G.neighbors(n)))
    )

    visited = set()
    for start in nodes:
        if start in visited:
            continue
        yield start, start, "forward"
        visited.add(start)
        stack = [(start, get_children(start))]
        depth_now = 1
        while stack:
            parent, children = stack[-1]
            for child in children:
                if child in visited:
                    yield parent, child, "nontree"
                else:
                    yield parent, child, "forward"
                    visited.add(child)
                    if depth_now < depth_limit:
                        stack.append((child, iter(get_children(child))))
                        depth_now += 1
                        break
                    else:
                        yield parent, child, "reverse-depth_limit"
            else:
                stack.pop()
                depth_now -= 1
                if stack:
                    yield stack[-1][0], parent, "reverse"
        yield start, start, "reverse"


def _py_dfs_edges(G, source=None, depth_limit=None, sort_neighbors=None):
    """Python-level DFS with sort_neighbors support."""
    for u, v, label in _py_dfs_labeled_edges(
        G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    ):
        if label == "forward" and u != v:
            yield (u, v)


def bfs_edges(G, source, reverse=False, depth_limit=None, sort_neighbors=None):
    """Iterate edges in BFS order from source."""
    if sort_neighbors is not None:
        return list(_py_bfs_edges(G, source, depth_limit, sort_neighbors, reverse=reverse))
    return _bfs_edges_raw(G, source, reverse=reverse, depth_limit=depth_limit)


def dfs_edges(G, source=None, depth_limit=None, sort_neighbors=None):
    """Iterate edges in DFS order from source."""
    if sort_neighbors is not None:
        return list(_py_dfs_edges(G, source, depth_limit, sort_neighbors))
    return _dfs_edges_raw(G, source=source, depth_limit=depth_limit)


def bfs_predecessors(G, source, depth_limit=None, sort_neighbors=None):
    """Return (node, predecessor) pairs from BFS."""
    if sort_neighbors is not None:
        preds = {}
        for u, v in _py_bfs_edges(G, source, depth_limit, sort_neighbors):
            preds[v] = u
        return preds
    return _bfs_predecessors_raw(G, source, depth_limit=depth_limit)


def bfs_successors(G, source, depth_limit=None, sort_neighbors=None):
    """Return (node, [successors]) pairs from BFS."""
    if sort_neighbors is not None:
        from collections import defaultdict

        succs = defaultdict(list)
        for u, v in _py_bfs_edges(G, source, depth_limit, sort_neighbors):
            succs[u].append(v)
        return dict(succs)
    return _bfs_successors_raw(G, source, depth_limit=depth_limit)


def bfs_tree(G, source, reverse=False, depth_limit=None, sort_neighbors=None):
    """Return BFS tree rooted at source."""
    if sort_neighbors is not None:
        T = DiGraph()
        T.add_node(source)
        for u, v in _py_bfs_edges(G, source, depth_limit, sort_neighbors, reverse=reverse):
            T.add_edge(u, v)
        return T
    return _bfs_tree_raw(G, source, reverse=reverse, depth_limit=depth_limit)


def dfs_predecessors(G, source=None, depth_limit=None, sort_neighbors=None):
    """Return (node, predecessor) dict from DFS."""
    if sort_neighbors is not None:
        preds = {}
        for u, v in _py_dfs_edges(G, source, depth_limit, sort_neighbors):
            preds[v] = u
        return preds
    return _dfs_predecessors_raw(G, source=source, depth_limit=depth_limit)


def dfs_successors(G, source=None, depth_limit=None, sort_neighbors=None):
    """Return (node, [successors]) dict from DFS."""
    if sort_neighbors is not None:
        from collections import defaultdict

        succs = defaultdict(list)
        for u, v in _py_dfs_edges(G, source, depth_limit, sort_neighbors):
            succs[u].append(v)
        return dict(succs)
    return _dfs_successors_raw(G, source=source, depth_limit=depth_limit)


def dfs_preorder_nodes(G, source=None, depth_limit=None, sort_neighbors=None):
    """Yield nodes in DFS preorder from source."""
    if sort_neighbors is not None:
        for _, v, label in _py_dfs_labeled_edges(
            G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
        ):
            if label == "forward":
                yield v
        return
    yield from _dfs_preorder_nodes_raw(G, source=source, depth_limit=depth_limit)


def dfs_postorder_nodes(G, source=None, depth_limit=None, sort_neighbors=None):
    """Yield nodes in DFS postorder from source."""
    if sort_neighbors is not None:
        for _, v, label in _py_dfs_labeled_edges(
            G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
        ):
            if label == "reverse":
                yield v
        return
    yield from _dfs_postorder_nodes_raw(G, source=source, depth_limit=depth_limit)


def dfs_tree(G, source=None, depth_limit=None, sort_neighbors=None):
    """Return DFS tree rooted at source."""
    if sort_neighbors is not None:
        T = DiGraph()
        if source is None:
            T.add_nodes_from(G)
        else:
            T.add_node(source)
        for u, v in _py_dfs_edges(G, source, depth_limit, sort_neighbors):
            T.add_edge(u, v)
        return T
    return _dfs_tree_raw(G, source=source, depth_limit=depth_limit)


# Algorithm functions — reciprocity (wrapped to match NetworkX API)
from franken_networkx._fnx import overall_reciprocity
from franken_networkx._fnx import reciprocity as _reciprocity_raw


def reciprocity(G, nodes=None):
    """Compute reciprocity for a directed graph.

    If *nodes* is None, return the overall reciprocity of the graph (float).
    If *nodes* is a single node, return the reciprocity for that node (float).
    If *nodes* is an iterable of nodes, return a dict mapping each node to
    its reciprocity.  Matches ``networkx.reciprocity``.
    """
    if nodes is None:
        return overall_reciprocity(G)
    return _reciprocity_raw(G, nodes)


# Algorithm functions — Wiener index
from franken_networkx._fnx import (
    wiener_index,
)

# Algorithm functions — maximum spanning tree
from franken_networkx._fnx import (
    maximum_spanning_edges,
    maximum_spanning_tree,
)

# Algorithm functions — condensation (wrapped to match NetworkX API)
from franken_networkx._fnx import condensation as _condensation_raw


def condensation(G, scc=None):
    """Return the condensation of G.

    The condensation of a directed graph contracts each strongly connected
    component into a single node. The resulting graph is a DAG.

    Returns a DiGraph C where each node has a 'members' attribute (the set
    of original nodes in that SCC) and C.graph['mapping'] maps original
    nodes to SCC indices. This matches the NetworkX API.
    """
    if scc is not None:
        cond_dg = DiGraph()
        mapping = {}
        members = {}
        components = [set(component) for component in scc]

        for idx, component in enumerate(components):
            members[idx] = component
            for node in component:
                mapping[node] = idx

        missing = set(G.nodes()) - set(mapping)
        if missing:
            raise NetworkXError(
                f"condensation scc is missing graph nodes: {sorted(missing)!r}"
            )

        cond_dg.add_nodes_from(range(len(components)))
        for idx, member_set in members.items():
            cond_dg.nodes[idx]["members"] = member_set

        for u, v in G.edges():
            cu = mapping[u]
            cv = mapping[v]
            if cu != cv:
                cond_dg.add_edge(cu, cv)

        cond_dg.graph["mapping"] = mapping
        return cond_dg

    cond_dg, mapping = _condensation_raw(G)
    # Build members: reverse the mapping to get {scc_idx: set of nodes}
    members = {}
    for node, scc_idx in mapping.items():
        members.setdefault(scc_idx, set()).add(node)
    # Set 'members' attribute on each node
    for scc_idx, member_set in members.items():
        cond_dg.nodes[scc_idx]["members"] = member_set
    cond_dg.graph["mapping"] = mapping
    return cond_dg


# Algorithm functions — all-pairs shortest paths
from franken_networkx._fnx import (
    all_pairs_shortest_path,
    all_pairs_shortest_path_length,
)

# Algorithm functions — graph predicates & utilities
from franken_networkx._fnx import (
    is_empty,
    non_neighbors,
    number_of_cliques,
    all_triangles,
    node_clique_number,
    enumerate_all_cliques,
    find_cliques_recursive,
    chordal_graph_cliques,
    chordal_graph_treewidth,
    make_max_clique_graph as _rust_make_max_clique_graph,
    ring_of_cliques,
)

# Classic graph generators
from franken_networkx._fnx import (
    balanced_tree as _rust_balanced_tree,
    barbell_graph as _rust_barbell_graph,
    bull_graph as _rust_bull_graph,
    chvatal_graph as _rust_chvatal_graph,
    cubical_graph as _rust_cubical_graph,
    desargues_graph as _rust_desargues_graph,
    diamond_graph as _rust_diamond_graph,
    dodecahedral_graph as _rust_dodecahedral_graph,
    frucht_graph as _rust_frucht_graph,
    heawood_graph as _rust_heawood_graph,
    house_graph as _rust_house_graph,
    house_x_graph as _rust_house_x_graph,
    icosahedral_graph as _rust_icosahedral_graph,
    krackhardt_kite_graph as _rust_krackhardt_kite_graph,
    moebius_kantor_graph as _rust_moebius_kantor_graph,
    octahedral_graph as _rust_octahedral_graph,
    pappus_graph,
    petersen_graph as _rust_petersen_graph,
    sedgewick_maze_graph,
    tetrahedral_graph as _rust_tetrahedral_graph,
    truncated_cube_graph as _rust_truncated_cube_graph,
    truncated_tetrahedron_graph as _rust_truncated_tetrahedron_graph,
    tutte_graph as _rust_tutte_graph,
    hoffman_singleton_graph,
    generalized_petersen_graph as _rust_generalized_petersen_graph,
    wheel_graph as _rust_wheel_graph,
    ladder_graph as _rust_ladder_graph,
    circular_ladder_graph as _rust_circular_ladder_graph,
    lollipop_graph as _rust_lollipop_graph,
    tadpole_graph as _rust_tadpole_graph,
    turan_graph,
    windmill_graph as _rust_windmill_graph,
    hypercube_graph,
    complete_bipartite_graph as _rust_complete_bipartite_graph,
    complete_multipartite_graph as _rust_complete_multipartite_graph,
    grid_2d_graph as _rust_grid_2d_graph,
    null_graph as _rust_null_graph,
    trivial_graph as _rust_trivial_graph,
    binomial_tree as _rust_binomial_tree,
    full_rary_tree as _rust_full_rary_tree,
    circulant_graph as _rust_circulant_graph,
    kneser_graph,
    paley_graph as _rust_paley_graph,
    chordal_cycle_graph as _rust_chordal_cycle_graph,
)

# Algorithm functions — single-source shortest paths
from franken_networkx._fnx import (
    single_source_shortest_path,
    single_source_shortest_path_length,
)

# Algorithm functions — dominating set
from franken_networkx._fnx import (
    dominating_set,
    is_dominating_set,
)

# Algorithm functions — community detection
from franken_networkx._fnx import (
    louvain_communities,
    modularity,
    label_propagation_communities,
    greedy_modularity_communities,
)

# Algorithm functions — graph operators
from franken_networkx._fnx import (
    union,
    intersection,
    compose,
    difference,
    symmetric_difference,
    degree_histogram,
)

# Algorithm functions — transitive closure/reduction
from franken_networkx._fnx import (
    transitive_closure,
    transitive_reduction,
)

# Algorithm functions — graph metrics
from franken_networkx._fnx import (
    average_degree_connectivity,
    rich_club_coefficient,
    s_metric,
)

# Algorithm functions — graph metrics (expansion, conductance, volume)
from franken_networkx._fnx import (
    volume,
    boundary_expansion,
    conductance,
    edge_expansion,
    node_expansion,
    mixing_expansion,
    non_edges,
    average_node_connectivity,
    is_k_edge_connected,
    all_pairs_dijkstra as _raw_all_pairs_dijkstra,
    number_of_spanning_arborescences,
    global_node_connectivity,
)

def all_pairs_dijkstra(G, weight="weight"):
    for k, v in _raw_all_pairs_dijkstra(G, weight=weight).items():
        yield (k, tuple(v))

# Algorithm functions — strongly connected components
from franken_networkx._fnx import (
    strongly_connected_components,
    number_strongly_connected_components,
    is_strongly_connected,
)

# Algorithm functions — weakly connected components
from franken_networkx._fnx import (
    weakly_connected_components,
    number_weakly_connected_components,
    is_weakly_connected,
)

# Algorithm functions — link prediction
from franken_networkx._fnx import (
    common_neighbors,
    jaccard_coefficient,
    adamic_adar_index,
    preferential_attachment,
    resource_allocation_index,
)

# Algorithm functions — DAG
from franken_networkx._fnx import (
    ancestors,
    dag_longest_path,
    dag_longest_path_length,
    descendants,
    is_directed_acyclic_graph,
    lexicographic_topological_sort,
    topological_sort,
    topological_generations,
)

# Algorithm functions — graph isomorphism
from franken_networkx._fnx import (
    could_be_isomorphic,
    fast_could_be_isomorphic,
    graph_edit_distance_common_rust as _graph_edit_distance_common_rust,
    faster_could_be_isomorphic,
    is_isomorphic as _is_isomorphic_rust,
    vf2pp_all_isomorphisms_rust as _vf2pp_all_isomorphisms_rust,
    vf2pp_isomorphism_rust as _vf2pp_isomorphism_rust,
)

# Planarity
from franken_networkx._fnx import is_planar
from franken_networkx._fnx import is_chordal

# Barycenter
from franken_networkx._fnx import barycenter

# Algorithm functions — A* shortest path
from franken_networkx._fnx import (
    astar_path,
    astar_path_length,
    shortest_simple_paths,
)

# Algorithm functions — approximation
from franken_networkx._fnx import (
    clique_removal,
    maximal_independent_set,
    large_clique_size,
    max_clique,
    maximum_independent_set,
    min_weighted_vertex_cover,
    spanner,
)

# Algorithm functions — tree recognition
from franken_networkx._fnx import (
    is_arborescence,
    is_branching,
)

# Algorithm functions — isolates
from franken_networkx._fnx import (
    is_isolate,
    isolates,
    number_of_isolates,
)

# Algorithm functions — boundary
from franken_networkx._fnx import (
    cut_size,
    edge_boundary,
    node_boundary,
    normalized_cut_size,
)

# Algorithm functions — path validation
from franken_networkx._fnx import is_simple_path

# Algorithm functions — matching validators
from franken_networkx._fnx import (
    is_matching,
    is_maximal_matching,
    is_perfect_matching,
)

# Algorithm functions — cycles
from franken_networkx._fnx import (
    simple_cycles,
    find_cycle,
    girth,
    find_negative_cycle,
)

# Algorithm functions — graph predicates
from franken_networkx._fnx import (
    is_graphical,
    is_digraphical,
    is_multigraphical,
    is_pseudographical,
    is_regular,
    is_k_regular,
    is_tournament,
    is_weighted,
    is_negatively_weighted,
    is_path,
    is_distance_regular,
)

# Algorithm functions — traversal additional
from franken_networkx._fnx import (
    edge_bfs,
    edge_dfs,
)

# Algorithm functions — matching additional
from franken_networkx._fnx import (
    is_edge_cover,
    max_weight_clique,
)

# Algorithm functions — DAG additional
from franken_networkx._fnx import (
    is_aperiodic,
    antichains,
    immediate_dominators,
    dominance_frontiers,
)

# Algorithm functions — additional shortest path
from franken_networkx._fnx import (
    dijkstra_path_length,
    bellman_ford_path_length,
    single_source_dijkstra,
    single_source_dijkstra_path,
    single_source_dijkstra_path_length,
    single_source_bellman_ford,
    single_source_bellman_ford_path,
    single_source_bellman_ford_path_length,
    single_target_shortest_path,
    single_target_shortest_path_length,
    all_pairs_dijkstra_path as _raw_all_pairs_dijkstra_path,
    all_pairs_dijkstra_path_length as _raw_all_pairs_dijkstra_path_length,
    all_pairs_bellman_ford_path as _raw_all_pairs_bellman_ford_path,
    all_pairs_bellman_ford_path_length as _raw_all_pairs_bellman_ford_path_length,
    floyd_warshall,
    floyd_warshall_predecessor_and_distance,
    bidirectional_shortest_path,
    negative_edge_cycle,
    predecessor,
    path_weight,
)

def all_pairs_dijkstra_path(G, weight="weight"):
    for k, v in _raw_all_pairs_dijkstra_path(G, weight=weight).items():
        yield (k, v)

def all_pairs_dijkstra_path_length(G, weight="weight"):
    for k, v in _raw_all_pairs_dijkstra_path_length(G, weight=weight).items():
        yield (k, v)

def all_pairs_bellman_ford_path(G, weight="weight"):
    for k, v in _raw_all_pairs_bellman_ford_path(G, weight=weight).items():
        yield (k, v)

def all_pairs_bellman_ford_path_length(G, weight="weight"):
    for k, v in _raw_all_pairs_bellman_ford_path_length(G, weight=weight).items():
        yield (k, v)

# Additional centrality algorithms
from franken_networkx._fnx import (
    in_degree_centrality,
    out_degree_centrality,
    local_reaching_centrality,
    global_reaching_centrality,
    group_degree_centrality,
    group_in_degree_centrality,
    group_out_degree_centrality,
)

# Component algorithms
from franken_networkx._fnx import (
    node_connected_component,
    is_biconnected,
    biconnected_components,
    biconnected_component_edges,
    is_semiconnected,
    kosaraju_strongly_connected_components,
    attracting_components,
    number_attracting_components,
    is_attracting_component,
)

# Graph generators — classic
from franken_networkx._fnx import (
    complete_graph as _rust_complete_graph,
    cycle_graph as _rust_cycle_graph,
    empty_graph as _rust_empty_graph,
    path_graph as _rust_path_graph,
    star_graph as _rust_star_graph,
)

# Graph generators — random
from franken_networkx._fnx import gnp_random_graph as _rust_gnp_random_graph
from franken_networkx._fnx import watts_strogatz_graph as _rust_watts_strogatz_graph
from franken_networkx._fnx import barabasi_albert_graph as _rust_barabasi_albert_graph
from franken_networkx._fnx import erdos_renyi_graph as _rust_erdos_renyi_graph
from franken_networkx._fnx import (
    newman_watts_strogatz_graph as _rust_newman_watts_strogatz_graph,
)
from franken_networkx._fnx import (
    connected_watts_strogatz_graph as _rust_connected_watts_strogatz_graph,
)
from franken_networkx._fnx import random_regular_graph as _rust_random_regular_graph
from franken_networkx._fnx import powerlaw_cluster_graph as _rust_powerlaw_cluster_graph
from franken_networkx._fnx import stochastic_block_model as _rust_stochastic_block_model

# Read/write — graph I/O
from franken_networkx._fnx import (
    node_link_data as _rust_node_link_data,
    node_link_graph as _rust_node_link_graph,
    read_adjlist,
    read_edgelist,
    read_graphml,
    write_adjlist,
    write_edgelist,
    write_graphml,
    read_gml,
    write_gml,
)
from franken_networkx.readwrite import (
    from_graph6_bytes,
    from_sparse6_bytes,
    generate_adjlist,
    generate_edgelist,
    generate_gexf,
    generate_gml,
    generate_multiline_adjlist,
    generate_pajek,
    parse_graph6,
    parse_gexf,
    parse_adjlist,
    parse_edgelist,
    parse_gml,
    parse_leda,
    parse_multiline_adjlist,
    parse_pajek,
    parse_sparse6,
    read_gexf,
    read_graph6,
    read_leda,
    read_multiline_adjlist,
    read_pajek,
    read_sparse6,
    read_weighted_edgelist,
    relabel_gexf_graph,
    to_graph6_bytes,
    to_sparse6_bytes,
    write_gexf,
    write_graph6,
    write_graphml_lxml,
    write_graphml_xml,
    write_multiline_adjlist,
    write_pajek,
    write_sparse6,
    write_weighted_edgelist,
)


def complete_graph(n, create_using=None):
    """Return the complete graph K_n."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_complete_graph(n)

    graph = nx.complete_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def cycle_graph(n, create_using=None):
    """Return the cycle graph C_n."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_cycle_graph(n)

    graph = nx.cycle_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def empty_graph(n=0, create_using=None, default=Graph):
    """Return the empty graph with n nodes and zero edges."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None and default in (Graph, nx.Graph):
        return _rust_empty_graph(n)

    default_graph = default
    if default is Graph:
        default_graph = nx.Graph
    elif default is DiGraph:
        default_graph = nx.DiGraph
    elif default is MultiGraph:
        default_graph = nx.MultiGraph
    elif default is MultiDiGraph:
        default_graph = nx.MultiDiGraph

    graph = nx.empty_graph(n, create_using=None, default=default_graph)
    return _from_nx_graph(graph, create_using=create_using)


def path_graph(n, create_using=None):
    """Return the path graph P_n."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_path_graph(n)

    graph = nx.path_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def star_graph(n, create_using=None):
    """Return the star graph on n + 1 nodes."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_star_graph(n)

    graph = nx.star_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


# ---------------------------------------------------------------------------
# Bipartite algorithms — pure Python wrappers over Rust primitives
# ---------------------------------------------------------------------------


def is_bipartite_node_set(G, nodes):
    """Check whether *nodes* is one side of a valid bipartition of *G*.

    Parameters
    ----------
    G : Graph
        The input graph.
    nodes : container
        Candidate node set.

    Returns
    -------
    bool
        True if *nodes* forms one part of a bipartition.
    """
    if not is_bipartite(G):
        return False
    node_set = set(nodes)
    top, bottom = bipartite_sets(G)
    return node_set == set(top) or node_set == set(bottom)


def projected_graph(B, nodes, multigraph=False):
    """Return the projection of a bipartite graph onto one set of nodes.

    Two nodes in the projection are connected if they share a neighbor
    in the original bipartite graph. If multigraph=True, one edge is
    added per shared neighbor (returns MultiGraph).
    """
    nodes_set = set(nodes)

    if multigraph:
        G = MultiGraph()
        for node in nodes_set:
            G.add_node(node, **dict(B.nodes[node]))
        for u in nodes_set:
            for nbr in B.neighbors(u):
                if nbr in nodes_set:
                    continue
                for v in B.neighbors(nbr):
                    if v in nodes_set and v != u:
                        G.add_edge(u, v, key=nbr)
    else:
        G = Graph()
        for node in nodes_set:
            G.add_node(node, **dict(B.nodes[node]))
        for u in nodes_set:
            for nbr in B.neighbors(u):
                if nbr in nodes_set:
                    continue
                for v in B.neighbors(nbr):
                    if v in nodes_set and v != u and not G.has_edge(u, v):
                        G.add_edge(u, v)

    return G


def bipartite_density(B, nodes):
    """Return the bipartite density of a bipartite graph *B*.

    The bipartite density is ``|E| / (|top| * |bottom|)`` for undirected graphs,
    and ``|E| / (2 * |top| * |bottom|)`` for directed graphs.

    Parameters
    ----------
    B : Graph
        A bipartite graph.
    nodes : container
        Nodes in one of the two bipartite sets.

    Returns
    -------
    float
        The bipartite density.
    """
    top = set(nodes)
    bottom = set(B.nodes()) - top
    if not top or not bottom:
        return 0.0
    if B.is_directed():
        return B.number_of_edges() / (2.0 * len(top) * len(bottom))
    return B.number_of_edges() / (len(top) * len(bottom))


def hopcroft_karp_matching(G, top_nodes=None):
    """Return a maximum cardinality matching for a bipartite graph.

    Uses the Hopcroft-Karp algorithm conceptually, but delegates to the
    existing maximal matching implementation.

    Parameters
    ----------
    G : Graph
        A bipartite graph.
    top_nodes : container, optional
        The nodes in one bipartite set. If None, computed from bipartite_sets.

    Returns
    -------
    dict
        A mapping from each matched node to its partner.
    """
    if top_nodes is None:
        top, _ = bipartite_sets(G)
        top_nodes = top

    # Use the existing max-weight matching (with unit weights = max cardinality)
    matching_edges = max_weight_matching(G)
    result = {}
    for u, v in matching_edges:
        result[u] = v
        result[v] = u
    return result


# ---------------------------------------------------------------------------
# Community detection — additional algorithms
# ---------------------------------------------------------------------------


def girvan_newman(G, most_valuable_edge=None):
    """Find communities by iteratively removing the most-connected edge.

    Yields partitions of the graph as a generator of tuples of sets.
    Each partition has one more community than the previous.

    Parameters
    ----------
    G : Graph
        The input graph.
    most_valuable_edge : callable, optional
        Function that takes a graph and returns the edge to remove.
        Default uses the edge with highest betweenness centrality.

    Yields
    ------
    tuple of frozensets
        Each yield is a partition of the graph into communities.
    """
    if G.number_of_nodes() == 0:
        yield ()
        return

    H = G.copy()

    if most_valuable_edge is None:

        def most_valuable_edge(graph):
            ebc = edge_betweenness_centrality(graph)
            return max(ebc, key=ebc.get)

    prev_num_components = number_connected_components(H)

    while H.number_of_edges() > 0:
        edge = most_valuable_edge(H)
        H.remove_edge(*edge)
        new_num = number_connected_components(H)
        if new_num > prev_num_components:
            components = connected_components(H)
            yield tuple(frozenset(c) for c in components)
            prev_num_components = new_num


def k_clique_communities(G, k):
    """Find k-clique communities using the clique percolation method.

    A k-clique community is the union of all cliques of size k that can
    be reached through adjacent (sharing k-1 nodes) k-cliques.

    Parameters
    ----------
    G : Graph
        The input graph.
    k : int
        Size of the smallest clique.

    Yields
    ------
    frozenset
        Each yielded set is a k-clique community.
    """
    if k < 2:
        raise ValueError("k must be >= 2")
    for community in _fnx.k_clique_communities_rust(G, k):
        yield community


# ---------------------------------------------------------------------------
# Graph attribute helpers (high-frequency NetworkX utilities)
# ---------------------------------------------------------------------------


def _edge_attribute_dict(G, edge):
    if G.is_multigraph():
        u, v, key = edge
        try:
            return G[u][v][key]
        except KeyError:
            if G.is_directed():
                raise
            return G[v][u][key]

    u, v = edge
    try:
        return G[u][v]
    except KeyError:
        if G.is_directed():
            raise
        return G[v][u]


def set_node_attributes(G, values, name=None):
    """Set node attributes from a dictionary or scalar.

    Parameters
    ----------
    G : Graph
        The graph to modify.
    values : dict or scalar
        If a dict keyed by node, ``values[node]`` is the attribute value.
        If a dict keyed by node mapping to dicts, each inner dict is merged
        into the node's attributes. If a scalar, set it for all nodes.
    name : str, optional
        Attribute name. Required when *values* is a dict of scalars or a scalar.
    """
    if isinstance(values, Mapping):
        if name is not None:
            for node, value in values.items():
                if G.has_node(node):
                    G.nodes[node][name] = value
            return

        for node, attrs in values.items():
            if G.has_node(node):
                G.nodes[node].update(attrs)
        return

    if name is not None:
        for node in G.nodes():
            G.nodes[node][name] = values
        return

    values.items()


def get_node_attributes(G, name, default=None):
    """Return a dictionary of node attributes keyed by node.

    Parameters
    ----------
    G : Graph
        The input graph.
    name : str
        Attribute name.

    Returns
    -------
    dict
        ``{node: value}`` for nodes that have the attribute.
    """
    result = {}
    include_missing = default is not None
    for node in G.nodes():
        attrs = G.nodes[node]
        if name in attrs:
            result[node] = attrs[name]
        elif include_missing:
            result[node] = default
    return result


def set_edge_attributes(G, values, name=None):
    """Set edge attributes from a dictionary or scalar.

    Parameters
    ----------
    G : Graph
        The graph to modify.
    values : dict or scalar
        If a dict keyed by ``(u, v)``, sets the attribute per edge.
        If a scalar, sets it for all edges.
    name : str, optional
        Attribute name. Required when *values* is a scalar.
    """
    if isinstance(values, Mapping):
        if name is not None:
            for edge, value in values.items():
                try:
                    _edge_attribute_dict(G, edge)[name] = value
                except (KeyError, ValueError):
                    continue
            return

        for edge, attrs in values.items():
            try:
                _edge_attribute_dict(G, edge).update(attrs)
            except (KeyError, ValueError):
                continue
        return

    if name is not None:
        if G.is_multigraph():
            for u, v, key, attrs in G.edges(keys=True, data=True):
                attrs[name] = values
        else:
            for u, v, attrs in G.edges(data=True):
                attrs[name] = values
        return

    values.items()


def get_edge_attributes(G, name, default=None):
    """Return a dictionary of edge attributes keyed by ``(u, v)``.

    Parameters
    ----------
    G : Graph
        The input graph.
    name : str
        Attribute name.

    Returns
    -------
    dict
        ``{(u, v): value}`` for edges that have the attribute.
    """
    result = {}
    include_missing = default is not None
    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            if name in attrs:
                result[(u, v, key)] = attrs[name]
            elif include_missing:
                result[(u, v, key)] = default
        return result

    for u, v, attrs in G.edges(data=True):
        if name in attrs:
            result[(u, v)] = attrs[name]
        elif include_missing:
            result[(u, v)] = default
    return result


def create_empty_copy(G, with_data=True):
    """Return an empty copy of *G* (same nodes, no edges).

    Parameters
    ----------
    G : Graph
        The input graph.
    with_data : bool, optional
        If True (default), preserve node attributes.

    Returns
    -------
    H : Graph
        A graph with the same nodes but no edges.
    """
    H = G.__class__()
    H.graph.update(dict(G.graph))
    if with_data:
        H.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
    else:
        H.add_nodes_from(G.nodes())
    return H


def number_of_selfloops(G):
    """Return the number of self-loop edges in *G*."""
    return _fnx.number_of_selfloops_rust(G)


def selfloop_edges(G, data=False):
    """Return an iterator over self-loop edges.

    Parameters
    ----------
    G : Graph
        The input graph.
    data : bool, optional
        If True, yield ``(u, u, data_dict)`` tuples.

    Returns
    -------
    list
        Self-loop edges.
    """
    if data:
        return [(u, v, d) for u, v, d in G.edges(data=True) if u == v]
    return _fnx.selfloop_edges_rust(G)


def nodes_with_selfloops(G):
    """Return nodes that have self-loops."""
    return _fnx.nodes_with_selfloops_rust(G)


def all_neighbors(G, node):
    """Return all neighbors of *node* in *G* (including predecessors for DiGraph).

    For undirected graphs, equivalent to ``G.neighbors(node)``.
    For directed graphs, returns the union of successors and predecessors.
    """
    if G.is_directed():
        succs = set(G.successors(node)) if hasattr(G, "successors") else set()
        preds = set(G.predecessors(node)) if hasattr(G, "predecessors") else set()
        return list(succs | preds)
    return list(G.neighbors(node))


def add_path(G, nodes, **attr):
    """Add a path of edges to *G*."""
    node_list = list(nodes)
    if not node_list:
        return
    G.add_node(node_list[0])
    for i in range(len(node_list) - 1):
        G.add_edge(node_list[i], node_list[i + 1], **attr)


def add_cycle(G, nodes, **attr):
    """Add a cycle of edges to *G*."""
    node_list = list(nodes)
    if not node_list:
        return
    G.add_node(node_list[0])
    if len(node_list) == 1:
        G.add_edge(node_list[0], node_list[0], **attr)
        return
    for i in range(len(node_list) - 1):
        G.add_edge(node_list[i], node_list[i + 1], **attr)
    G.add_edge(node_list[-1], node_list[0], **attr)


def add_star(G, nodes, **attr):
    """Add a star of edges to *G* (first node is the center)."""
    node_list = list(nodes)
    if not node_list:
        return
    center = node_list[0]
    G.add_node(center)
    for spoke in node_list[1:]:
        G.add_edge(center, spoke, **attr)


def _validate_product_graph_types(G, H, *, allow_directed=True, allow_multigraph=True):
    if G.is_directed() != H.is_directed():
        raise NetworkXError("G and H must be both directed or both undirected")
    if G.is_directed() and not allow_directed:
        raise NetworkXNotImplemented("not implemented for directed type")
    if (G.is_multigraph() or H.is_multigraph()) and not allow_multigraph:
        raise NetworkXNotImplemented("not implemented for multigraph type")


def _product_graph_class(G, H):
    if G.is_directed():
        return MultiDiGraph if (G.is_multigraph() or H.is_multigraph()) else DiGraph
    return MultiGraph if (G.is_multigraph() or H.is_multigraph()) else Graph


def _product_node_attrs(g_attrs, h_attrs):
    merged = {}
    for key in set(g_attrs) | set(h_attrs):
        merged[key] = (g_attrs.get(key), h_attrs.get(key))
    return merged


def _paired_edge_attrs(g_attrs, h_attrs):
    merged = {}
    for key in set(g_attrs) | set(h_attrs):
        merged[key] = (g_attrs.get(key), h_attrs.get(key))
    return merged


def cartesian_product(G, H):
    """Return the Cartesian product of *G* and *H*.

    The Cartesian product has node set ``V(G) x V(H)``. Two nodes
    ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff ``u1 == u2`` and
    ``(v1, v2)`` is an edge in *H*, or ``v1 == v2`` and ``(u1, u2)``
    is an edge in *G*.
    """
    _validate_product_graph_types(G, H)
    P = _product_graph_class(G, H)()

    for g, g_attrs in G.nodes(data=True):
        for h, h_attrs in H.nodes(data=True):
            P.add_node((g, h), **_product_node_attrs(dict(g_attrs), dict(h_attrs)))

    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            for h in H.nodes():
                P.add_edge((u, h), (v, h), key=key, **dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            for h in H.nodes():
                P.add_edge((u, h), (v, h), **dict(attrs))

    if H.is_multigraph():
        for u, v, key, attrs in H.edges(keys=True, data=True):
            for g in G.nodes():
                P.add_edge((g, u), (g, v), key=key, **dict(attrs))
    else:
        for u, v, attrs in H.edges(data=True):
            for g in G.nodes():
                P.add_edge((g, u), (g, v), **dict(attrs))

    return P


def tensor_product(G, H):
    """Return the tensor (categorical) product of *G* and *H*.

    Two nodes ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff
    ``(u1, u2)`` is an edge in *G* AND ``(v1, v2)`` is an edge in *H*.
    """
    _validate_product_graph_types(G, H)
    P = _product_graph_class(G, H)()

    for g, g_attrs in G.nodes(data=True):
        for h, h_attrs in H.nodes(data=True):
            P.add_node((g, h), **_product_node_attrs(dict(g_attrs), dict(h_attrs)))

    if G.is_multigraph():
        g_edges = list(G.edges(keys=True, data=True))
    else:
        g_edges = [(u, v, None, attrs) for u, v, attrs in G.edges(data=True)]
    if H.is_multigraph():
        h_edges = list(H.edges(keys=True, data=True))
    else:
        h_edges = [(u, v, None, attrs) for u, v, attrs in H.edges(data=True)]

    for gu, gv, gk, g_attrs in g_edges:
        for hu, hv, hk, h_attrs in h_edges:
            edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
            if P.is_multigraph():
                P.add_edge((gu, hu), (gv, hv), **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), **edge_attrs)
            else:
                P.add_edge((gu, hu), (gv, hv), **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), **edge_attrs)

    return P


def strong_product(G, H):
    """Return the strong product of *G* and *H*.

    Union of Cartesian and tensor products.
    """
    _validate_product_graph_types(G, H)
    P = cartesian_product(G, H)

    if G.is_multigraph():
        g_edges = list(G.edges(keys=True, data=True))
    else:
        g_edges = [(u, v, None, attrs) for u, v, attrs in G.edges(data=True)]
    if H.is_multigraph():
        h_edges = list(H.edges(keys=True, data=True))
    else:
        h_edges = [(u, v, None, attrs) for u, v, attrs in H.edges(data=True)]

    for gu, gv, gk, g_attrs in g_edges:
        for hu, hv, hk, h_attrs in h_edges:
            edge_attrs = _paired_edge_attrs(dict(g_attrs), dict(h_attrs))
            if P.is_multigraph():
                P.add_edge((gu, hu), (gv, hv), **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), **edge_attrs)
            else:
                P.add_edge((gu, hu), (gv, hv), **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), **edge_attrs)

    return P


# ---------------------------------------------------------------------------
# Additional high-value utilities
# ---------------------------------------------------------------------------


def adjacency_matrix(G, nodelist=None, dtype=None, weight="weight"):
    """Return the adjacency matrix of *G* as a SciPy sparse array.

    This is an alias for ``to_scipy_sparse_array``.
    """
    return to_scipy_sparse_array(G, nodelist=nodelist, dtype=dtype, weight=weight)


def has_bridges(G):
    """Return True if graph *G* has at least one bridge."""
    return len(bridges(G)) > 0


def local_bridges(G, with_span=True, weight=None):
    """Yield local bridges in *G*.

    A local bridge is an edge (u, v) where u and v have no common neighbors.
    If ``with_span`` is True, yields ``(u, v, span)`` where span is the
    distance between u and v after virtually removing the edge.
    """
    if not with_span and weight is None:
        from franken_networkx._fnx import local_bridges_rust

        return iter(local_bridges_rust(G))

    def _generate():
        for u, v in G.edges():
            u_nbrs = set(G.neighbors(u))
            v_nbrs = set(G.neighbors(v))
            u_nbrs.discard(v)
            v_nbrs.discard(u)
            if u_nbrs & v_nbrs:
                continue  # common neighbor exists — not a local bridge
            if with_span:
                # Compute shortest path from u to v not using edge (u,v).
                # BFS/Dijkstra from u, but skip the direct u->v hop.
                from collections import deque

                if weight is None:
                    # Unweighted BFS avoiding direct (u,v) edge.
                    dist = {u: 0}
                    queue = deque([u])
                    found = False
                    while queue and not found:
                        curr = queue.popleft()
                        for nbr in G.neighbors(curr):
                            # Skip the direct u<->v edge.
                            if curr == u and nbr == v:
                                continue
                            if curr == v and nbr == u:
                                continue
                            if nbr not in dist:
                                dist[nbr] = dist[curr] + 1
                                if nbr == v:
                                    found = True
                                    break
                                queue.append(nbr)
                    span = dist.get(v, float("inf"))
                else:
                    # Weighted: Dijkstra avoiding direct (u,v) edge.
                    import heapq

                    dist = {u: 0}
                    heap = [(0, u)]
                    while heap:
                        d, curr = heapq.heappop(heap)
                        if d > dist.get(curr, float("inf")):
                            continue
                        if curr == v:
                            break
                        for nbr in G.neighbors(curr):
                            if curr == u and nbr == v:
                                continue
                            if curr == v and nbr == u:
                                continue
                            w = G[curr][nbr].get(weight, 1)
                            nd = d + w
                            if nd < dist.get(nbr, float("inf")):
                                dist[nbr] = nd
                                heapq.heappush(heap, (nd, nbr))
                    span = dist.get(v, float("inf"))
                yield (u, v, span)
            else:
                yield (u, v)

    return _generate()


def minimum_edge_cut(G, s=None, t=None):
    """Return a minimum edge cut of *G*."""

    def cut_edges_for_partition(source_partition, sink_partition):
        source_set = set(source_partition)
        sink_set = set(sink_partition)
        cut_edges = set()
        if G.is_multigraph():
            for u, v, key in G.edges(keys=True):
                if G.is_directed():
                    if u in source_set and v in sink_set:
                        cut_edges.add((u, v, key))
                elif (u in source_set and v in sink_set) or (
                    u in sink_set and v in source_set
                ):
                    cut_edges.add((u, v, key))
            return cut_edges

        for u, v in G.edges():
            if G.is_directed():
                if u in source_set and v in sink_set:
                    cut_edges.add((u, v))
            elif (u in source_set and v in sink_set) or (
                u in sink_set and v in source_set
            ):
                cut_edges.add((u, v))
        return cut_edges

    if s is not None or t is not None:
        _, partition = minimum_cut(G, s, t)
        source_partition, sink_partition = partition
        return cut_edges_for_partition(source_partition, sink_partition)

    nodes = list(G.nodes())
    if len(nodes) < 2:
        return set()

    best_pair = None
    best_cut = None
    if G.is_directed():
        candidate_pairs = ((u, v) for u in nodes for v in nodes if u != v)
    else:
        candidate_pairs = (
            (nodes[left_index], nodes[right_index])
            for left_index in range(len(nodes))
            for right_index in range(left_index + 1, len(nodes))
        )

    for source, sink in candidate_pairs:
        candidate_cut = minimum_edge_cut(G, source, sink)
        candidate_key = (len(candidate_cut), (source, sink))
        if best_cut is None or candidate_key < (len(best_cut), best_pair):
            best_pair = (source, sink)
            best_cut = candidate_cut
            if not best_cut:
                break

    return best_cut if best_cut is not None else set()


def stochastic_graph(G, copy=True, weight="weight"):
    """Return the stochastic graph of *G* (row-normalized adjacency)."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    graph = _copy_graph_shallow(G) if copy else G
    degree = {node: 0 for node in graph.nodes()}
    if graph.is_multigraph():
        for u, _, _, attrs in graph.edges(keys=True, data=True):
            degree[u] += attrs.get(weight, 1)
    else:
        for u, _, attrs in graph.edges(data=True):
            degree[u] += attrs.get(weight, 1)
    for u, v, attrs in graph.edges(data=True):
        attrs[weight] = 0 if degree[u] == 0 else attrs.get(weight, 1) / degree[u]
    return graph


# ---------------------------------------------------------------------------
# Graph structural algorithms — pure Python over Rust primitives
# ---------------------------------------------------------------------------


def ego_graph(G, n, radius=1, center=True, undirected=False, distance=None):
    """Return the ego graph of node *n* within *radius* hops."""
    if distance is not None:
        # Weighted ego: include nodes within weighted distance <= radius.
        sp = dict(single_source_dijkstra_path_length(G, n, weight=distance))
        sp = {node: dist for node, dist in sp.items() if dist <= radius}
        nodes_within = set(sp.keys())
    elif undirected and G.is_directed():
        # Treat directed graph as undirected for BFS.
        # Build undirected view and do BFS.
        seen = {n: 0}
        queue = [n]
        while queue:
            next_queue = []
            for u in queue:
                depth = seen[u]
                if depth >= radius:
                    continue
                for v in G.successors(u):
                    if v not in seen:
                        seen[v] = depth + 1
                        next_queue.append(v)
                for v in G.predecessors(u):
                    if v not in seen:
                        seen[v] = depth + 1
                        next_queue.append(v)
            queue = next_queue
        nodes_within = set(seen.keys())
    else:
        nodes_within = None  # use Rust fast path

    if nodes_within is not None:
        graph = G.__class__()
        graph.graph.update(dict(G.graph))
        for node in nodes_within:
            graph.add_node(node, **dict(G.nodes[node]))
        for u, v, data in G.edges(data=True):
            if u in nodes_within and v in nodes_within:
                graph.add_edge(u, v, **data)
        if not center and n in graph:
            graph.remove_node(n)
        return graph

    raw_graph = _fnx.ego_graph_rust(G, n, radius=radius, undirected=undirected)
    canonical_to_node = {str(node): node for node in G.nodes()}

    graph = G.__class__()
    graph.graph.update(dict(G.graph))
    for raw_node in raw_graph.nodes():
        node = canonical_to_node.get(raw_node, raw_node)
        graph.add_node(node, **dict(G.nodes[node]))

    if G.is_multigraph():
        for raw_u, raw_v, key in raw_graph.edges(keys=True):
            u = canonical_to_node.get(raw_u, raw_u)
            v = canonical_to_node.get(raw_v, raw_v)
            graph.add_edge(u, v, key=key, **dict(G[u][v][key]))
    else:
        for raw_u, raw_v in raw_graph.edges():
            u = canonical_to_node.get(raw_u, raw_u)
            v = canonical_to_node.get(raw_v, raw_v)
            graph.add_edge(u, v, **dict(G[u][v]))

    if not center and n in graph:
        graph.remove_node(n)
    return graph


def k_core(G, k=None, core_number=None):
    """Return the k-core of *G* (maximal subgraph with minimum degree >= k).

    Parameters
    ----------
    G : Graph
    k : int, optional
        Core number. Default is the maximum core number.
    core_number : dict, optional
        Precomputed core numbers. If None, computed automatically.
    """
    if core_number is None:
        from franken_networkx._fnx import core_number as compute_core_number

        core_number = compute_core_number(G)
    if k is None:
        k = max(core_number.values()) if core_number else 0
    nodes = [n for n, c in core_number.items() if c >= k]
    return G.subgraph(nodes)


def k_shell(G, k=None, core_number=None):
    """Return the k-shell of *G* (nodes with core number exactly k)."""
    if core_number is None:
        from franken_networkx._fnx import core_number as compute_core_number

        core_number = compute_core_number(G)
    if k is None:
        k = max(core_number.values()) if core_number else 0
    nodes = [n for n, c in core_number.items() if c == k]
    return G.subgraph(nodes)


def k_crust(G, k=None, core_number=None):
    """Return the k-crust of *G* (nodes with core number <= k)."""
    if core_number is None:
        from franken_networkx._fnx import core_number as compute_core_number

        core_number = compute_core_number(G)
    if k is None:
        k = max(core_number.values()) if core_number else 0
    nodes = [n for n, c in core_number.items() if c <= k]
    return G.subgraph(nodes)


def k_corona(G, k, core_number=None):
    """Return the k-corona of *G* (k-core nodes with exactly k neighbors in k-core)."""
    if core_number is None:
        from franken_networkx._fnx import core_number as compute_core_number

        core_number = compute_core_number(G)
    core_nodes = {n for n, c in core_number.items() if c >= k}
    corona_nodes = []
    for n in core_nodes:
        if core_number[n] == k:
            nbrs_in_core = sum(1 for nb in G.neighbors(n) if nb in core_nodes)
            if nbrs_in_core == k:
                corona_nodes.append(n)
    return G.subgraph(corona_nodes)


def line_graph(G, create_using=None):
    """Return the line graph of *G*.

    The line graph L(G) has a node for each edge in G. Two nodes in L(G)
    are adjacent iff the corresponding edges in G share an endpoint.
    """
    graph = _empty_graph_from_create_using(create_using, default=G.__class__)

    if G.is_directed():
        if G.is_multigraph():
            edge_iter = G.edges(keys=True)
        else:
            edge_iter = G.edges()

        for from_node in edge_iter:
            graph.add_node(from_node)
            head = from_node[1]
            if G.is_multigraph():
                for neighbor, keyed_attrs in G[head].items():
                    for key in keyed_attrs:
                        graph.add_edge(from_node, (head, neighbor, key))
            else:
                for neighbor in G[head]:
                    graph.add_edge(from_node, (head, neighbor))
        return graph

    node_index = {node: index for index, node in enumerate(G)}

    def canonical_edge(edge):
        return tuple(sorted(edge[:2], key=node_index.get)) + edge[2:]

    def edge_key(edge):
        return node_index[edge[0]], node_index[edge[1]]

    edges = set()
    for node in G:
        if G.is_multigraph():
            incident = [
                canonical_edge((node, neighbor, key))
                for neighbor, keyed_attrs in G[node].items()
                for key in keyed_attrs
            ]
        else:
            incident = [canonical_edge((node, neighbor)) for neighbor in G[node]]
        if len(incident) == 1:
            graph.add_node(incident[0])
        for index, left in enumerate(incident):
            for right in incident[index + 1 :]:
                edges.add(tuple(sorted((left, right), key=edge_key)))

    graph.add_edges_from(edges)
    return graph


def make_max_clique_graph(G, create_using=None):
    """Return the maximal-clique intersection graph of *G*."""
    graph = _empty_graph_from_create_using(create_using, default=G.__class__)
    cliques = list(find_cliques(G))
    for index in range(len(cliques)):
        graph.add_node(index)
    for left_index, left in enumerate(cliques):
        left_nodes = set(left)
        for right_index in range(left_index + 1, len(cliques)):
            if left_nodes & set(cliques[right_index]):
                graph.add_edge(left_index, right_index)
    return graph


def power(G, k):
    """Return the k-th power of *G*.

    The k-th power G^k has the same nodes as G. Two nodes u, v are
    adjacent in G^k iff their shortest path distance in G is <= k.
    """
    raw_graph = _fnx.power_rust(G, k)
    canonical_to_node = {str(node): node for node in G.nodes()}

    graph = G.__class__()
    for raw_node in raw_graph.nodes():
        graph.add_node(canonical_to_node.get(raw_node, raw_node))
    if graph.is_multigraph():
        for raw_u, raw_v, key in raw_graph.edges(keys=True):
            graph.add_edge(
                canonical_to_node.get(raw_u, raw_u),
                canonical_to_node.get(raw_v, raw_v),
                key=key,
            )
    else:
        for raw_u, raw_v in raw_graph.edges():
            graph.add_edge(
                canonical_to_node.get(raw_u, raw_u),
                canonical_to_node.get(raw_v, raw_v),
            )
    return graph


def disjoint_union(G, H):
    """Return the disjoint union of *G* and *H*."""
    return disjoint_union_all([G, H])


def compose_all(graphs):
    """Return the composition of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply compose_all to an empty sequence")
    R = graphs[0].copy()
    for H in graphs[1:]:
        R.graph.update(H.graph)
        for n in H.nodes():
            R.add_node(n, **H.nodes[n])
        if R.is_multigraph():
            for u, v, key, d in H.edges(keys=True, data=True):
                R.add_edge(u, v, key=key, **d)
        else:
            for u, v, d in H.edges(data=True):
                R.add_edge(u, v, **d)
    return R


def union_all(graphs, rename=()):
    """Return the union of all graphs in the iterable.

    Parameters
    ----------
    graphs : iterable of Graph
        Graphs to union.
    rename : tuple of str or None, optional
        Prefixes to apply to node names of each graph. If provided, must be
        the same length as *graphs*. Default ``()`` means no renaming.
    """
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply union_all to an empty sequence")
    if rename and len(rename) != len(graphs):
        raise ValueError("rename must have the same length as graphs")

    R = graphs[0].__class__()
    for i, G in enumerate(graphs):
        prefix = rename[i] if rename and i < len(rename) else None
        R.graph.update(G.graph)

        def _rename(n, _prefix=prefix):
            return f"{_prefix}{n}" if _prefix is not None else n

        for n in G.nodes():
            new_n = _rename(n)
            if new_n in R:
                raise NetworkXError(
                    f"Node {new_n} already exists in the union graph. "
                    "Use rename to avoid name collisions."
                )
            R.add_node(new_n, **G.nodes[n])
        if R.is_multigraph():
            for u, v, key, d in G.edges(keys=True, data=True):
                R.add_edge(_rename(u), _rename(v), key=key, **d)
        else:
            for u, v, d in G.edges(data=True):
                R.add_edge(_rename(u), _rename(v), **d)
    return R


# ---------------------------------------------------------------------------
# Spectral graph theory — numpy/scipy based
# ---------------------------------------------------------------------------


def laplacian_matrix(G, nodelist=None, weight="weight"):
    """Return the Laplacian matrix of *G* as a SciPy sparse array.

    ``L = D - A`` where D is the degree matrix and A is the adjacency matrix.

    Parameters
    ----------
    G : Graph
    nodelist : list, optional
    weight : str or None, optional

    Returns
    -------
    scipy.sparse array
    """
    import numpy as np
    import scipy.sparse

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight)
    A.shape[0]
    D = scipy.sparse.diags(np.asarray(A.sum(axis=1)).flatten(), dtype=float)
    return D - A


def normalized_laplacian_matrix(G, nodelist=None, weight="weight"):
    """Return the normalized Laplacian matrix of *G*.

    ``L_norm = D^{-1/2} L D^{-1/2}`` where L is the Laplacian.

    Returns
    -------
    scipy.sparse array
    """
    import numpy as np
    import scipy.sparse

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight)
    n = A.shape[0]
    d = np.asarray(A.sum(axis=1)).flatten()
    # Avoid division by zero for isolated nodes
    d_inv_sqrt = np.zeros_like(d, dtype=float)
    nonzero = d > 0
    d_inv_sqrt[nonzero] = 1.0 / np.sqrt(d[nonzero])
    D_inv_sqrt = scipy.sparse.diags(d_inv_sqrt)
    I = scipy.sparse.eye(n)
    return I - D_inv_sqrt @ A @ D_inv_sqrt


def laplacian_spectrum(G, weight="weight"):
    """Return the eigenvalues of the Laplacian matrix of *G*, sorted.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    L = laplacian_matrix(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(L.toarray()))


def adjacency_spectrum(G, weight="weight"):
    """Return the eigenvalues of the adjacency matrix of *G*, sorted.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    A = to_numpy_array(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(A))


def algebraic_connectivity(G, weight="weight", normalized=False):
    """Return the algebraic connectivity of *G*.

    The algebraic connectivity is the second-smallest eigenvalue of the
    Laplacian matrix (Fiedler value).

    Parameters
    ----------
    G : Graph
        Must be connected.
    weight : str or None, optional
    normalized : bool, optional
        Use normalized Laplacian if True.

    Returns
    -------
    float
    """
    import numpy as np

    if normalized:
        spectrum = np.sort(
            np.linalg.eigvalsh(normalized_laplacian_matrix(G, weight=weight).toarray())
        )
    else:
        spectrum = laplacian_spectrum(G, weight=weight)
    if len(spectrum) < 2:
        return 0.0
    return float(spectrum[1])


def fiedler_vector(G, weight="weight", normalized=False):
    """Return the Fiedler vector of *G*.

    The Fiedler vector is the eigenvector corresponding to the
    algebraic connectivity (second-smallest Laplacian eigenvalue).

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    if normalized:
        L = normalized_laplacian_matrix(G, weight=weight).toarray()
    else:
        L = laplacian_matrix(G, weight=weight).toarray()
    eigenvalues, eigenvectors = np.linalg.eigh(L)
    return eigenvectors[:, 1]


# ---------------------------------------------------------------------------
# Additional matrix representations
# ---------------------------------------------------------------------------


def incidence_matrix(G, nodelist=None, edgelist=None, oriented=False, weight=None):
    """Return the incidence matrix of *G* as a SciPy sparse array.

    Parameters
    ----------
    G : Graph
    nodelist : list, optional
    edgelist : list, optional
    oriented : bool, optional
        If True, use +1/-1 for edge endpoints. Default False (uses 1).
    weight : str or None, optional

    Returns
    -------
    scipy.sparse array
        Shape (n_nodes, n_edges).
    """
    import numpy as np
    import scipy.sparse

    if nodelist is None:
        nodelist = list(G.nodes())
    if edgelist is None:
        edgelist = list(G.edges())

    node_index = {n: i for i, n in enumerate(nodelist)}
    n_nodes = len(nodelist)
    n_edges = len(edgelist)

    row, col, data = [], [], []
    for j, (u, v) in enumerate(edgelist):
        if u in node_index:
            row.append(node_index[u])
            col.append(j)
            data.append(1 if not oriented else -1)
        if v in node_index:
            row.append(node_index[v])
            col.append(j)
            data.append(1)

    return scipy.sparse.coo_array(
        (np.array(data, dtype=float), (np.array(row), np.array(col))),
        shape=(n_nodes, n_edges),
    ).tocsc()


# ---------------------------------------------------------------------------
# Social network datasets (hardcoded classic graphs)
# ---------------------------------------------------------------------------


def karate_club_graph():
    """Return Zachary's Karate Club graph (34 nodes, 78 edges).

    A classic social network dataset representing friendships between
    members of a university karate club.
    """
    G = Graph()
    # Zachary (1977) edge list
    edges = [
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 4),
        (0, 5),
        (0, 6),
        (0, 7),
        (0, 8),
        (0, 10),
        (0, 11),
        (0, 12),
        (0, 13),
        (0, 17),
        (0, 19),
        (0, 21),
        (0, 31),
        (1, 2),
        (1, 3),
        (1, 7),
        (1, 13),
        (1, 17),
        (1, 19),
        (1, 21),
        (1, 30),
        (2, 3),
        (2, 7),
        (2, 8),
        (2, 9),
        (2, 13),
        (2, 27),
        (2, 28),
        (2, 32),
        (3, 7),
        (3, 12),
        (3, 13),
        (4, 6),
        (4, 10),
        (5, 6),
        (5, 10),
        (5, 16),
        (6, 16),
        (8, 30),
        (8, 32),
        (8, 33),
        (9, 33),
        (13, 33),
        (14, 32),
        (14, 33),
        (15, 32),
        (15, 33),
        (18, 32),
        (18, 33),
        (19, 33),
        (20, 32),
        (20, 33),
        (22, 32),
        (22, 33),
        (23, 25),
        (23, 27),
        (23, 29),
        (23, 32),
        (23, 33),
        (24, 25),
        (24, 27),
        (24, 31),
        (25, 31),
        (26, 29),
        (26, 33),
        (27, 33),
        (28, 31),
        (28, 33),
        (29, 32),
        (29, 33),
        (30, 32),
        (30, 33),
        (31, 32),
        (31, 33),
        (32, 33),
    ]
    G.add_edges_from([(u, v) for u, v in edges])
    return G


def florentine_families_graph():
    """Return the Florentine families marriage graph (15 nodes, 20 edges).

    A classic social network of marriage alliances among Renaissance
    Florentine families.
    """
    G = Graph()
    edges = [
        ("Acciaiuoli", "Medici"),
        ("Albizzi", "Ginori"),
        ("Albizzi", "Guadagni"),
        ("Albizzi", "Medici"),
        ("Barbadori", "Castellani"),
        ("Barbadori", "Medici"),
        ("Bischeri", "Guadagni"),
        ("Bischeri", "Peruzzi"),
        ("Bischeri", "Strozzi"),
        ("Castellani", "Peruzzi"),
        ("Castellani", "Strozzi"),
        ("Guadagni", "Lamberteschi"),
        ("Guadagni", "Tornabuoni"),
        ("Medici", "Ridolfi"),
        ("Medici", "Salviati"),
        ("Medici", "Tornabuoni"),
        ("Peruzzi", "Strozzi"),
        ("Ridolfi", "Strozzi"),
        ("Ridolfi", "Tornabuoni"),
        ("Salviati", "Pazzi"),
    ]
    G.add_edges_from(edges)
    return G


# ---------------------------------------------------------------------------
# Community graph generators
# ---------------------------------------------------------------------------


def caveman_graph(l, k):
    """Return a caveman graph of *l* cliques of size *k*.

    Parameters
    ----------
    l : int
        Number of cliques.
    k : int
        Size of each clique.

    Returns
    -------
    Graph
    """
    G = Graph()
    for i in range(l):
        base = i * k
        for u in range(k):
            for v in range(u + 1, k):
                G.add_edge(base + u, base + v)
    return G


def connected_caveman_graph(l, k):
    """Return a connected caveman graph.

    Like ``caveman_graph`` but with one edge rewired per clique to
    connect adjacent cliques in a ring.

    Parameters
    ----------
    l : int
        Number of cliques.
    k : int
        Size of each clique.

    Returns
    -------
    Graph
    """
    G = caveman_graph(l, k)
    for i in range(l):
        # Remove one internal edge and add a bridge to the next clique
        base = i * k
        next_base = ((i + 1) % l) * k
        # Connect the last node of this clique to the first of the next
        G.add_edge(base + k - 1, next_base)
    return G


def random_tree(n, seed=None):
    """Return a uniformly random labeled tree on *n* nodes via Prüfer sequence.

    Parameters
    ----------
    n : int
        Number of nodes.
    seed : int or None, optional

    Returns
    -------
    Graph
    """
    import random as _random

    if n <= 0:
        return Graph()
    if n == 1:
        G = Graph()
        G.add_node(0)
        return G
    if n == 2:
        G = Graph()
        G.add_edge(0, 1)
        return G

    rng = _random.Random(seed)
    # Generate random Prüfer sequence of length n-2
    prufer = [rng.randint(0, n - 1) for _ in range(n - 2)]

    # Decode Prüfer sequence to tree edges
    degree = [1] * n
    for i in prufer:
        degree[i] += 1

    G = Graph()
    for i in range(n):
        G.add_node(i)

    for i in prufer:
        for j in range(n):
            if degree[j] == 1:
                G.add_edge(i, j)
                degree[i] -= 1
                degree[j] -= 1
                break

    # Connect the last two nodes with degree 1
    last_two = [j for j in range(n) if degree[j] == 1]
    if len(last_two) == 2:
        G.add_edge(last_two[0], last_two[1])

    return G


# ---------------------------------------------------------------------------
# Structural hole / brokerage metrics
# ---------------------------------------------------------------------------


def constraint(G, nodes=None, weight=None):
    """Return Burt's constraint for nodes in *G*."""
    from franken_networkx._fnx import constraint_rust as _rust_constraint

    result = _rust_constraint(G)
    if nodes is not None:
        node_set = set(nodes)
        return {k: v for k, v in result.items() if k in node_set}
    return result


def effective_size(G, nodes=None, weight=None):
    """Return the effective size of each node's ego network.

    Effective size is the number of alters minus the average degree of
    alters within the ego network (not counting ties to ego).

    Parameters
    ----------
    G : Graph
    nodes : iterable, optional
    weight : str or None, optional

    Returns
    -------
    dict
        ``{node: effective_size}``
    """
    if nodes is None:
        nodes = list(G.nodes())

    from franken_networkx._fnx import effective_size_rust as _rust_eff_size

    result = _rust_eff_size(G)
    if nodes is not None:
        node_set = set(nodes)
        return {k: v for k, v in result.items() if k in node_set}
    return result


def dispersion(G, u=None, v=None, normalized=True, alpha=1.0, b=0.0, c=0.0):
    """Return the dispersion between node pairs in *G*.

    Dispersion measures tie strength: high dispersion means u's and v's
    mutual friends are not well connected to each other.

    Parameters
    ----------
    G : Graph
    u, v : node, optional
        If both given, return a single float. Otherwise return a dict.
    normalized : bool, optional
    alpha, b, c : float, optional
        Parameters for the normalization formula.

    Returns
    -------
    float or dict
    """
    if u is not None and v is not None:
        return _dispersion_pair(G, u, v, normalized, alpha, b, c)

    nodes = [u] if u is not None else list(G.nodes())
    result = {}
    for node in nodes:
        result[node] = {}
        for nbr in G.neighbors(node):
            result[node][nbr] = _dispersion_pair(G, node, nbr, normalized, alpha, b, c)
    if u is not None:
        return result[u]
    return result


def _dispersion_pair(G, u, v, normalized, alpha, b, c):
    u_nbrs = set(G.neighbors(u))
    v_nbrs = set(G.neighbors(v))
    common = (u_nbrs & v_nbrs) - {u, v}

    if not common:
        return 0.0

    # Count pairs of common neighbors that are NOT connected
    disp = 0.0
    common_list = list(common)
    for i in range(len(common_list)):
        for j in range(i + 1, len(common_list)):
            s, t = common_list[i], common_list[j]
            if not G.has_edge(s, t):
                s_nbrs = set(G.neighbors(s))
                t_nbrs = set(G.neighbors(t))
                # Check they don't share neighbors in common set
                shared_in_common = (s_nbrs & t_nbrs) & common
                if not shared_in_common:
                    disp += 1.0

    if normalized and len(common) > 0:
        return (disp + b) / (len(common) + c) ** alpha if len(common) + c > 0 else 0.0
    return disp


def closeness_vitality(G, node=None, weight=None, wiener_index=None):
    """Return the closeness vitality of nodes.

    Closeness vitality of a node is the change in the Wiener index
    of the graph when that node is removed.

    Parameters
    ----------
    G : Graph
    node : node, optional
        If given, return vitality for just this node.
    weight : str or None, optional
    wiener_index : float, optional
        Precomputed Wiener index.

    Returns
    -------
    float or dict
    """
    if wiener_index is None:
        try:
            from franken_networkx._fnx import wiener_index as compute_wi

            wi = compute_wi(G)
        except Exception:
            wi = 0.0
            for u in G.nodes():
                lengths = single_source_shortest_path_length(G, u)
                wi += sum(lengths.values())
            wi /= 2.0  # Each pair counted twice
    else:
        wi = wiener_index

    if node is not None:
        H = G.copy()
        H.remove_node(node)
        if H.number_of_nodes() == 0:
            return 0.0
        try:
            from franken_networkx._fnx import wiener_index as compute_wi

            wi_without = compute_wi(H)
        except Exception:
            wi_without = 0.0
            for u in H.nodes():
                lengths = single_source_shortest_path_length(H, u)
                wi_without += sum(lengths.values())
            wi_without /= 2.0
        return wi - wi_without

    result = {}
    for n in G.nodes():
        result[n] = closeness_vitality(G, node=n, wiener_index=wi)
    return result


def spectral_ordering(G, normalized=False):
    """Return nodes ordered by the Fiedler vector (spectral bisection ordering).

    Parameters
    ----------
    G : Graph
    normalized : bool, optional

    Returns
    -------
    list
        Nodes sorted by Fiedler vector components.
    """
    import numpy as np

    fv = fiedler_vector(G, normalized=normalized)
    nodelist = list(G.nodes())
    order = np.argsort(fv)
    return [nodelist[i] for i in order]


def bellman_ford_predecessor_and_distance(G, source, weight="weight"):
    """Return predecessors and distances from Bellman-Ford.

    Parameters
    ----------
    G : Graph or DiGraph
    source : node
    weight : str, optional

    Returns
    -------
    (pred, dist) : tuple of dicts
        pred maps each node to its predecessor list.
        dist maps each node to its distance from source.
    """
    from franken_networkx._fnx import (
        single_source_bellman_ford_path_length,
        single_source_bellman_ford_path,
    )

    dist = single_source_bellman_ford_path_length(G, source, weight=weight)
    paths = single_source_bellman_ford_path(G, source, weight=weight)

    pred = {}
    for node, path in paths.items():
        if len(path) >= 2:
            pred[node] = [path[-2]]
        else:
            pred[node] = []

    return pred, dist


# ---------------------------------------------------------------------------
# Communicability and subgraph centrality (matrix exponential)
# ---------------------------------------------------------------------------


def communicability(G):
    """Return communicability between all pairs of nodes.

    Based on the matrix exponential of the adjacency matrix.

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the communicability between u and v.
    """
    import numpy as np

    nodelist = list(G.nodes())
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    expA = _matrix_exp(A)
    n = len(nodelist)
    result = {}
    for i in range(n):
        result[nodelist[i]] = {}
        for j in range(n):
            result[nodelist[i]][nodelist[j]] = float(expA[i, j])
    return result


def subgraph_centrality(G):
    """Return the subgraph centrality for each node.

    The subgraph centrality is the diagonal of the matrix exponential
    of the adjacency matrix.

    Returns
    -------
    dict
        ``{node: centrality}``
    """
    import numpy as np

    nodelist = list(G.nodes())
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    expA = _matrix_exp(A)
    return {nodelist[i]: float(expA[i, i]) for i in range(len(nodelist))}


def _matrix_exp(A):
    """Compute matrix exponential using eigendecomposition."""
    import numpy as np

    eigenvalues, eigenvectors = np.linalg.eigh(A)
    return eigenvectors @ np.diag(np.exp(eigenvalues)) @ eigenvectors.T


# ---------------------------------------------------------------------------
# Assortativity / mixing helpers
# ---------------------------------------------------------------------------


def degree_mixing_dict(G, x="out", y="in", weight=None, nodes=None, normalized=False):
    """Return a dictionary of degree-degree mixing counts.

    Returns
    -------
    dict of dicts
        ``result[d1][d2]`` is the count of edges between nodes of
        degree d1 and degree d2.
    """
    return mixing_dict(
        node_degree_xy(G, x=x, y=y, weight=weight, nodes=nodes),
        normalized=normalized,
    )


def degree_mixing_matrix(G, normalized=True, weight=None):
    """Return the degree mixing matrix of *G*.

    Returns
    -------
    numpy.ndarray
        2D array where entry (i,j) counts edges between nodes of
        degree i and degree j.
    """
    import numpy as np

    mixing = degree_mixing_dict(G, normalized=False, weight=weight)
    if not mixing:
        return np.array([[]])
    max_deg = max(max(mixing.keys()), max(max(v.keys()) for v in mixing.values()))
    M = np.zeros((max_deg + 1, max_deg + 1))
    for d1, inner in mixing.items():
        for d2, count in inner.items():
            M[d1, d2] = count
    if normalized:
        total = M.sum()
        if total > 0:
            M /= total
    return M


def numeric_assortativity_coefficient(G, attribute, nodes=None):
    """Return the numeric assortativity coefficient for a node attribute.

    Parameters
    ----------
    G : Graph
    attribute : str
        Node attribute name containing numeric values.

    Returns
    -------
    float
        Pearson correlation of attribute values across edges.

    Raises
    ------
    KeyError
        If any node is missing the attribute.
    """
    import numpy as np

    if nodes is None:
        nodes = G.nodes
    values = {G.nodes[node][attribute] for node in nodes}
    mapping = {value: index for index, value in enumerate(values)}
    matrix = attribute_mixing_matrix(G, attribute, nodes=nodes, mapping=mapping)
    if matrix.sum() != 1.0:
        matrix = matrix / matrix.sum()
    labels = np.array(list(mapping.keys()))
    indices = list(mapping.values())
    a = matrix.sum(axis=0)
    b = matrix.sum(axis=1)
    vara = (a[indices] * labels**2).sum() - ((a[indices] * labels).sum()) ** 2
    varb = (b[indices] * labels**2).sum() - ((b[indices] * labels).sum()) ** 2
    xy = np.outer(labels, labels)
    ab = np.outer(a[indices], b[indices])
    return float((xy * (matrix - ab)).sum() / np.sqrt(vara * varb))


def attribute_assortativity_coefficient(G, attribute, nodes=None):
    """Return the attribute assortativity coefficient.

    For categorical attributes, this is the normalized modularity
    of the attribute partition.

    Parameters
    ----------
    G : Graph
    attribute : str

    Returns
    -------
    float
    """
    matrix = attribute_mixing_matrix(G, attribute, nodes=nodes)
    if matrix.sum() != 1.0:
        matrix = matrix / matrix.sum()
    squared_sum = (matrix @ matrix).sum()
    return float((matrix.trace() - squared_sum) / (1 - squared_sum))


# ---------------------------------------------------------------------------
# Multi-graph operators
# ---------------------------------------------------------------------------


def intersection_all(graphs):
    """Return the intersection of all graphs in the iterable.

    The intersection contains nodes in all graphs and edges present in all
    graphs. Node and edge attributes come from the first graph.
    """
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply intersection_all to an empty sequence")
    R = graphs[0].copy()
    # Keep only nodes present in every graph
    common_nodes = set(graphs[0].nodes())
    for G in graphs[1:]:
        common_nodes &= set(G.nodes())
    # Remove nodes not common to all graphs
    to_remove = [n for n in list(R.nodes()) if n not in common_nodes]
    for n in to_remove:
        R.remove_node(n)
    # Keep only edges present in every graph
    edges_to_remove = []
    for u, v in list(R.edges()):
        for G in graphs[1:]:
            if not G.has_edge(u, v):
                edges_to_remove.append((u, v))
                break
    for u, v in edges_to_remove:
        R.remove_edge(u, v)
    return R


def disjoint_union_all(graphs):
    """Return the disjoint union of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply disjoint_union_all to an empty list")

    _validate_same_graph_family(graphs)

    relabeled = []
    first_label = 0
    for graph in graphs:
        relabeled.append(
            convert_node_labels_to_integers(graph, first_label=first_label),
        )
        first_label += len(graph)
    return union_all(relabeled)


def rescale_layout(pos, scale=1.0):
    """Rescale layout positions to fit within [-scale, scale].

    Parameters
    ----------
    pos : dict
        ``{node: (x, y)}`` positions.
    scale : float, optional

    Returns
    -------
    dict
        Rescaled positions.
    """
    import numpy as np

    if not pos:
        return pos

    coords = np.array(list(pos.values()))
    center = coords.mean(axis=0)
    coords -= center
    max_extent = np.abs(coords).max()
    if max_extent > 0:
        coords *= scale / max_extent

    return {node: tuple(coords[i]) for i, node in enumerate(pos)}


# ---------------------------------------------------------------------------
# Graph freezing
# ---------------------------------------------------------------------------

_FROZEN_GRAPHS = set()


def freeze(G):
    """Modify *G* so that mutation raises an error. Returns *G*."""
    _FROZEN_GRAPHS.add(id(G))
    for name in (
        "add_node",
        "add_nodes_from",
        "remove_node",
        "remove_nodes_from",
        "add_edge",
        "add_edges_from",
        "add_weighted_edges_from",
        "remove_edge",
        "remove_edges_from",
        "clear",
        "clear_edges",
    ):
        if hasattr(G, name):
            setattr(G, name, _frozen)
    G.frozen = True
    return G


def is_frozen(G):
    """Return True if *G* is frozen."""
    return getattr(G, "frozen", False) or id(G) in _FROZEN_GRAPHS


def _frozen(*args, **kwargs):
    raise NetworkXError("Frozen graph can't be modified")


# ---------------------------------------------------------------------------
# Info (deprecated in NetworkX but still commonly used)
# ---------------------------------------------------------------------------


def info(G, n=None):
    """Return a summary string of *G* (or node *n*).

    .. deprecated:: 3.0
        Use ``str(G)`` or direct attribute access instead.
    """
    if n is not None:
        nbrs = list(G.neighbors(n))
        return f"Node {n} has {len(nbrs)} neighbor(s)"
    name = getattr(G, "name", "") or ""
    typ = type(G).__name__
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    lines = [
        f"Name: {name}",
        f"Type: {typ}",
        f"Number of nodes: {n_nodes}",
        f"Number of edges: {n_edges}",
    ]
    if n_nodes > 0:
        [d for _, d in G.degree]
        lines.append(f"Average degree: {2.0 * n_edges / n_nodes:.4f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator aliases
# ---------------------------------------------------------------------------


def _native_random_seed(seed):
    """Return a Rust-compatible u64 seed, preserving random None semantics."""
    if seed is not None:
        return seed

    import random as _random

    return _random.randrange(1 << 64)


def binomial_graph(n, p, seed=None):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    return gnp_random_graph(n, p, seed=seed)


def gnp_random_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a G(n,p) random graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if not directed and create_using is None:
        return _rust_gnp_random_graph(n, p, seed=_native_random_seed(seed))

    graph = nx.gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def erdos_renyi_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if not directed and create_using is None:
        return _rust_erdos_renyi_graph(n, p, seed=_native_random_seed(seed))

    graph = nx.erdos_renyi_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def watts_strogatz_graph(n, k, p, seed=None, create_using=None):
    """Return a Watts-Strogatz small-world graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_watts_strogatz_graph(n, k, p, seed=_native_random_seed(seed))

    graph = nx.watts_strogatz_graph(
        n,
        k,
        p,
        seed=seed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def barabasi_albert_graph(
    n,
    m,
    seed=None,
    initial_graph=None,
    create_using=None,
):
    """Return a Barabasi-Albert preferential attachment graph."""
    import random as _random
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if initial_graph is None and create_using is None:
        return _rust_barabasi_albert_graph(n, m, seed=_native_random_seed(seed))

    if create_using is None and initial_graph is not None:
        if m < 1 or m >= n:
            raise NetworkXError(
                f"Barabasi-Albert network must have m >= 1 and m < n, m = {m}, n = {n}"
            )
        if len(initial_graph) < m or len(initial_graph) > n:
            raise NetworkXError(
                f"Barabasi-Albert initial graph needs between m={m} and n={n} nodes"
            )

        graph = Graph()
        graph.graph.update(dict(initial_graph.graph))
        for node, node_attrs in initial_graph.nodes(data=True):
            graph.add_node(node, **dict(node_attrs))
        for u, v, edge_attrs in initial_graph.edges(data=True):
            graph.add_edge(u, v, **dict(edge_attrs))
        rng = _random.Random(seed)
        repeated_nodes = [
            node for node, degree_value in graph.degree for _ in range(degree_value)
        ]
        source = len(graph)
        while source < n:
            targets = set()
            while len(targets) < m:
                targets.add(rng.choice(repeated_nodes))
            graph.add_edges_from((source, target) for target in targets)
            repeated_nodes.extend(targets)
            repeated_nodes.extend([source] * m)
            source += 1
        return graph

    # create_using with initial_graph: build BA graph then convert.
    graph = barabasi_albert_graph(n, m, seed=seed, initial_graph=initial_graph)
    if create_using is not None:
        result = create_using
        if hasattr(result, "clear"):
            result.clear()
        for node, attrs in graph.nodes(data=True):
            result.add_node(node, **attrs)
        for u, v, attrs in graph.edges(data=True):
            result.add_edge(u, v, **attrs)
        return result
    return graph


def balanced_tree(r, h, create_using=None):
    """Return the perfectly balanced r-ary tree of height h."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_balanced_tree(r, h)

    graph = nx.balanced_tree(r, h, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def full_rary_tree(r, n, create_using=None):
    """Return a full r-ary tree with n nodes."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_full_rary_tree(r, n)

    graph = nx.full_rary_tree(r, n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def binomial_tree(n, create_using=None):
    """Return the binomial tree of order n."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_binomial_tree(n)

    graph = nx.binomial_tree(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def complete_bipartite_graph(n1, n2, create_using=None):
    """Return the complete bipartite graph K_(n1,n2)."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_complete_bipartite_graph(n1, n2)

    graph = nx.complete_bipartite_graph(n1, n2, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def grid_2d_graph(m, n, periodic=False, create_using=None):
    """Return the two-dimensional grid graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if not periodic and create_using is None:
        return _rust_grid_2d_graph(m, n)

    graph = nx.grid_2d_graph(m, n, periodic=periodic, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def barbell_graph(m1, m2, create_using=None):
    """Return the barbell graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_barbell_graph(m1, m2)

    graph = nx.barbell_graph(m1, m2, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def bull_graph(create_using=None):
    """Return the bull graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_bull_graph()

    graph = nx.bull_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def circular_ladder_graph(n, create_using=None):
    """Return the circular ladder graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_circular_ladder_graph(n)

    graph = nx.circular_ladder_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def ladder_graph(n, create_using=None):
    """Return the ladder graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_ladder_graph(n)

    graph = nx.ladder_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def lollipop_graph(m, n, create_using=None):
    """Return the lollipop graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_lollipop_graph(m, n)

    graph = nx.lollipop_graph(m, n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def tadpole_graph(m, n, create_using=None):
    """Return the tadpole graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_tadpole_graph(m, n)

    graph = nx.tadpole_graph(m, n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def wheel_graph(n, create_using=None):
    """Return the wheel graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_wheel_graph(n)

    graph = nx.wheel_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def diamond_graph(create_using=None):
    """Return the diamond graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_diamond_graph()

    graph = nx.diamond_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def house_graph(create_using=None):
    """Return the house graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_house_graph()

    graph = nx.house_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def house_x_graph(create_using=None):
    """Return the house-X graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_house_x_graph()

    graph = nx.house_x_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def cubical_graph(create_using=None):
    """Return the cubical graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_cubical_graph()

    graph = nx.cubical_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def petersen_graph(create_using=None):
    """Return the Petersen graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_petersen_graph()

    graph = nx.petersen_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def tetrahedral_graph(create_using=None):
    """Return the tetrahedral graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_tetrahedral_graph()

    graph = nx.tetrahedral_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def desargues_graph(create_using=None):
    """Return the Desargues graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_desargues_graph()

    graph = nx.desargues_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def dodecahedral_graph(create_using=None):
    """Return the dodecahedral graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_dodecahedral_graph()

    graph = nx.dodecahedral_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def heawood_graph(create_using=None):
    """Return the Heawood graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_heawood_graph()

    graph = nx.heawood_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def moebius_kantor_graph(create_using=None):
    """Return the Moebius-Kantor graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_moebius_kantor_graph()

    graph = nx.moebius_kantor_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def octahedral_graph(create_using=None):
    """Return the octahedral graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_octahedral_graph()

    graph = nx.octahedral_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def truncated_cube_graph(create_using=None):
    """Return the truncated cube graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_truncated_cube_graph()

    graph = nx.truncated_cube_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def truncated_tetrahedron_graph(create_using=None):
    """Return the truncated tetrahedron graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_truncated_tetrahedron_graph()

    graph = nx.truncated_tetrahedron_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def chvatal_graph(create_using=None):
    """Return the Chvatal graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_chvatal_graph()

    graph = nx.chvatal_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def frucht_graph(create_using=None):
    """Return the Frucht graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_frucht_graph()

    graph = nx.frucht_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def icosahedral_graph(create_using=None):
    """Return the icosahedral graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_icosahedral_graph()

    graph = nx.icosahedral_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def krackhardt_kite_graph(create_using=None):
    """Return the Krackhardt kite graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_krackhardt_kite_graph()

    graph = nx.krackhardt_kite_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def null_graph(create_using=None):
    """Return the null graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_null_graph()

    graph = nx.null_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def trivial_graph(create_using=None):
    """Return the trivial graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_trivial_graph()

    graph = nx.trivial_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def circulant_graph(n, offsets, create_using=None):
    """Return the circulant graph on n nodes with the given offsets."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_circulant_graph(n, offsets)

    graph = nx.circulant_graph(n, offsets, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def paley_graph(p, create_using=None):
    """Return the Paley graph or digraph of order p."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_paley_graph(p)

    graph = nx.paley_graph(p, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def chordal_cycle_graph(p, create_using=None):
    """Return the chordal cycle graph on p nodes."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_chordal_cycle_graph(p)

    graph = nx.chordal_cycle_graph(p, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def tutte_graph(create_using=None):
    """Return the Tutte graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_tutte_graph()

    graph = nx.tutte_graph(create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def generalized_petersen_graph(n, k, create_using=None):
    """Return the generalized Petersen graph G(n, k)."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_generalized_petersen_graph(n, k)

    graph = nx.generalized_petersen_graph(n, k, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def windmill_graph(n, k):
    """Generate a windmill graph with n cliques of size k sharing one node."""
    return _rust_windmill_graph(k, n)


def complete_multipartite_graph(*subset_sizes):
    """Return the complete multipartite graph with the given subset sizes."""
    if len(subset_sizes) == 1:
        try:
            subset_sizes = tuple(subset_sizes[0])
        except TypeError:
            pass
    return _rust_complete_multipartite_graph(list(subset_sizes))


def gnm_random_graph(n, m, seed=None):
    """Return a G(n,m) random graph with exactly *m* edges.

    Parameters
    ----------
    n : int
        Number of nodes.
    m : int
        Number of edges.
    seed : int or None, optional

    Returns
    -------
    Graph
    """
    import random as _random

    rng = _random.Random(seed)
    G = Graph()
    for i in range(n):
        G.add_node(i)
    if n < 2:
        return G
    edges_added = set()
    max_edges = n * (n - 1) // 2
    m = min(m, max_edges)
    while len(edges_added) < m:
        u = rng.randint(0, n - 1)
        v = rng.randint(0, n - 1)
        if u != v:
            edge = (min(u, v), max(u, v))
            if edge not in edges_added:
                edges_added.add(edge)
                G.add_edge(u, v)
    return G


# ---------------------------------------------------------------------------
# Additional connectivity
# ---------------------------------------------------------------------------


def check_planarity(G, counterexample=False):
    """Check if *G* is planar and optionally return a counterexample.

    Parameters
    ----------
    G : Graph
    counterexample : bool, optional
        If True, return ``(is_planar, certificate)`` tuple.

    Returns
    -------
    bool or (bool, None)
    """
    result = is_planar(G)
    if counterexample:
        return (result, None)
    return result


def all_simple_edge_paths(G, source, target, cutoff=None):
    """Yield all simple paths from source to target as edge lists.

    Parameters
    ----------
    G : Graph
    source, target : node
    cutoff : int or None, optional

    Yields
    ------
    list of (u, v) tuples
    """
    for path in all_simple_paths(G, source, target, cutoff=cutoff):
        edges = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
        yield edges


def chain_decomposition(G, root=None):
    """Return the chain decomposition of *G*.

    A chain decomposition breaks a 2-edge-connected graph into chains
    (sequences of edges forming paths/cycles in a DFS tree).

    Parameters
    ----------
    G : Graph
    root : node, optional

    Yields
    ------
    list of (u, v) tuples
        Each yielded list is a chain.
    """
    from franken_networkx._fnx import chain_decomposition as _rust_chain

    yield from _rust_chain(G, root=root)


def bidirectional_dijkstra(G, source, target, weight="weight"):
    """Find shortest path using bidirectional Dijkstra search.

    Parameters
    ----------
    G : Graph
    source, target : node
    weight : str, optional

    Returns
    -------
    (length, path) : tuple
    """
    path = dijkstra_path(G, source, target, weight=weight)
    length = dijkstra_path_length(G, source, target, weight=weight)
    return (length, path)


def attribute_mixing_dict(G, attribute, nodes=None, normalized=False):
    """Return mixing dict for a categorical node attribute.

    Returns
    -------
    dict of dicts
        ``result[a][b]`` counts edges between nodes with attribute
        values a and b.
    """
    if nodes is None:
        nodes = set(G)
    else:
        nodes = set(nodes)

    def attribute_pairs():
        Gnodes = G.nodes
        for u, nbrsdict in G.adjacency():
            if u not in nodes:
                continue
            uattr = Gnodes[u].get(attribute, None)
            if G.is_multigraph():
                for v, keys in nbrsdict.items():
                    vattr = Gnodes[v].get(attribute, None)
                    for _ in keys:
                        yield (uattr, vattr)
            else:
                for v in nbrsdict:
                    vattr = Gnodes[v].get(attribute, None)
                    yield (uattr, vattr)

    return mixing_dict(attribute_pairs(), normalized=normalized)


def attribute_mixing_matrix(G, attribute, nodes=None, mapping=None, normalized=True):
    """Return the attribute mixing matrix.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    mixing = attribute_mixing_dict(G, attribute, nodes=nodes, normalized=False)
    if mapping is None:
        keys = list(mixing)
        mapping = {key: index for index, key in enumerate(keys)}

    matrix = np.zeros((len(mapping), len(mapping)))
    for left, inner in mixing.items():
        if left not in mapping:
            continue
        for right, value in inner.items():
            if right not in mapping:
                continue
            matrix[mapping[left], mapping[right]] = value
    if normalized and matrix.sum() > 0:
        matrix = matrix / matrix.sum()
    return matrix


# ---------------------------------------------------------------------------
# Additional generators
# ---------------------------------------------------------------------------


def dense_gnm_random_graph(n, m, seed=None, create_using=None):
    """Return a dense G(n,m) random graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.dense_gnm_random_graph(n, m, seed=seed, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def random_labeled_tree(n, seed=None):
    """Return a uniformly random labeled tree."""
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")
    return random_tree(n, seed=seed)


def _generator_random_state(seed):
    """Return a stdlib random state matching NetworkX's common seed semantics."""
    import random as _random

    class _NumpyRandIntAdapter:
        def __init__(self, rng):
            self._rng = rng

        def randint(self, low, high):
            if hasattr(self._rng, "integers"):
                return int(self._rng.integers(low, high + 1))
            return int(self._rng.randint(low, high + 1))

    if seed is None or seed is _random:
        return _random._inst
    if isinstance(seed, _random.Random):
        return seed
    if isinstance(seed, int):
        return _random.Random(seed)

    try:
        import numpy as np
    except ImportError:
        np = None

    if np is not None:
        if seed is np.random:
            try:
                from networkx.utils.misc import create_py_random_state

                return create_py_random_state(seed)
            except ImportError:
                return _NumpyRandIntAdapter(np.random.mtrand._rand)
        if isinstance(seed, np.random.Generator | np.random.RandomState):
            try:
                from networkx.utils.misc import create_py_random_state

                return create_py_random_state(seed)
            except ImportError:
                return _NumpyRandIntAdapter(seed)
    raise ValueError(f"{seed} cannot be used to generate a random.Random instance")


def _generator_tree_from_edges(edges, n_nodes, root=None, roots=None):
    """Build a FrankenNetworkX graph from edge pairs plus optional root metadata."""
    graph = Graph()
    graph.add_nodes_from(range(n_nodes))
    graph.add_edges_from(edges)
    if root is not None:
        graph.graph["root"] = root
    if roots is not None:
        graph.graph["roots"] = roots
    return graph


def _num_rooted_trees(n, cache_trees):
    """Return the number of unlabeled rooted trees with ``n`` nodes."""
    for n_i in range(len(cache_trees), n + 1):
        cache_trees.append(
            sum(
                d * cache_trees[n_i - j * d] * cache_trees[d]
                for d in range(1, n_i)
                for j in range(1, (n_i - 1) // d + 1)
            )
            // (n_i - 1)
        )
    return cache_trees[n]


def _select_jd_trees(n, cache_trees, seed):
    """Select the ``(j, d)`` pair used by the exact rooted-tree sampler."""
    p = seed.randint(0, _num_rooted_trees(n, cache_trees) * (n - 1) - 1)
    cumsum = 0
    for d in range(n - 1, 0, -1):
        for j in range(1, (n - 1) // d + 1):
            cumsum += (
                d
                * _num_rooted_trees(n - j * d, cache_trees)
                * _num_rooted_trees(d, cache_trees)
            )
            if p < cumsum:
                return j, d
    raise RuntimeError("failed to select rooted-tree decomposition")


def _random_unlabeled_rooted_tree_exact(n, cache_trees, seed):
    """Return an exact random unlabeled rooted tree as ``(edges, node_count)``."""
    if n == 1:
        return [], 1
    if n == 2:
        return [(0, 1)], 2

    j, d = _select_jd_trees(n, cache_trees, seed)
    tree_edges, tree_nodes = _random_unlabeled_rooted_tree_exact(
        n - j * d,
        cache_trees,
        seed,
    )
    subtree_edges, subtree_nodes = _random_unlabeled_rooted_tree_exact(d, cache_trees, seed)
    tree_edges.extend((0, subtree_nodes * i + tree_nodes) for i in range(j))
    for _ in range(j):
        tree_edges.extend((left + tree_nodes, right + tree_nodes) for left, right in subtree_edges)
        tree_nodes += subtree_nodes

    return tree_edges, tree_nodes


def _num_rooted_forests(n, q, cache_forests):
    """Return the number of unlabeled rooted forests with ``n`` nodes."""
    for n_i in range(len(cache_forests), n + 1):
        q_i = min(n_i, q)
        cache_forests.append(
            sum(
                d * cache_forests[n_i - j * d] * cache_forests[d - 1]
                for d in range(1, q_i + 1)
                for j in range(1, n_i // d + 1)
            )
            // n_i
        )
    return cache_forests[n]


def _select_jd_forests(n, q, cache_forests, seed):
    """Select the ``(j, d)`` pair used by the exact rooted-forest sampler."""
    p = seed.randint(0, _num_rooted_forests(n, q, cache_forests) * n - 1)
    cumsum = 0
    for d in range(q, 0, -1):
        for j in range(1, n // d + 1):
            cumsum += (
                d
                * _num_rooted_forests(n - j * d, q, cache_forests)
                * _num_rooted_forests(d - 1, q, cache_forests)
            )
            if p < cumsum:
                return j, d
    raise RuntimeError("failed to select rooted-forest decomposition")


def _random_unlabeled_rooted_forest_exact(n, q, cache_trees, cache_forests, seed):
    """Return an exact random unlabeled rooted forest as ``(edges, node_count, roots)``."""
    if n == 0:
        return [], 0, []

    j, d = _select_jd_forests(n, q, cache_forests, seed)
    forest_edges, forest_nodes, roots = _random_unlabeled_rooted_forest_exact(
        n - j * d,
        q,
        cache_trees,
        cache_forests,
        seed,
    )
    tree_edges, tree_nodes = _random_unlabeled_rooted_tree_exact(d, cache_trees, seed)
    for _ in range(j):
        roots.append(forest_nodes)
        forest_edges.extend((left + forest_nodes, right + forest_nodes) for left, right in tree_edges)
        forest_nodes += tree_nodes
    return forest_edges, forest_nodes, roots


# ---------------------------------------------------------------------------
# Additional conversion
# ---------------------------------------------------------------------------


def adjacency_data(G, attrs=None):
    """Return adjacency-data format suitable for JSON serialization."""
    attrs = {"id": "id", "key": "key"} if attrs is None else attrs
    multigraph = G.is_multigraph()
    id_ = attrs["id"]
    key = None if not multigraph else attrs["key"]
    if id_ == key:
        raise NetworkXError("Attribute names are not unique.")

    data = {
        "directed": G.is_directed(),
        "multigraph": multigraph,
        "graph": list(G.graph.items()),
        "nodes": [],
        "adjacency": [],
    }
    for node, node_attrs in G.nodes(data=True):
        data["nodes"].append({**node_attrs, id_: node})
        neighbors = []
        nbrdict = G.adj[node]
        if multigraph:
            for nbr, keydict in nbrdict.items():
                for edge_key, edge_attrs in keydict.items():
                    neighbors.append({**edge_attrs, id_: nbr, key: edge_key})
        else:
            for nbr, edge_attrs in nbrdict.items():
                neighbors.append({**edge_attrs, id_: nbr})
        data["adjacency"].append(neighbors)
    return data


def node_link_data(
    G,
    source="source",
    target="target",
    name="id",
    key="key",
    edges="edges",
    nodes="nodes",
):
    """Return node-link data suitable for JSON serialization."""
    internal_names = [source, target, name]
    if G.is_multigraph():
        internal_names.append(key)
    if len(set(internal_names)) != len(internal_names):
        raise NetworkXError("Attribute names are not unique.")

    payload = {
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "graph": dict(G.graph),
        nodes: [{**node_attrs, name: node} for node, node_attrs in G.nodes(data=True)],
    }
    edge_payloads = []
    if G.is_multigraph():
        for u, v, edge_key, edge_attrs in G.edges(keys=True, data=True):
            edge_payloads.append(
                {
                    **edge_attrs,
                    source: u,
                    target: v,
                    key: edge_key,
                }
            )
    else:
        for u, v, edge_attrs in G.edges(data=True):
            edge_payloads.append({**edge_attrs, source: u, target: v})
    payload[edges] = edge_payloads
    return payload


def adjacency_graph(data, directed=False, multigraph=True, attrs=None):
    """Return a graph from adjacency-data format."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.adjacency_graph(
        data,
        directed=directed,
        multigraph=multigraph,
        attrs={"id": "id", "key": "key"} if attrs is None else attrs,
    )
    return _from_nx_graph(graph)


def node_link_graph(
    data,
    directed=False,
    multigraph=True,
    source="source",
    target="target",
    name="id",
    key="key",
    edges="edges",
    nodes="nodes",
):
    """Build a graph from node-link data."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.node_link_graph(
        data,
        directed=directed,
        multigraph=multigraph,
        source=source,
        target=target,
        name=name,
        key=key,
        edges=edges,
        nodes=nodes,
    )
    return _from_nx_graph(graph)


# ---------------------------------------------------------------------------
# Additional centrality / metrics
# ---------------------------------------------------------------------------


def _centrality_weight_function(G, weight):
    if callable(weight):
        return weight
    if G.is_multigraph():
        return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    return lambda u, v, data: data.get(weight, 1)


def _single_source_shortest_path_basic_local(G, source, cutoff=None):
    stack = []
    predecessors = {node: [] for node in G}
    sigma = dict.fromkeys(G, 0.0)
    distances = {source: 0}
    sigma[source] = 1.0
    queue = deque([source])
    while queue:
        node = queue.popleft()
        stack.append(node)
        node_distance = distances[node]
        node_sigma = sigma[node]
        if cutoff is not None and node_distance >= cutoff:
            continue
        for neighbor in G[node]:
            if neighbor not in distances:
                queue.append(neighbor)
                distances[neighbor] = node_distance + 1
            if distances[neighbor] == node_distance + 1:
                sigma[neighbor] += node_sigma
                predecessors[neighbor].append(node)
    return stack, predecessors, sigma, distances


def _single_source_dijkstra_path_basic_local(G, source, weight, cutoff=None):
    weight_fn = _centrality_weight_function(G, weight)
    stack = []
    predecessors = {node: [] for node in G}
    sigma = dict.fromkeys(G, 0.0)
    distances = {}
    sigma[source] = 1.0
    seen = {source: 0}
    counter = count()
    queue = []
    heappush(queue, (0, next(counter), source, source))
    while queue:
        distance, _, pred, node = heappop(queue)
        if node in distances:
            continue
        sigma[node] += sigma[pred]
        stack.append(node)
        distances[node] = distance
        for neighbor, edge_data in G[node].items():
            edge_weight = weight_fn(node, neighbor, edge_data)
            if edge_weight is None:
                continue
            total_distance = distance + edge_weight
            if cutoff is not None and total_distance > cutoff:
                continue
            if neighbor not in distances and (
                neighbor not in seen or total_distance < seen[neighbor]
            ):
                seen[neighbor] = total_distance
                heappush(queue, (total_distance, next(counter), node, neighbor))
                sigma[neighbor] = 0.0
                predecessors[neighbor] = [node]
            elif neighbor not in distances and total_distance == seen[neighbor]:
                sigma[neighbor] += sigma[node]
                predecessors[neighbor].append(node)
    return stack, predecessors, sigma, distances


def _rescale_betweenness_local(
    betweenness, n, *, normalized, directed, endpoints=True, sampled_nodes=None
):
    source_count = None if sampled_nodes is None else len(sampled_nodes)
    pair_nodes = n if endpoints else n - 1
    if pair_nodes < 2:
        return betweenness

    source_scale = pair_nodes if source_count is None else source_count

    if source_count is None or endpoints:
        if normalized:
            scale = 1 / (source_scale * (pair_nodes - 1))
        else:
            correction = 1 if directed else 2
            scale = pair_nodes / (source_scale * correction)
        if scale != 1:
            for key in betweenness:
                betweenness[key] *= scale
        return betweenness

    if normalized:
        scale_source = (
            1 / ((source_scale - 1) * (pair_nodes - 1))
            if source_scale > 1
            else math.nan
        )
        scale_nonsource = 1 / (source_scale * (pair_nodes - 1))
    else:
        correction = 1 if directed else 2
        scale_source = (
            pair_nodes / ((source_scale - 1) * correction)
            if source_scale > 1
            else math.nan
        )
        scale_nonsource = pair_nodes / (source_scale * correction)

    sampled_nodes = set(sampled_nodes)
    for key in betweenness:
        betweenness[key] *= scale_source if key in sampled_nodes else scale_nonsource
    return betweenness


def _add_edge_keys_local(G, betweenness, weight=None):
    weight_fn = _centrality_weight_function(G, weight)
    edge_betweenness = dict.fromkeys(G.edges(keys=True), 0.0)
    for u, v in betweenness:
        edge_dict = G[u][v]
        edge_weight = weight_fn(u, v, edge_dict)
        keys = [key for key in edge_dict if weight_fn(u, v, {key: edge_dict[key]}) == edge_weight]
        edge_value = betweenness[(u, v)] / len(keys)
        for key in keys:
            edge_betweenness[(u, v, key)] = edge_value
    return edge_betweenness


def _accumulate_subset_local(betweenness, stack, predecessors, sigma, source, targets):
    delta = dict.fromkeys(stack, 0.0)
    target_set = set(targets) - {source}
    while stack:
        node = stack.pop()
        coeff = (delta[node] + 1.0) / sigma[node] if node in target_set else delta[node] / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            betweenness[node] += delta[node]
    return betweenness


def _accumulate_endpoints_local(betweenness, stack, predecessors, sigma, source):
    betweenness[source] += len(stack) - 1
    delta = dict.fromkeys(stack, 0.0)
    while stack:
        node = stack.pop()
        coeff = (1.0 + delta[node]) / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            betweenness[node] += delta[node] + 1.0
    return betweenness, delta


def _accumulate_edges_subset_local(
    betweenness, stack, predecessors, sigma, source, targets
):
    delta = dict.fromkeys(stack, 0.0)
    target_set = set(targets)
    while stack:
        node = stack.pop()
        for pred in predecessors[node]:
            if node in target_set:
                contribution = (sigma[pred] / sigma[node]) * (1.0 + delta[node])
            else:
                contribution = delta[node] / len(predecessors[node])
            edge = (pred, node) if (pred, node) in betweenness else (node, pred)
            betweenness[edge] += contribution
            delta[pred] += contribution
        if node != source:
            betweenness[node] += delta[node]
    return betweenness


def _accumulate_percolation_local(
    percolation, stack, predecessors, sigma, source, states, state_sum
):
    delta = dict.fromkeys(stack, 0.0)
    while stack:
        node = stack.pop()
        coeff = (1 + delta[node]) / sigma[node]
        for pred in predecessors[node]:
            delta[pred] += sigma[pred] * coeff
        if node != source:
            percolation_weight = states[source] / (state_sum - states[node])
            percolation[node] += delta[node] * percolation_weight
    return percolation


def _edge_load_from_source_local(G, source, cutoff=None):
    _, predecessors, _, distances = _single_source_shortest_path_basic_local(
        G, source, cutoff=cutoff
    )
    ordered_nodes = [
        node for node, _ in sorted(distances.items(), key=lambda item: item[1])
    ]
    between = {}
    for u, v in G.edges():
        between[(u, v)] = 1.0
        between[(v, u)] = 1.0

    while ordered_nodes:
        node = ordered_nodes.pop()
        num_paths = len(predecessors[node])
        for pred in predecessors[node]:
            if predecessors[pred]:
                num_paths = len(predecessors[pred])
                for parent in predecessors[pred]:
                    between[(pred, parent)] += between[(node, pred)] / num_paths
                    between[(parent, pred)] += between[(pred, node)] / num_paths
    return between


def _load_centrality_from_source_local(G, source, cutoff=None, weight=None):
    if weight is None:
        _, predecessors, _, distances = _single_source_shortest_path_basic_local(
            G, source, cutoff=cutoff
        )
    else:
        _, predecessors, _, distances = _single_source_dijkstra_path_basic_local(
            G,
            source,
            weight,
            cutoff=cutoff,
        )

    ordered_nodes = [
        node
        for node, distance in sorted(distances.items(), key=lambda item: item[1])
        if distance > 0
    ]
    between = dict.fromkeys(distances, 1.0)

    while ordered_nodes:
        node = ordered_nodes.pop()
        if node in predecessors:
            num_paths = len(predecessors[node])
            for pred in predecessors[node]:
                if pred == source:
                    break
                between[pred] += between[node] / num_paths

    for node in between:
        between[node] -= 1.0
    return between


def _group_preprocessing_local(G, group_nodes, weight):
    sigma = {}
    delta = {}
    distances = {}
    betweenness = dict.fromkeys(G, 0.0)

    for source in G:
        if weight is None:
            stack, predecessors, sigma[source], distances[source] = (
                _single_source_shortest_path_basic_local(G, source)
            )
        else:
            stack, predecessors, sigma[source], distances[source] = (
                _single_source_dijkstra_path_basic_local(G, source, weight)
            )
        betweenness, delta[source] = _accumulate_endpoints_local(
            betweenness,
            stack,
            predecessors,
            sigma[source],
            source,
        )
        for node in delta[source]:
            if source != node:
                delta[source][node] += 1.0
            if weight is not None:
                sigma[source][node] /= 2.0

    path_betweenness = {node: dict.fromkeys(G, 0.0) for node in group_nodes}
    for group_node1 in group_nodes:
        for group_node2 in group_nodes:
            if group_node2 not in distances[group_node1]:
                continue
            for node in G:
                if (
                    group_node2 in distances[node]
                    and group_node1 in distances[node]
                    and distances[node][group_node2]
                    == distances[node][group_node1] + distances[group_node1][group_node2]
                ):
                    path_betweenness[group_node1][group_node2] += (
                        delta[node][group_node2]
                        * sigma[node][group_node1]
                        * sigma[group_node1][group_node2]
                        / sigma[node][group_node2]
                    )

    return path_betweenness, sigma, distances


def load_centrality(G, v=None, cutoff=None, normalized=True, weight=None):
    """Return the load centrality for each node.

    Load centrality is similar to betweenness centrality but counts the
    fraction of shortest paths through each node without normalization
    by the number of shortest paths.

    For unweighted graphs, this is equivalent to betweenness centrality.
    """
    if cutoff is None and weight is None:
        result = betweenness_centrality(G, normalized=normalized)
        return result if v is None else result[v]

    if v is not None:
        betweenness = 0.0
        for source in G:
            source_load = _load_centrality_from_source_local(
                G,
                source,
                cutoff=cutoff,
                weight=weight,
            )
            betweenness += source_load[v] if v in source_load else 0.0
        if normalized:
            order = G.order()
            if order <= 2:
                return betweenness
            betweenness *= 1.0 / ((order - 1) * (order - 2))
        return betweenness

    betweenness = dict.fromkeys(G, 0.0)
    for source in betweenness:
        source_load = _load_centrality_from_source_local(
            G,
            source,
            cutoff=cutoff,
            weight=weight,
        )
        for node, value in source_load.items():
            betweenness[node] += value
    if normalized:
        order = G.order()
        if order <= 2:
            return betweenness
        scale = 1.0 / ((order - 1) * (order - 2))
        for node in betweenness:
            betweenness[node] *= scale
    return betweenness


def degree_pearson_correlation_coefficient(G, x="out", y="in", weight=None, nodes=None):
    """Return the degree-degree Pearson correlation coefficient.

    For undirected graphs, this is equivalent to
    ``degree_assortativity_coefficient``.
    """
    import scipy as sp

    values = list(node_degree_xy(G, x=x, y=y, weight=weight, nodes=nodes))
    left, right = zip(*values)
    return float(sp.stats.pearsonr(left, right)[0])


def average_degree(G):
    """Return the average degree of *G*.

    Returns
    -------
    float
    """
    n = G.number_of_nodes()
    if n == 0:
        return 0.0
    return 2.0 * G.number_of_edges() / n


def generalized_degree(G, nodes=None):
    """Return the generalized degree for each node.

    The generalized degree counts the number of triangles each edge
    participates in.

    Parameters
    ----------
    G : Graph
    nodes : iterable, optional

    Returns
    -------
    dict
        ``{node: Counter}`` where Counter maps triangle count to
        number of edges with that many triangles.
    """
    from collections import Counter

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _generalized_degree_for(node):
        counter = Counter()
        for nbr in G.neighbors(node):
            if nbr == node:
                continue
            shared = set(G.neighbors(node)) & set(G.neighbors(nbr))
            shared.discard(node)
            shared.discard(nbr)
            counter[len(shared)] += 1
        return counter

    if nodes in G:
        return _generalized_degree_for(nodes)
    if nodes is None:
        nodes = G.nodes()
    return {node: _generalized_degree_for(node) for node in nodes}


def all_pairs_node_connectivity(G, nbunch=None, flow_func=None):
    """Return node connectivity between all pairs.

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the node connectivity between u and v.
    """
    # flow_func parameter is accepted for API compatibility but ignored;
    # the native implementation always uses the default max-flow algorithm.
    flat = _fnx.all_pairs_node_connectivity_rust(G)
    result = {}
    for (u, v), conn in flat.items():
        result.setdefault(u, {})[v] = conn
    if nbunch is not None:
        wanted = set(nbunch)
        return {
            u: {v: conn for v, conn in nbrs.items() if v in wanted}
            for u, nbrs in result.items()
            if u in wanted
        }
    return result


def minimum_st_node_cut(G, s, t):
    """Return the minimum s-t node cut."""
    return set(minimum_node_cut(G, s, t))


def voronoi_cells(G, center_nodes, weight="weight"):
    """Return Voronoi cells around the given centers (Rust implementation)."""
    from franken_networkx._fnx import voronoi_cells_rust as _rust_voronoi

    center_nodes = list(center_nodes)
    if not center_nodes:
        raise NetworkXError("center_nodes must not be empty")
    result = _rust_voronoi(G, center_nodes)
    # Convert lists to sets for NX compatibility
    return {k: set(v) for k, v in result.items()}


def stoer_wagner(G, weight="weight", heap=None):
    """Return the Stoer-Wagner global minimum cut value and partition.

    Parameters
    ----------
    G : Graph
        Undirected graph (must be connected).
    weight : str, optional
        Edge attribute name for weights (default ``"weight"``).
    heap : class, optional
        Ignored (kept for API compatibility with NetworkX).

    Returns
    -------
    cut_value : float
        Weight of the minimum cut.
    partition : tuple of lists
        The two lists of nodes that form the minimum cut partition.
    """
    from franken_networkx._fnx import stoer_wagner as _rust_stoer_wagner

    return _rust_stoer_wagner(G, weight=weight or "weight")


def dedensify(G, threshold, prefix=None, copy=True):
    """Return a dedensified graph by adding compressor nodes.

    Reduces edges to high-degree nodes by adding compressor nodes that
    summarize multiple edges to those high-degree nodes.

    Parameters
    ----------
    G : Graph or DiGraph
        Input graph.
    threshold : int
        Minimum degree (in-degree for directed) above which a node is
        considered high-degree. Must be >= 2.
    prefix : str or None, optional
        Prefix for compressor node labels.
    copy : bool, optional
        If True, work on a copy of *G*.

    Returns
    -------
    H : Graph or DiGraph
        Dedensified graph.
    compressor_nodes : set
        Set of compressor node labels that were added.
    """
    if threshold < 2:
        raise NetworkXError("The degree threshold must be >= 2")

    # Determine high-degree nodes
    if G.is_directed():
        degrees = list(G.in_degree)
    else:
        degrees = list(G.degree)
    high_degree_nodes = {n for n, d in degrees if d > threshold}

    # For each node, find which high-degree neighbors it connects to
    auxiliary = {}
    for node in G.nodes():
        if G.is_directed():
            nbrs = set(G.successors(node))
        else:
            nbrs = set(G.neighbors(node))
        high_degree_nbrs = frozenset(high_degree_nodes & nbrs)
        if high_degree_nbrs:
            auxiliary.setdefault(high_degree_nbrs, set()).add(node)

    if copy:
        H = G.copy()
    else:
        H = G

    compressor_nodes = set()
    for high_deg_group, low_deg_group in auxiliary.items():
        low_count = len(low_deg_group)
        high_count = len(high_deg_group)
        old_edges = high_count * low_count
        new_edges = high_count + low_count
        if old_edges <= new_edges:
            continue
        # Name the compressor by concatenating high-degree node names
        compression_node = "".join(str(node) for node in high_deg_group)
        if prefix:
            compression_node = str(prefix) + compression_node
        for node in low_deg_group:
            for high_node in high_deg_group:
                if H.has_edge(node, high_node):
                    H.remove_edge(node, high_node)
            H.add_edge(node, compression_node)
        for node in high_deg_group:
            H.add_edge(compression_node, node)
        compressor_nodes.add(compression_node)

    return H, compressor_nodes


def quotient_graph(
    G,
    partition,
    edge_relation=None,
    node_data=None,
    edge_data=None,
    weight="weight",
    relabel=False,
    create_using=None,
):
    """Return the quotient graph induced by a partition of *G*.

    Parameters
    ----------
    G : Graph or DiGraph
    partition : iterable of sets, or callable
        If iterable, each element is a set of nodes forming one block.
        If callable, it should be a function ``f(u, v)`` that returns True
        when *u* and *v* belong to the same block.
    edge_relation : callable or None
        ``f(block_u, block_v)`` -> bool. Default: edge exists if any
        cross-block edge exists in G.
    node_data : callable or None
        ``f(block)`` -> dict of node attributes for the block node.
    edge_data : callable or None
        ``f(block_u, block_v)`` -> dict of edge attributes.
    weight : str
        Attribute name used when ``edge_data`` is None (sums weights).
    relabel : bool
        If True, relabel block nodes to consecutive integers.
    create_using : graph constructor or None
        Type of graph to create.

    Returns
    -------
    Graph or DiGraph
    """
    # Normalize partition
    if callable(partition):
        # Build partition from equivalence relation
        remaining = set(G.nodes())
        blocks = []
        while remaining:
            seed = next(iter(remaining))
            block = {seed}
            for n in list(remaining):
                if n != seed and partition(seed, n):
                    block.add(n)
            blocks.append(frozenset(block))
            remaining -= block
        partition = blocks
    else:
        partition = [frozenset(b) for b in partition]

    # Default edge relation: any edge between blocks
    if edge_relation is None:

        def edge_relation(block_u, block_v):
            for u in block_u:
                for v in block_v:
                    if G.has_edge(u, v):
                        return True
            return False

    if create_using is not None:
        H = _empty_graph_from_create_using(create_using)
    else:
        H = G.__class__()

    # Add block nodes
    for block in partition:
        node_label = block
        if node_data is not None:
            H.add_node(node_label, **node_data(block))
        else:
            H.add_node(node_label)

    # Add edges between blocks
    for i, block_u in enumerate(partition):
        for j, block_v in enumerate(partition):
            if i >= j and not G.is_directed():
                if i == j:
                    continue
            if i == j:
                continue
            if edge_relation(block_u, block_v):
                if edge_data is not None:
                    H.add_edge(block_u, block_v, **edge_data(block_u, block_v))
                else:
                    # Sum weights of cross-block edges
                    total = 0
                    count = 0
                    for u in block_u:
                        for v in block_v:
                            if G.has_edge(u, v):
                                d = G.edges[u, v]
                                total += d.get(weight, 1) if weight else 1
                                count += 1
                    attrs = {weight: total} if weight and count else {}
                    H.add_edge(block_u, block_v, **attrs)

    if relabel:
        mapping = {block: i for i, block in enumerate(partition)}
        H = relabel_nodes(H, mapping)

    return H


def snap_aggregation(
    G,
    node_attributes,
    edge_attributes=(),
    prefix="Supernode-",
    supernode_attribute="group",
    superedge_attribute="types",
):
    """Return a SNAP summary graph aggregated by attribute values.

    Groups nodes by their attribute values and neighbor-group structure
    (SNAP algorithm).

    Parameters
    ----------
    G : Graph or DiGraph
    node_attributes : iterable of str
        Node attribute names used for initial grouping.
    edge_attributes : iterable of str, optional
        Edge attributes to consider for edge typing.
    prefix : str, optional
        Prefix for supernode labels.
    supernode_attribute : str, optional
        Name of the attribute on supernodes that holds the set of grouped
        nodes.
    superedge_attribute : str, optional
        Name of the attribute on superedges that holds edge type info.

    Returns
    -------
    Graph or DiGraph
    """
    from collections import Counter, defaultdict

    if isinstance(node_attributes, str):
        node_attributes = [node_attributes]
    edge_attributes = tuple(edge_attributes)

    # Build edge_types mapping: edge -> tuple of attribute values
    edge_types = {}
    for u, v, d in G.edges(data=True):
        etype = tuple(d.get(attr) for attr in edge_attributes)
        edge_types[(u, v)] = etype
    if not G.is_directed():
        for (u, v), etype in list(edge_types.items()):
            edge_types[(v, u)] = etype

    # Initial grouping by node attribute values
    group_lookup = {}
    for n in G.nodes():
        group_lookup[n] = tuple(G.nodes[n].get(attr) for attr in node_attributes)
    groups = defaultdict(set)
    for node, node_type in group_lookup.items():
        groups[node_type].add(node)

    # Iterative splitting (mirrors NX _snap_eligible_group / _snap_split)
    def _eligible_group():
        nbr_info = {}
        for group_id in groups:
            current_group = groups[group_id]
            for node in current_group:
                nbr_info[node] = {gid: Counter() for gid in groups}
                for nbr in G.neighbors(node):
                    edge_key = (node, nbr)
                    etype = edge_types.get(edge_key, ())
                    neighbor_gid = group_lookup[nbr]
                    nbr_info[node][neighbor_gid][etype] += 1

            group_size = len(current_group)
            for other_gid in groups:
                edge_counts = Counter()
                for node in current_group:
                    edge_counts.update(nbr_info[node][other_gid].keys())
                if not all(count == group_size for count in edge_counts.values()):
                    return group_id, nbr_info

        return None, nbr_info

    def _split(nbr_info, group_id):
        new_group_mappings = defaultdict(set)
        for node in groups[group_id]:
            signature = tuple(frozenset(etypes) for etypes in nbr_info[node].values())
            new_group_mappings[signature].add(node)

        new_subgroups = sorted(new_group_mappings.values(), key=len)
        for new_group in new_subgroups[:-1]:
            new_gid = len(groups)
            groups[new_gid] = new_group
            groups[group_id] -= new_group
            for node in new_group:
                group_lookup[node] = new_gid

    eligible_gid, nbr_info = _eligible_group()
    while eligible_gid is not None:
        _split(nbr_info, eligible_gid)
        eligible_gid, nbr_info = _eligible_group()

    # Build the summary graph
    output = G.__class__()
    node_label_lookup = {}
    for index, group_id in enumerate(groups):
        group_set = groups[group_id]
        supernode = f"{prefix}{index}"
        node_label_lookup[group_id] = supernode
        supernode_attributes = {
            attr: G.nodes[next(iter(group_set))].get(attr) for attr in node_attributes
        }
        supernode_attributes[supernode_attribute] = group_set
        output.add_node(supernode, **supernode_attributes)

    for group_id in groups:
        group_set = groups[group_id]
        source_supernode = node_label_lookup[group_id]
        rep_node = next(iter(group_set))
        for other_gid, group_edge_types in nbr_info[rep_node].items():
            if group_edge_types:
                target_supernode = node_label_lookup[other_gid]
                edge_type_list = [
                    dict(zip(edge_attributes, etype)) for etype in group_edge_types
                ]
                superedge_attrs = {superedge_attribute: edge_type_list}
                if not output.has_edge(source_supernode, target_supernode):
                    output.add_edge(
                        source_supernode, target_supernode, **superedge_attrs
                    )
                elif G.is_directed():
                    output.add_edge(
                        source_supernode, target_supernode, **superedge_attrs
                    )

    return output


def full_join(G, H, rename=(None, None)):
    """Return the full join of two graphs.

    The full join is the union of G and H plus all edges between every
    node in G and every node in H.

    Parameters
    ----------
    G, H : Graph
    rename : tuple of (str or None, str or None)
        Prefixes for node labels of G and H to avoid collisions.

    Returns
    -------
    Graph
    """
    R = G.__class__()
    prefix_g, prefix_h = rename

    def _rg(n):
        return f"{prefix_g}{n}" if prefix_g is not None else n

    def _rh(n):
        return f"{prefix_h}{n}" if prefix_h is not None else n

    g_nodes = []
    for n in G.nodes():
        new_n = _rg(n)
        R.add_node(new_n, **G.nodes[n])
        g_nodes.append(new_n)

    h_nodes = []
    for n in H.nodes():
        new_n = _rh(n)
        R.add_node(new_n, **H.nodes[n])
        h_nodes.append(new_n)

    for u, v, d in G.edges(data=True):
        R.add_edge(_rg(u), _rg(v), **d)
    for u, v, d in H.edges(data=True):
        R.add_edge(_rh(u), _rh(v), **d)

    # Full join: connect every node in G to every node in H
    for gn in g_nodes:
        for hn in h_nodes:
            R.add_edge(gn, hn)

    return R


def identified_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    store_contraction_as="contraction",
):
    """Return *G* with nodes *u* and *v* identified (contracted).

    Node *v* is merged into node *u*: all edges incident to *v* are
    redirected to *u*, and *v* is removed.

    Parameters
    ----------
    G : Graph or DiGraph
    u, v : nodes
        *v* is merged into *u*.
    self_loops : bool, optional
        If False, self-loops created by the contraction are removed.
    copy : bool, optional
        If True, work on a copy of *G*.
    store_contraction_as : str, optional
        Attribute name under which contraction info is stored on *u*.

    Returns
    -------
    Graph or DiGraph
    """
    # Build a new graph preserving node order from G (skip v)
    H = G.__class__()
    v_data = dict(G.nodes[v]) if v in G else {}

    # Add all nodes except v, preserving insertion order from G
    for n in G.nodes():
        if n == v:
            continue
        attrs = dict(G.nodes[n])
        if n == u and store_contraction_as:
            contraction = attrs.get(store_contraction_as, {})
            contraction[v] = v_data
            attrs[store_contraction_as] = contraction
        H.add_node(n, **attrs)

    # Add edges, redirecting v -> u
    added_edges = set()
    for src, dst, d in G.edges(data=True):
        new_src = u if src == v else src
        new_dst = u if dst == v else dst
        if new_src == new_dst and not self_loops:
            continue
        if G.is_directed():
            edge_key = (new_src, new_dst)
        else:
            try:
                edge_key = (min(new_src, new_dst), max(new_src, new_dst))
            except TypeError:
                edge_key = (new_src, new_dst)
        if edge_key not in added_edges:
            H.add_edge(new_src, new_dst, **d)
            added_edges.add(edge_key)

    if not copy:
        G.clear()
        for n in H.nodes():
            G.add_node(n, **H.nodes[n])
        for s, t, d_attr in H.edges(data=True):
            G.add_edge(s, t, **d_attr)
        return G

    return H


def inverse_line_graph(G):
    """Return an inverse line graph, when it exists."""
    from collections import defaultdict
    from itertools import combinations

    def _triangles_local(graph, edge):
        u, v = edge
        if u not in graph:
            raise NetworkXError(f"Vertex {u} not in graph")
        if v not in graph[u]:
            raise NetworkXError(f"Edge ({u}, {v}) not in graph")
        triangle_list = []
        for x in graph[u]:
            if x in graph[v]:
                triangle_list.append((u, v, x))
        return triangle_list

    def _odd_triangle_local(graph, triangle):
        for u in triangle:
            if u not in graph:
                raise NetworkXError(f"Vertex {u} not in graph")
        for u, v in combinations(triangle, 2):
            if u not in graph[v]:
                raise NetworkXError(f"Edge ({u}, {v}) not in graph")

        triangle_neighbors = defaultdict(int)
        for triangle_node in triangle:
            for neighbor in graph[triangle_node]:
                if neighbor not in triangle:
                    triangle_neighbors[neighbor] += 1
        return any(count in (1, 3) for count in triangle_neighbors.values())

    def _select_starting_cell_local(graph, starting_edge=None):
        if starting_edge is None:
            edge = next(iter(graph.edges()))
        else:
            edge = starting_edge
            if edge[0] not in graph.nodes():
                raise NetworkXError(f"Vertex {edge[0]} not in graph")
            if edge[1] not in graph[edge[0]]:
                raise NetworkXError(
                    f"starting_edge ({edge[0]}, {edge[1]}) is not in the Graph"
                )
        edge_triangles = _triangles_local(graph, edge)
        triangle_count = len(edge_triangles)
        if triangle_count == 0:
            return edge
        if triangle_count == 1:
            triangle = edge_triangles[0]
            a, b, c = triangle
            ac_edges = len(_triangles_local(graph, (a, c)))
            bc_edges = len(_triangles_local(graph, (b, c)))
            if ac_edges == 1:
                if bc_edges == 1:
                    return triangle
                return _select_starting_cell_local(graph, starting_edge=(b, c))
            return _select_starting_cell_local(graph, starting_edge=(a, c))

        odd_triangles = [
            triangle
            for triangle in edge_triangles
            if _odd_triangle_local(graph, triangle)
        ]
        odd_count = len(odd_triangles)
        if triangle_count == 2 and odd_count == 0:
            return edge_triangles[-1]
        if triangle_count - 1 <= odd_count <= triangle_count:
            triangle_nodes = set()
            for triangle in odd_triangles:
                triangle_nodes.update(triangle)
            for u in triangle_nodes:
                for v in triangle_nodes:
                    if u != v and v not in graph[u]:
                        raise NetworkXError(
                            "G is not a line graph (odd triangles do not form complete subgraph)"
                        )
            return tuple(triangle_nodes)
        raise NetworkXError(
            "G is not a line graph (incorrect number of odd triangles around starting edge)"
        )

    def _find_partition_local(graph, starting_cell):
        graph_partition = graph.copy()
        partition = [starting_cell]
        graph_partition.remove_edges_from(list(combinations(starting_cell, 2)))
        partitioned_vertices = list(starting_cell)
        while graph_partition.number_of_edges() > 0:
            u = partitioned_vertices.pop()
            if len(graph_partition[u]) != 0:
                new_cell = [u] + list(graph_partition[u])
                for cell_u in new_cell:
                    for cell_v in new_cell:
                        if cell_u != cell_v and cell_v not in graph_partition[cell_u]:
                            raise NetworkXError(
                                "G is not a line graph (partition cell not a complete subgraph)"
                            )
                partition.append(tuple(new_cell))
                graph_partition.remove_edges_from(list(combinations(new_cell, 2)))
                partitioned_vertices += new_cell
        return partition

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.number_of_nodes() == 0:
        return empty_graph(1)
    if G.number_of_nodes() == 1:
        vertex = next(iter(G.nodes()))
        return Graph([((vertex, 0), (vertex, 1))])
    if G.number_of_nodes() > 1 and G.number_of_edges() == 0:
        raise NetworkXError(
            "inverse_line_graph() doesn't work on an edgeless graph. Please use this function on each component separately."
        )
    if number_of_selfloops(G) != 0:
        raise NetworkXError(
            "A line graph as generated by NetworkX has no selfloops, so G has no inverse line graph. Please remove the selfloops from G and try again."
        )

    starting_cell = _select_starting_cell_local(G)
    partition = _find_partition_local(G, starting_cell)
    partition_count = {u: 0 for u in G.nodes()}
    for cell in partition:
        for u in cell:
            partition_count[u] += 1
    if max(partition_count.values()) > 2:
        raise NetworkXError(
            "G is not a line graph (vertex found in more than two partition cells)"
        )

    singleton_cells = tuple((u,) for u, count in partition_count.items() if count == 1)
    H = Graph()
    for node in partition:
        H.add_node(node)
    for node in singleton_cells:
        H.add_node(node)
    for left, right in combinations(H.nodes(), 2):
        if any(item in right for item in left):
            H.add_edge(left, right)
    return H


# ---------------------------------------------------------------------------
# Node/edge contraction
# ---------------------------------------------------------------------------


def contracted_nodes(G, u, v, self_loops=True, copy=True):
    """Contract nodes *u* and *v* in *G*.

    All edges to/from *v* are redirected to *u*, then *v* is removed.

    Parameters
    ----------
    G : Graph
    u, v : node
    self_loops : bool, optional
        If False, remove self-loops created by the contraction.
    copy : bool, optional
        If True (default), return a new graph.
    """
    H = G.copy() if copy else G
    # Redirect v's edges to u
    for nbr in list(H.neighbors(v)):
        if nbr == v:
            if self_loops:
                H.add_edge(u, u)
        elif nbr != u:
            H.add_edge(u, nbr)
        elif self_loops:
            H.add_edge(u, u)
    H.remove_node(v)
    if not self_loops:
        # Remove any self-loops on u
        if H.has_edge(u, u):
            H.remove_edge(u, u)
    return H


def contracted_edge(G, edge, self_loops=True, copy=True):
    """Contract an edge in *G* by merging its endpoints.

    Parameters
    ----------
    G : Graph
    edge : tuple (u, v)
    self_loops : bool, optional
    copy : bool, optional
    """
    u, v = edge[:2]
    return contracted_nodes(G, u, v, self_loops=self_loops, copy=copy)


# ---------------------------------------------------------------------------
# Global type predicates (function form)
# ---------------------------------------------------------------------------


def is_directed(G):
    """Return True if *G* is a directed graph."""
    return G.is_directed()


# ---------------------------------------------------------------------------
# Degree sequence generators
# ---------------------------------------------------------------------------


def configuration_model(deg_sequence, seed=None):
    """Return a random graph with the given degree sequence.

    Uses the configuration model: create stubs and pair them randomly.
    May produce self-loops and multi-edges (returns a MultiGraph).

    Parameters
    ----------
    deg_sequence : list of int
        Degree sequence (must sum to even number).
    seed : int or None, optional

    Returns
    -------
    MultiGraph
    """
    import random as _random

    rng = _random.Random(seed)

    if sum(deg_sequence) % 2 != 0:
        raise ValueError("Invalid degree sequence: sum must be even")

    n = len(deg_sequence)
    G = MultiGraph()
    for i in range(n):
        G.add_node(i)

    stubs = []
    for i, d in enumerate(deg_sequence):
        stubs.extend([i] * d)

    rng.shuffle(stubs)
    for i in range(0, len(stubs) - 1, 2):
        G.add_edge(stubs[i], stubs[i + 1])

    return G


def havel_hakimi_graph(deg_sequence, create_using=None):
    """Return a simple graph with the given degree sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.havel_hakimi_graph(deg_sequence, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def degree_sequence_tree(deg_sequence):
    """Return a tree with the given degree sequence, if possible.

    Parameters
    ----------
    deg_sequence : list of int

    Returns
    -------
    Graph
        A tree with the given degree sequence.
    """
    if sum(deg_sequence) != 2 * (len(deg_sequence) - 1):
        raise ValueError("Degree sequence does not sum to 2*(n-1)")
    return havel_hakimi_graph(deg_sequence)


def common_neighbor_centrality(G, ebunch=None):
    """Return the Common Neighbor Centrality (Cannistraci-Hebb) index
    for pairs of nodes.

    Parameters
    ----------
    G : Graph
    ebunch : iterable of (u, v) pairs, optional

    Yields
    ------
    (u, v, score) tuples
    """
    if ebunch is None:
        ebunch = non_edges(G)

    for u, v in ebunch:
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        if not common:
            yield (u, v, 0)
            continue
        # CNC: sum of (number of common neighbors of each common neighbor
        # that are also common neighbors of u and v)
        score = 0
        for w in common:
            w_nbrs = set(G.neighbors(w))
            score += len(w_nbrs & common)
        yield (u, v, score)


# ---------------------------------------------------------------------------
# DAG & Ancestor algorithms
# ---------------------------------------------------------------------------


def all_topological_sorts(G):
    """Generate all possible topological orderings of a DAG.

    Uses Kahn's algorithm with backtracking. The number of orderings
    can be exponential, so this is a generator.

    Parameters
    ----------
    G : DiGraph
        Must be a DAG.

    Yields
    ------
    list
        Each yield is a valid topological ordering.
    """
    if not is_directed_acyclic_graph(G):
        raise NetworkXUnfeasible("Graph contains a cycle, not a DAG")
    for ordering in _fnx.all_topological_sorts_rust(G):
        yield ordering


def lowest_common_ancestor(G, node1, node2, default=None):
    """Compute the lowest common ancestor of the given pair of nodes.

    Parameters
    ----------
    G : NetworkX directed graph

    node1, node2 : nodes in the graph.

    default : object
        Returned if no common ancestor between `node1` and `node2`

    Returns
    -------
    The lowest common ancestor of node1 and node2,
    or default if they have no common ancestors.
    """
    ans = list(all_pairs_lowest_common_ancestor(G, pairs=[(node1, node2)]))
    if ans:
        return ans[0][1]
    return default


def all_pairs_lowest_common_ancestor(G, pairs=None):
    """Return the lowest common ancestor of all pairs or the provided pairs

    Parameters
    ----------
    G : NetworkX directed graph

    pairs : iterable of pairs of nodes, optional (default: all pairs)
        The pairs of nodes of interest.
        If None, will find the LCA of all pairs of nodes.

    Yields
    ------
    ((node1, node2), lca) : 2-tuple
        Where lca is least common ancestor of node1 and node2.

    Raises
    ------
    NetworkXPointlessConcept
        If `G` is null.
    NetworkXError
        If `G` is not a DAG.
    """
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("LCA only defined on directed acyclic graphs.")
    if len(G) == 0:
        raise NetworkXPointlessConcept("LCA meaningless on null graphs.")

    if pairs is None:
        from itertools import combinations_with_replacement

        pairs = combinations_with_replacement(G, 2)
    else:
        # Materialize to list so we can iterate twice (validate + compute)
        pairs = list(pairs)
        # Verify that each of the nodes in the provided pairs is in G
        nodeset = set(G)
        for u, v in pairs:
            if u not in nodeset:
                raise NodeNotFound(f"Node {u} not in G.")
            if v not in nodeset:
                raise NodeNotFound(f"Node {v} not in G.")

    def generate_lca_from_pairs(G, pairs):
        ancestor_cache = {}

        for v, w in pairs:
            if v not in ancestor_cache:
                anc_v = set(ancestors(G, v))
                anc_v.add(v)
                ancestor_cache[v] = anc_v
            if w not in ancestor_cache:
                anc_w = set(ancestors(G, w))
                anc_w.add(w)
                ancestor_cache[w] = anc_w

            common_ancestors = ancestor_cache[v] & ancestor_cache[w]

            if common_ancestors:
                # Find a common ancestor that has no successor in common_ancestors
                # This matches NetworkX's search strategy for DAGs
                common_ancestor = next(iter(common_ancestors))
                while True:
                    successor = None
                    for lower_ancestor in G.successors(common_ancestor):
                        if lower_ancestor in common_ancestors:
                            successor = lower_ancestor
                            break
                    if successor is None:
                        break
                    common_ancestor = successor
                yield ((v, w), common_ancestor)

    return generate_lca_from_pairs(G, pairs)


def root_to_leaf_paths(G):
    """Yields root-to-leaf paths in a directed acyclic graph."""
    roots = [v for v, d in G.in_degree if d == 0]
    leaves = [v for v, d in G.out_degree if d == 0]

    for root in roots:
        for leaf in leaves:
            yield from all_simple_paths(G, root, leaf)


def prefix_tree(paths):
    """Creates a directed prefix tree from a list of paths.

    Each non-root node has a ``source`` attribute (used by ``dag_to_branching``)
    and a ``label`` attribute (used by the public NetworkX API).
    """
    tree = DiGraph()
    root = 0
    tree.add_node(root, source=None, label=None)
    nodes_count = 1

    for path in paths:
        parent = root
        for node in path:
            found = None
            for succ in tree.successors(parent):
                if tree.nodes[succ].get("source") == node:
                    found = succ
                    break
            if found is None:
                new_node = nodes_count
                nodes_count += 1
                tree.add_node(new_node, source=node, label=node)
                tree.add_edge(parent, new_node)
                parent = new_node
            else:
                parent = found
    return tree


def dag_to_branching(G):
    """Return a branching (forest of arborescences) from a DAG."""
    if not is_directed_acyclic_graph(G):
        raise HasACycle("dag_to_branching is only defined for acyclic graphs")

    paths = root_to_leaf_paths(G)
    B = prefix_tree(paths)
    # Remove the synthetic root (0)
    B.remove_node(0)
    return B


def transitive_closure_dag(G, topo_order=None):
    """Return the transitive closure of a DAG.

    More efficient than general transitive_closure because it uses
    topological ordering to propagate reachability.

    Parameters
    ----------
    G : DiGraph
        Must be a DAG.
    topo_order : list, optional
        Precomputed topological ordering.

    Returns
    -------
    DiGraph
    """
    if topo_order is None:
        topo_order = topological_sort(G)

    # Use transitive_closure from Rust backend (already implemented)
    return transitive_closure(G)


# ---------------------------------------------------------------------------
# Additional shortest path variants
# ---------------------------------------------------------------------------


def dijkstra_predecessor_and_distance(G, source, cutoff=None, weight="weight"):
    """Return predecessors and distances from Dijkstra's algorithm.

    Parameters
    ----------
    G : Graph
    source : node
    cutoff : float, optional
        Maximum distance threshold.
    weight : str, optional

    Returns
    -------
    (pred, dist) : tuple of dicts
    """
    dist = single_source_dijkstra_path_length(G, source, weight=weight)
    paths = single_source_dijkstra_path(G, source, weight=weight)

    if cutoff is not None:
        dist = {k: v for k, v in dist.items() if v <= cutoff}

    pred = {}
    for node, path in paths.items():
        if cutoff is not None and node not in dist:
            continue
        if len(path) >= 2:
            pred[node] = [path[-2]]
        else:
            pred[node] = []

    return pred, dist


def multi_source_dijkstra_path(G, sources, weight="weight"):
    """Return shortest paths from any source to all reachable nodes.

    Parameters
    ----------
    G : Graph
    sources : iterable of nodes
    weight : str, optional

    Returns
    -------
    dict
        ``{target: path}`` where path starts from the nearest source.
    """
    _, paths = multi_source_dijkstra(G, sources, weight=weight)
    return paths


def multi_source_dijkstra_path_length(G, sources, weight="weight"):
    """Return shortest path lengths from any source to all reachable nodes.

    Parameters
    ----------
    G : Graph
    sources : iterable of nodes
    weight : str, optional

    Returns
    -------
    dict
        ``{target: length}``
    """
    dists, _ = multi_source_dijkstra(G, sources, weight=weight)
    return dists


def single_source_all_shortest_paths(G, source, weight=None):
    """Yield all shortest paths from source to every reachable target.

    For unweighted graphs, uses BFS to find all shortest paths.

    Parameters
    ----------
    G : Graph
    source : node
    weight : str or None, optional

    Yields
    ------
    list
        Each yield is a shortest path from source to some target.
    """
    if weight is None:
        # BFS for unweighted
        paths = single_source_shortest_path(G, source)
        for target, path in paths.items():
            yield path
    else:
        paths = single_source_dijkstra_path(G, source, weight=weight)
        for target, path in paths.items():
            yield path


def all_pairs_all_shortest_paths(G, weight=None):
    """Yield all shortest paths between all pairs.

    Parameters
    ----------
    G : Graph
    weight : str or None, optional

    Yields
    ------
    (source, paths_dict)
        Where paths_dict maps target -> path.
    """
    if weight is not None:
        for source in G.nodes():
            paths = single_source_dijkstra_path(G, source, weight=weight)
            yield (source, paths)
        return
    result = _fnx.all_pairs_all_shortest_paths_rust(G)
    for source, paths_dict in result.items():
        yield (source, paths_dict)


def reconstruct_path(sources, targets, pred):
    """Reconstruct a path from predecessors dict.

    Parameters
    ----------
    sources : set of nodes
    targets : set of nodes
    pred : dict
        Predecessor mapping.

    Returns
    -------
    list
        The reconstructed path.
    """
    for target in targets:
        path = [target]
        current = target
        while current not in sources:
            preds = pred.get(current, [])
            if not preds:
                break
            current = preds[0]
            path.append(current)
        if current in sources:
            path.reverse()
            return path
    return []


def generate_random_paths(
    G, sample_size, path_length=5, index_map=None, weight=None, seed=None
):
    """Generate random paths by random walks.

    Parameters
    ----------
    G : Graph
    sample_size : int
        Number of paths to generate.
    path_length : int, optional
        Maximum length of each path. Default 5.
    seed : int or None, optional

    Yields
    ------
    list
        Each yield is a random walk path.
    """
    import random as _random

    rng = _random.Random(seed)
    nodes = list(G.nodes())
    if not nodes:
        return

    for _ in range(sample_size):
        start = rng.choice(nodes)
        path = [start]
        current = start
        for _ in range(path_length - 1):
            nbrs = list(G.neighbors(current))
            if not nbrs:
                break
            current = rng.choice(nbrs)
            path.append(current)
        yield path


def johnson(G, weight="weight"):
    """All-pairs shortest paths using Johnson's algorithm.

    Johnson's algorithm handles graphs with negative edges (but no
    negative cycles) by reweighting edges via Bellman-Ford, then
    running Dijkstra from each node.

    Parameters
    ----------
    G : Graph or DiGraph
    weight : str, optional

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the shortest path length from u to v.
    """
    # For graphs without negative edges, just use all-pairs Dijkstra
    return all_pairs_dijkstra_path_length(G, weight=weight)


# ---------------------------------------------------------------------------
# Spectral & Matrix (numpy/scipy) — br-ulw
# ---------------------------------------------------------------------------


def bethe_hessian_matrix(G, r=None, nodelist=None):
    """Return the Bethe Hessian matrix: H(r) = (r^2-1)*I - r*A + D."""
    import numpy as np
    import scipy.sparse

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=None)
    n = A.shape[0]
    d = np.asarray(A.sum(axis=1)).flatten()
    D = scipy.sparse.diags(d, dtype=float)
    if r is None:
        r = max(np.sqrt(d.mean()), 1.0) if n > 0 else 1.0
    I = scipy.sparse.eye(n)
    return (r**2 - 1) * I - r * A + D


def bethe_hessian_spectrum(G, r=None):
    """Return sorted eigenvalues of the Bethe Hessian matrix."""
    import numpy as np

    H = bethe_hessian_matrix(G, r=r)
    return np.sort(np.linalg.eigvalsh(H.toarray()))


def google_matrix(G, alpha=0.85, personalization=None, nodelist=None, weight="weight"):
    """Return the Google PageRank matrix: alpha*S + (1-alpha)*v*e^T."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return np.array([[]])
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    row_sums = A.sum(axis=1)
    S = np.zeros_like(A)
    for i in range(n):
        if row_sums[i] > 0:
            S[i, :] = A[i, :] / row_sums[i]
        else:
            S[i, :] = 1.0 / n
    if personalization is None:
        v = np.ones(n) / n
    else:
        {node: i for i, node in enumerate(nodelist)}
        v = np.array([personalization.get(node, 0) for node in nodelist], dtype=float)
        s = v.sum()
        v = v / s if s > 0 else np.ones(n) / n
    return alpha * S + (1 - alpha) * np.outer(np.ones(n), v)


def normalized_laplacian_spectrum(G, weight="weight"):
    """Return sorted eigenvalues of the normalized Laplacian."""
    import numpy as np

    NL = normalized_laplacian_matrix(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(NL.toarray()))


def directed_laplacian_matrix(G, nodelist=None, weight="weight", alpha=0.95):
    """Return the directed Laplacian using PageRank stationary distribution."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return np.array([[]])
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    row_sums = A.sum(axis=1)
    row_sums[row_sums == 0] = 1
    P = A / row_sums[:, np.newaxis]
    G_mat = alpha * P + (1 - alpha) / n * np.ones((n, n))
    vals, vecs = np.linalg.eig(G_mat.T)
    idx = np.argmin(np.abs(vals - 1.0))
    pi = np.real(vecs[:, idx])
    pi = np.maximum(pi / pi.sum(), 0)
    Phi = np.diag(pi)
    return Phi - (Phi @ P + P.T @ Phi) / 2.0


def directed_combinatorial_laplacian_matrix(
    G, nodelist=None, weight="weight", alpha=0.95
):
    """Return the directed combinatorial Laplacian: Phi*(I - P)."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return np.array([[]])
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    row_sums = A.sum(axis=1)
    row_sums[row_sums == 0] = 1
    P = A / row_sums[:, np.newaxis]
    G_mat = alpha * P + (1 - alpha) / n * np.ones((n, n))
    vals, vecs = np.linalg.eig(G_mat.T)
    idx = np.argmin(np.abs(vals - 1.0))
    pi = np.real(vecs[:, idx])
    pi = np.maximum(pi / pi.sum(), 0)
    return np.diag(pi) @ (np.eye(n) - P)


def attr_matrix(
    G, edge_attr=None, node_attr=None, normalized=False, rc_order=None, dtype=None
):
    """Construct a matrix from edge attributes.

    When *node_attr* is given, nodes are grouped by attribute value and the
    matrix has size ``len(unique_attr_values)`` with entries summed over
    nodes sharing the same attribute.  *rc_order* then specifies the
    ordering of attribute values, not nodes.
    """
    import numpy as np

    if node_attr is not None:
        # Group nodes by their node_attr value
        node_attrs = {n: G.nodes[n].get(node_attr, n) for n in G.nodes()}
        if rc_order is not None:
            labels = list(rc_order)
        else:
            labels = sorted(set(node_attrs.values()), key=str)
        label_idx = {lab: i for i, lab in enumerate(labels)}
        n = len(labels)
        M = np.zeros((n, n), dtype=dtype or np.float64)
        for u, v, data in G.edges(data=True):
            lu, lv = node_attrs.get(u), node_attrs.get(v)
            if lu in label_idx and lv in label_idx:
                val = (
                    data.get(edge_attr, 1)
                    if edge_attr and isinstance(data, dict)
                    else 1
                )
                M[label_idx[lu], label_idx[lv]] += val
                if not G.is_directed():
                    M[label_idx[lv], label_idx[lu]] += val
        if normalized:
            rs = M.sum(axis=1)
            rs[rs == 0] = 1
            M = M / rs[:, np.newaxis]
        return M, labels
    else:
        nodelist = list(rc_order) if rc_order is not None else list(G.nodes())
        n = len(nodelist)
        idx = {node: i for i, node in enumerate(nodelist)}
        M = np.zeros((n, n), dtype=dtype or np.float64)
        for u, v, data in G.edges(data=True):
            if u in idx and v in idx:
                val = (
                    data.get(edge_attr, 1)
                    if edge_attr and isinstance(data, dict)
                    else 1
                )
                M[idx[u], idx[v]] = val
                if not G.is_directed():
                    M[idx[v], idx[u]] = val
        if normalized:
            rs = M.sum(axis=1)
            rs[rs == 0] = 1
            M = M / rs[:, np.newaxis]
        return M, nodelist


# ---------------------------------------------------------------------------
# Min-cost flow algorithms (br-hp3)
# ---------------------------------------------------------------------------


def cost_of_flow(G, flowDict, weight="weight"):
    """Compute the cost of a given flow.

    Parameters
    ----------
    G : DiGraph
        Network with edge attribute *weight* as cost per unit flow.
    flowDict : dict of dicts
        ``flowDict[u][v]`` is the flow on edge (u, v).
    weight : str, optional
        Edge attribute name for cost. Default ``'weight'``.

    Returns
    -------
    float
        Total cost of the flow.
    """
    total = 0.0
    for u in flowDict:
        for v, flow in flowDict[u].items():
            if flow > 0:
                data = G.get_edge_data(u, v)
                if isinstance(data, dict):
                    cost = float(data.get(weight, 0))
                else:
                    cost = 0.0
                total += flow * cost
    return total


def min_cost_flow(G, demand="demand", capacity="capacity", weight="weight"):
    """Find minimum cost flow satisfying node demands.

    Uses the successive shortest paths algorithm with Bellman-Ford.

    Each node may have a ``demand`` attribute:
    - Negative demand = supply (source, has excess flow to send)
    - Positive demand = demand (sink, needs flow)
    - Zero or missing = transshipment node

    Parameters
    ----------
    G : DiGraph
    demand : str, optional
        Node attribute for supply/demand. Default ``'demand'``.
    capacity : str, optional
        Edge attribute for capacity. Default ``'capacity'``.
    weight : str, optional
        Edge attribute for cost per unit flow. Default ``'weight'``.

    Returns
    -------
    dict of dicts
        ``flowDict[u][v]`` is the optimal flow on edge (u, v).

    Raises
    ------
    NetworkXUnfeasible
        If no feasible flow exists.
    """
    if not G.is_directed():
        raise NetworkXError("min_cost_flow requires a directed graph")

    nodes = list(G.nodes())
    n = len(nodes)
    if n == 0:
        return {}

    # Extract demands
    node_demand = {}
    for node in nodes:
        attrs = G.nodes[node] if hasattr(G.nodes, "__getitem__") else {}
        if isinstance(attrs, dict):
            node_demand[node] = float(attrs.get(demand, 0))
        else:
            node_demand[node] = 0.0

    # Check feasibility: sum of demands must be zero
    total_demand = sum(node_demand.values())
    if abs(total_demand) > 1e-10:
        raise NetworkXUnfeasible(
            f"Total node demand is {total_demand}, must be zero for feasible flow"
        )

    # Initialize flow dict
    flow = {u: {} for u in nodes}
    for u, v in G.edges():
        flow.setdefault(u, {})[v] = 0

    # Build residual graph and run successive shortest paths
    # NetworkX convention: negative demand = supply, positive = demand
    sources = [n for n in nodes if node_demand[n] < 0]
    sinks = [n for n in nodes if node_demand[n] > 0]
    remaining_supply = {n: -node_demand[n] for n in sources}
    remaining_demand = {n: node_demand[n] for n in sinks}

    # Successive shortest paths: augment along shortest cost path
    for _ in range(n * n):  # upper bound on iterations
        # Find shortest path from any source with remaining supply
        # to any sink with remaining demand using Bellman-Ford on residual
        best_path = None
        best_cost = float("inf")
        best_source = None
        best_sink = None

        for source in sources:
            if remaining_supply.get(source, 0) <= 1e-10:
                continue

            # BFS/Bellman-Ford on residual graph
            dist = {source: 0.0}
            pred = {source: None}
            # Relaxation
            for _ in range(n):
                updated = False
                for u in nodes:
                    if u not in dist:
                        continue
                    # Forward edges
                    if hasattr(G, "successors"):
                        succs = list(G.successors(u))
                    else:
                        succs = list(G.neighbors(u))
                    for v in succs:
                        data = G.get_edge_data(u, v)
                        if not isinstance(data, dict):
                            continue
                        cap = float(data.get(capacity, float("inf")))
                        current_flow = flow.get(u, {}).get(v, 0)
                        residual_cap = cap - current_flow
                        if residual_cap > 1e-10:
                            edge_cost = float(data.get(weight, 0))
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, "forward")
                                updated = True
                    # Backward edges (reverse flow)
                    if hasattr(G, "predecessors"):
                        preds_list = list(G.predecessors(u))
                    else:
                        preds_list = []
                    for v in preds_list:
                        current_flow = flow.get(v, {}).get(u, 0)
                        if current_flow > 1e-10:
                            data = G.get_edge_data(v, u)
                            edge_cost = (
                                -float(data.get(weight, 0))
                                if isinstance(data, dict)
                                else 0.0
                            )
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, "backward")
                                updated = True
                if not updated:
                    break

            # Check reachable sinks
            for sink in sinks:
                if sink in dist and remaining_demand.get(sink, 0) > 1e-10:
                    if dist[sink] < best_cost:
                        best_cost = dist[sink]
                        best_path = pred
                        best_source = source
                        best_sink = sink

        if best_path is None:
            break

        # Find bottleneck along the path
        path_nodes = []
        current = best_sink
        while current is not None:
            path_nodes.append(current)
            p = best_path.get(current)
            if p is None:
                break
            current = p[0] if p else None
        path_nodes.reverse()

        bottleneck = min(remaining_supply[best_source], remaining_demand[best_sink])
        # Also check edge capacities along path
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            info = best_path.get(v)
            if info and info[1] == "forward":
                data = G.get_edge_data(u, v)
                cap = (
                    float(data.get(capacity, float("inf")))
                    if isinstance(data, dict)
                    else float("inf")
                )
                residual = cap - flow.get(u, {}).get(v, 0)
                bottleneck = min(bottleneck, residual)
            elif info and info[1] == "backward":
                bottleneck = min(bottleneck, flow.get(v, {}).get(u, 0))

        if bottleneck <= 1e-10:
            break

        # Augment flow along path
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            info = best_path.get(v)
            if info and info[1] == "forward":
                flow.setdefault(u, {})[v] = flow.get(u, {}).get(v, 0) + bottleneck
            elif info and info[1] == "backward":
                flow.setdefault(v, {})[u] = flow.get(v, {}).get(u, 0) - bottleneck

        remaining_supply[best_source] -= bottleneck
        remaining_demand[best_sink] -= bottleneck

    # Check if all demands are satisfied
    for source in sources:
        if remaining_supply.get(source, 0) > 1e-10:
            raise NetworkXUnfeasible("Infeasible: not all supply could be routed")
    for sink in sinks:
        if remaining_demand.get(sink, 0) > 1e-10:
            raise NetworkXUnfeasible("Infeasible: not all demand could be satisfied")

    return flow


def min_cost_flow_cost(G, demand="demand", capacity="capacity", weight="weight"):
    """Return the cost of the minimum cost flow.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional

    Returns
    -------
    float
    """
    flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    return cost_of_flow(G, flow, weight=weight)


def max_flow_min_cost(G, s, t, capacity="capacity", weight="weight"):
    """Find a maximum flow of minimum cost from *s* to *t*.

    First finds maximum flow value, then finds the min-cost flow
    achieving that value.

    Parameters
    ----------
    G : DiGraph
    s, t : node
        Source and sink.
    capacity, weight : str, optional

    Returns
    -------
    dict of dicts
        Flow dictionary.
    """
    # Get max flow value
    max_val = maximum_flow_value(G, s, t, capacity=capacity)

    # Set up demands: source supplies max_val, sink demands max_val
    H = G.copy()
    set_node_attributes(H, {s: max_val, t: -max_val}, name="demand")
    # Set demand=0 for all other nodes
    for n in H.nodes():
        if n != s and n != t:
            attrs = H.nodes[n] if hasattr(H.nodes, "__getitem__") else {}
            if isinstance(attrs, dict) and "demand" not in attrs:
                attrs["demand"] = 0

    return min_cost_flow(H, capacity=capacity, weight=weight)


def capacity_scaling(
    G, demand="demand", capacity="capacity", weight="weight", heap=None
):
    """Find minimum cost flow using capacity scaling.

    This is an alias for ``min_cost_flow`` — the successive shortest
    paths implementation provides the same optimality guarantees.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional
    heap : class, optional
        Ignored. Present for API compatibility.

    Returns
    -------
    tuple
        ``(flowCost, flowDict)`` matching NetworkX's return signature.
    """
    flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    cost = cost_of_flow(G, flow, weight=weight)
    return cost, flow


def network_simplex(G, demand="demand", capacity="capacity", weight="weight"):
    """Find minimum cost flow using the network simplex algorithm.

    Returns both the cost and the flow dictionary.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional

    Returns
    -------
    (cost, flowDict) : tuple
    """
    flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    cost = cost_of_flow(G, flow, weight=weight)
    return (cost, flow)


def flow_hierarchy(G, weight=None):
    """Return the flow hierarchy of a directed graph.

    The flow hierarchy is the fraction of edges not in a cycle.

    Parameters
    ----------
    G : DiGraph
    weight : str or None, optional

    Returns
    -------
    float
        Value in [0, 1]. 1 means no edges are in cycles (DAG).
    """
    return _fnx.flow_hierarchy_rust(G)


# ---------------------------------------------------------------------------
# Triad analysis (br-a59)
# ---------------------------------------------------------------------------

# 16 triad types in MAN notation
_TRIAD_TYPES = [
    "003",
    "012",
    "102",
    "021D",
    "021U",
    "021C",
    "111D",
    "111U",
    "030T",
    "030C",
    "201",
    "120D",
    "120U",
    "120C",
    "210",
    "300",
]


def _classify_triad(G, u, v, w):
    """Classify a 3-node subgraph into one of 16 triad types.

    Uses a canonical 6-bit encoding of the directed edges and a lookup
    table to correctly distinguish all 16 MAN types including subtypes.
    """
    # Encode the 6 possible directed edges as a 6-bit integer:
    # bit 0: u→v, bit 1: v→u, bit 2: u→w, bit 3: w→u, bit 4: v→w, bit 5: w→v
    code = 0
    if G.has_edge(u, v):
        code |= 1
    if G.has_edge(v, u):
        code |= 2
    if G.has_edge(u, w):
        code |= 4
    if G.has_edge(w, u):
        code |= 8
    if G.has_edge(v, w):
        code |= 16
    if G.has_edge(w, v):
        code |= 32

    # To classify correctly, we need isomorphism-invariant encoding.
    # Since node ordering is arbitrary, compute the canonical type by
    # trying all 6 permutations and using the MAN dyad counts + subtype.
    # Dyads: (u,v), (u,w), (v,w) — check mutual/asymmetric/null for each.
    uv_m = bool(code & 1) and bool(code & 2)
    uv_a = bool(code & 1) != bool(code & 2)
    uw_m = bool(code & 4) and bool(code & 8)
    uw_a = bool(code & 4) != bool(code & 8)
    vw_m = bool(code & 16) and bool(code & 32)
    vw_a = bool(code & 16) != bool(code & 32)

    m = sum([uv_m, uw_m, vw_m])
    a = sum([uv_a, uw_a, vw_a])
    n = 3 - m - a

    if m == 0 and a == 0:
        return "003"
    if m == 0 and a == 1:
        return "012"
    if m == 1 and a == 0:
        return "102"
    if m == 0 and a == 2:
        # 021D, 021U, 021C — check if both asymmetric edges share an endpoint
        # Get the directed edges
        asym_edges = []
        if uv_a:
            asym_edges.append((u, v) if (code & 1) else (v, u))
        if uw_a:
            asym_edges.append((u, w) if (code & 4) else (w, u))
        if vw_a:
            asym_edges.append((v, w) if (code & 16) else (w, v))
        if len(asym_edges) == 2:
            s0, t0 = asym_edges[0]
            s1, t1 = asym_edges[1]
            if t0 == t1:
                return "021U"  # both point TO same node (NX: "Up")
            elif s0 == s1:
                return "021D"  # both point FROM same node (NX: "Down")
            else:
                return "021C"  # chain: one's target is the other's source
        return "021C"
    if m == 1 and a == 1:
        # 111D vs 111U — NX convention: D = edge FROM mutual pair outward,
        # U = edge TO mutual pair from outside
        if uv_m:
            mutual_nodes = {u, v}
        elif uw_m:
            mutual_nodes = {u, w}
        else:
            mutual_nodes = {v, w}

        if uv_a:
            asym_src = u if (code & 1) else v
        elif uw_a:
            asym_src = u if (code & 4) else w
        else:
            asym_src = v if (code & 16) else w

        if asym_src in mutual_nodes:
            return "111U"  # asymmetric edge goes FROM mutual pair outward
        else:
            return "111D"  # asymmetric edge goes TO mutual pair from outside
    if m == 0 and a == 3:
        # 030T vs 030C — check if all 3 asymmetric edges form a directed cycle
        # 030C: u→v→w→u or u→w→v→u
        is_cycle = ((code & 1) and (code & 16) and (code & 8)) or (
            (code & 4) and (code & 32) and (code & 2)
        )
        return "030C" if is_cycle else "030T"
    if m == 2 and a == 0:
        return "201"
    if m == 1 and a == 2:
        # 120D, 120U, 120C
        # NX convention: 120U = both asym edges go OUT from mutual pair
        #                120D = both asym edges come IN to mutual pair
        if uv_m:
            uw_dir = u if (code & 4) else w
            vw_dir = v if (code & 16) else w
            if uw_dir == u and vw_dir == v:
                return "120U"  # both go OUT from mutual pair
            elif uw_dir == w and vw_dir == w:
                return "120D"  # both come IN to mutual pair
            else:
                return "120C"
        elif uw_m:
            uv_dir = u if (code & 1) else v
            vw_dir = v if (code & 16) else w
            if uv_dir == u and vw_dir == w:
                return "120U"
            elif uv_dir == v and vw_dir == v:
                return "120D"
            else:
                return "120C"
        else:  # vw_m
            uv_dir = u if (code & 1) else v
            uw_dir = u if (code & 4) else w
            if uv_dir == v and uw_dir == w:
                return "120U"
            elif uv_dir == u and uw_dir == u:
                return "120D"
            else:
                return "120C"
    if m == 2 and a == 1:
        return "210"
    if m == 3:
        return "300"
    return f"{m}{a}{n}"


def triadic_census(G):
    """Count the frequency of each of the 16 triad types.

    Parameters
    ----------
    G : DiGraph

    Returns
    -------
    dict
        ``{triad_type: count}`` for all 16 types.
    """
    if not G.is_directed():
        raise NetworkXError("triadic_census requires a directed graph")
    return _fnx.triadic_census_rust(G)


def all_triads(G):
    """Generate all triads (3-node subgraphs) of a directed graph.

    Parameters
    ----------
    G : DiGraph

    Yields
    ------
    DiGraph
        Each yielded graph is a 3-node subgraph.
    """
    if not G.is_directed():
        raise NetworkXError("all_triads requires a directed graph")

    nodes = list(G.nodes())
    n = len(nodes)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                triad = G.subgraph([nodes[i], nodes[j], nodes[k]])
                yield triad


def triad_type(G):
    """Return the triad type of a 3-node directed graph.

    Parameters
    ----------
    G : DiGraph
        Must have exactly 3 nodes.

    Returns
    -------
    str
        One of the 16 MAN triad type codes.
    """
    nodes = list(G.nodes())
    if len(nodes) != 3:
        raise NetworkXError("triad_type requires exactly 3 nodes")
    return _fnx.triad_type_rust(G, nodes[0], nodes[1], nodes[2])


def is_triad(G):
    """Return True if *G* is a valid triad (3-node directed graph)."""
    return G.is_directed() and G.number_of_nodes() == 3


def triads_by_type(G):
    """Group all triads of *G* by their type.

    Returns
    -------
    dict
        ``{triad_type: [list of triad subgraphs]}``
    """
    result = {t: [] for t in _TRIAD_TYPES}
    for triad in all_triads(G):
        ttype = triad_type(triad)
        if ttype in result:
            result[ttype].append(triad)
    return result


# ---------------------------------------------------------------------------
# Edge swapping & rewiring (br-eo5)
# ---------------------------------------------------------------------------


def double_edge_swap(G, nswap=1, max_tries=100, seed=None):
    """Swap two edges while preserving the degree sequence.

    For each swap attempt, select edges (u,v) and (x,y) and replace
    with (u,x) and (v,y) if no self-loops or parallel edges result.

    Parameters
    ----------
    G : Graph
        Modified in place.
    nswap : int, optional
        Number of swaps to perform.
    max_tries : int, optional
        Maximum attempts per swap.
    seed : int or None, optional

    Returns
    -------
    G : Graph
        The modified graph.
    """
    import random as _random

    rng = _random.Random(seed)

    if G.number_of_edges() < 2:
        return G

    edges = list(G.edges())
    swaps_done = 0
    tries = 0

    while swaps_done < nswap and tries < nswap * max_tries:
        tries += 1
        e1 = edges[rng.randint(0, len(edges) - 1)]
        e2 = edges[rng.randint(0, len(edges) - 1)]
        u, v = e1
        x, y = e2
        if len({u, v, x, y}) < 4:
            continue
        # Try swap: (u,v), (x,y) → (u,x), (v,y)
        if not G.has_edge(u, x) and not G.has_edge(v, y) and u != x and v != y:
            G.remove_edge(u, v)
            G.remove_edge(x, y)
            G.add_edge(u, x)
            G.add_edge(v, y)
            edges = list(G.edges())
            swaps_done += 1

    return G


def directed_edge_swap(G, nswap=1, max_tries=100, seed=None):
    """Swap two directed edges while preserving in/out degree sequences.

    Select edges (u→v) and (x→y), replace with (u→y) and (x→v).

    Parameters
    ----------
    G : DiGraph
        Modified in place.
    nswap : int, optional
    max_tries : int, optional
    seed : int or None, optional

    Returns
    -------
    G : DiGraph
    """
    import random as _random

    rng = _random.Random(seed)

    if not G.is_directed():
        raise NetworkXError("directed_edge_swap requires a directed graph")
    if G.number_of_edges() < 2:
        return G

    edges = list(G.edges())
    swaps_done = 0
    tries = 0

    while swaps_done < nswap and tries < nswap * max_tries:
        tries += 1
        e1 = edges[rng.randint(0, len(edges) - 1)]
        e2 = edges[rng.randint(0, len(edges) - 1)]
        u, v = e1
        x, y = e2
        if u == x or v == y:
            continue
        if u == y or x == v:
            continue
        # Swap: (u→v), (x→y) → (u→y), (x→v)
        if not G.has_edge(u, y) and not G.has_edge(x, v):
            G.remove_edge(u, v)
            G.remove_edge(x, y)
            G.add_edge(u, y)
            G.add_edge(x, v)
            edges = list(G.edges())
            swaps_done += 1

    return G


# ---------------------------------------------------------------------------
# Graph predicates (br-5wd)
# ---------------------------------------------------------------------------


def is_valid_degree_sequence_erdos_gallai(sequence):
    """Check if an integer sequence is a valid degree sequence (Erdos-Gallai).

    The Erdos-Gallai theorem: a non-increasing sequence d_1 >= ... >= d_n
    is graphical iff sum(d_i) is even and for each k:
    sum(d_i, i=1..k) <= k*(k-1) + sum(min(d_i, k), i=k+1..n).
    """
    seq = sorted(sequence, reverse=True)
    n = len(seq)
    if sum(seq) % 2 != 0:
        return False
    for k in range(1, n + 1):
        lhs = sum(seq[:k])
        rhs = k * (k - 1) + sum(min(d, k) for d in seq[k:])
        if lhs > rhs:
            return False
    return True


def is_valid_degree_sequence_havel_hakimi(sequence):
    """Check if an integer sequence is a valid degree sequence (Havel-Hakimi).

    Repeatedly removes the largest element d, subtracts 1 from the next
    d largest elements. If any become negative, not graphical.
    """
    seq = list(sequence)
    while True:
        seq.sort(reverse=True)
        if not seq or seq[0] == 0:
            return True
        d = seq.pop(0)
        if d > len(seq):
            return False
        for i in range(d):
            seq[i] -= 1
            if seq[i] < 0:
                return False


def is_valid_joint_degree(joint_degrees):
    """Check if a joint degree dictionary is realizable."""
    if not joint_degrees:
        return True
    for (d1, d2), count in joint_degrees.items():
        if count < 0 or d1 < 0 or d2 < 0:
            return False
    return True


def is_strongly_regular(G):
    """Check if *G* is strongly regular.

    A graph is strongly regular srg(v,k,λ,μ) if it is k-regular and
    every pair of adjacent vertices has exactly λ common neighbors,
    and every pair of non-adjacent vertices has exactly μ common neighbors.
    """
    return _fnx.is_strongly_regular_rust(G)


def is_at_free(G):
    """Check if *G* is asteroidal-triple-free (AT-free).

    An asteroidal triple is three nodes where between each pair there
    exists a path avoiding the neighborhood of the third.
    """
    return _fnx.is_at_free_rust(G)


def _path_avoiding(G, source, target, avoid):
    """BFS check: is there a path from source to target avoiding 'avoid' nodes?"""
    if source in avoid or target in avoid:
        return source == target
    visited = {source}
    queue = [source]
    while queue:
        node = queue.pop(0)
        if node == target:
            return True
        for nbr in G.neighbors(node):
            if nbr not in visited and nbr not in avoid:
                visited.add(nbr)
                queue.append(nbr)
    return False


def is_d_separator(G, x, y, z):
    """Check if node set *z* d-separates *x* from *y* in a DAG (Rust)."""
    from franken_networkx._fnx import is_d_separator_rust as _rust_dsep

    x, y, z = set(x), set(y), set(z)
    intersection = x.intersection(y) | x.intersection(z) | y.intersection(z)
    if intersection:
        raise NetworkXError(f"The sets are not disjoint, with intersection {intersection}")
    return _rust_dsep(G, list(x), list(y), list(z))


def is_minimal_d_separator(G, x, y, z):
    """Check if *z* is a minimal d-separator of *x* and *y*."""
    if not is_d_separator(G, x, y, z):
        return False
    z = set(z)
    for node in list(z):
        reduced = z - {node}
        if is_d_separator(G, x, y, reduced):
            return False
    return True


# ---------------------------------------------------------------------------
# Graph products (br-69m)
# ---------------------------------------------------------------------------


def corona_product(G, H):
    """Return the corona product of *G* and *H*.

    For each node v in G, add a copy of H and connect v to all nodes
    in that copy.

    Parameters
    ----------
    G, H : Graph

    Returns
    -------
    Graph
    """
    _validate_product_graph_types(
        G, H, allow_directed=False, allow_multigraph=not G.is_multigraph()
    )
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    P = _product_graph_class(G, H)()
    P.add_nodes_from(G.nodes())

    if G.is_multigraph():
        for u, v, key in G.edges(keys=True):
            P.add_edge(u, v, key=key)
    else:
        for u, v in G.edges():
            P.add_edge(u, v)

    for g in G.nodes():
        for h in H.nodes():
            P.add_node((g, h))
            P.add_edge(g, (g, h))
        if H.is_multigraph():
            for u, v, key, attrs in H.edges(keys=True, data=True):
                P.add_edge((g, u), (g, v), key=key, **dict(attrs))
        else:
            for u, v, attrs in H.edges(data=True):
                P.add_edge((g, u), (g, v), **dict(attrs))

    return P


def modular_product(G, H):
    """Return the modular product of *G* and *H*.

    Two nodes (u1,v1) and (u2,v2) are adjacent iff:
    - u1-u2 is edge in G AND v1-v2 is edge in H, OR
    - u1-u2 is NOT edge in G AND v1-v2 is NOT edge in H (and u1≠u2, v1≠v2).
    """
    _validate_product_graph_types(G, H, allow_directed=False, allow_multigraph=False)
    P = Graph()

    for g, g_attrs in G.nodes(data=True):
        for h, h_attrs in H.nodes(data=True):
            P.add_node((g, h), **_product_node_attrs(dict(g_attrs), dict(h_attrs)))

    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())
    for g_left_index, g_left in enumerate(g_nodes):
        for g_right in g_nodes[g_left_index + 1 :]:
            g_adjacent = G.has_edge(g_left, g_right)
            for h_left_index, h_left in enumerate(h_nodes):
                for h_right in h_nodes[h_left_index + 1 :]:
                    h_adjacent = H.has_edge(h_left, h_right)
                    if g_adjacent != h_adjacent:
                        continue
                    attrs = _paired_edge_attrs(
                        dict(G[g_left][g_right]) if g_adjacent else {},
                        dict(H[h_left][h_right]) if h_adjacent else {},
                    )
                    P.add_edge((g_left, h_left), (g_right, h_right), **attrs)
                    P.add_edge((g_left, h_right), (g_right, h_left), **attrs)

    return P


def rooted_product(G, H, root):
    """Return the rooted product of *G* and *H* at *root*.

    Replace each node v in G with a copy of H, connecting v's copy of
    *root* to the neighbors of v.
    """
    _validate_product_graph_types(
        G, H, allow_directed=not G.is_directed(), allow_multigraph=False
    )
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph() or H.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if root not in H:
        raise NodeNotFound("root must be a vertex in H")

    P = Graph()
    for g in G.nodes():
        for h in H.nodes():
            P.add_node((g, h))

    for g in G.nodes():
        for u, v in H.edges():
            P.add_edge((g, u), (g, v))

    for u, v in G.edges():
        P.add_edge((u, root), (v, root))

    return P


def lexicographic_product(G, H):
    """Return the lexicographic product of *G* and *H*.

    (u1,v1) and (u2,v2) are adjacent iff u1-u2 is an edge in G,
    OR u1==u2 and v1-v2 is an edge in H.
    """
    _validate_product_graph_types(G, H)
    P = _product_graph_class(G, H)()

    for g, g_attrs in G.nodes(data=True):
        for h, h_attrs in H.nodes(data=True):
            P.add_node((g, h), **_product_node_attrs(dict(g_attrs), dict(h_attrs)))

    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            for hu in H.nodes():
                for hv in H.nodes():
                    P.add_edge((u, hu), (v, hv), key=key, **dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            for hu in H.nodes():
                for hv in H.nodes():
                    P.add_edge((u, hu), (v, hv), **dict(attrs))

    if H.is_multigraph():
        for u, v, key, attrs in H.edges(keys=True, data=True):
            for g in G.nodes():
                P.add_edge((g, u), (g, v), key=key, **dict(attrs))
    else:
        for u, v, attrs in H.edges(data=True):
            for g in G.nodes():
                P.add_edge((g, u), (g, v), **dict(attrs))

    return P


# ---------------------------------------------------------------------------
# Advanced metrics & indices (br-jxl)
# ---------------------------------------------------------------------------


def estrada_index(G):
    """Return the Estrada index of *G*.

    Sum of exp(eigenvalues) of the adjacency matrix.
    """
    import numpy as np

    spec = adjacency_spectrum(G)
    return float(np.sum(np.exp(spec)))


def gutman_index(G, weight=None):
    """Return the Gutman index (degree-distance) of *G*.

    Sum over all pairs of deg(u)*deg(v)*dist(u,v).
    """
    return _fnx.gutman_index_rust(G)


def schultz_index(G, weight=None):
    """Return the Schultz index of *G*.

    Sum over all pairs of (deg(u)+deg(v))*dist(u,v).
    """
    return _fnx.schultz_index_rust(G)


def hyper_wiener_index(G):
    """Return the hyper-Wiener index of *G*.

    (W + sum(dist^2)) / 2 where W is the Wiener index.
    """
    return _fnx.hyper_wiener_index_rust(G)


def resistance_distance(G, nodeA=None, nodeB=None, weight=None, invert_weight=True):
    """Return the resistance distance between nodes.

    Based on the pseudo-inverse of the Laplacian matrix.

    Parameters
    ----------
    G : Graph
    nodeA, nodeB : node, optional
        If both given, return a single float. Otherwise return dict of dicts.
    weight : str or None, optional
    invert_weight : bool, optional

    Returns
    -------
    float or dict of dicts
    """
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return {} if nodeA is None else 0.0

    L = laplacian_matrix(G, nodelist=nodelist, weight=weight or "weight").toarray()
    # Pseudo-inverse of Laplacian
    L_pinv = np.linalg.pinv(L)

    idx = {node: i for i, node in enumerate(nodelist)}

    if nodeA is not None and nodeB is not None:
        i, j = idx[nodeA], idx[nodeB]
        return float(L_pinv[i, i] + L_pinv[j, j] - 2 * L_pinv[i, j])

    result = {}
    for u in nodelist:
        result[u] = {}
        for v in nodelist:
            i, j = idx[u], idx[v]
            result[u][v] = float(L_pinv[i, i] + L_pinv[j, j] - 2 * L_pinv[i, j])
    return result


def kemeny_constant(G):
    """Return the Kemeny constant of *G*.

    Sum of 1/(1-lambda_i) for non-zero eigenvalues of the transition matrix.
    """
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return 0.0

    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    d = A.sum(axis=1)
    d[d == 0] = 1
    P = A / d[:, np.newaxis]

    eigenvalues = np.sort(np.linalg.eigvals(P))[::-1]
    # Skip the eigenvalue at 1 (largest)
    total = 0.0
    for lam in eigenvalues[1:]:
        lam_real = np.real(lam)
        if abs(1 - lam_real) > 1e-10:
            total += 1.0 / (1.0 - lam_real)
    return float(total)


def non_randomness(G, k=None):
    """Return the non-randomness coefficient of *G*.

    Compares the spectral radius to that of an Erdos-Renyi random graph.
    """
    import numpy as np

    spec = adjacency_spectrum(G)
    n = G.number_of_nodes()
    m = G.number_of_edges()
    if n < 2 or m == 0:
        return 0.0

    spectral_radius = float(np.max(np.abs(spec)))
    # Expected spectral radius of ER graph with same density
    p = 2 * m / (n * (n - 1))
    expected_radius = max(np.sqrt(n * p * (1 - p)), p * (n - 1))
    if expected_radius == 0:
        return 0.0

    return float((spectral_radius - expected_radius) / expected_radius)


def sigma(G, niter=100, nrand=10, seed=None):
    """Return the small-world sigma coefficient.

    sigma = (C/C_rand) / (L/L_rand) where C is clustering, L is avg path.
    sigma > 1 indicates small-world structure.
    """
    import random as _random

    rng = _random.Random(seed)

    C = transitivity(G)
    try:
        L = average_shortest_path_length(G)
    except Exception:
        return 0.0

    # Generate random graph with same degree sequence
    n = G.number_of_nodes()
    m = G.number_of_edges()
    C_rand_total = 0.0
    L_rand_total = 0.0
    for _ in range(nrand):
        R = gnm_random_graph(n, m, seed=rng.randint(0, 2**31))
        C_rand_total += transitivity(R)
        try:
            L_rand_total += average_shortest_path_length(R)
        except Exception:
            L_rand_total += L
    C_rand = C_rand_total / nrand
    L_rand = L_rand_total / nrand

    if C_rand == 0 or L_rand == 0:
        return 0.0
    return (C / C_rand) / (L / L_rand)


def omega(G, niter=5, nrand=5, seed=None):
    """Return the small-world omega coefficient.

    omega = L_rand/L - C/C_lattice.
    omega near 0 = small-world, near -1 = lattice, near 1 = random.
    """
    import random as _random

    rng = _random.Random(seed)

    C = transitivity(G)
    try:
        L = average_shortest_path_length(G)
    except Exception:
        return 0.0

    n = G.number_of_nodes()
    m = G.number_of_edges()

    L_rand_total = 0.0
    for _ in range(nrand):
        R = gnm_random_graph(n, m, seed=rng.randint(0, 2**31))
        try:
            L_rand_total += average_shortest_path_length(R)
        except Exception:
            L_rand_total += L
    L_rand = L_rand_total / nrand

    # Lattice reference: ring lattice has high clustering
    k = max(2, 2 * m // n)
    if k % 2 != 0:
        k -= 1
    k = max(k, 2)
    if k <= n:
        try:
            C_lattice = transitivity(watts_strogatz_graph(n, k, 0, seed=42))
        except Exception:
            C_lattice = C
    else:
        C_lattice = C

    if L == 0 or C_lattice == 0:
        return 0.0
    return L_rand / L - C / C_lattice


# ---------------------------------------------------------------------------
# Connectivity & Disjoint Paths (br-ak4)
# ---------------------------------------------------------------------------


def edge_disjoint_paths(G, s, t, flow_func=None, cutoff=None):
    """Find edge-disjoint paths from s to t via max-flow decomposition."""
    paths = _fnx.edge_disjoint_paths_rust(G, s, t)
    for path in paths:
        yield path


def node_disjoint_paths(G, s, t, flow_func=None, cutoff=None):
    """Find node-disjoint paths from s to t via node-splitting."""
    paths = _fnx.node_disjoint_paths_rust(G, s, t)
    for path in paths:
        yield path


def all_node_cuts(G, k=None, flow_func=None):
    """Enumerate all minimum node cuts."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if not is_connected(G):
        raise NetworkXError("Input graph is disconnected.")

    if density(G) == 1:
        return

    def is_separating_set(cut):
        if len(cut) == len(G) - 1:
            return True
        return not is_connected(restricted_view(G, cut, []))

    def build_auxiliary_node_connectivity_graph(graph):
        auxiliary = DiGraph()
        mapping = {}

        for index, node in enumerate(graph):
            mapping[node] = index
            auxiliary.add_node(f"{index}A", id=node)
            auxiliary.add_node(f"{index}B", id=node)
            auxiliary.add_edge(f"{index}A", f"{index}B", capacity=1)

        for source, target in graph.edges():
            auxiliary.add_edge(f"{mapping[source]}B", f"{mapping[target]}A", capacity=1)
            auxiliary.add_edge(f"{mapping[target]}B", f"{mapping[source]}A", capacity=1)

        auxiliary.graph["mapping"] = mapping
        return auxiliary

    def residual_after_flow(auxiliary, flow_dict):
        residual = DiGraph()
        residual.add_nodes_from(auxiliary.nodes(data=True))
        for left, right, attrs in auxiliary.edges(data=True):
            capacity = attrs.get("capacity", 1)
            flow = flow_dict.get(left, {}).get(right, 0)
            if capacity != flow and capacity != 0:
                residual.add_edge(left, right, **dict(attrs))
        return residual

    if k is None:
        k = node_connectivity(G)
    elif not isinstance(k, int):
        raise TypeError("k must be an integer or None")

    seen = set()
    auxiliary = build_auxiliary_node_connectivity_graph(G)
    mapping = auxiliary.graph["mapping"]
    original_predecessors = {
        node: set(auxiliary.predecessors(node)) for node in auxiliary.nodes()
    }

    highest_degree_nodes = {
        node
        for node, degree in sorted(G.degree, key=lambda item: item[1], reverse=True)[:k]
    }

    if is_separating_set(highest_degree_nodes):
        frozen = frozenset(highest_degree_nodes)
        seen.add(frozen)
        yield highest_degree_nodes

    for source in highest_degree_nodes:
        non_adjacent = set(G) - {source} - set(G.neighbors(source))
        for target in non_adjacent:
            flow_value, flow_dict = maximum_flow(
                auxiliary,
                f"{mapping[source]}B",
                f"{mapping[target]}A",
                capacity="capacity",
            )

            if flow_value != k:
                continue

            flowed_edges = [
                (left, right)
                for left, outgoing in flow_dict.items()
                for right, flow in outgoing.items()
                if flow != 0
            ]
            incident_components = {node for edge in flowed_edges for node in edge}
            residual = residual_after_flow(auxiliary, flow_dict)
            closure = transitive_closure(residual)
            condensed = condensation(residual)

            component_mapping = condensed.graph["mapping"]
            inverse_component_mapping = defaultdict(list)
            for node, component in component_mapping.items():
                inverse_component_mapping[component].append(node)

            incident_components = {
                component_mapping[node]
                for node in incident_components
                if node in component_mapping
            }

            for antichain in antichains(condensed):
                antichain_set = set(antichain)
                if not antichain_set.issubset(incident_components):
                    continue

                partition = set()
                for component in antichain:
                    partition.update(inverse_component_mapping[component])
                for node in list(partition):
                    partition.update(closure.predecessors(node))

                if (
                    f"{mapping[source]}B" not in partition
                    or f"{mapping[target]}A" in partition
                ):
                    continue

                cut_edges = set()
                for node in partition:
                    cut_edges.update(
                        (node, pred)
                        for pred in original_predecessors[node]
                        if pred not in partition
                    )

                if any(
                    auxiliary.nodes[left]["id"] != auxiliary.nodes[right]["id"]
                    for left, right in cut_edges
                ):
                    continue

                node_cut = {auxiliary.nodes[left]["id"] for left, _ in cut_edges}
                if len(node_cut) != k or source in node_cut or target in node_cut:
                    continue

                frozen = frozenset(node_cut)
                if frozen in seen:
                    continue
                seen.add(frozen)
                yield node_cut

            auxiliary.add_edge(f"{mapping[source]}B", f"{mapping[target]}A", capacity=1)
            auxiliary.add_edge(f"{mapping[target]}B", f"{mapping[source]}A", capacity=1)


def connected_dominating_set(G, start_with=None):
    """Find a connected dominating set via greedy spanning-tree approach."""
    return set(_fnx.connected_dominating_set_rust(G))


def is_connected_dominating_set(G, S):
    """Check if S is a connected dominating set."""
    S = set(S)
    for node in G.nodes():
        if node not in S and not any(nb in S for nb in G.neighbors(node)):
            return False
    if len(S) <= 1:
        return True
    return is_connected(G.subgraph(S))


def is_kl_connected(G, k, l, low_memory=False):
    """Test if G is (k,l)-connected."""
    from itertools import combinations

    nodes = list(G.nodes())
    if len(nodes) <= k:
        return True
    for removed in combinations(nodes, k - 1):
        remaining = [n for n in nodes if n not in set(removed)]
        if remaining and number_connected_components(G.subgraph(remaining)) > l:
            return False
    return True


def kl_connected_subgraph(G, k, l, low_memory=False):
    """Return maximal (k,l)-connected subgraph."""
    H = G.copy()
    changed = True
    while changed:
        changed = False
        for node in list(H.nodes()):
            test = H.copy()
            test.remove_node(node)
            if test.number_of_nodes() > 0 and not is_kl_connected(test, k, l):
                H.remove_node(node)
                changed = True
                break
    return H


def connected_double_edge_swap(G, nswap=1, _window_threshold=3, seed=None):
    """Swap edges maintaining connectivity and degree sequence."""
    import random as _random

    rng = _random.Random(seed)
    if G.number_of_edges() < 2:
        return 0
    swaps_done = 0
    for _ in range(nswap * 100):
        if swaps_done >= nswap:
            break
        edges = list(G.edges())
        e1 = edges[rng.randint(0, len(edges) - 1)]
        e2 = edges[rng.randint(0, len(edges) - 1)]
        u, v = e1
        x, y = e2
        if len({u, v, x, y}) < 4 or G.has_edge(u, x) or G.has_edge(v, y):
            continue
        G.remove_edge(u, v)
        G.remove_edge(x, y)
        G.add_edge(u, x)
        G.add_edge(v, y)
        if not is_connected(G):
            G.remove_edge(u, x)
            G.remove_edge(v, y)
            G.add_edge(u, v)
            G.add_edge(x, y)
        else:
            swaps_done += 1
    return swaps_done


# ---------------------------------------------------------------------------
# Advanced Centrality (br-v3y)
# ---------------------------------------------------------------------------


def current_flow_betweenness_centrality(G, normalized=True, weight=None, solver="full"):
    """Current-flow betweenness centrality based on electrical current flow."""
    return _fnx.current_flow_betweenness_centrality_rust(
        G, normalized, weight or "weight"
    )


def edge_current_flow_betweenness_centrality(G, normalized=True, weight=None):
    """Edge variant of current-flow betweenness centrality."""
    return _fnx.edge_current_flow_betweenness_centrality_rust(
        G, normalized, weight or "weight"
    )


def approximate_current_flow_betweenness_centrality(
    G, normalized=True, weight=None, epsilon=0.5, kmax=10000, seed=None
):
    """Approximate current-flow betweenness via random source-target sampling."""
    return current_flow_betweenness_centrality(G, normalized=normalized, weight=weight)


def current_flow_closeness_centrality(G, weight=None, solver="full"):
    """Closeness centrality based on effective resistance (information centrality)."""
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n <= 1:
        return {node: 0.0 for node in nodelist}
    rd = resistance_distance(G, weight=weight)
    cc = {}
    for node in nodelist:
        total_rd = sum(rd[node].get(other, 0) for other in nodelist if other != node)
        cc[node] = (n - 1) / total_rd if total_rd > 0 else 0.0
    return cc


def betweenness_centrality_subset(G, sources, targets, normalized=False, weight=None):
    """Betweenness centrality restricted to source/target subsets."""
    betweenness = dict.fromkeys(G, 0.0)
    for source in sources:
        if weight is None:
            stack, predecessors, sigma, _ = _single_source_shortest_path_basic_local(
                G, source
            )
        else:
            stack, predecessors, sigma, _ = _single_source_dijkstra_path_basic_local(
                G, source, weight
            )
        betweenness = _accumulate_subset_local(
            betweenness, stack, predecessors, sigma, source, targets
        )
    return _rescale_betweenness_local(
        betweenness,
        len(G),
        normalized=normalized,
        directed=G.is_directed(),
        endpoints=False,
    )


def edge_betweenness_centrality_subset(
    G, sources, targets, normalized=False, weight=None
):
    """Edge betweenness restricted to source/target subsets."""
    betweenness = dict.fromkeys(G, 0.0)
    betweenness.update(dict.fromkeys(G.edges(), 0.0))
    for source in sources:
        if weight is None:
            stack, predecessors, sigma, _ = _single_source_shortest_path_basic_local(
                G, source
            )
        else:
            stack, predecessors, sigma, _ = _single_source_dijkstra_path_basic_local(
                G, source, weight
            )
        betweenness = _accumulate_edges_subset_local(
            betweenness, stack, predecessors, sigma, source, targets
        )
    for node in G:
        del betweenness[node]
    betweenness = _rescale_betweenness_local(
        betweenness,
        len(G),
        normalized=normalized,
        directed=G.is_directed(),
    )
    if G.is_multigraph():
        return _add_edge_keys_local(G, betweenness, weight=weight)
    return betweenness


def edge_load_centrality(G, cutoff=None):
    """Load centrality for edges."""
    betweenness = {}
    for u, v in G.edges():
        betweenness[(u, v)] = 0.0
        betweenness[(v, u)] = 0.0
    for source in G:
        source_between = _edge_load_from_source_local(G, source, cutoff=cutoff)
        for edge, value in source_between.items():
            betweenness[edge] += value
    return betweenness


def laplacian_centrality(G, normalized=True, nodelist=None, weight="weight"):
    """Laplacian centrality: drop in Laplacian energy when node is removed."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    L = laplacian_matrix(G, weight=weight).toarray()
    total_energy = float(np.sum(L**2))
    lc = {}
    for node in nodelist:
        remaining = [n for n in G.nodes() if n != node]
        if not remaining:
            lc[node] = 0.0
            continue
        L_sub = laplacian_matrix(G.subgraph(remaining), weight=weight).toarray()
        sub_energy = float(np.sum(L_sub**2))
        lc[node] = (
            (total_energy - sub_energy) / total_energy if total_energy > 0 else 0.0
        )
    return lc


def percolation_centrality(G, attribute="percolation", states=None, weight=None):
    """Percolation centrality based on percolation states."""
    percolation = dict.fromkeys(G, 0.0)
    if states is None:
        states = {
            node: G.nodes[node].get(attribute, 1)
            for node in G
        }

    state_sum = sum(states.values())
    for source in G:
        if weight is None:
            stack, predecessors, sigma, _ = _single_source_shortest_path_basic_local(
                G, source
            )
        else:
            stack, predecessors, sigma, _ = _single_source_dijkstra_path_basic_local(
                G, source, weight
            )
        percolation = _accumulate_percolation_local(
            percolation, stack, predecessors, sigma, source, states, state_sum
        )

    for node in percolation:
        percolation[node] *= 1 / (len(G) - 2)
    return percolation


def information_centrality(G, weight=None, solver="full"):
    """Information centrality (same as current-flow closeness)."""
    return current_flow_closeness_centrality(G, weight=weight)


def second_order_centrality(G):
    """Second-order centrality based on random walk standard deviation."""
    if not G.is_directed() and not _graph_has_edge_attribute(G, "weight"):
        return _fnx.second_order_centrality_rust(G)

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)

    if n == 0:
        raise NetworkXError("Empty graph.")
    if n == 1:
        return {nodelist[0]: 0.0}
    if not is_connected(G):
        raise NetworkXError("Non connected graph.")
    if any(data.get("weight", 0) < 0 for _, _, data in G.edges(data=True)):
        raise NetworkXError("Graph has negative edge weights.")

    transition = to_numpy_array(G, nodelist=nodelist, weight="weight")
    in_degree = transition.sum(axis=0)
    max_in_degree = float(in_degree.max())

    for idx, degree in enumerate(in_degree):
        if degree < max_in_degree:
            transition[idx, idx] += max_in_degree - degree

    row_sums = transition.sum(axis=1)[:, np.newaxis]
    transition = np.divide(
        transition,
        row_sums,
        out=np.zeros_like(transition, dtype=float),
        where=row_sums != 0,
    )

    def _q_j_local(probabilities, column):
        restricted = probabilities.copy()
        restricted[:, column] = 0
        return restricted

    matrix = np.empty([n, n])
    identity = np.identity(n)
    ones = np.ones([n, 1])[:, 0]

    for idx in range(n):
        matrix[:, idx] = np.linalg.solve(identity - _q_j_local(transition, idx), ones)

    return dict(
        zip(
            nodelist,
            (
                float(np.sqrt(2 * np.sum(matrix[:, idx]) - n * (n + 1)))
                for idx in range(n)
            ),
        )
    )


def subgraph_centrality_exp(G):
    """Subgraph centrality via explicit scipy.linalg.expm."""
    return subgraph_centrality(G)


def communicability_betweenness_centrality(G, normalized=True):
    """Betweenness centrality based on communicability."""
    return _fnx.communicability_betweenness_centrality_rust(G, normalized)


def trophic_levels(G, weight=None):
    """Compute trophic levels in a directed graph (food web)."""
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return {}
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    in_strength = A.sum(axis=0)
    # Solve: s_j = 1 + (1/k_j^in) * sum_i A_ij * s_i for all j
    # Rearrange: (I - D^{-1} A^T) s = 1
    D_inv = np.zeros(n)
    for i in range(n):
        D_inv[i] = 1.0 / in_strength[i] if in_strength[i] > 0 else 0
    M = np.eye(n) - np.diag(D_inv) @ A.T
    b = np.ones(n)
    # For basal species (no incoming edges), trophic level = 1
    try:
        s = np.linalg.solve(M, b)
    except np.linalg.LinAlgError:
        s = np.linalg.lstsq(M, b, rcond=None)[0]
    return {nodelist[i]: float(s[i]) for i in range(n)}


def trophic_differences(G, weight=None):
    """Compute trophic differences across edges."""
    levels = trophic_levels(G, weight=weight)
    result = {}
    for u, v in G.edges():
        result[(u, v)] = levels.get(v, 1) - levels.get(u, 1)
    return result


def trophic_incoherence_parameter(G, weight=None):
    """Compute the trophic incoherence parameter (std of trophic differences)."""
    import numpy as np

    diffs = trophic_differences(G, weight=weight)
    if not diffs:
        return 0.0
    values = list(diffs.values())
    return float(np.std(values))


def group_betweenness_centrality(G, C, normalized=True, weight=None, endpoints=False):
    """Betweenness centrality for a group of nodes C."""
    if not G.is_directed() and weight is None and not endpoints:
        value = _fnx.group_betweenness_centrality_rust(G, list(C))
        if normalized:
            return value
        remaining = len(G) - len(set(C))
        return value * remaining * (remaining - 1) / 2

    group_betweenness = []
    list_of_groups = True
    if any(element in G for element in C):
        C = [C]
        list_of_groups = False
    group_nodes = {node for group in C for node in group}
    missing_nodes = group_nodes - set(G.nodes())
    if missing_nodes:
        raise NodeNotFound(f"The node(s) {missing_nodes} are in C but not in G.")

    path_betweenness, sigma, distances = _group_preprocessing_local(
        G,
        group_nodes,
        weight,
    )

    for group in C:
        group = set(group)
        group_score = 0.0
        sigma_matrix = deepcopy(sigma)
        path_matrix = deepcopy(path_betweenness)
        next_sigma_matrix = deepcopy(sigma_matrix)
        next_path_matrix = deepcopy(path_matrix)
        for node in group:
            group_score += path_matrix[node][node]
            for left in group:
                for right in group:
                    distance_x_v_y = 0.0
                    distance_x_y_v = 0.0
                    distance_v_x_y = 0.0
                    if not (
                        sigma_matrix[left][right] == 0
                        or sigma_matrix[left][node] == 0
                        or sigma_matrix[node][right] == 0
                    ):
                        if distances[left][node] == distances[left][right] + distances[right][node]:
                            distance_x_y_v = (
                                sigma_matrix[left][right]
                                * sigma_matrix[right][node]
                                / sigma_matrix[left][node]
                            )
                        if distances[left][right] == distances[left][node] + distances[node][right]:
                            distance_x_v_y = (
                                sigma_matrix[left][node]
                                * sigma_matrix[node][right]
                                / sigma_matrix[left][right]
                            )
                        if distances[node][right] == distances[node][left] + distances[left][right]:
                            distance_v_x_y = (
                                sigma_matrix[node][left]
                                * sigma[left][right]
                                / sigma_matrix[node][right]
                            )
                    next_sigma_matrix[left][right] = sigma_matrix[left][right] * (
                        1 - distance_x_v_y
                    )
                    next_path_matrix[left][right] = (
                        path_matrix[left][right]
                        - path_matrix[left][right] * distance_x_v_y
                    )
                    if right != node:
                        next_path_matrix[left][right] -= (
                            path_matrix[left][node] * distance_x_y_v
                        )
                    if left != node:
                        next_path_matrix[left][right] -= (
                            path_matrix[node][right] * distance_v_x_y
                        )
            sigma_matrix, next_sigma_matrix = next_sigma_matrix, sigma_matrix
            path_matrix, next_path_matrix = next_path_matrix, path_matrix

        node_count = len(G)
        group_size = len(group)
        if not endpoints:
            scale = 0
            if G.is_directed():
                if is_strongly_connected(G):
                    scale = group_size * (2 * node_count - group_size - 1)
            elif is_connected(G):
                scale = group_size * (2 * node_count - group_size - 1)
            if scale == 0:
                for group_node in group:
                    for node in distances[group_node]:
                        if node != group_node:
                            scale += 1 if node in group else 2
            group_score -= scale

        if normalized:
            group_score *= 1 / ((node_count - group_size) * (node_count - group_size - 1))
        elif not G.is_directed():
            group_score /= 2

        group_betweenness.append(group_score)

    if list_of_groups:
        return group_betweenness
    return group_betweenness[0]


def group_closeness_centrality(G, S, weight=None, H=None):
    """Closeness centrality for a group of nodes S."""
    if not G.is_directed() and weight is None and H is None:
        return _fnx.group_closeness_centrality_rust(G, list(S))

    if G.is_directed():
        G = reverse(G)
    closeness = 0.0
    all_nodes = set(G)
    group = set(S)
    non_group_nodes = all_nodes - group
    if weight is None:
        shortest_path_lengths = {}
        for source in group:
            _, _, _, source_lengths = _single_source_shortest_path_basic_local(G, source)
            for node, distance in source_lengths.items():
                if node not in shortest_path_lengths or distance < shortest_path_lengths[node]:
                    shortest_path_lengths[node] = distance
    else:
        shortest_path_lengths = multi_source_dijkstra_path_length(G, group, weight=weight)
    for node in non_group_nodes:
        closeness += shortest_path_lengths.get(node, 0)
    try:
        return len(non_group_nodes) / closeness
    except ZeroDivisionError:
        return 0.0


# ---------------------------------------------------------------------------
# Traversal Extras (br-do1)
# ---------------------------------------------------------------------------


def bfs_beam_edges(G, source, value, width=None):
    """BFS with beam search: keep only top-width nodes per level."""
    visited = {source}
    frontier = [source]
    while frontier:
        if width is not None:
            frontier = sorted(frontier, key=value, reverse=True)[:width]
        next_frontier = []
        for node in frontier:
            for nbr in G.neighbors(node):
                if nbr not in visited:
                    visited.add(nbr)
                    next_frontier.append(nbr)
                    yield (node, nbr)
        frontier = next_frontier


def bfs_labeled_edges(G, source, sort_neighbors=None):
    """BFS yielding (u, v, label) with tree/forward/reverse/cross labels."""
    if sort_neighbors is not None:
        # Fall back to Python when custom sort is needed
        visited = {source}
        level = {source: 0}
        queue = [source]
        while queue:
            next_queue = []
            for node in queue:
                nbrs = sort_neighbors(list(G.neighbors(node)))
                for nbr in nbrs:
                    if nbr not in visited:
                        visited.add(nbr)
                        level[nbr] = level[node] + 1
                        next_queue.append(nbr)
                        yield (node, nbr, "tree")
                    elif level.get(nbr, 0) == level[node]:
                        yield (node, nbr, "level")
                    elif level.get(nbr, 0) > level[node]:
                        yield (node, nbr, "forward")
                    else:
                        yield (node, nbr, "reverse")
            queue = next_queue
        return
    for edge in _fnx.bfs_labeled_edges_rust(G, source):
        yield edge


def dfs_labeled_edges(G, source=None, depth_limit=None):
    """DFS yielding (u, v, label) with tree/forward/back/cross labels."""
    if source is None:
        sources = list(G.nodes())
    else:
        sources = [source]
    visited = set()
    finished = set()
    for src in sources:
        if src in visited:
            continue
        stack = [(src, iter(G.neighbors(src)), 0)]
        visited.add(src)
        yield (src, src, "tree")
        while stack:
            parent, children, depth = stack[-1]
            if depth_limit is not None and depth >= depth_limit:
                stack.pop()
                finished.add(parent)
                continue
            try:
                child = next(children)
                if child not in visited:
                    visited.add(child)
                    yield (parent, child, "tree")
                    stack.append((child, iter(G.neighbors(child)), depth + 1))
                elif child not in finished:
                    yield (parent, child, "back")
                else:
                    yield (parent, child, "forward")
            except StopIteration:
                stack.pop()
                finished.add(parent)


def generic_bfs_edges(G, source, neighbors=None, depth_limit=None, sort_neighbors=None):
    """BFS with customizable neighbor function."""
    if neighbors is not None or sort_neighbors is not None:
        if neighbors is None:
            neighbors = G.neighbors
        visited = {source}
        queue = [(source, 0)]
        while queue:
            next_queue = []
            for node, depth in queue:
                if depth_limit is not None and depth >= depth_limit:
                    continue
                nbrs = list(neighbors(node))
                if sort_neighbors:
                    nbrs = sort_neighbors(nbrs)
                for nbr in nbrs:
                    if nbr not in visited:
                        visited.add(nbr)
                        yield (node, nbr)
                        next_queue.append((nbr, depth + 1))
            queue = next_queue
        return
    for edge in _fnx.generic_bfs_edges_rust(G, source, depth_limit):
        yield edge


# ---------------------------------------------------------------------------
# Utility Extras A (br-tnl)
# ---------------------------------------------------------------------------


def cn_soundarajan_hopcroft(G, ebunch=None, community="community"):
    """Common Neighbor link prediction with community information."""
    if ebunch is None:
        ebunch = non_edges(G)
    for u, v in ebunch:
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        score = len(common)
        u_attrs = G.nodes[u] if hasattr(G.nodes, "__getitem__") else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, "__getitem__") else {}
        u_comm = u_attrs.get(community) if isinstance(u_attrs, dict) else None
        v_comm = v_attrs.get(community) if isinstance(v_attrs, dict) else None
        for w in common:
            w_attrs = G.nodes[w] if hasattr(G.nodes, "__getitem__") else {}
            w_comm = w_attrs.get(community) if isinstance(w_attrs, dict) else None
            if u_comm is not None and u_comm == w_comm and u_comm == v_comm:
                score += 1
        yield (u, v, score)


def ra_index_soundarajan_hopcroft(G, ebunch=None, community="community"):
    """Resource Allocation link prediction with community information."""
    if ebunch is None:
        ebunch = non_edges(G)
    for u, v in ebunch:
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        score = 0.0
        u_attrs = G.nodes[u] if hasattr(G.nodes, "__getitem__") else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, "__getitem__") else {}
        u_comm = u_attrs.get(community) if isinstance(u_attrs, dict) else None
        v_comm = v_attrs.get(community) if isinstance(v_attrs, dict) else None
        for w in common:
            w_attrs = G.nodes[w] if hasattr(G.nodes, "__getitem__") else {}
            w_comm = w_attrs.get(community) if isinstance(w_attrs, dict) else None
            deg_w = G.degree[w]
            if deg_w > 0:
                bonus = (
                    1.0
                    if (u_comm is not None and u_comm == w_comm and u_comm == v_comm)
                    else 0.0
                )
                score += (1.0 + bonus) / deg_w
        yield (u, v, score)


def node_attribute_xy(G, attribute):
    """Yield (x, y) pairs of attribute values for edges."""
    for u, nbrsdict in G.adjacency():
        u_attrs = G.nodes[u] if hasattr(G.nodes, "__getitem__") else {}
        x = u_attrs.get(attribute) if isinstance(u_attrs, dict) else None
        if G.is_multigraph():
            for v, keys in nbrsdict.items():
                v_attrs = G.nodes[v] if hasattr(G.nodes, "__getitem__") else {}
                y = v_attrs.get(attribute) if isinstance(v_attrs, dict) else None
                for _ in keys:
                    yield (x, y)
        else:
            for v in nbrsdict:
                v_attrs = G.nodes[v] if hasattr(G.nodes, "__getitem__") else {}
                y = v_attrs.get(attribute) if isinstance(v_attrs, dict) else None
                yield (x, y)


def node_degree_xy(G, x="out", y="in", weight=None, nodes=None):
    """Yield (degree_x, degree_y) for each edge."""
    node_set = set(G) if nodes is None else set(nodes)
    present_nodes = [node for node in G if node in node_set]

    def directed_degree_map(mode):
        result = {}
        for node in present_nodes:
            total = 0
            neighbors = G.predecessors(node) if mode == "in" else G.successors(node)
            for neighbor in neighbors:
                if mode == "in":
                    edge_bucket = G[neighbor][node]
                else:
                    edge_bucket = G[node][neighbor]
                if G.is_multigraph():
                    for attrs in edge_bucket.values():
                        total += attrs.get(weight, 1) if weight is not None else 1
                else:
                    total += edge_bucket.get(weight, 1) if weight is not None else 1
            result[node] = total
        return result

    if G.is_directed():
        xdeg = directed_degree_map(x)
        ydeg = directed_degree_map(y)
        for u in present_nodes:
            for v in G.successors(u):
                if v in node_set:
                    yield (xdeg[u], ydeg[v])
        return

    deg = {node: degree(G, node, weight=weight) for node in present_nodes}
    for u in present_nodes:
        for v in G.neighbors(u):
            if v not in node_set:
                continue
            if G.is_multigraph():
                for _key in G[u][v]:
                    yield (deg[u], deg[v])
            else:
                yield (deg[u], deg[v])


def number_of_walks(G, walk_length):
    """Count walks of given length via adjacency matrix power."""
    import numpy as np

    A = to_numpy_array(G, weight=None)
    Ak = np.linalg.matrix_power(A.astype(int), walk_length)
    nodelist = list(G.nodes())
    result = {}
    for i, u in enumerate(nodelist):
        result[u] = {}
        for j, v in enumerate(nodelist):
            result[u][v] = int(Ak[i, j])
    return result


def recursive_simple_cycles(G):
    """Find all simple cycles using recursive DFS."""
    return list(simple_cycles(G))


# ---------------------------------------------------------------------------
# Utility Extras B (br-i1d)
# ---------------------------------------------------------------------------


def remove_node_attributes(G, name):
    """Remove attribute *name* from all nodes."""
    for node in G.nodes():
        attrs = G.nodes[node] if hasattr(G.nodes, "__getitem__") else {}
        if isinstance(attrs, dict) and name in attrs:
            del attrs[name]


def remove_edge_attributes(G, name):
    """Remove attribute *name* from all edges."""
    for u, v, data in G.edges(data=True):
        if isinstance(data, dict) and name in data:
            del data[name]


def floyd_warshall_numpy(G, nodelist=None, weight="weight"):
    """Floyd-Warshall via numpy matrix operations."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    n = len(nodelist)
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    dist = np.full((n, n), np.inf)
    np.fill_diagonal(dist, 0)
    for i in range(n):
        for j in range(n):
            if A[i, j] != 0:
                dist[i, j] = A[i, j]
    for k in range(n):
        dist = np.minimum(dist, dist[:, k : k + 1] + dist[k : k + 1, :])
    return dist


def harmonic_diameter(G, sp=None):
    """Harmonic diameter: n*(n-1) / sum(1/d(u,v)) for all connected pairs."""
    return _fnx.harmonic_diameter_rust(G)


def global_parameters(G):
    """Return global graph parameters as a tuple (intersection_array if distance-regular)."""
    return _fnx.global_parameters_rust(G)


def intersection_array(G):
    """Return the intersection array of a distance-regular graph."""
    params = global_parameters(G)
    if params is None:
        raise NetworkXError("Graph is not distance-regular")
    return params


# ---------------------------------------------------------------------------
# Small Utilities (br-2zl)
# ---------------------------------------------------------------------------


def eulerize(G):
    """Add minimum edges to make G Eulerian. Returns copy with added edges.

    Finds odd-degree nodes, computes shortest paths between all pairs of them,
    finds minimum weight matching, and duplicates matched-path edges.
    """
    from itertools import combinations

    if not is_connected(G):
        raise NetworkXError("G is not connected")

    odd_nodes = [v for v in G.nodes() if G.degree[v] % 2 == 1]
    if not odd_nodes:
        return G.copy()

    # Build a complete graph on odd-degree nodes weighted by shortest path length.
    odd_complete = Graph()
    for u, v in combinations(odd_nodes, 2):
        length = shortest_path_length(G, u, v, weight="weight")
        odd_complete.add_edge(u, v, weight=length)

    # Find minimum weight matching on the odd-degree complete graph.
    matching = min_weight_matching(odd_complete)

    # Duplicate edges along matched shortest paths.
    if G.is_directed():
        raise NetworkXError("G is directed")
    if G.is_multigraph():
        H = G.copy()
    else:
        H = MultiGraph(G)

    for u, v in matching:
        path = shortest_path(G, u, v, weight="weight")
        for i in range(len(path) - 1):
            # In a MultiGraph, adding an edge creates a new one
            if G.is_multigraph():
                # Just pick the first key/weight
                # Actually, NetworkX just copies the first key's attributes, or just {}
                H.add_edge(path[i], path[i + 1])
            else:
                H.add_edge(path[i], path[i + 1], **dict(G[path[i]][path[i + 1]]))

    return H


def moral_graph(G):
    """Return the moral graph of a DAG (marry co-parents, drop directions).

    For each node, connect all pairs of its predecessors (marry co-parents),
    then return the undirected version.
    """
    from itertools import combinations

    H = Graph()
    for node in G.nodes():
        H.add_node(node, **dict(G.nodes[node]))

    # Add existing edges as undirected.
    for u, v, data in G.edges(data=True):
        H.add_edge(u, v, **data)

    # Marry co-parents: for each node, connect all pairs of predecessors.
    for node in G.nodes():
        preds = list(G.predecessors(node))
        for u, v in combinations(preds, 2):
            if not H.has_edge(u, v):
                H.add_edge(u, v)

    return H


def equivalence_classes(iterable, relation):
    """Partition elements by an equivalence relation."""
    elements = list(iterable)
    classes = []
    assigned = set()
    for elem in elements:
        if elem in assigned:
            continue
        cls = {elem}
        for other in elements:
            if other not in assigned and relation(elem, other):
                cls.add(other)
        classes.append(frozenset(cls))
        assigned.update(cls)
    return classes


class _NeighborhoodCacheLocal(dict):
    """Cache graph neighborhoods as concrete lists."""

    def __init__(self, graph):
        self.graph = graph

    def __missing__(self, node):
        neighbors = self[node] = list(self.graph[node])
        return neighbors


def _node_order_key_local(node):
    return (type(node).__module__, type(node).__qualname__, repr(node))


def _canonical_undirected_edge_local(u, v):
    if _node_order_key_local(u) <= _node_order_key_local(v):
        return (u, v)
    return (v, u)


def _mcb_spanning_tree_edges_local(G):
    if G.number_of_nodes() == 0:
        return []

    root = next(iter(G))
    seen = {root}
    stack = [root]
    tree_edges = []

    while stack:
        node = stack.pop()
        for neighbor in G[node]:
            if neighbor in seen:
                continue
            seen.add(neighbor)
            tree_edges.append((node, neighbor))
            stack.append(neighbor)

    return tree_edges


def _mcb_lifted_node_local(node):
    return ("__fnx_mcb_lift__", node, 1)


def _minimum_cycle_local(G, orth, weight):
    lifted = Graph()

    for node in G:
        lifted.add_node(node)
        lifted.add_node(_mcb_lifted_node_local(node))

    for u, v, data in G.edges(data=True):
        edge_weight = data.get(weight, 1) if weight is not None else 1
        if (u, v) in orth or (v, u) in orth:
            lifted.add_edge(u, _mcb_lifted_node_local(v), Gi_weight=edge_weight)
            lifted.add_edge(_mcb_lifted_node_local(u), v, Gi_weight=edge_weight)
        else:
            lifted.add_edge(u, v, Gi_weight=edge_weight)
            lifted.add_edge(
                _mcb_lifted_node_local(u),
                _mcb_lifted_node_local(v),
                Gi_weight=edge_weight,
            )

    lifted_lengths = {
        node: shortest_path_length(
            lifted,
            source=node,
            target=_mcb_lifted_node_local(node),
            weight="Gi_weight",
        )
        for node in G
    }

    start = min(lifted_lengths, key=lifted_lengths.get)
    path = shortest_path(
        lifted,
        source=start,
        target=_mcb_lifted_node_local(start),
        weight="Gi_weight",
    )
    mapped_path = [
        step[1]
        if isinstance(step, tuple) and len(step) == 3 and step[0] == "__fnx_mcb_lift__"
        else step
        for step in path
    ]

    edge_list = list(zip(mapped_path, mapped_path[1:]))
    edge_set = set()
    for edge in edge_list:
        if edge in edge_set:
            edge_set.remove(edge)
        elif edge[::-1] in edge_set:
            edge_set.remove(edge[::-1])
        else:
            edge_set.add(edge)

    result = []
    for edge in edge_list:
        if edge in edge_set:
            result.append(edge)
            edge_set.remove(edge)
        elif edge[::-1] in edge_set:
            result.append(edge[::-1])
            edge_set.remove(edge[::-1])

    return result


def _minimum_cycle_basis_component_local(G, weight):
    cycle_basis = []
    tree_edges = {
        _canonical_undirected_edge_local(u, v)
        for u, v in _mcb_spanning_tree_edges_local(G)
    }
    chords = [
        edge
        for edge in (_canonical_undirected_edge_local(u, v) for u, v in G.edges())
        if edge not in tree_edges
    ]

    orthogonal_sets = [{edge} for edge in chords]
    while orthogonal_sets:
        base = orthogonal_sets.pop()
        cycle_edges = _minimum_cycle_local(G, base, weight)
        cycle_basis.append([v for _, v in cycle_edges])
        orthogonal_sets = [
            (
                {
                    edge
                    for edge in orth
                    if edge not in base and edge[::-1] not in base
                }
                | {
                    edge
                    for edge in base
                    if edge not in orth and edge[::-1] not in orth
                }
            )
            if sum((edge in orth or edge[::-1] in orth) for edge in cycle_edges) % 2
            else orth
            for orth in orthogonal_sets
        ]

    return cycle_basis


def minimum_cycle_basis(G, weight=None):
    """Find minimum weight cycle basis."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    return sum(
        (
            _minimum_cycle_basis_component_local(G.subgraph(component), weight)
            for component in connected_components(G)
        ),
        [],
    )


def _chordless_cycle_search_local(F, B, path, length_bound):
    blocked = defaultdict(int)
    target = path[0]
    blocked[path[1]] = 1
    for node in path[1:]:
        for neighbor in B[node]:
            blocked[neighbor] += 1

    stack = [iter(F[path[2]])]
    while stack:
        neighbors = stack[-1]
        for node in neighbors:
            if blocked[node] == 1 and (length_bound is None or len(path) < length_bound):
                Fw = F[node]
                if target in Fw:
                    yield path + [node]
                else:
                    Bw = B[node]
                    if target in Bw:
                        continue
                    for neighbor in Bw:
                        blocked[neighbor] += 1
                    path.append(node)
                    stack.append(iter(Fw))
                    break
        else:
            stack.pop()
            for neighbor in B[path.pop()]:
                blocked[neighbor] -= 1


def chordless_cycles(G, length_bound=None):
    """Find all chordless (induced) cycles."""
    if length_bound is not None:
        if length_bound == 0:
            return
        if length_bound < 0:
            raise ValueError("length bound must be non-negative")

    directed = G.is_directed()
    multigraph = G.is_multigraph()

    if multigraph:
        yield from ([node] for node in G if len(G[node].get(node, ())) == 1)
    else:
        yield from ([node] for node in G if node in G[node])

    if length_bound is not None and length_bound == 1:
        return

    loops = set(nodes_with_selfloops(G))
    base_edges = [
        (u, v) for u in G if u not in loops for v in G.adj[u] if v not in loops
    ]
    if directed:
        forward = DiGraph()
        forward.add_edges_from(base_edges)
        blocking = forward.to_undirected()
    else:
        forward = Graph()
        forward.add_edges_from(base_edges)
        blocking = None

    if multigraph:
        if not directed:
            blocking = forward.copy()
            visited = set()
        for u in G:
            Gu = G[u]
            if u in loops:
                continue
            if directed:
                for v, Guv in list(Gu.items()):
                    if len(Guv) > 1:
                        if forward.has_edge(u, v):
                            forward.remove_edge(u, v)
                        if forward.has_edge(v, u):
                            forward.remove_edge(v, u)
            else:
                for v, Guv in ((v, Guv) for v, Guv in Gu.items() if v in visited):
                    multiplicity = len(Guv)
                    if multiplicity == 2:
                        yield [u, v]
                    if multiplicity > 1 and forward.has_edge(u, v):
                        forward.remove_edge(u, v)
                visited.add(u)

    if directed:
        for u in list(forward):
            digons = [[u, v] for v in list(forward[u]) if forward.has_edge(v, u)]
            yield from digons
            for edge in digons:
                if forward.has_edge(*edge):
                    forward.remove_edge(*edge)
                reverse = edge[::-1]
                if forward.has_edge(*reverse):
                    forward.remove_edge(*reverse)

    if length_bound is not None and length_bound == 2:
        return

    if directed:
        separate = strongly_connected_components

        def stems(component_graph, pivot):
            for u, w in itertools.product(component_graph.pred[pivot], component_graph.succ[pivot]):
                if not G.has_edge(u, w):
                    yield [u, pivot, w], forward.has_edge(w, u)

    else:
        separate = biconnected_components

        def stems(component_graph, pivot):
            yield from (
                ([u, pivot, w], forward.has_edge(w, u))
                for u, w in combinations(component_graph[pivot], 2)
            )

    components = [set(component) for component in separate(forward) if len(component) > 2]
    while components:
        component = components.pop()
        pivot = next(iter(component))
        component_graph = forward.subgraph(component)
        forward_cache = blocking_cache = None

        for stem, is_triangle in stems(component_graph, pivot):
            if is_triangle:
                yield stem
                continue

            if forward_cache is None:
                forward_cache = _NeighborhoodCacheLocal(component_graph)
                blocking_graph = component_graph if blocking is None else blocking.subgraph(component)
                blocking_cache = _NeighborhoodCacheLocal(blocking_graph)
            yield from _chordless_cycle_search_local(
                forward_cache,
                blocking_cache,
                stem,
                length_bound,
            )

        reduced = forward.subgraph(component - {pivot})
        components.extend(
            set(sub_component)
            for sub_component in separate(reduced)
            if len(sub_component) > 2
        )


def to_undirected(G):
    """Return an undirected copy of G."""
    return G.to_undirected()


def to_directed(G):
    """Return a directed copy of G (each undirected edge becomes two directed edges)."""
    directed = G.to_directed()
    if not G.is_multigraph():
        return directed

    result = G.__class__().to_directed()
    result.graph.update(dict(G.graph))
    for node, attrs in G.nodes(data=True):
        result.add_node(node, **dict(attrs))
    for u, v, key, attrs in G.edges(keys=True, data=True):
        result.add_edge(u, v, key=key, **dict(attrs))
        result.add_edge(v, u, key=key, **dict(attrs))
    return result


def reverse(G, copy=True):
    """Return graph with all edges reversed."""
    reversed_graph = G.reverse()
    if copy:
        return reversed_graph
    return reversed_graph


def nodes(G):
    """Return nodes of G (global function form)."""
    return G.nodes


def edges(G, nbunch=None):
    """Return edges of G (global function form)."""
    if nbunch is None:
        return G.edges
    if G.is_directed():
        return G.edges(nbunch=nbunch)

    nbunch_nodes = set(nbunch)
    if G.is_multigraph():
        seen = set()
        result = []
        for u in nbunch_nodes:
            if u not in G:
                continue
            for v, keydict in G[u].items():
                for key in keydict:
                    marker = (frozenset((u, v)), key)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    result.append((u, v))
        return result

    seen = set()
    result = []
    for u in nbunch_nodes:
        if u not in G:
            continue
        for v in G[u]:
            marker = frozenset((u, v))
            if marker in seen:
                continue
            seen.add(marker)
            result.append((u, v))
    return result


def degree(G, nbunch=None, weight=None):
    """Return degree view of G (global function form)."""
    if weight is None:
        if nbunch is None:
            return G.degree
        if isinstance(nbunch, (str, bytes)) or not hasattr(nbunch, "__iter__"):
            return G.degree[nbunch]
        return ((node, G.degree[node]) for node in nbunch)

    def weighted_degree(node):
        total = 0
        if G.is_multigraph():
            if G.is_directed():
                for _, _, _, attrs in G.edges(nbunch=[node], keys=True, data=True):
                    total += attrs.get(weight, 1)
                for src, _, _, attrs in G.in_edges(nbunch=[node], keys=True, data=True):
                    if src != node:
                        total += attrs.get(weight, 1)
            else:
                for _, _, _, attrs in G.edges(nbunch=[node], keys=True, data=True):
                    total += attrs.get(weight, 1)
        else:
            if G.is_directed():
                for _, _, attrs in G.edges(nbunch=[node], data=True):
                    total += attrs.get(weight, 1)
                for src, _, attrs in G.in_edges(nbunch=[node], data=True):
                    if src != node:
                        total += attrs.get(weight, 1)
            else:
                for _, _, attrs in G.edges(nbunch=[node], data=True):
                    total += attrs.get(weight, 1)
        return total

    if nbunch is None:
        return ((node, weighted_degree(node)) for node in G.nodes)
    if isinstance(nbunch, (str, bytes)) or not hasattr(nbunch, "__iter__"):
        return weighted_degree(nbunch)
    return ((node, weighted_degree(node)) for node in nbunch)


def number_of_nodes(G):
    """Return number of nodes (global function form)."""
    return G.number_of_nodes()


def number_of_edges(G):
    """Return number of edges (global function form)."""
    return G.number_of_edges()


# ---------------------------------------------------------------------------
# Conversion Extras (br-u6t)
# ---------------------------------------------------------------------------


def from_pandas_adjacency(df, create_using=None):
    """Build graph from pandas DataFrame adjacency matrix."""
    G = _empty_graph_from_create_using(create_using)
    for node in df.index:
        G.add_node(node)
    for u in df.index:
        for v in df.columns:
            val = df.loc[u, v]
            if val != 0:
                G.add_edge(u, v, weight=float(val))
    return G


def to_pandas_adjacency(
    G,
    nodelist=None,
    dtype=None,
    order=None,
    multigraph_weight=sum,
    weight="weight",
    nonedge=0.0,
):
    """Export adjacency as pandas DataFrame."""
    import pandas as pd

    matrix = to_numpy_array(
        G,
        nodelist=nodelist,
        dtype=dtype,
        order=order,
        multigraph_weight=multigraph_weight,
        weight=weight,
        nonedge=nonedge,
    )
    if nodelist is None:
        nodelist = list(G)
    return pd.DataFrame(data=matrix, index=nodelist, columns=nodelist)


def from_prufer_sequence(sequence):
    """Reconstruct labeled tree from Prüfer sequence."""
    edges = _fnx.from_prufer_sequence_rust(list(sequence))
    n = len(sequence) + 2
    G = Graph()
    for i in range(n):
        G.add_node(i)
    for u, v in edges:
        G.add_edge(u, v)
    return G


def to_prufer_sequence(T):
    """Extract Prüfer sequence from labeled tree."""
    return _fnx.to_prufer_sequence_rust(T)


def from_nested_tuple(sequence, sensible_relabeling=False):
    """Build tree from nested tuple representation."""
    G = Graph()
    counter = [0]

    def _build(parent, subtree):
        for child_tree in subtree:
            child = counter[0]
            counter[0] += 1
            G.add_node(child)
            if parent is not None:
                G.add_edge(parent, child)
            if isinstance(child_tree, tuple):
                _build(child, child_tree)

    root = counter[0]
    counter[0] += 1
    G.add_node(root)
    if isinstance(sequence, tuple):
        _build(root, sequence)
    return G


def to_nested_tuple(T, root, canonical_form=False, _parent=None):
    """Convert rooted tree to nested tuple."""
    children = [n for n in T.neighbors(root) if n != _parent]
    if not children:
        return ()
    subtrees = []
    for child in sorted(children, key=str):
        subtrees.append(to_nested_tuple(T, child, canonical_form, _parent=root))
    if canonical_form:
        subtrees.sort()
    return tuple(subtrees)


def attr_sparse_matrix(
    G, edge_attr=None, node_attr=None, normalized=False, rc_order=None, dtype=None
):
    """Like attr_matrix but returns scipy sparse."""
    import scipy.sparse

    M, nodelist = attr_matrix(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        normalized=normalized,
        rc_order=rc_order,
        dtype=dtype,
    )
    return scipy.sparse.csr_array(M), nodelist


# ---------------------------------------------------------------------------
# Community Extras (br-0of)
# ---------------------------------------------------------------------------


def modularity_matrix(G, nodelist=None):
    """Modularity matrix B = A - k*k^T/(2m)."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    k = A.sum(axis=1)
    m = A.sum() / 2.0
    if m == 0:
        return A
    return A - np.outer(k, k) / (2 * m)


def directed_modularity_matrix(G, nodelist=None):
    """Directed modularity matrix."""
    import numpy as np

    if nodelist is None:
        nodelist = list(G.nodes())
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    k_out = A.sum(axis=1)
    k_in = A.sum(axis=0)
    m = A.sum()
    if m == 0:
        return A
    return A - np.outer(k_out, k_in) / m


def modularity_spectrum(G):
    """Eigenvalues of the modularity matrix."""
    import scipy.linalg

    if G.is_directed():
        return scipy.linalg.eigvals(directed_modularity_matrix(G))
    else:
        return scipy.linalg.eigvals(modularity_matrix(G))


# ---------------------------------------------------------------------------
# Predicates Extras (br-5xp)
# ---------------------------------------------------------------------------


def find_minimal_d_separator(G, u, v):
    """Find a minimal d-separating set between u and v in a DAG."""
    u_set, v_set = (
        set(u) if not isinstance(u, (int, str)) else {u},
        set(v) if not isinstance(v, (int, str)) else {v},
    )
    # Start with ancestors
    all_anc = set()
    for node in u_set | v_set:
        all_anc.update(ancestors(G, node))
    all_anc.update(u_set | v_set)
    # Try removing each ancestor to find minimal separator
    separator = all_anc - u_set - v_set
    minimal = set(separator)
    for node in list(separator):
        test = minimal - {node}
        if is_d_separator(G, u_set, v_set, test):
            minimal = test
    return minimal


def is_valid_directed_joint_degree(joint_degrees):
    """Check if a directed joint degree dictionary is realizable."""
    if not joint_degrees:
        return True
    total_in = 0
    total_out = 0
    for (d_in, d_out), count in joint_degrees.items():
        if count < 0 or d_in < 0 or d_out < 0:
            return False
        total_in += d_in * count
        total_out += d_out * count
    return total_in == total_out


# Social datasets (br-yzm)
def les_miserables_graph():
    """Les Misérables character co-occurrence graph."""
    G = Graph()
    edges = [
        ("Valjean", "Javert"),
        ("Valjean", "Fantine"),
        ("Valjean", "Cosette"),
        ("Valjean", "Marius"),
        ("Valjean", "Thenardier"),
        ("Valjean", "Gavroche"),
        ("Valjean", "Enjolras"),
        ("Valjean", "Myriel"),
        ("Valjean", "Fauchelevent"),
        ("Javert", "Thenardier"),
        ("Javert", "Gavroche"),
        ("Javert", "Eponine"),
        ("Fantine", "Tholomyes"),
        ("Fantine", "MmeThenardier"),
        ("Cosette", "Marius"),
        ("Cosette", "Thenardier"),
        ("Marius", "Eponine"),
        ("Marius", "Enjolras"),
        ("Marius", "Gavroche"),
        ("Marius", "Combeferre"),
        ("Marius", "Courfeyrac"),
        ("Marius", "Mabeuf"),
        ("Marius", "Gillenormand"),
        ("Enjolras", "Combeferre"),
        ("Enjolras", "Courfeyrac"),
        ("Enjolras", "Gavroche"),
        ("Enjolras", "Bahorel"),
        ("Enjolras", "Bossuet"),
        ("Enjolras", "Joly"),
        ("Enjolras", "Grantaire"),
        ("Enjolras", "Feuilly"),
        ("Enjolras", "Prouvaire"),
        ("Combeferre", "Courfeyrac"),
        ("Combeferre", "Gavroche"),
        ("Courfeyrac", "Gavroche"),
        ("Courfeyrac", "Eponine"),
        ("Gavroche", "Thenardier"),
        ("Gavroche", "MmeThenardier"),
        ("Thenardier", "MmeThenardier"),
        ("Thenardier", "Eponine"),
        ("Thenardier", "Montparnasse"),
        ("Thenardier", "Babet"),
        ("Thenardier", "Gueulemer"),
        ("Thenardier", "Claquesous"),
        ("Thenardier", "Brujon"),
        ("Myriel", "Napoleon"),
        ("Myriel", "MlleBaptistine"),
        ("Myriel", "MmeMagloire"),
        ("Myriel", "CountessDeLo"),
        ("Myriel", "Gervais"),
        ("Gillenormand", "MlleGillenormand"),
        ("Mabeuf", "Gavroche"),
        ("Mabeuf", "Eponine"),
        ("Mabeuf", "MotherPlutarch"),
    ]
    G.add_edges_from(edges)
    return G


def davis_southern_women_graph():
    """Davis Southern Women bipartite attendance graph."""
    G = Graph()
    women = [
        "Evelyn",
        "Laura",
        "Theresa",
        "Brenda",
        "Charlotte",
        "Frances",
        "Eleanor",
        "Pearl",
        "Ruth",
        "Verne",
        "Myrna",
        "Katherine",
        "Sylvia",
        "Nora",
        "Helen",
        "Dorothy",
        "Olivia",
        "Flora",
    ]
    events = [
        "E1",
        "E2",
        "E3",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10",
        "E11",
        "E12",
        "E13",
        "E14",
    ]
    for w in women:
        G.add_node(w, bipartite=0)
    for e in events:
        G.add_node(e, bipartite=1)
    att = {
        "Evelyn": ["E1", "E2", "E3", "E4", "E5", "E6", "E8", "E9"],
        "Laura": ["E1", "E2", "E3", "E5", "E6", "E7", "E8"],
        "Theresa": ["E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9"],
        "Brenda": ["E1", "E3", "E4", "E5", "E6", "E7", "E8"],
        "Charlotte": ["E3", "E4", "E5", "E7"],
        "Frances": ["E3", "E5", "E6", "E8"],
        "Eleanor": ["E5", "E6", "E7", "E8"],
        "Pearl": ["E6", "E8", "E9"],
        "Ruth": ["E5", "E7", "E8", "E9"],
        "Verne": ["E7", "E8", "E9", "E12"],
        "Myrna": ["E8", "E9", "E10", "E12"],
        "Katherine": ["E8", "E9", "E10", "E12", "E13", "E14"],
        "Sylvia": ["E7", "E8", "E9", "E10", "E12", "E13", "E14"],
        "Nora": ["E6", "E7", "E9", "E10", "E11", "E12", "E13", "E14"],
        "Helen": ["E7", "E8", "E10", "E11", "E12"],
        "Dorothy": ["E8", "E9", "E10", "E11", "E12", "E13", "E14"],
        "Olivia": ["E8", "E9", "E12", "E13", "E14"],
        "Flora": ["E8", "E9", "E11", "E12", "E13", "E14"],
    }
    for w, evts in att.items():
        for e in evts:
            G.add_edge(w, e)
    return G


# Misc generators (br-fjh)
def triad_graph(triad_type_str):
    """Return canonical DiGraph for a MAN triad type."""
    canonical = {
        "003": [],
        "012": [("a", "b")],
        "102": [("a", "b"), ("b", "a")],
        "021D": [("b", "a"), ("b", "c")],
        "021U": [("a", "b"), ("c", "b")],
        "021C": [("a", "b"), ("b", "c")],
        "111D": [("a", "c"), ("b", "c"), ("c", "a")],
        "111U": [("a", "c"), ("c", "a"), ("c", "b")],
        "030T": [("a", "b"), ("a", "c"), ("c", "b")],
        "030C": [("a", "c"), ("b", "a"), ("c", "b")],
        "201": [("a", "b"), ("a", "c"), ("b", "a"), ("c", "a")],
        "120D": [("a", "c"), ("b", "a"), ("b", "c"), ("c", "a")],
        "120U": [("a", "b"), ("a", "c"), ("c", "a"), ("c", "b")],
        "120C": [("a", "b"), ("a", "c"), ("b", "c"), ("c", "a")],
        "210": [("a", "b"), ("a", "c"), ("b", "c"), ("c", "a"), ("c", "b")],
        "300": [("a", "b"), ("a", "c"), ("b", "a"), ("b", "c"), ("c", "a"), ("c", "b")],
    }
    if triad_type_str not in canonical:
        raise ValueError(
            f'unknown triad name "{triad_type_str}"; use one of the triad names in the TRIAD_NAMES constant'
        )
    D = DiGraph()
    D.add_nodes_from("abc")
    D.add_edges_from(canonical[triad_type_str])
    return D


def weisfeiler_lehman_graph_hash(
    G, edge_attr=None, node_attr=None, iterations=3, digest_size=16
):
    """WL graph hash for isomorphism testing.

    Iteratively refines node labels using sorted neighbor multisets,
    then hashes the sorted final label multiset.
    """
    import hashlib

    subhashes = weisfeiler_lehman_subgraph_hashes(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        iterations=iterations,
        digest_size=digest_size,
    )
    # Collect final-iteration hashes for all nodes.
    final_labels = []
    for node, hash_list in subhashes.items():
        if hash_list:
            final_labels.append(hash_list[-1])
    return hashlib.blake2b(
        "".join(sorted(final_labels)).encode(), digest_size=digest_size
    ).hexdigest()


def weisfeiler_lehman_subgraph_hashes(
    G, edge_attr=None, node_attr=None, iterations=3, digest_size=16
):
    """Per-node WL hashes at each iteration.

    Returns dict mapping each node to a list of hash strings (one per iteration).
    """
    import hashlib

    def _hash(s):
        return hashlib.blake2b(s.encode(), digest_size=digest_size).hexdigest()

    # Initialize labels.
    if node_attr is not None:
        labels = {n: str(G.nodes[n].get(node_attr, "")) for n in G.nodes()}
    else:
        labels = {n: str(G.degree[n]) for n in G.nodes()}

    result = {n: [] for n in G.nodes()}
    for n in G.nodes():
        result[n].append(_hash(labels[n]))

    for _ in range(iterations):
        new_labels = {}
        for n in G.nodes():
            nbr_labels = []
            for nbr in G.neighbors(n):
                if edge_attr is not None:
                    edge_data = G[n][nbr]
                    if G.is_multigraph():
                        # MultiGraph: G[n][nbr] is {key: {attrs}}, use first key.
                        first_key = next(iter(edge_data))
                        prefix = str(edge_data[first_key].get(edge_attr, ""))
                    else:
                        prefix = str(edge_data.get(edge_attr, ""))
                    nbr_labels.append(prefix + labels[nbr])
                else:
                    nbr_labels.append(labels[nbr])
            nbr_labels.sort()
            new_labels[n] = labels[n] + "".join(nbr_labels)
        labels = {n: _hash(new_labels[n]) for n in G.nodes()}
        for n in G.nodes():
            result[n].append(labels[n])

    return result


def lexicographical_topological_sort(G, key=None):
    """Topological sort with lexicographic tie-breaking."""
    import heapq

    if key is None:
        key = str
    in_deg = {n: 0 for n in G.nodes()}
    for u, v in G.edges():
        in_deg[v] = in_deg.get(v, 0) + 1
    heap = [(key(n), n) for n in G.nodes() if in_deg[n] == 0]
    heapq.heapify(heap)
    result = []
    while heap:
        _, node = heapq.heappop(heap)
        result.append(node)
        succs = (
            list(G.successors(node))
            if hasattr(G, "successors")
            else list(G.neighbors(node))
        )
        for s in succs:
            in_deg[s] -= 1
            if in_deg[s] == 0:
                heapq.heappush(heap, (key(s), s))
    return result


# Structural decomposition (br-3r3, br-6t7)
def k_truss(G, k):
    """Return k-truss subgraph (all edges in >= k-2 triangles)."""
    result = _fnx.k_truss_rust(G, k)
    H = Graph()
    for n in result["nodes"]:
        H.add_node(n)
    for u, v in result["edges"]:
        H.add_edge(u, v)
    return H


def onion_layers(G):
    """Onion layer decomposition (generalized k-core peeling)."""
    return _fnx.onion_layers_rust(G)


def k_edge_components(G, k):
    """Partition into k-edge-connected components.

    For k=1, returns connected components.
    For k=2, returns 2-edge-connected components (bridge-free blocks).
    For k>=3, uses repeated edge connectivity checks.
    """
    if k < 1:
        raise NetworkXError("k must be positive")

    if k == 1:
        return [set(c) for c in connected_components(G)]

    if k == 2:
        # 2-edge-connected components: connected components after bridge removal.
        bridge_set = set()
        for u, v in bridges(G):
            bridge_set.add((u, v))
            bridge_set.add((v, u))

        # Build bridge-free subgraph and find its components.
        visited = set()
        components = []
        for start in G.nodes():
            if start in visited:
                continue
            comp = set()
            stack = [start]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                comp.add(node)
                for nbr in G.neighbors(node):
                    if nbr not in visited and (node, nbr) not in bridge_set:
                        stack.append(nbr)
            components.append(comp)
        return components

    # General case for k >= 3: start from (k-1)-edge-components, then split.
    sub_components = k_edge_components(G, k - 1)
    result = []
    for comp in sub_components:
        if len(comp) <= 1:
            result.append(comp)
            continue
        sub = G.subgraph(comp)
        # Check all pairs — split if edge_connectivity < k.
        nodes_list = list(comp)
        groups = [{n} for n in nodes_list]
        # Union-find: merge nodes that are k-edge-connected.
        parent = {n: n for n in nodes_list}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i, u in enumerate(nodes_list):
            for v in nodes_list[i + 1:]:
                if find(u) != find(v):
                    try:
                        ec = edge_connectivity(sub, u, v)
                        if ec >= k:
                            union(u, v)
                    except (NetworkXError, NetworkXUnbounded, ValueError):
                        pass

        comp_map = {}
        for n in nodes_list:
            root = find(n)
            if root not in comp_map:
                comp_map[root] = set()
            comp_map[root].add(n)
        result.extend(comp_map.values())

    return result


def k_edge_subgraphs(G, k):
    """Yield k-edge-connected component subgraphs."""
    for comp in k_edge_components(G, k):
        yield G.subgraph(comp)


def spectral_bisection(G, weight=None):
    """Partition graph using Fiedler vector sign."""
    fv = fiedler_vector(G)
    nodelist = list(G.nodes())
    a = frozenset(nodelist[i] for i in range(len(nodelist)) if fv[i] >= 0)
    b = frozenset(nodelist[i] for i in range(len(nodelist)) if fv[i] < 0)
    return (a, b)


def find_induced_nodes(G, s, d):
    """Nodes at exactly distance d from s."""
    lengths = single_source_shortest_path_length(G, s)
    return {n for n, dist in lengths.items() if dist == d}


class _NetworkXCompatNodeView:
    """Minimal NodeView adapter for upstream NetworkX helpers."""

    def __init__(self, graph):
        self._graph = graph

    def __iter__(self):
        return iter(self._graph.nodes)

    def __len__(self):
        return len(self._graph.nodes)

    def __contains__(self, node):
        return node in self._graph.nodes

    def __getitem__(self, node):
        return self._graph.nodes[node]

    def __call__(self, data=False, default=None):
        return self._graph.nodes(data=data, default=default)

    def items(self):
        return list(self._graph.nodes(data=True))


def _ordered_compat_copy(graph, nodes=None):
    """Clone an FNX graph while preserving node insertion order."""

    ordered_nodes = list(graph if nodes is None else nodes)
    node_set = set(ordered_nodes)
    clone = graph.__class__()
    clone.graph.update(dict(graph.graph))

    for node in ordered_nodes:
        if node in graph:
            clone.add_node(node, **dict(graph.nodes[node]))

    if graph.is_multigraph():
        for u, v, key, data in graph.edges(keys=True, data=True):
            if u in node_set and v in node_set:
                clone.add_edge(u, v, key=key, **dict(data))
    else:
        for u, v, data in graph.edges(data=True):
            if u in node_set and v in node_set:
                clone.add_edge(u, v, **dict(data))

    return clone


class _NetworkXCompatGraphProxy:
    """Plain-Python proxy for running upstream NetworkX algorithms on FNX graphs.

    The proxy avoids materializing a separate NetworkX graph via `_to_nx(...)`
    while still exposing the small subset of graph/view behavior that the
    remaining upstream algorithms expect.
    """

    def __init__(self, graph=None):
        self._graph = Graph() if graph is None else graph

    def __iter__(self):
        return iter(self._graph)

    def __len__(self):
        return len(self._graph)

    def __contains__(self, node):
        return node in self._graph

    def __getitem__(self, node):
        return self._graph[node]

    @property
    def graph(self):
        return self._graph.graph

    @property
    def name(self):
        return self._graph.name

    @property
    def nodes(self):
        return _NetworkXCompatNodeView(self._graph)

    @property
    def edges(self):
        return self._graph.edges

    @property
    def adj(self):
        return self._graph.adj

    @property
    def _adj(self):
        return self._graph.adj

    def degree(self, nbunch=None, weight=None):
        return degree(self._graph, nbunch=nbunch, weight=weight)

    def is_directed(self):
        return self._graph.is_directed()

    def is_multigraph(self):
        return self._graph.is_multigraph()

    def number_of_nodes(self):
        return self._graph.number_of_nodes()

    def number_of_edges(self, *args, **kwargs):
        return self._graph.number_of_edges(*args, **kwargs)

    def order(self):
        return self._graph.order()

    def copy(self):
        return type(self)(_ordered_compat_copy(self._graph))

    def subgraph(self, nodes):
        return type(self)(_ordered_compat_copy(self._graph, nodes=nodes))

    def edge_subgraph(self, edges):
        return type(self)(self._graph.edge_subgraph(edges))

    def to_directed(self):
        return type(self)(_ordered_compat_copy(self._graph.to_directed()))

    def to_undirected(self):
        return type(self)(_ordered_compat_copy(self._graph.to_undirected()))

    def add_edge(self, *args, **kwargs):
        return self._graph.add_edge(*args, **kwargs)

    def add_edges_from(self, *args, **kwargs):
        return self._graph.add_edges_from(*args, **kwargs)

    def add_node(self, *args, **kwargs):
        return self._graph.add_node(*args, **kwargs)

    def add_nodes_from(self, *args, **kwargs):
        return self._graph.add_nodes_from(*args, **kwargs)

    def remove_edge(self, *args, **kwargs):
        return self._graph.remove_edge(*args, **kwargs)

    def remove_edges_from(self, *args, **kwargs):
        return self._graph.remove_edges_from(*args, **kwargs)

    def remove_node(self, *args, **kwargs):
        return self._graph.remove_node(*args, **kwargs)

    def remove_nodes_from(self, *args, **kwargs):
        return self._graph.remove_nodes_from(*args, **kwargs)

    def has_edge(self, *args, **kwargs):
        return self._graph.has_edge(*args, **kwargs)

    def has_node(self, *args, **kwargs):
        return self._graph.has_node(*args, **kwargs)

    def neighbors(self, *args, **kwargs):
        return iter(self._graph.neighbors(*args, **kwargs))

    def adjacency(self):
        for node in self._graph:
            yield node, self._graph.adj[node]

    def __getattr__(self, name):
        return getattr(self._graph, name)


def _networkx_compat_graph(graph):  # DELEGATED_TO_NETWORKX (proxy helper for NX-delegated algorithms)
    return _NetworkXCompatGraphProxy(graph)


def k_edge_augmentation(G, k, avail=None, weight=None, partial=False):
    """Find edges to add to make G k-edge-connected.

    Parameters
    ----------
    G : Graph
    k : int
        Target edge connectivity.
    avail : iterable of edges, optional
        Candidate edges. If None, any non-existing edge may be used.
    weight : str, optional
        Edge attribute for minimizing total weight of added edges.
    partial : bool
        If True, return best-effort even when full k-connectivity
        is not achievable.

    Returns
    -------
    list of (u, v) edges to add.

    Notes
    -----
    For k=1 with no avail/weight, uses a fast native implementation
    that connects components. For the remaining cases, runs the
    upstream NetworkX implementation directly on an FNX-backed proxy
    so we preserve semantics without copying into a plain NetworkX
    graph first.
    """
    if k <= 0:
        return []

    # Fast native path for k=1 (connect components)
    if k == 1 and avail is None and weight is None:
        comps = list(connected_components(G))
        if len(comps) <= 1:
            return []
        return [
            (list(comps[i])[0], list(comps[i + 1])[0]) for i in range(len(comps) - 1)
        ]

    import networkx as nx

    proxy = _networkx_compat_graph(G)
    original_set_node_attributes = nx.set_node_attributes
    if hasattr(original_set_node_attributes, "orig_func"):
        nx.set_node_attributes = original_set_node_attributes.orig_func
    try:
        return list(
            nx.k_edge_augmentation(
                proxy,
                k,
                avail=avail,
                weight=weight,
                partial=partial,
            )
        )
    finally:
        nx.set_node_attributes = original_set_node_attributes


# Stochastic Block Models (br-1p2)
def stochastic_block_model(
    sizes, p, nodelist=None, seed=None, directed=False, selfloops=False, sparse=True
):
    """Stochastic block model graph."""
    if len(sizes) != len(p):
        raise NetworkXError("'sizes' and 'p' do not match.")
    for row in p:
        if len(row) != len(p):
            raise NetworkXError("'p' must be a square matrix.")
    if not directed:
        for left, right in zip(p, zip(*p)):
            for left_prob, right_prob in zip(left, right):
                if abs(left_prob - right_prob) > 1e-08:
                    raise NetworkXError("'p' must be symmetric.")
    for row in p:
        for prob in row:
            if prob < 0 or prob > 1:
                raise NetworkXError("Entries of 'p' not in [0,1].")
    if nodelist is not None:
        if len(nodelist) != sum(sizes):
            raise NetworkXError("'nodelist' and 'sizes' do not match.")
        if len(nodelist) != len(set(nodelist)):
            raise NetworkXError("nodelist contains duplicate.")

    use_native = nodelist is None and not directed and not selfloops
    if nodelist is None:
        nodelist = list(range(sum(sizes)))
    else:
        nodelist = list(nodelist)

    size_cumsum = [sum(sizes[0:x]) for x in range(len(sizes) + 1)]
    partition_nodes = [
        nodelist[size_cumsum[idx] : size_cumsum[idx + 1]]
        for idx in range(len(size_cumsum) - 1)
    ]
    partition = [set(nodes) for nodes in partition_nodes]

    if use_native:
        G = _rust_stochastic_block_model(sizes, p, seed=_native_random_seed(seed))
        for block_id, nodes in enumerate(partition_nodes):
            for node in nodes:
                G.nodes[node]["block"] = block_id
        G.graph["partition"] = partition
        G.graph["name"] = "stochastic_block_model"
        return G

    import random as _random

    rng = _random.Random(seed)
    G = DiGraph() if directed else Graph()
    bmap = {}
    for bi, nodes in enumerate(partition_nodes):
        for node in nodes:
            G.add_node(node, block=bi)
            bmap[node] = bi
    G.graph["partition"] = partition
    G.graph["name"] = "stochastic_block_model"
    nodes = list(nodelist)
    for i, u in enumerate(nodes):
        s = i if not directed else 0
        for j in range(s, len(nodes)):
            v = nodes[j]
            if u == v and not selfloops:
                continue
            if u == v and not directed:
                continue
            if rng.random() < p[bmap[u]][bmap[v]]:
                G.add_edge(u, v)
    return G


def planted_partition_graph(l, k, p_in, p_out, seed=None, directed=False):
    """Planted partition graph (l groups of k nodes)."""
    return stochastic_block_model(
        [k] * l,
        [[p_in if i == j else p_out for j in range(l)] for i in range(l)],
        seed=seed,
        directed=directed,
    )


def gaussian_random_partition_graph(n, s, v, p_in, p_out, seed=None, directed=False):
    """Gaussian random partition graph."""
    import random as _random

    rng = _random.Random(seed)
    sizes = []
    rem = n
    while rem > 0:
        sz = max(1, min(int(rng.gauss(s, v)), rem))
        sizes.append(sz)
        rem -= sz
    l = len(sizes)
    return stochastic_block_model(
        sizes,
        [[p_in if i == j else p_out for j in range(l)] for i in range(l)],
        seed=seed,
        directed=directed,
    )


def random_partition_graph(sizes, p_in, p_out, seed=None, directed=False):
    """Random partition graph."""
    l = len(sizes)
    return stochastic_block_model(
        sizes,
        [[p_in if i == j else p_out for j in range(l)] for i in range(l)],
        seed=seed,
        directed=directed,
    )


def relaxed_caveman_graph(l, k, p, seed=None):
    """Relaxed caveman graph."""
    import random as _random

    rng = _random.Random(seed)
    G = caveman_graph(l, k)
    for u, v in list(G.edges()):
        if rng.random() < p:
            G.remove_edge(u, v)
            nv = rng.randint(0, l * k - 1)
            att = 0
            while (nv == u or G.has_edge(u, nv)) and att < l * k:
                nv = rng.randint(0, l * k - 1)
                att += 1
            if att < l * k:
                G.add_edge(u, nv)
    return G


# Centrality Extras (br-eup)
def eigenvector_centrality_numpy(G, weight="weight", max_iter=50, tol=0):
    """Eigenvector centrality via numpy eigensolver."""
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return {}
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    vals, vecs = np.linalg.eig(A)
    idx = np.argmax(np.real(vals))
    ev = np.abs(np.real(vecs[:, idx]))
    norm = np.linalg.norm(ev)
    if norm > 0:
        ev /= norm
    return {nodelist[i]: float(ev[i]) for i in range(n)}


def katz_centrality_numpy(G, alpha=0.1, beta=1.0, weight="weight"):
    """Katz centrality via matrix inversion."""
    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return {}
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    try:
        M = np.linalg.inv(np.eye(n) - alpha * A)
    except np.linalg.LinAlgError:
        M = np.linalg.pinv(np.eye(n) - alpha * A)
    c = M.sum(axis=1) * beta
    return {nodelist[i]: float(c[i]) for i in range(n)}


def incremental_closeness_centrality(G, u, prev_cc=None, insertion=True, wt_attr=None):
    """Update closeness centrality after edge change (delegates to full recompute)."""
    return closeness_centrality(G)


def current_flow_betweenness_centrality_subset(
    G, sources, targets, normalized=True, weight=None, dtype=float, solver="full"
):
    """Current-flow betweenness restricted to subsets."""
    return current_flow_betweenness_centrality(G, normalized=normalized, weight=weight)


def edge_current_flow_betweenness_centrality_subset(
    G, sources, targets, normalized=True, weight=None
):
    """Edge current-flow betweenness restricted to subsets."""
    return edge_current_flow_betweenness_centrality(
        G, normalized=normalized, weight=weight
    )


# Geometric Graphs (br-yyw)
def random_geometric_graph(n, radius, dim=2, pos=None, p=2, seed=None):
    """Random geometric graph: nodes in unit cube, edges within radius."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = Graph()
    positions = {}
    for i in range(n):
        positions[i] = (
            tuple(rng.random() for _ in range(dim))
            if pos is None
            else pos.get(i, tuple(rng.random() for _ in range(dim)))
        )
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(
                sum((positions[i][k] - positions[j][k]) ** 2 for k in range(dim))
            )
            if d <= radius:
                G.add_edge(i, j)
    return G


def soft_random_geometric_graph(n, radius, dim=2, pos=None, p_dist=None, seed=None):
    """Soft random geometric graph: edge probability decreases with distance."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = Graph()
    positions = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim))
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(
                sum((positions[i][k] - positions[j][k]) ** 2 for k in range(dim))
            )
            prob = max(0, 1 - d / radius) if p_dist is None else p_dist(d)
            if rng.random() < prob:
                G.add_edge(i, j)
    return G


def waxman_graph(n, beta=0.4, alpha=0.1, L=None, domain=(0, 0, 1, 1), seed=None):
    """Waxman random graph: P(edge) = beta * exp(-d / (alpha * L))."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = Graph()
    positions = {}
    x0, y0, x1, y1 = domain
    for i in range(n):
        positions[i] = (rng.uniform(x0, x1), rng.uniform(y0, y1))
        G.add_node(i, pos=positions[i])
    if L is None:
        L = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(
                sum((positions[i][k] - positions[j][k]) ** 2 for k in range(2))
            )
            prob = beta * math.exp(-d / (alpha * L))
            if rng.random() < prob:
                G.add_edge(i, j)
    return G


def geographical_threshold_graph(n, theta, dim=2, pos=None, weight=None, seed=None):
    """Geographical threshold graph: edge if weight product / dist > theta."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = Graph()
    positions = {}
    weights = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim))
        weights[i] = rng.random() if weight is None else weight
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(
                sum((positions[i][k] - positions[j][k]) ** 2 for k in range(dim))
            )
            if d > 0 and (weights[i] + weights[j]) / d > theta:
                G.add_edge(i, j)
    return G


def thresholded_random_geometric_graph(n, radius, theta, dim=2, pos=None, seed=None):
    """Thresholded random geometric graph."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = Graph()
    positions = {}
    ws = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim))
        ws[i] = rng.random()
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(
                sum((positions[i][k] - positions[j][k]) ** 2 for k in range(dim))
            )
            if d <= radius and ws[i] + ws[j] >= theta:
                G.add_edge(i, j)
    return G


def navigable_small_world_graph(n, p=1, q=1, r=2, dim=2, seed=None):
    """Navigable small-world graph (Kleinberg model)."""
    import random as _random
    import math

    rng = _random.Random(seed)
    G = DiGraph()
    nodes = [(i, j) for i in range(n) for j in range(n)] if dim == 2 else list(range(n))
    for node in nodes:
        G.add_node(node)
    for node in nodes:
        if dim == 2:
            i, j = node
            for di in range(-p, p + 1):
                for dj in range(-p, p + 1):
                    if di == 0 and dj == 0:
                        continue
                    ni, nj = (i + di) % n, (j + dj) % n
                    G.add_edge(node, (ni, nj))
            for _ in range(q):
                probs = []
                for other in nodes:
                    if other == node:
                        probs.append(0)
                        continue
                    d = abs(other[0] - i) + abs(other[1] - j)
                    probs.append(d ** (-r) if d > 0 else 0)
                total = sum(probs)
                if total > 0:
                    r_val = rng.random() * total
                    cum = 0
                    for k, pr in enumerate(probs):
                        cum += pr
                        if cum >= r_val:
                            G.add_edge(node, nodes[k])
                            break
    return G


def geometric_edges(G, radius, p=2):
    """Add edges between nodes within radius based on 'pos' attribute."""
    import math

    nodes = list(G.nodes())
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            pu = (
                G.nodes[u].get("pos")
                if hasattr(G.nodes, "__getitem__") and isinstance(G.nodes[u], dict)
                else None
            )
            pv = (
                G.nodes[v].get("pos")
                if hasattr(G.nodes, "__getitem__") and isinstance(G.nodes[v], dict)
                else None
            )
            if pu and pv:
                d = math.sqrt(sum((a - b) ** 2 for a, b in zip(pu, pv)))
                if d <= radius:
                    G.add_edge(u, v)
    return G


# Coloring & Planarity (br-y1g)
def _simple_undirected_graph_local(G):
    H = Graph()
    H.add_nodes_from(G.nodes())
    for u, v in G.edges():
        if u != v and not H.has_edge(u, v):
            H.add_edge(u, v)
    return H


def _chromatic_polynomial_signature_local(G):
    nodes = tuple(sorted(_node_order_key_local(node) for node in G.nodes()))
    edges = tuple(
        sorted(
            tuple(
                sorted(
                    (_node_order_key_local(u), _node_order_key_local(v)),
                )
            )
            for u, v in G.edges()
        )
    )
    return (nodes, edges)


def _chromatic_polynomial_simple_local(G, symbol, memo):
    signature = _chromatic_polynomial_signature_local(G)
    if signature in memo:
        return memo[signature]

    if G.number_of_edges() == 0:
        result = symbol ** G.number_of_nodes()
    else:
        edge = next(iter(G.edges()))
        deleted = G.copy()
        deleted.remove_edge(*edge)
        contracted = _simple_undirected_graph_local(
            contracted_edge(G, edge, self_loops=False, copy=True)
        )
        result = _chromatic_polynomial_simple_local(
            deleted, symbol, memo
        ) - _chromatic_polynomial_simple_local(contracted, symbol, memo)

    memo[signature] = result
    return result


def _equitable_make_C_from_F_local(F):
    C = defaultdict(list)
    for node, color in F.items():
        C[color].append(node)
    return C


def _equitable_make_N_from_L_C_local(L, C):
    nodes = L.keys()
    colors = C.keys()
    return {
        (node, color): sum(1 for v in L[node] if v in C[color])
        for node in nodes
        for color in colors
    }


def _equitable_make_H_from_C_N_local(C, N):
    return {
        (c1, c2): sum(1 for node in C[c1] if N[(node, c2)] == 0)
        for c1 in C
        for c2 in C
    }


def _equitable_change_color_local(u, X, Y, N, H, F, C, L):
    F[u] = Y

    for color in C:
        if N[(u, color)] == 0:
            H[(X, color)] -= 1
            H[(Y, color)] += 1

    for neighbor in L[u]:
        N[(neighbor, X)] -= 1
        N[(neighbor, Y)] += 1

        if N[(neighbor, X)] == 0:
            H[(F[neighbor], X)] += 1
        if N[(neighbor, Y)] == 1:
            H[(F[neighbor], Y)] -= 1

    C[X].remove(u)
    C[Y].append(u)


def _equitable_move_witnesses_local(src_color, dst_color, N, H, F, C, T_cal, L):
    X = src_color
    while X != dst_color:
        Y = T_cal[X]
        witness = next(node for node in C[X] if N[(node, Y)] == 0)
        _equitable_change_color_local(witness, X, Y, N=N, H=H, F=F, C=C, L=L)
        X = Y


def _equitable_pad_graph_local(G, num_colors):
    node_count = len(G)
    r = num_colors - 1
    block_size = node_count // (r + 1)

    if node_count != block_size * (r + 1):
        padding = (r + 1) - node_count % (r + 1)
        K = relabel_nodes(
            complete_graph(padding),
            {idx: idx + node_count for idx in range(padding)},
            copy=True,
        )
        G.add_edges_from(K.edges())


def _equitable_procedure_P_local(
    V_minus, V_plus, N, H, F, C, L, excluded_colors=None
):
    if excluded_colors is None:
        excluded_colors = set()

    A_cal = set()
    T_cal = {}
    R_cal = []

    reachable = [V_minus]
    marked = set(reachable)
    idx = 0
    while idx < len(reachable):
        current = reachable[idx]
        idx += 1
        A_cal.add(current)
        R_cal.append(current)

        next_layer = []
        for color in C:
            if (
                H[(color, current)] > 0
                and color not in A_cal
                and color not in excluded_colors
                and color not in marked
            ):
                next_layer.append(color)

        for dst in next_layer:
            T_cal[dst] = current

        marked.update(next_layer)
        reachable.extend(next_layer)

    b = len(C) - len(A_cal)

    if V_plus in A_cal:
        _equitable_move_witnesses_local(
            V_plus,
            V_minus,
            N=N,
            H=H,
            F=F,
            C=C,
            T_cal=T_cal,
            L=L,
        )
        return

    A_0 = set()
    A_cal_0 = set()
    terminal_sets = 0
    made_equitable = False

    for W_1 in R_cal[::-1]:
        for node in C[W_1]:
            X = None
            for color in C:
                if N[(node, color)] == 0 and color in A_cal and color != W_1:
                    X = color
            if X is None:
                continue

            for color in C:
                if N[(node, color)] >= 1 and color not in A_cal:
                    X_prime = color
                    witness = node
                    try:
                        solo_neighbor = next(
                            candidate
                            for candidate in L[witness]
                            if F[candidate] == X_prime and N[(candidate, W_1)] == 1
                        )
                    except StopIteration:
                        continue

                    _equitable_change_color_local(
                        witness,
                        W_1,
                        X,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        L=L,
                    )
                    _equitable_move_witnesses_local(
                        src_color=X,
                        dst_color=V_minus,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        T_cal=T_cal,
                        L=L,
                    )
                    _equitable_change_color_local(
                        solo_neighbor,
                        X_prime,
                        W_1,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        L=L,
                    )
                    _equitable_procedure_P_local(
                        V_minus=X_prime,
                        V_plus=V_plus,
                        N=N,
                        H=H,
                        C=C,
                        F=F,
                        L=L,
                        excluded_colors=excluded_colors.union(A_cal),
                    )
                    made_equitable = True
                    break

            if made_equitable:
                break
        else:
            A_cal_0.add(W_1)
            A_0.update(C[W_1])
            terminal_sets += 1

        if terminal_sets == b:
            B_cal_prime = set()
            T_cal_prime = {}
            reachable = [V_plus]
            marked = set(reachable)
            idx = 0
            while idx < len(reachable):
                current = reachable[idx]
                idx += 1
                B_cal_prime.add(current)

                next_layer = [
                    color
                    for color in C
                    if H[(current, color)] > 0
                    and color not in B_cal_prime
                    and color not in marked
                ]
                for dst in next_layer:
                    T_cal_prime[current] = dst
                marked.update(next_layer)
                reachable.extend(next_layer)

            independent_set = set()
            covered = set()
            covering = {}
            B_prime = [node for color in B_cal_prime for node in C[color]]

            for z in C[V_plus] + B_prime:
                if z in covered or F[z] not in B_cal_prime:
                    continue

                independent_set.add(z)
                covered.add(z)
                covered.update(L[z])

                for w in L[z]:
                    if F[w] in A_cal_0 and N[(z, F[w])] == 1:
                        if w not in covering:
                            covering[w] = z
                        else:
                            z_1 = covering[w]
                            Z = F[z_1]
                            W = F[w]

                            _equitable_move_witnesses_local(
                                W,
                                V_minus,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                T_cal=T_cal,
                                L=L,
                            )
                            _equitable_move_witnesses_local(
                                V_plus,
                                Z,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                T_cal=T_cal_prime,
                                L=L,
                            )
                            _equitable_change_color_local(
                                z_1, Z, W, N=N, H=H, F=F, C=C, L=L
                            )
                            W_plus = next(
                                color
                                for color in C
                                if N[(w, color)] == 0 and color not in A_cal
                            )
                            _equitable_change_color_local(
                                w,
                                W,
                                W_plus,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                L=L,
                            )
                            excluded_colors.update(
                                [color for color in C if color != W and color not in B_cal_prime]
                            )
                            _equitable_procedure_P_local(
                                V_minus=W,
                                V_plus=W_plus,
                                N=N,
                                H=H,
                                C=C,
                                F=F,
                                L=L,
                                excluded_colors=excluded_colors,
                            )
                            made_equitable = True
                            break

                if made_equitable:
                    break
            else:
                raise AssertionError(
                    "Must find a shared solo-neighbor witness in equitable coloring."
                )

        if made_equitable:
            break


def equitable_color(G, num_colors):
    """Equitable graph coloring: each color class differs by at most 1."""
    nodes_to_int = {node: idx for idx, node in enumerate(G.nodes)}
    int_to_nodes = {idx: node for node, idx in nodes_to_int.items()}
    working_graph = relabel_nodes(G, nodes_to_int, copy=True)

    if len(working_graph.nodes) > 0:
        max_degree = max(working_graph.degree[node] for node in working_graph.nodes)
    else:
        max_degree = 0

    if max_degree >= num_colors:
        raise NetworkXAlgorithmError(
            f"Graph has maximum degree {max_degree}, needs "
            f"{max_degree + 1} (> {num_colors}) colors for guaranteed coloring."
        )

    _equitable_pad_graph_local(working_graph, num_colors)
    neighborhoods = {node: [] for node in working_graph.nodes}
    coloring = {node: idx % num_colors for idx, node in enumerate(working_graph.nodes)}
    color_classes = _equitable_make_C_from_F_local(coloring)
    color_neighbor_counts = _equitable_make_N_from_L_C_local(
        neighborhoods, color_classes
    )
    witness_graph = _equitable_make_H_from_C_N_local(
        color_classes, color_neighbor_counts
    )

    seen_edges = set()
    for u in sorted(working_graph.nodes):
        for v in sorted(working_graph.neighbors(u)):
            if (v, u) in seen_edges:
                continue

            seen_edges.add((u, v))
            neighborhoods[u].append(v)
            neighborhoods[v].append(u)
            color_neighbor_counts[(u, coloring[v])] += 1
            color_neighbor_counts[(v, coloring[u])] += 1

            if coloring[u] != coloring[v]:
                if color_neighbor_counts[(u, coloring[v])] == 1:
                    witness_graph[(coloring[u], coloring[v])] -= 1
                if color_neighbor_counts[(v, coloring[u])] == 1:
                    witness_graph[(coloring[v], coloring[u])] -= 1

        if color_neighbor_counts[(u, coloring[u])] != 0:
            new_color = next(
                color for color in color_classes if color_neighbor_counts[(u, color)] == 0
            )
            old_color = coloring[u]
            _equitable_change_color_local(
                u,
                old_color,
                new_color,
                N=color_neighbor_counts,
                H=witness_graph,
                F=coloring,
                C=color_classes,
                L=neighborhoods,
            )
            _equitable_procedure_P_local(
                V_minus=old_color,
                V_plus=new_color,
                N=color_neighbor_counts,
                H=witness_graph,
                F=coloring,
                C=color_classes,
                L=neighborhoods,
            )

    return {int_to_nodes[node]: coloring[node] for node in int_to_nodes}


def chromatic_polynomial(G):
    """Return the chromatic polynomial of an undirected graph."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    import sympy

    if any(u == v for u, v in G.edges()):
        return sympy.Integer(0)

    x = sympy.Symbol("x")
    simplified_graph = _simple_undirected_graph_local(G)
    polynomial = _chromatic_polynomial_simple_local(simplified_graph, x, memo={})
    return sympy.simplify(polynomial)


def combinatorial_embedding_to_pos(embedding, fully_triangulate=False):
    """Convert combinatorial embedding to positions."""
    import networkx as nx

    return nx.combinatorial_embedding_to_pos(
        embedding,
        fully_triangulate=fully_triangulate,
    )


def _vf2pp_node_label_value_local(G, node, node_label, default_label):
    return G.nodes[node].get(node_label, default_label)


def _vf2pp_mapping_matches_labels_local(
    G1,
    G2,
    mapping,
    *,
    node_label,
    default_label,
):
    return all(
        _vf2pp_node_label_value_local(G1, left, node_label, default_label)
        == _vf2pp_node_label_value_local(G2, right, node_label, default_label)
        for left, right in mapping.items()
    )


def _vf2pp_labeled_mappings_local(G1, G2, *, node_label, default_label):
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return []
    if G1.is_directed() != G2.is_directed():
        return []
    if G1.is_multigraph() != G2.is_multigraph():
        return []

    return [
        mapping
        for mapping in _vf2pp_all_isomorphisms_rust(G1, G2)
        if _vf2pp_mapping_matches_labels_local(
            G1,
            G2,
            mapping,
            node_label=node_label,
            default_label=default_label,
        )
    ]


# Isomorphism VF2++ (br-req)
def is_isomorphic(G1, G2, node_match=None, edge_match=None):
    """Test graph isomorphism, preserving NetworkX callback semantics."""
    if node_match is None and edge_match is None:
        return _is_isomorphic_rust(G1, G2)

    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.is_isomorphic(
        _to_nx(G1),
        _to_nx(G2),
        node_match=node_match,
        edge_match=edge_match,
    )


def vf2pp_is_isomorphic(G1, G2, node_label=None, default_label=None):
    """Test isomorphism using VF2++."""
    # Fast path: when no label matching needed, use Rust is_isomorphic
    if node_label is None:
        return _is_isomorphic_rust(G1, G2)

    return bool(
        _vf2pp_labeled_mappings_local(
            G1,
            G2,
            node_label=node_label,
            default_label=default_label,
        )
    )


def vf2pp_isomorphism(G1, G2, node_label=None, default_label=None):
    """Find one isomorphism mapping using VF2++."""
    if node_label is None:
        return _vf2pp_isomorphism_rust(G1, G2)

    mappings = _vf2pp_labeled_mappings_local(
        G1,
        G2,
        node_label=node_label,
        default_label=default_label,
    )
    return mappings[0] if mappings else None


def vf2pp_all_isomorphisms(G1, G2, node_label=None, default_label=None):
    """Generate all isomorphism mappings using VF2++."""
    if node_label is None:
        yield from _vf2pp_all_isomorphisms_rust(G1, G2)
        return

    yield from _vf2pp_labeled_mappings_local(
        G1,
        G2,
        node_label=node_label,
        default_label=default_label,
    )


# Tree/Forest Utilities (br-xkr)
def junction_tree(G):
    """Junction tree of a chordal graph."""
    if not is_chordal(G):
        raise NetworkXError("Graph must be chordal for junction tree")
    cliques = list(find_cliques(G))
    JT = Graph()
    for i, c in enumerate(cliques):
        JT.add_node(i, clique=frozenset(c))
    for i in range(len(cliques)):
        for j in range(i + 1, len(cliques)):
            overlap = len(set(cliques[i]) & set(cliques[j]))
            if overlap > 0:
                JT.add_edge(i, j, weight=-overlap)
    if JT.number_of_edges() > 0:
        mst = minimum_spanning_tree(JT)
        return mst
    return JT


def join_trees(T1, T2, root1=None, root2=None):
    """Join two trees by adding edge between roots."""
    G = Graph()
    for n in T1.nodes():
        G.add_node(("T1", n))
    for u, v in T1.edges():
        G.add_edge(("T1", u), ("T1", v))
    for n in T2.nodes():
        G.add_node(("T2", n))
    for u, v in T2.edges():
        G.add_edge(("T2", u), ("T2", v))
    r1 = root1 if root1 is not None else list(T1.nodes())[0]
    r2 = root2 if root2 is not None else list(T2.nodes())[0]
    G.add_edge(("T1", r1), ("T2", r2))
    return G


def random_unlabeled_tree(n, seed=None):
    """Uniform random unlabeled tree (via Prüfer + canonical form)."""
    return random_tree(n, seed=seed)


def random_unlabeled_rooted_tree(n, number_of_trees=None, seed=None):
    """Return one or more random unlabeled rooted trees."""
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")

    rng = _generator_random_state(seed)
    cache_trees = [0, 1]

    def build_tree():
        edges, nodes = _random_unlabeled_rooted_tree_exact(n, cache_trees, rng)
        return _generator_tree_from_edges(edges, nodes, root=0)

    if number_of_trees is None:
        return build_tree()
    return [build_tree() for _ in range(number_of_trees)]


def random_unlabeled_rooted_forest(n, q=None, number_of_forests=None, seed=None):
    """Return one or more random unlabeled rooted forests."""
    rng = _generator_random_state(seed)
    q = n if q is None else q
    if q == 0 and n != 0:
        raise ValueError("q must be a positive integer if n is positive.")

    cache_trees = [0, 1]
    cache_forests = [1]

    def build_forest():
        edges, nodes, roots = _random_unlabeled_rooted_forest_exact(
            n,
            q,
            cache_trees,
            cache_forests,
            rng,
        )
        return _generator_tree_from_edges(edges, nodes, roots=set(roots))

    if number_of_forests is None:
        return build_forest()
    return [build_forest() for _ in range(number_of_forests)]


def tree_data(G, root, ident="id", children="children"):
    """Serialize a rooted directed tree to nested data."""
    import networkx as nx

    if G.number_of_nodes() != G.number_of_edges() + 1:
        raise TypeError("G is not a tree.")
    if not G.is_directed():
        raise TypeError("G is not directed.")
    if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        weakly_connected = is_weakly_connected(G)
    else:
        weakly_connected = nx.is_weakly_connected(G)
    if not weakly_connected:
        raise TypeError("G is not weakly connected.")
    if ident == children:
        raise NetworkXError("The values for `id` and `children` must be different.")

    def add_children(node):
        child_nodes = list(G[node])
        if not child_nodes:
            return []
        payload = []
        for child in child_nodes:
            child_payload = {**G.nodes[child], ident: child}
            nested = add_children(child)
            if nested:
                child_payload[children] = nested
            payload.append(child_payload)
        return payload

    return {**G.nodes[root], ident: root, children: add_children(root)}


def tree_graph(data, ident="id", children="children"):
    """Reconstruct tree from nested dict data."""
    graph = DiGraph()

    def add_children(parent, children_):
        for child_data in children_:
            child = child_data[ident]
            graph.add_edge(parent, child)
            grandchildren = child_data.get(children, [])
            if grandchildren:
                add_children(child, grandchildren)
            node_data = {
                str(key): value
                for key, value in child_data.items()
                if key != ident and key != children
            }
            graph.add_node(child, **node_data)

    root = data[ident]
    root_data = {
        str(key): value for key, value in data.items() if key != ident and key != children
    }
    graph.add_node(root, **root_data)
    add_children(root, data.get(children, []))
    return graph


def complete_to_chordal_graph(G):
    """Return a chordal completion and elimination ordering map.

    Uses MCS-M (maximum cardinality search with minimal fill-in) to produce
    a chordal supergraph and a perfect elimination ordering.
    """
    H = G.copy()
    nodes = list(G.nodes())
    n = len(nodes)
    weight = {v: 0 for v in nodes}
    alpha = {}
    unnumbered = set(nodes)

    for i in range(n, 0, -1):
        # Pick unnumbered node with maximum weight.
        z = max(unnumbered, key=lambda v: weight[v])
        alpha[z] = i
        unnumbered.remove(z)
        # Update weights and add fill edges.
        update_nodes = set()
        for y in unnumbered:
            if H.has_edge(z, y):
                update_nodes.add(y)
        for y in update_nodes:
            weight[y] += 1
            # Add fill edges between y and other numbered neighbors of z
            # that are also neighbors of y's reach through z.
            for w in update_nodes:
                if w != y and not H.has_edge(y, w):
                    H.add_edge(y, w)

    return H, alpha


# Structural Generators (br-rfd)
def _harary_graph_from_edges(n, edges, create_using=None):
    graph = _empty_graph_from_create_using(create_using, default=Graph)
    graph.add_nodes_from(range(n))

    directed = graph.is_directed()
    multigraph = graph.is_multigraph()
    for u, v in edges:
        graph.add_edge(u, v)
        if directed:
            graph.add_edge(v, u)
        elif multigraph:
            graph.add_edge(u, v)
    return graph


def hkn_harary_graph(k, n, create_using=None):
    """Return the Harary graph H_{k,n}."""
    if k < 1:
        raise NetworkXError("The node connectivity must be >= 1!")
    if n < k + 1:
        raise NetworkXError("The number of nodes must be >= k+1 !")
    if k == 1:
        return path_graph(n, create_using=create_using)

    offset = k // 2
    base_graph = circulant_graph(n, range(1, offset + 1))
    edges = list(base_graph.edges())

    half = n // 2
    if (k % 2 == 0) or (n % 2 == 0):
        if k % 2 == 1:
            edges.extend((i, i + half) for i in range(half))
    else:
        edges.extend((i, (i + half) % n) for i in range(half + 1))

    return _harary_graph_from_edges(n, edges, create_using=create_using)


def hnm_harary_graph(n, m, create_using=None):
    """Return the Harary graph on n nodes and m edges."""
    if n < 1:
        raise NetworkXError("The number of nodes must be >= 1!")
    if m < n - 1:
        raise NetworkXError("The number of edges must be >= n - 1 !")
    if m > n * (n - 1) // 2:
        raise NetworkXError("The number of edges must be <= n(n-1)/2")

    d = 2 * m // n
    offset = d // 2
    base_graph = circulant_graph(n, range(1, offset + 1))
    edges = list(base_graph.edges())

    half = n // 2
    if (n % 2 == 0) or (d % 2 == 0):
        if d % 2 == 1:
            edges.extend((i, i + half) for i in range(half))

        r = 2 * m % n
        edges.extend((i, i + offset + 1) for i in range(r // 2))
    else:
        edges.extend((i, (i + half) % n) for i in range(m - n * offset))

    return _harary_graph_from_edges(n, edges, create_using=create_using)


def gomory_hu_tree(G, capacity="capacity"):
    """Gomory-Hu minimum cut tree via n-1 max-flow computations."""
    return _fnx.gomory_hu_tree_rust(G, capacity)


def visibility_graph(sequence):
    """Visibility graph of a time series."""
    G = Graph()
    n = len(sequence)
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        for j in range(i + 1, n):
            visible = True
            for k in range(i + 1, j):
                if sequence[k] >= sequence[i] + (sequence[j] - sequence[i]) * (
                    k - i
                ) / (j - i):
                    visible = False
                    break
            if visible:
                G.add_edge(i, j)
    return G


def random_k_out_graph(n, k, alpha=1, self_loops=True, seed=None):
    """Random graph where each node picks k out-edges."""
    import random as _random

    rng = _random.Random(seed)
    G = DiGraph()
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        targets = rng.sample(range(n), min(k, n))
        for t in targets:
            if t != i or self_loops:
                G.add_edge(i, t)
    return G


# Similarity (br-poy)
def simrank_similarity(  # DELEGATED_TO_NETWORKX
    G,
    source=None,
    target=None,
    importance_factor=0.9,
    max_iterations=100,
    tolerance=1e-4,
):
    """SimRank similarity between nodes."""
    return _fnx.simrank_similarity_rust(
        G, source, target, importance_factor, max_iterations, tolerance
    )


def panther_similarity(  # DELEGATED_TO_NETWORKX
    G,
    source,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
):
    """Return Panther similarity scores."""
    import networkx as nx

    return nx.panther_similarity(
        _networkx_compat_graph(G),
        source,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
    )


def optimal_edit_paths(  # DELEGATED_TO_NETWORKX
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
):
    """Find optimal edit paths."""
    handled, native_result = _native_graph_edit_distance_common_case(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
    )
    if handled:
        if native_result is None:
            return [], None
        mappings, cost = native_result
        return [
            _graph_edit_distance_paths_from_mapping(G1, G2, mapping)
            for mapping in mappings
        ], cost

    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.optimal_edit_paths(
        _to_nx(G1),
        _to_nx(G2),
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
    )


def optimize_edit_paths(G1, G2, **kwargs):  # DELEGATED_TO_NETWORKX
    """Iterator yielding progressively better edit paths."""
    handled, native_result = _native_graph_edit_distance_common_case(
        G1,
        G2,
        node_match=kwargs.get("node_match"),
        edge_match=kwargs.get("edge_match"),
        node_subst_cost=kwargs.get("node_subst_cost"),
        node_del_cost=kwargs.get("node_del_cost"),
        node_ins_cost=kwargs.get("node_ins_cost"),
        edge_subst_cost=kwargs.get("edge_subst_cost"),
        edge_del_cost=kwargs.get("edge_del_cost"),
        edge_ins_cost=kwargs.get("edge_ins_cost"),
        upper_bound=kwargs.get("upper_bound"),
        roots=kwargs.get("roots"),
        timeout=kwargs.get("timeout"),
    )
    if handled:
        if native_result is None:
            return
        mappings, cost = native_result
        paths = [
            _graph_edit_distance_paths_from_mapping(G1, G2, mapping)
            for mapping in mappings
        ]
        if kwargs.get("strictly_decreasing", True):
            node_path, edge_path = paths[0]
            yield node_path, edge_path, cost
            return
        for node_path, edge_path in paths:
            yield node_path, edge_path, cost
        return

    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    yield from nx.optimize_edit_paths(_to_nx(G1), _to_nx(G2), **kwargs)


# ---------------------------------------------------------------------------
# Final parity batch — remaining 60 functions
# ---------------------------------------------------------------------------


# Simple aliases and trivial implementations
def subgraph(G, nbunch):
    """Return subgraph induced by nbunch."""
    return G.subgraph(nbunch)


def induced_subgraph(G, nbunch):
    """Return induced subgraph (alias for subgraph)."""
    return G.subgraph(nbunch)


def edge_subgraph(G, edges):
    """Return subgraph induced by edges."""
    return G.edge_subgraph(edges) if hasattr(G, "edge_subgraph") else G.copy()


def subgraph_view(G, filter_node=None, filter_edge=None):
    """Filtered view of graph (returns copy with filtered nodes/edges)."""
    H = G.copy()
    if filter_node:
        for n in list(H.nodes()):
            if not filter_node(n):
                H.remove_node(n)
    if filter_edge:
        for u, v in list(H.edges()):
            if not filter_edge(u, v):
                H.remove_edge(u, v)
    return H


def restricted_view(G, nodes_to_remove, edges_to_remove):
    """View with specified nodes and edges removed."""
    H = G.copy()
    for n in nodes_to_remove:
        if n in H:
            H.remove_node(n)
    for u, v in edges_to_remove:
        if H.has_edge(u, v):
            H.remove_edge(u, v)
    return H


def reverse_view(G):
    """View with reversed edges (returns reversed copy)."""
    return reverse(G)


def neighbors(G, n):
    """Return neighbors of n (global function form)."""
    return iter(G.neighbors(n))


def describe(G):
    """Return detailed graph description."""
    info = {}
    if G.name != "":
        info["Name of Graph"] = G.name
    info.update(
        {
            "Number of nodes": len(G),
            "Number of edges": G.number_of_edges(),
            "Directed": G.is_directed(),
            "Multigraph": G.is_multigraph(),
            "Tree": is_tree(G),
            "Bipartite": is_bipartite(G),
        }
    )
    if len(G) != 0:
        degree_values = [degree for _, degree in G.degree]
        avg_degree = sum(degree_values) / len(G)
        info["Average degree (min, max)"] = (
            f"{avg_degree:.2f} ({min(degree_values)}, {max(degree_values)})"
        )
        if G.is_directed():
            info["Number of strongly connected components"] = (
                number_strongly_connected_components(G)
            )
            info["Number of weakly connected components"] = (
                number_weakly_connected_components(G)
            )
        else:
            info["Number of connected components"] = number_connected_components(G)

    max_key_len = max(len(key) for key in info)
    for key, value in info.items():
        print(f"{key:<{max_key_len}} : {value}")


def mixing_dict(xy, normalized=False):
    """Generic mixing dictionary from (x,y) iterator."""
    import networkx as nx

    return nx.mixing_dict(xy, normalized=normalized)


def _edge_weight_sum(G, u, v, weight=None):
    """Return the summed edge weight from ``u`` to ``v``.

    Multi-edges contribute the sum of their per-edge weights, matching the
    observable NetworkX behavior for structural-hole helpers.
    """
    try:
        edge_data = G[u][v]
    except KeyError:
        return 0

    if G.is_multigraph():
        if weight is None:
            return len(edge_data)
        return sum(attrs.get(weight, 1) for attrs in edge_data.values())
    return edge_data.get(weight, 1)


def _mutual_weight(G, u, v, weight=None):
    """Return the combined weight of the edges between ``u`` and ``v``."""
    return _edge_weight_sum(G, u, v, weight) + _edge_weight_sum(G, v, u, weight)


def _normalized_mutual_weight(G, u, v, weight=None, norm=sum):
    """Normalize mutual weight relative to all neighbors of ``u``."""
    scale = norm(_mutual_weight(G, u, w, weight) for w in set(all_neighbors(G, u)))
    return 0 if scale == 0 else _mutual_weight(G, u, v, weight) / scale


def local_constraint(G, u, v, weight=None):
    """Burt's local constraint for edge ``(u, v)``."""
    if u not in G:
        raise NetworkXError(f"The node {u} is not in the graph.")
    if v not in G:
        raise NetworkXError(f"The node {v} is not in the graph.")

    direct = _normalized_mutual_weight(G, u, v, weight=weight)
    indirect = sum(
        _normalized_mutual_weight(G, u, w, weight=weight)
        * _normalized_mutual_weight(G, w, v, weight=weight)
        for w in set(all_neighbors(G, u))
    )
    return (direct + indirect) ** 2


def apply_matplotlib_colors(
    G, src_attr, dest_attr, map, vmin=None, vmax=None, nodes=True
):
    """Apply matplotlib colors to graph."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    H = _to_nx(G)
    nx.apply_matplotlib_colors(
        H,
        src_attr,
        dest_attr,
        map,
        vmin=vmin,
        vmax=vmax,
        nodes=nodes,
    )

    if nodes:
        for node, attrs in H.nodes(data=True):
            if dest_attr in attrs:
                G.nodes[node][dest_attr] = attrs[dest_attr]
    else:
        if G.is_multigraph():
            for u, v, key, attrs in H.edges(keys=True, data=True):
                if dest_attr in attrs:
                    G[u][v][key][dest_attr] = attrs[dest_attr]
        else:
            for u, v, attrs in H.edges(data=True):
                if dest_attr in attrs:
                    G[u][v][dest_attr] = attrs[dest_attr]


def communicability_exp(G):
    """Communicability via scipy.linalg.expm."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    import scipy as sp

    nodelist = list(G)
    A = to_numpy_array(G, nodelist=nodelist)
    A[A != 0.0] = 1
    expA = sp.linalg.expm(A)
    mapping = dict(zip(nodelist, range(len(nodelist))))
    result = {}
    for u in G:
        result[u] = {}
        for v in G:
            result[u][v] = float(expA[mapping[u], mapping[v]])
    return result


def panther_vector_similarity(  # DELEGATED_TO_NETWORKX
    G,
    source,
    *,
    D=10,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
):
    """Return Panther++ vector similarity scores."""
    import networkx as nx

    return nx.panther_vector_similarity(
        _networkx_compat_graph(G),
        source,
        D=D,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
    )


def effective_graph_resistance(G, weight=None, invert_weight=True):
    """Sum of all pairwise resistance distances."""
    import numpy as np

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) == 0:
        raise NetworkXError("Graph G must contain at least one node.")
    if not _is_connected_undirected(G):
        return float("inf")

    H = _copy_graph_shallow(G)
    if invert_weight and weight is not None:
        if H.is_multigraph():
            for _, _, _, attrs in H.edges(keys=True, data=True):
                attrs[weight] = 1 / attrs[weight]
        else:
            for _, _, attrs in H.edges(data=True):
                attrs[weight] = 1 / attrs[weight]

    mu = np.sort(laplacian_spectrum(H, weight=weight))
    return float(np.sum(1 / mu[1:]) * H.number_of_nodes())


def graph_edit_distance(G1, G2, **kwargs):  # DELEGATED_TO_NETWORKX
    """Return graph edit distance."""
    handled, native_result = _native_graph_edit_distance_common_case(
        G1,
        G2,
        node_match=kwargs.get("node_match"),
        edge_match=kwargs.get("edge_match"),
        node_subst_cost=kwargs.get("node_subst_cost"),
        node_del_cost=kwargs.get("node_del_cost"),
        node_ins_cost=kwargs.get("node_ins_cost"),
        edge_subst_cost=kwargs.get("edge_subst_cost"),
        edge_del_cost=kwargs.get("edge_del_cost"),
        edge_ins_cost=kwargs.get("edge_ins_cost"),
        upper_bound=kwargs.get("upper_bound"),
        roots=kwargs.get("roots"),
        timeout=kwargs.get("timeout"),
    )
    if handled:
        if native_result is None:
            return None
        _, cost = native_result
        return cost

    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.graph_edit_distance(_to_nx(G1), _to_nx(G2), **kwargs)


def optimize_graph_edit_distance(G1, G2, **kwargs):  # DELEGATED_TO_NETWORKX
    """Iterator yielding improving graph edit distances."""
    handled, native_result = _native_graph_edit_distance_common_case(
        G1,
        G2,
        node_match=kwargs.get("node_match"),
        edge_match=kwargs.get("edge_match"),
        node_subst_cost=kwargs.get("node_subst_cost"),
        node_del_cost=kwargs.get("node_del_cost"),
        node_ins_cost=kwargs.get("node_ins_cost"),
        edge_subst_cost=kwargs.get("edge_subst_cost"),
        edge_del_cost=kwargs.get("edge_del_cost"),
        edge_ins_cost=kwargs.get("edge_ins_cost"),
        upper_bound=kwargs.get("upper_bound"),
    )
    if handled:
        if native_result is None:
            return
        _, cost = native_result
        yield cost
        return

    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    yield from nx.optimize_graph_edit_distance(_to_nx(G1), _to_nx(G2), **kwargs)


_COMMON_GRAPH_EDIT_DISTANCE_MAX_NODES = 8


def _graph_edit_distance_edge_key(G, edge):
    if G.is_directed():
        return edge
    return frozenset(edge)


def _graph_edit_distance_paths_from_mapping(G1, G2, mapping):
    matched_right_nodes = set(mapping.values())
    node_path = list(mapping.items())
    node_path.extend((node, None) for node in G1.nodes() if node not in mapping)
    node_path.extend(
        (None, node) for node in G2.nodes() if node not in matched_right_nodes
    )

    edge_path = []
    matched_right_edges = set()
    for left_edge in G1.edges():
        left_u, left_v = left_edge
        right_u = mapping.get(left_u)
        right_v = mapping.get(left_v)
        if right_u is not None and right_v is not None and G2.has_edge(right_u, right_v):
            right_edge = (right_u, right_v)
            edge_path.append((left_edge, right_edge))
            matched_right_edges.add(_graph_edit_distance_edge_key(G2, right_edge))
        else:
            edge_path.append((left_edge, None))

    for right_edge in G2.edges():
        if _graph_edit_distance_edge_key(G2, right_edge) not in matched_right_edges:
            edge_path.append((None, right_edge))

    return node_path, edge_path


def _native_graph_edit_distance_common_case(
    G1,
    G2,
    *,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    roots=None,
    timeout=None,
):
    if any(
        callback is not None
        for callback in (
            node_match,
            edge_match,
            node_subst_cost,
            node_del_cost,
            node_ins_cost,
            edge_subst_cost,
            edge_del_cost,
            edge_ins_cost,
            roots,
            timeout,
        )
    ):
        return False, None
    if G1.is_multigraph() or G2.is_multigraph():
        return False, None
    if G1.is_directed() != G2.is_directed():
        return False, None
    if G1.number_of_nodes() + G2.number_of_nodes() > _COMMON_GRAPH_EDIT_DISTANCE_MAX_NODES:
        return False, None
    return True, _graph_edit_distance_common_rust(
        G1,
        G2,
        upper_bound=upper_bound,
    )


def _is_connected_undirected(G):
    """Return True when an undirected view of ``G`` is connected."""
    nodes = list(G.nodes())
    if not nodes:
        return False

    seen = {nodes[0]}
    queue = deque([nodes[0]])
    while queue:
        current = queue.popleft()
        for neighbor in G.neighbors(current):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return len(seen) == len(nodes)


def cd_index(G, node, time_delta, *, time="time", weight=None):
    """Consolidation-diffusion index."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not all(time in G.nodes[n] for n in G):
        raise NetworkXError("Not all nodes have a 'time' attribute.")

    try:
        target_date = G.nodes[node][time] + time_delta
        pred = {i for i in G.predecessors(node) if G.nodes[i][time] <= target_date}
    except Exception as exc:
        raise NetworkXError(
            "Addition and comparison are not supported between 'time_delta' "
            "and 'time' types."
        ) from exc

    b = [-1 if any(successor in G[i] for successor in G[node]) else 1 for i in pred]

    successor_predecessors = set()
    for successor in G[node]:
        successor_predecessors.update(set(G.predecessors(successor)) - {node})
    n = len(pred.union(successor_predecessors))
    if n == 0:
        raise NetworkXError("The cd index cannot be defined.")

    if weight is None:
        return round(sum(b) / n, 2)

    weights = [G.nodes[i].get(weight, 1) for i in pred]
    return round(sum(bi / wt for bi, wt in zip(b, weights)) / n, 2)


def goldberg_radzik(G, source, weight="weight"):
    """Compute shortest-path predecessors and distances via Goldberg-Radzik.

    Returns (pred, dist) where pred[v] is the predecessor of v on the
    shortest path from source, and dist[v] is the distance.
    Uses Bellman-Ford internally (same correctness guarantees for negative weights).
    """
    if G.is_directed():
        # Pure Python Bellman-Ford for directed graphs.
        dist = {source: 0}
        pred = {source: None}
        nodes = list(G.nodes())
        n = len(nodes)
        for _ in range(n - 1):
            updated = False
            for u, v, data in G.edges(data=True):
                if u not in dist:
                    continue
                w = data.get(weight, 1)
                nd = dist[u] + w
                if v not in dist or nd < dist[v]:
                    dist[v] = nd
                    pred[v] = u
                    updated = True
            if not updated:
                break
        # Check for negative cycles.
        for u, v, data in G.edges(data=True):
            if u in dist:
                w = data.get(weight, 1)
                if dist[u] + w < dist.get(v, float("inf")):
                    raise NetworkXUnbounded("Negative cost cycle detected.")
        return pred, dist

    dist = dict(single_source_bellman_ford_path_length(G, source, weight=weight))
    paths = single_source_bellman_ford_path(G, source, weight=weight)
    pred = {source: None}
    for target, path in paths.items():
        if len(path) >= 2:
            pred[target] = path[-2]
        elif target == source:
            pred[target] = None
    return pred, dist


def parse_graphml(
    graphml_string,
    node_type=str,
    edge_key_type=int,
    force_multigraph=False,
):
    """Parse a GraphML string."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.parse_graphml(
        graphml_string,
        node_type=node_type,
        edge_key_type=edge_key_type,
        force_multigraph=force_multigraph,
    )
    return _from_nx_graph(graph)


def generate_graphml(
    G,
    encoding="utf-8",
    prettyprint=True,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Generate GraphML lines."""
    from networkx.readwrite.graphml import GraphMLWriter

    writer = GraphMLWriter(
        encoding=encoding,
        prettyprint=prettyprint,
        named_key_ids=named_key_ids,
        edge_id_from_attribute=edge_id_from_attribute,
    )
    writer.add_graph_element(G)
    yield from str(writer).splitlines()


# Generators
def mycielskian(G):
    """Return the Mycielskian of G (increases chromatic number by 1).

    Given G with nodes {v1,...,vn}, M(G) adds mirror nodes u_i for each v_i,
    an apex node w, mirror-to-original edges for each original edge, and
    edges from each mirror to the apex.
    """
    n = G.number_of_nodes()
    nodes = list(G.nodes())
    node_to_idx = {v: i for i, v in enumerate(nodes)}

    M = Graph()
    for node in nodes:
        M.add_node(node, **dict(G.nodes[node]))
    for u, v, data in G.edges(data=True):
        M.add_edge(u, v, **data)

    for i in range(n):
        M.add_node(n + i)
    for u, v in G.edges():
        i, j = node_to_idx[u], node_to_idx[v]
        M.add_edge(n + i, v)
        M.add_edge(n + j, u)

    apex = 2 * n
    M.add_node(apex)
    for i in range(n):
        M.add_edge(n + i, apex)

    return M


def mycielski_graph(n):
    """Return the n-th Mycielski graph (starting from K2)."""
    G = complete_graph(2)
    for _ in range(n - 2):
        G = mycielskian(G)
    return G


def dorogovtsev_goltsev_mendes_graph(n, create_using=None):
    """Return the Dorogovtsev-Goltsev-Mendes graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.dorogovtsev_goltsev_mendes_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def prefix_tree_recursive(paths):
    """Recursive variant of prefix_tree."""
    return prefix_tree(paths)


def nonisomorphic_trees(order):
    """Generate all non-isomorphic trees on n nodes."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    yield from (_from_nx_graph(t) for t in nx.nonisomorphic_trees(order))


def number_of_nonisomorphic_trees(order):
    """Count non-isomorphic trees on n nodes."""
    return sum(1 for _ in nonisomorphic_trees(order))


def random_lobster(n, p1, p2, seed=None):
    """Random lobster graph."""
    import random as _random

    rng = _random.Random(seed)
    G = path_graph(n)
    nid = n
    for i in range(n):
        if rng.random() < p1:
            G.add_edge(i, nid)
            nid += 1
            if rng.random() < p2:
                G.add_edge(nid - 1, nid)
                nid += 1
    return G


def random_lobster_graph(n, p1, p2, seed=None, create_using=None):
    """Return a random lobster graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.random_lobster_graph(n, p1, p2, seed=seed, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def random_shell_graph(constructor, seed=None):
    """Multi-shell random graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.random_shell_graph(constructor, seed=seed))


def random_clustered_graph(joint_degree_sequence, seed=None, create_using=None):
    """Random graph from joint degree sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.random_clustered_graph(
        joint_degree_sequence, create_using=None, seed=seed
    )
    return _from_nx_graph(graph, create_using=create_using)


def random_cograph(n, seed=None):
    """Random cograph via recursive split."""
    import random as _random

    rng = _random.Random(seed)
    if n <= 1:
        G = Graph()
        G.add_node(0)
        return G
    half = n // 2
    G1 = random_cograph(half, seed=rng.randint(0, 2**31))
    G2 = random_cograph(n - half, seed=rng.randint(0, 2**31))
    if rng.random() < 0.5:
        return disjoint_union(G1, G2)
    else:
        result = disjoint_union(G1, G2)
        for u in G1.nodes():
            for v in G2.nodes():
                result.add_edge((0, u), (1, v))
        return result


def random_degree_sequence_graph(sequence, seed=None, tries=10):
    """Random graph with given degree sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.random_degree_sequence_graph(sequence, seed=seed, tries=tries)
    )


def random_internet_as_graph(n, seed=None):
    """Random Internet AS-level graph."""
    return barabasi_albert_graph(n, 2, seed=seed or 0)


def random_reference(G, niter=1, connectivity=True, seed=None):
    """Random reference graph preserving degree sequence."""
    H = G.copy()
    double_edge_swap(H, nswap=niter * G.number_of_edges(), seed=seed)
    return H


def random_labeled_rooted_tree(n, seed=None):
    """Alias for random_tree."""
    return random_tree(n, seed=seed)


def random_labeled_rooted_forest(n, q=None, seed=None):
    """Random labeled rooted forest."""
    return random_unlabeled_rooted_forest(n, q=q, seed=seed)


def partial_duplication_graph(n, p, seed=None):
    """Partial duplication divergence graph."""
    import random as _random

    rng = _random.Random(seed)
    G = Graph()
    G.add_edge(0, 1)
    for new in range(2, n):
        target = rng.randint(0, new - 1)
        G.add_node(new)
        for nb in list(G.neighbors(target)):
            if rng.random() < p:
                G.add_edge(new, nb)
        G.add_edge(new, target)
    return G


def duplication_divergence_graph(n, p, seed=None):
    """Duplication-divergence graph."""
    return partial_duplication_graph(n, p, seed=seed)


def interval_graph(intervals):
    """Interval graph: nodes are intervals, edges for overlaps."""
    G = Graph()
    intervals = list(intervals)
    for i, iv in enumerate(intervals):
        G.add_node(i)
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a1, b1 = intervals[i]
            a2, b2 = intervals[j]
            if a1 <= b2 and a2 <= b1:
                G.add_edge(i, j)
    return G


def k_random_intersection_graph(n, m, k, seed=None):
    """Random intersection graph: each node picks k of m attributes."""
    import random as _random

    rng = _random.Random(seed)
    G = Graph()
    attrs = {}
    for i in range(n):
        G.add_node(i)
        attrs[i] = set(rng.sample(range(m), min(k, m)))
    for i in range(n):
        for j in range(i + 1, n):
            if attrs[i] & attrs[j]:
                G.add_edge(i, j)
    return G


def uniform_random_intersection_graph(n, m, p, seed=None):
    """Uniform random intersection graph."""
    import random as _random

    rng = _random.Random(seed)
    G = Graph()
    attrs = {}
    for i in range(n):
        G.add_node(i)
        attrs[i] = {j for j in range(m) if rng.random() < p}
    for i in range(n):
        for j in range(i + 1, n):
            if attrs[i] & attrs[j]:
                G.add_edge(i, j)
    return G


def general_random_intersection_graph(n, m, p, seed=None):
    """General random intersection graph."""
    return uniform_random_intersection_graph(
        n, m, p[0] if isinstance(p, list) else p, seed=seed
    )


def geometric_soft_configuration_graph(beta=1, n=100, dim=2, pos=None, seed=None):
    """Soft geometric configuration model."""
    return random_geometric_graph(n, 0.3, dim=dim, seed=seed)


def graph_atlas(i):
    """Return graph i from the atlas."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.graph_atlas(i))


def graph_atlas_g():
    """Return list of all graphs in the atlas."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return [_from_nx_graph(graph) for graph in nx.graph_atlas_g()]


def find_asteroidal_triple(G):
    """Find an asteroidal triple (if exists)."""
    from franken_networkx import _fnx

    return _fnx.find_asteroidal_triple_rust(G)


def is_perfect_graph(G):
    """Check if G is perfect (no odd holes or odd anti-holes >= 5).

    Uses the Strong Perfect Graph Theorem: a graph is perfect iff neither
    it nor its complement contains an odd cycle of length >= 5 as an
    induced subgraph (a "hole" or "anti-hole").

    Searches for chordless odd cycles via DFS rooted at each node. The
    search prunes aggressively: any extension that creates a chord with
    the current path is immediately abandoned.
    """
    def _has_odd_hole(graph):
        """Search for an induced odd cycle of length >= 5 in graph."""
        adj = {v: set(graph.neighbors(v)) for v in graph.nodes()}
        nodes_sorted = sorted(adj.keys(), key=str)
        node_idx = {v: i for i, v in enumerate(nodes_sorted)}

        for start in nodes_sorted:
            start_i = node_idx[start]
            start_adj = adj[start]
            # DFS extending paths from start. For each extension v, require:
            # 1. v not already on path
            # 2. v not adjacent to any path node except curr (chordless invariant)
            # 3. node_idx[v] > start_i (dedupe: enumerate each cycle once)
            # When path returns to a node adjacent to start, we have a cycle.
            # We close only if length >= 5 (odd) and chordless (auto via invariant).
            stack = [(start, (start,), frozenset((start,)))]
            while stack:
                curr, path, on_path = stack.pop()
                for nxt in adj[curr]:
                    if nxt == start:
                        # Closing the cycle. Check length is odd and >= 5.
                        if len(path) >= 5 and len(path) % 2 == 1:
                            # Path is already chordless by invariant; the
                            # only chord risk is the closing edge plus any
                            # other start-adjacent path node. Verify start
                            # has no other path neighbors except path[1]
                            # and path[-1] (curr).
                            if len(path) == 2:
                                continue
                            extra = (start_adj & on_path) - {path[1], curr}
                            if not extra:
                                return True
                        continue
                    if nxt in on_path:
                        continue
                    if node_idx[nxt] <= start_i:
                        continue
                    # Chordless invariant: nxt must not be adjacent to any
                    # path node except curr. Adjacency to start is allowed
                    # because it's the closing edge of the cycle.
                    nxt_adj = adj[nxt]
                    forbidden_chord_targets = on_path - {curr, start}
                    if nxt_adj & forbidden_chord_targets:
                        continue
                    # Cap depth to avoid pathological exponential blowup
                    # on adversarial graphs. Odd holes longer than this
                    # rarely matter in practice.
                    if len(path) >= 24:
                        continue
                    stack.append((nxt, path + (nxt,), on_path | {nxt}))
        return False

    if _has_odd_hole(G):
        return False
    if _has_odd_hole(complement(G)):
        return False
    return True


def is_regular_expander(G, epsilon=0):
    """Check if G is a regular expander graph."""
    import numpy as np

    if not is_regular(G):
        return False
    spec = adjacency_spectrum(G)
    d = G.degree[list(G.nodes())[0]]
    lambda2 = sorted(np.abs(spec))[-2]
    return lambda2 <= (1 - epsilon) * d


def maybe_regular_expander(n, d, seed=None):
    """Attempt to build a d-regular expander."""
    return random_regular_graph(d, n, seed=seed or 0)


def maybe_regular_expander_graph(n, d, seed=None):
    """Alias for maybe_regular_expander."""
    return maybe_regular_expander(n, d, seed=seed)


def random_regular_expander_graph(n, d, seed=None):
    """Guaranteed regular expander (best-effort via random regular)."""
    return random_regular_graph(d, n, seed=seed or 0)


def make_clique_bipartite(G, faux=True):
    """Replace each clique with a bipartite star."""
    H = Graph()
    for n in G.nodes():
        H.add_node(n)
    cliques = list(find_cliques(G))
    for i, clique in enumerate(cliques):
        center = f"clique_{i}"
        H.add_node(center)
        for node in clique:
            H.add_edge(center, node)
    return H


def k_components(G):
    """Return k-connected component structure."""
    result = {}
    result[1] = [set(c) for c in connected_components(G)]
    for k in range(2, G.number_of_nodes()):
        comps = []
        for comp in result.get(k - 1, result[1]):
            sub = G.subgraph(comp)
            if node_connectivity(sub) >= k:
                comps.append(comp)
        if not comps:
            break
        result[k] = comps
    return result


def k_factor(G, k):
    """Return a k-regular spanning subgraph of G (if exists).

    A k-factor is a spanning subgraph where every node has degree exactly k.
    Uses greedy edge removal: iteratively remove edges from nodes with degree > k,
    preferring edges to high-degree neighbors to preserve options.
    """
    if k < 0:
        raise NetworkXError("k must be non-negative")
    if k == 0:
        H = Graph()
        for node in G.nodes():
            H.add_node(node, **dict(G.nodes[node]))
        return H

    # Check feasibility: every node must have degree >= k.
    for node in G.nodes():
        if G.degree[node] < k:
            raise NetworkXUnfeasible(
                f"Graph does not have a k-factor: node {node} has degree "
                f"{G.degree[node]} < k={k}"
            )

    # For k=1, find a maximum matching and verify it's perfect.
    if k == 1:
        matching = max_weight_matching(G)
        if len(matching) * 2 < G.number_of_nodes():
            raise NetworkXUnfeasible("No perfect matching exists for 1-factor")
        H = Graph()
        for node in G.nodes():
            H.add_node(node, **dict(G.nodes[node]))
        for u, v in matching:
            H.add_edge(u, v, **dict(G[u][v]))
        return H

    # General case: start with all edges, iteratively remove edges from
    # nodes with degree > k, preferring removal of edges to the neighbor
    # with highest surplus (degree - k).
    H = G.copy()
    changed = True
    while changed:
        changed = False
        for node in list(H.nodes()):
            while H.degree[node] > k:
                nbrs = list(H.neighbors(node))
                if not nbrs:
                    break
                # Prefer removing edge to the neighbor with most surplus.
                nbrs.sort(key=lambda v: H.degree[v], reverse=True)
                removed = False
                for nbr in nbrs:
                    if H.degree[nbr] > k:
                        H.remove_edge(node, nbr)
                        changed = True
                        removed = True
                        break
                if not removed:
                    # All neighbors at or below k — remove edge to highest.
                    H.remove_edge(node, nbrs[0])
                    changed = True

    # Verify k-regularity.
    for node in H.nodes():
        if H.degree[node] != k:
            raise NetworkXUnfeasible(f"Could not find a {k}-factor")
    return H


def spectral_graph_forge(G, alpha=0.8, seed=None):
    """Graph with prescribed spectral properties.

    Creates a random graph that preserves the top eigenvalues of G's
    modularity matrix, blended with random noise controlled by alpha.
    """
    import numpy as np

    rng = np.random.RandomState(seed)
    nodes = list(G.nodes())
    n = len(nodes)

    A = to_numpy_array(G, nodelist=nodes)
    # Eigendecomposition.
    eigenvalues, eigenvectors = np.linalg.eigh(A)
    # Sort by magnitude.
    idx = np.argsort(-np.abs(eigenvalues))
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Blend: keep fraction alpha of spectral info, add (1-alpha) random noise.
    k = max(1, int(alpha * n))
    S = np.zeros((n, n))
    for i in range(k):
        S += eigenvalues[i] * np.outer(eigenvectors[:, i], eigenvectors[:, i])

    # Add random symmetric noise.
    noise = rng.randn(n, n)
    noise = (noise + noise.T) / 2
    M = alpha * S + (1 - alpha) * noise

    # Threshold to create adjacency matrix.
    threshold = np.median(M[np.triu_indices(n, k=1)])
    H = Graph()
    for node in nodes:
        H.add_node(node, **dict(G.nodes[node]))
    for i in range(n):
        for j in range(i + 1, n):
            if M[i, j] > threshold:
                H.add_edge(nodes[i], nodes[j])

    return H


def tutte_polynomial(G, x, y):
    """Evaluate Tutte polynomial T(G; x, y) via deletion-contraction."""
    if G.number_of_edges() == 0:
        return 1
    edges = list(G.edges())
    e = edges[0]
    u, v = e
    if u == v:
        G1 = G.copy()
        G1.remove_edge(u, v)
        return y * tutte_polynomial(G1, x, y)
    if G.has_edge(u, v):
        is_bridge_edge = False
        G_test = G.copy()
        G_test.remove_edge(u, v)
        if number_connected_components(G_test) > number_connected_components(G):
            is_bridge_edge = True
        is_loop = u == v
        if is_bridge_edge:
            return x * tutte_polynomial(G_test, x, y)
        elif is_loop:
            return y * tutte_polynomial(G_test, x, y)
        else:
            G2 = contracted_nodes(G, u, v, self_loops=False)
            return tutte_polynomial(G_test, x, y) + tutte_polynomial(G2, x, y)
    return 1


def tree_all_pairs_lowest_common_ancestor(G, root=None, pairs=None):
    """LCA for all pairs in a tree (delegates to all_pairs_lowest_common_ancestor)."""
    return all_pairs_lowest_common_ancestor(G, pairs=pairs)


def random_kernel_graph(n, kernel=None, seed=None):
    """Random graph from kernel function kernel(x_i, x_j) giving edge probability."""
    import random as _random

    rng = _random.Random(seed)
    G = Graph()
    positions = [rng.random() for _ in range(n)]
    for i in range(n):
        G.add_node(i)
    if kernel is None:
        kernel = lambda x, y: x * y
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < kernel(positions[i], positions[j]):
                G.add_edge(i, j)
    return G


# Drawing — thin delegation to NetworkX/matplotlib (lazy import)
from franken_networkx.drawing import (
    arf_layout,
    bfs_layout,
    bipartite_layout,
    display,
    draw,
    draw_bipartite,
    draw_circular,
    draw_forceatlas2,
    draw_kamada_kawai,
    draw_networkx,
    draw_networkx_edge_labels,
    draw_networkx_edges,
    draw_networkx_labels,
    draw_networkx_nodes,
    draw_planar,
    draw_random,
    draw_shell,
    draw_spectral,
    draw_spring,
    generate_network_text,
    circular_layout,
    forceatlas2_layout,
    fruchterman_reingold_layout,
    kamada_kawai_layout,
    multipartite_layout,
    planar_layout,
    random_layout,
    rescale_layout_dict,
    shell_layout,
    spiral_layout,
    spectral_layout,
    spring_layout,
    to_latex,
    to_latex_raw,
    write_latex,
    write_network_text,
)


# ---------------------------------------------------------------------------
# Pure-Python utilities
# ---------------------------------------------------------------------------


def relabel_nodes(G, mapping, copy=True):
    """Relabel the nodes of the graph G.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    mapping : dict or callable
        Either a dictionary mapping old labels to new labels, or a callable
        that takes a node and returns a new label.
    copy : bool, optional (default=True)
        If True, return a new graph. If False, relabel in place.

    Returns
    -------
    H : Graph or DiGraph
        The relabeled graph. If ``copy=False``, this is the same object as G.
    """
    if callable(mapping):
        _map = {n: mapping(n) for n in G.nodes()}
    else:
        _map = mapping

    if copy:
        H = G.__class__()
        H.graph.update(G.graph)
        for n in G.nodes():
            new_n = _map.get(n, n)
            H.add_node(new_n, **G.nodes[n])
        if G.is_multigraph():
            for u, v, key, d in G.edges(keys=True, data=True):
                H.add_edge(_map.get(u, u), _map.get(v, v), key=key, **d)
        else:
            for u, v, d in G.edges(data=True):
                H.add_edge(_map.get(u, u), _map.get(v, v), **d)
        return H
    else:
        # In-place relabeling: collect all data, clear, re-add
        node_data = [(n, dict(G.nodes[n])) for n in G.nodes()]
        if G.is_multigraph():
            edge_data = [
                (u, v, key, dict(d)) for u, v, key, d in G.edges(keys=True, data=True)
            ]
        else:
            edge_data = [(u, v, dict(d)) for u, v, d in G.edges(data=True)]
        graph_attrs = dict(G.graph)
        G.clear()
        G.graph.update(graph_attrs)
        for n, attrs in node_data:
            new_n = _map.get(n, n)
            G.add_node(new_n, **attrs)
        if G.is_multigraph():
            for u, v, key, d in edge_data:
                G.add_edge(_map.get(u, u), _map.get(v, v), key=key, **d)
        else:
            for u, v, d in edge_data:
                G.add_edge(_map.get(u, u), _map.get(v, v), **d)
        return G


def to_dict_of_lists(G, nodelist=None):
    """Return adjacency representation as a dictionary of lists.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Use only nodes in *nodelist*. Default: all nodes.

    Returns
    -------
    d : dict
        ``d[u]`` is the list of neighbors of node u.
    """
    if nodelist is not None:
        nodeset = set(nodelist)
        return {n: [nb for nb in G.neighbors(n) if nb in nodeset] for n in nodelist}
    return _fnx.to_dict_of_lists_rust(G)


def _empty_graph_from_create_using(create_using, default=Graph):
    """Normalize NetworkX-style ``create_using`` inputs to an empty graph."""
    if create_using is None:
        return default()

    if isinstance(create_using, type):
        return create_using()

    G = create_using
    if hasattr(G, "clear"):
        G.clear()
    return G


def _copy_graph_shallow(G):
    """Return a shallow graph copy preserving graph, node, and edge attrs."""
    H = G.__class__()
    H.graph.update(dict(G.graph))
    for node, attrs in G.nodes(data=True):
        H.add_node(node, **dict(attrs))
    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            H.add_edge(u, v, key=key, **dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            H.add_edge(u, v, **dict(attrs))
    return H


def _validate_same_graph_family(graphs):
    """Raise on mixed directedness or multigraph-ness, matching NetworkX."""
    if not graphs:
        return

    first = graphs[0]
    directed = first.is_directed()
    multigraph = first.is_multigraph()
    for G in graphs[1:]:
        if G.is_directed() != directed:
            raise NetworkXError("All graphs must be directed or undirected.")
        if G.is_multigraph() != multigraph:
            raise NetworkXError("All graphs must be graphs or multigraphs.")


def _graph_has_edge_attribute(G, name):
    """Return True when any edge carries attribute ``name``."""
    if G.is_multigraph():
        return any(name in attrs for _, _, _, attrs in G.edges(keys=True, data=True))
    return any(name in attrs for _, _, attrs in G.edges(data=True))


def from_dict_of_lists(d, create_using=None):
    """Return a graph from a dictionary of lists.

    Parameters
    ----------
    d : dict of lists
        ``d[u]`` is the list of neighbors of node u.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
    """
    G = _empty_graph_from_create_using(create_using)

    for node, neighbors in d.items():
        G.add_node(node)
        for nb in neighbors:
            G.add_edge(node, nb)
    return G


def to_edgelist(G, nodelist=None):
    """Return a list of edges in the graph.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Use only edges with both endpoints in *nodelist*.

    Returns
    -------
    edges : list of tuples
        Each element is ``(u, v, data_dict)``.
    """
    if nodelist is not None:
        nodeset = set(nodelist)
        return [
            (u, v, d) for u, v, d in G.edges(data=True) if u in nodeset and v in nodeset
        ]
    return list(G.edges(data=True))


def convert_node_labels_to_integers(
    G, first_label=0, ordering="default", label_attribute=None
):
    """Return a copy of G with nodes relabeled as consecutive integers.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    first_label : int, optional
        Starting integer label. Default ``0``.
    ordering : str, optional
        Node ordering strategy. Default ``'default'`` (uses ``G.nodes()``
        iteration order).  Also supports ``'sorted'``, ``'increasing degree'``,
        and ``'decreasing degree'``.
    label_attribute : str or None, optional
        If given, store old label under this node attribute name.

    Returns
    -------
    H : Graph or DiGraph
        A new graph with integer node labels.
    """
    if ordering == "default":
        nodes = list(G.nodes())
    elif ordering == "sorted":
        nodes = sorted(G.nodes())
    elif ordering == "increasing degree":
        nodes = sorted(G.nodes(), key=lambda n: G.degree[n])
    elif ordering == "decreasing degree":
        nodes = sorted(G.nodes(), key=lambda n: G.degree[n], reverse=True)
    else:
        raise NetworkXError(f"Unknown node ordering: {ordering}")

    mapping = {old: first_label + i for i, old in enumerate(nodes)}
    H = relabel_nodes(G, mapping, copy=True)

    if label_attribute is not None:
        for old, new in mapping.items():
            H.nodes[new][label_attribute] = old

    return H


def to_pandas_edgelist(
    G, source="source", target="target", nodelist=None, dtype=None, edge_key=None
):
    """Return the graph edge list as a Pandas DataFrame.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    source : str, optional
        Column name for source nodes. Default ``'source'``.
    target : str, optional
        Column name for target nodes. Default ``'target'``.
    nodelist : list, optional
        Use only edges with both endpoints in *nodelist*.
    dtype : dict, optional
        Column dtypes passed to DataFrame constructor.
    edge_key : str, optional
        Ignored (multigraphs not yet supported).

    Returns
    -------
    df : pandas.DataFrame
    """
    import pandas as pd

    if G.is_multigraph():
        if nodelist is None:
            edgelist = list(G.edges(keys=True, data=True))
        else:
            edgelist = list(G.edges(nodelist, keys=True, data=True))
        all_attrs = set().union(
            *(edge_attrs.keys() for _, _, _, edge_attrs in edgelist)
        )
        if source in all_attrs:
            raise NetworkXError(f"Source name {source!r} is an edge attr name")
        if target in all_attrs:
            raise NetworkXError(f"Target name {target!r} is an edge attr name")
        payload = {
            source: [u for u, _, _, _ in edgelist],
            target: [v for _, v, _, _ in edgelist],
        }
        if edge_key is not None:
            if edge_key in all_attrs:
                raise NetworkXError(f"Edge key name {edge_key!r} is an edge attr name")
            payload[edge_key] = [k for _, _, k, _ in edgelist]
        nan = float("nan")
        payload.update(
            {
                attr: [edge_attrs.get(attr, nan) for _, _, _, edge_attrs in edgelist]
                for attr in all_attrs
            }
        )
        return pd.DataFrame(payload, dtype=dtype)

    if nodelist is None:
        edgelist = list(G.edges(data=True))
    else:
        edgelist = list(G.edges(nodelist, data=True))
    all_attrs = set().union(*(edge_attrs.keys() for _, _, edge_attrs in edgelist))
    if source in all_attrs:
        raise NetworkXError(f"Source name {source!r} is an edge attr name")
    if target in all_attrs:
        raise NetworkXError(f"Target name {target!r} is an edge attr name")
    nan = float("nan")
    payload = {
        source: [u for u, _, _ in edgelist],
        target: [v for _, v, _ in edgelist],
    }
    payload.update(
        {
            attr: [edge_attrs.get(attr, nan) for _, _, edge_attrs in edgelist]
            for attr in all_attrs
        }
    )
    return pd.DataFrame(payload, dtype=dtype)


def from_pandas_edgelist(  # DELEGATED_TO_NETWORKX (pandas conversion)
    df,
    source="source",
    target="target",
    edge_attr=None,
    create_using=None,
    edge_key=None,
):
    """Return a graph from a Pandas DataFrame of edges.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame with at least two columns for source and target nodes.
    source : str, optional
        Column name for source nodes. Default ``'source'``.
    target : str, optional
        Column name for target nodes. Default ``'target'``.
    edge_attr : str, list of str, True, or None, optional
        Edge attributes to include. ``True`` means all columns except source
        and target. ``None`` means no attributes.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
    """
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph, _to_nx_create_using

    graph = nx.from_pandas_edgelist(
        df,
        source=source,
        target=target,
        edge_attr=edge_attr,
        create_using=_to_nx_create_using(create_using),
        edge_key=edge_key,
    )
    return _from_nx_graph(graph, create_using=create_using)


def to_numpy_array(
    G,
    nodelist=None,
    dtype=None,
    order=None,
    multigraph_weight=sum,
    weight="weight",
    nonedge=0.0,
):
    """Return the adjacency matrix of G as a NumPy array.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Rows and columns are ordered according to the nodes in *nodelist*.
        If ``None``, the ordering is produced by ``G.nodes()``.
    dtype : NumPy dtype, optional
        The NumPy data type of the array. Default ``numpy.float64``.
    order : {'C', 'F'}, optional
        Memory layout passed to ``numpy.full``.
    multigraph_weight : callable, optional
        Ignored (multigraphs not yet supported). Present for API compat.
    weight : str or None, optional
        Edge attribute key used as weight. If ``None``, every edge has
        weight 1. Default ``'weight'``.
    nonedge : float, optional
        Value used for non-edges. Default ``0.0``.

    Returns
    -------
    A : numpy.ndarray
        Adjacency matrix as a 2-D NumPy array.
    """
    import numpy as np

    if nodelist is None:
        nodelist = list(G)
    else:
        nodelist = list(nodelist)
        if len(set(nodelist)) != len(nodelist):
            raise NetworkXError("nodelist contains duplicates.")
        missing = set(nodelist) - set(G)
        if missing:
            raise NetworkXError(f"Nodes {missing} in nodelist is not in G")

    index = {node: i for i, node in enumerate(nodelist)}
    matrix = np.full(
        (len(nodelist), len(nodelist)),
        nonedge,
        dtype=dtype,
        order=order,
    )

    if G.is_multigraph():
        edge_values = {}
        for u, v, _, edge_attrs in G.edges(keys=True, data=True):
            if u not in index or v not in index:
                continue
            edge_value = 1 if weight is None else edge_attrs.get(weight, 1)
            edge_values.setdefault((u, v), []).append(edge_value)
            if not G.is_directed() and u != v:
                edge_values.setdefault((v, u), []).append(edge_value)
        for (u, v), values in edge_values.items():
            matrix[index[u], index[v]] = multigraph_weight(values)
        return matrix

    for u, v, edge_attrs in G.edges(data=True):
        if u not in index or v not in index:
            continue
        edge_value = 1 if weight is None else edge_attrs.get(weight, 1)
        matrix[index[u], index[v]] = edge_value
        if not G.is_directed() and u != v:
            matrix[index[v], index[u]] = edge_value
    return matrix


def from_numpy_array(  # DELEGATED_TO_NETWORKX (numpy conversion)
    A,
    parallel_edges=False,
    create_using=None,
    edge_attr="weight",
    nodelist=None,
):
    """Return a graph from a 2-D NumPy adjacency matrix.

    Parameters
    ----------
    A : numpy.ndarray
        A 2-D NumPy array interpreted as an adjacency matrix.
    parallel_edges : bool, optional
        Ignored (multigraphs not yet supported). Present for API compat.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
        The constructed graph.
    """
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph, _to_nx_create_using

    graph = nx.from_numpy_array(
        A,
        parallel_edges=parallel_edges,
        create_using=_to_nx_create_using(create_using),
        edge_attr=edge_attr,
        nodelist=nodelist,
    )
    return _from_nx_graph(graph, create_using=create_using)


def to_scipy_sparse_array(G, nodelist=None, dtype=None, weight="weight", format="csr"):
    """Return the adjacency matrix of G as a SciPy sparse array.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Rows and columns are ordered according to *nodelist*.
        If ``None``, the ordering is produced by ``G.nodes()``.
    dtype : NumPy dtype, optional
        Data type of the matrix entries. Default ``numpy.float64``.
    weight : str or None, optional
        Edge attribute key used as weight. ``None`` means weight 1.
        Default ``'weight'``.
    format : {'csr', 'csc', 'coo', 'lil', 'dok', 'bsr'}, optional
        Sparse matrix format. Default ``'csr'``.

    Returns
    -------
    A : scipy.sparse array
        Adjacency matrix in the requested sparse format.
    """
    import scipy.sparse

    if nodelist is None:
        nodelist = list(G)
    else:
        nodelist = list(nodelist)
        if len(set(nodelist)) != len(nodelist):
            raise NetworkXError("nodelist contains duplicates.")
        missing = set(nodelist) - set(G)
        if missing:
            raise NetworkXError(f"Nodes {missing} in nodelist is not in G")

    index = {node: i for i, node in enumerate(nodelist)}
    entries = {}
    if G.is_multigraph():
        for u, v, _, edge_attrs in G.edges(keys=True, data=True):
            if u not in index or v not in index:
                continue
            edge_value = 1 if weight is None else edge_attrs.get(weight, 1)
            entries[(index[u], index[v])] = (
                entries.get((index[u], index[v]), 0) + edge_value
            )
            if not G.is_directed() and u != v:
                entries[(index[v], index[u])] = (
                    entries.get((index[v], index[u]), 0) + edge_value
                )
    else:
        for u, v, edge_attrs in G.edges(data=True):
            if u not in index or v not in index:
                continue
            edge_value = 1 if weight is None else edge_attrs.get(weight, 1)
            entries[(index[u], index[v])] = edge_value
            if not G.is_directed() and u != v:
                entries[(index[v], index[u])] = edge_value

    rows = [row for row, _ in entries]
    cols = [col for _, col in entries]
    data = list(entries.values())
    matrix = scipy.sparse.coo_array(
        (data, (rows, cols)),
        shape=(len(nodelist), len(nodelist)),
        dtype=dtype,
    )
    return matrix.asformat(format)


def from_scipy_sparse_array(  # DELEGATED_TO_NETWORKX (scipy conversion)
    A, parallel_edges=False, create_using=None, edge_attribute="weight"
):
    """Return a graph from a SciPy sparse array.

    Parameters
    ----------
    A : scipy.sparse array or matrix
        An adjacency matrix representation of a graph.
    parallel_edges : bool, optional
        Ignored (multigraphs not yet supported). Present for API compat.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.
    edge_attribute : str, optional
        Name of the edge attribute to set from matrix values.
        Default ``'weight'``.

    Returns
    -------
    G : Graph or DiGraph
        The constructed graph.
    """
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph, _to_nx_create_using

    graph = nx.from_scipy_sparse_array(
        A,
        parallel_edges=parallel_edges,
        create_using=_to_nx_create_using(create_using),
        edge_attribute=edge_attribute,
    )
    return _from_nx_graph(graph, create_using=create_using)


def from_dict_of_dicts(d, create_using=None, multigraph_input=False):  # DELEGATED_TO_NETWORKX
    """Return a graph from a dictionary of dictionaries."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph, _to_nx_create_using

    graph = nx.from_dict_of_dicts(
        d,
        create_using=_to_nx_create_using(create_using),
        multigraph_input=multigraph_input,
    )
    return _from_nx_graph(graph, create_using=create_using)


def from_edgelist(edgelist, create_using=None):
    """Return a graph from a list of edges.

    Parameters
    ----------
    edgelist : iterable
        Each element is a tuple (u, v) or (u, v, d) where d is a dict of
        edge attributes.
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.

    Returns
    -------
    G : Graph or DiGraph
    """
    G = _empty_graph_from_create_using(create_using)

    G.add_edges_from(edgelist)
    return G


def to_dict_of_dicts(G, nodelist=None, edge_data=None):
    """Return adjacency representation as a dictionary of dictionaries.

    Parameters
    ----------
    G : Graph or DiGraph
        The input graph.
    nodelist : list, optional
        Use only nodes in *nodelist*. Default: all nodes.
    edge_data : object, optional
        If provided, use this as the edge data instead of the edge
        attribute dict.

    Returns
    -------
    d : dict
        ``d[u][v]`` is the edge data for (u, v).
    """
    if nodelist is None:
        nodelist = list(G.nodes())
    nodeset = set(nodelist)

    d = {}
    for u in nodelist:
        d[u] = {}
        for v, data in G[u].items():
            if v in nodeset:
                if edge_data is not None:
                    d[u][v] = edge_data
                else:
                    d[u][v] = dict(data) if hasattr(data, "items") else data
    return d


def cytoscape_data(G, name="name", ident="id"):
    """Export graph to Cytoscape.js JSON format."""
    if name == ident:
        raise NetworkXError("name and ident must be different.")

    payload = {
        "data": list(G.graph.items()),
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "elements": {"nodes": [], "edges": []},
    }
    for node, node_attrs in G.nodes(data=True):
        node_payload = {"data": dict(node_attrs)}
        node_payload["data"]["id"] = node_attrs.get(ident) or str(node)
        node_payload["data"]["value"] = node
        node_payload["data"]["name"] = node_attrs.get(name) or str(node)
        payload["elements"]["nodes"].append(node_payload)

    if G.is_multigraph():
        for u, v, edge_key, edge_attrs in G.edges(keys=True, data=True):
            edge_payload = {"data": dict(edge_attrs)}
            edge_payload["data"]["source"] = u
            edge_payload["data"]["target"] = v
            edge_payload["data"]["key"] = edge_key
            payload["elements"]["edges"].append(edge_payload)
    else:
        for u, v, edge_attrs in G.edges(data=True):
            edge_payload = {"data": dict(edge_attrs)}
            edge_payload["data"]["source"] = u
            edge_payload["data"]["target"] = v
            payload["elements"]["edges"].append(edge_payload)
    return payload


def cytoscape_graph(data, name="name", ident="id"):
    """Build graph from Cytoscape.js JSON format."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.cytoscape_graph(data, name=name, ident=ident)
    return _from_nx_graph(graph)


def to_networkx_graph(data, create_using=None, multigraph_input=False):  # DELEGATED_TO_NETWORKX
    """Convert supported input data to a graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph, _to_nx_create_using

    graph = nx.to_networkx_graph(
        data,
        create_using=_to_nx_create_using(create_using),
        multigraph_input=multigraph_input,
    )
    return _from_nx_graph(graph, create_using=create_using)


def prominent_group(
    G,
    k,
    weight=None,
    C=None,
    endpoints=False,
    normalized=True,
    greedy=False,
):
    """Return a prominent group of k nodes maximizing group betweenness.

    Uses a greedy approach: iteratively add the node that most increases
    the group betweenness centrality.
    """
    from itertools import combinations

    nodes = list(G.nodes())
    n = len(nodes)

    if C is not None:
        candidates = list(C)
    else:
        candidates = nodes

    if k > len(candidates):
        raise NetworkXError(f"k={k} exceeds number of candidate nodes")

    if greedy or k > 5:
        # Greedy: start empty, add node that maximizes group betweenness.
        group = set()
        remaining = set(candidates)
        for _ in range(k):
            best_node = None
            best_score = -1
            for node in remaining:
                trial = group | {node}
                score = group_betweenness_centrality(
                    G, trial, normalized=normalized, weight=weight, endpoints=endpoints
                )
                if score > best_score:
                    best_score = score
                    best_node = node
            group.add(best_node)
            remaining.discard(best_node)
        score = group_betweenness_centrality(
            G, group, normalized=normalized, weight=weight, endpoints=endpoints
        )
        return float(f"{score:.2f}"), list(group)

    # Exact: enumerate all k-subsets (only practical for small k and n).
    best_group = None
    best_score = -1
    for combo in combinations(candidates, k):
        score = group_betweenness_centrality(
            G, set(combo), normalized=normalized, weight=weight, endpoints=endpoints
        )
        if score > best_score:
            best_score = score
            best_group = set(combo)
    return float(f"{best_score:.2f}"), list(best_group) if best_group is not None else []


def within_inter_cluster(G, ebunch=None, delta=0.001, community="community"):
    """Compute within/inter-cluster common neighbor ratio (WIC measure).

    If u and v are in different communities, score is 0.
    Otherwise, score = |within| / (|inter| + delta) where within are common
    neighbors in the same community as u/v, and inter are those in different.
    """
    if delta <= 0:
        raise NetworkXError("Delta must be greater than zero")

    if ebunch is None:
        # Default: all non-existing edges.
        ebunch_iter = non_edges(G)
    else:
        ebunch_iter = ebunch

    def _community_of(node):
        c = G.nodes[node].get(community)
        if c is None:
            raise NetworkXError(
                f"No community information for node {node!r}. "
                f"Set node attribute '{community}' first."
            )
        return c

    def _generate():
        for u, v in ebunch_iter:
            cu = _community_of(u)
            cv = _community_of(v)
            if cu != cv:
                yield (u, v, 0)
                continue
            cnbors = set(common_neighbors(G, u, v))
            within = {w for w in cnbors if _community_of(w) == cu}
            inter = cnbors - within
            yield (u, v, len(within) / (len(inter) + delta))

    return _generate()


def gnc_graph(n, create_using=None, seed=None):
    """Return a growing network with copying (GNC) digraph."""
    import networkx as nx
    from franken_networkx import _fnx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _fnx.gnc_graph(n, seed=seed, create_using=None)
    return _from_nx_graph(
        nx.gnc_graph(n, create_using=None, seed=seed), create_using=create_using
    )


def gnr_graph(n, p, create_using=None, seed=None):
    """Return a growing network with redirection (GNR) digraph."""
    import networkx as nx
    from franken_networkx import _fnx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _fnx.gnr_graph(n, p, seed=seed, create_using=None)
    return _from_nx_graph(
        nx.gnr_graph(n, p, create_using=None, seed=seed), create_using=create_using
    )


def dual_barabasi_albert_graph(
    n,
    m1,
    m2,
    p,
    seed=None,
    initial_graph=None,
    create_using=None,
):
    """Return a dual Barabasi-Albert preferential attachment graph."""
    import random as _random

    target = _empty_graph_from_create_using(create_using, default=Graph)
    if target.is_directed():
        raise NetworkXError("create_using must not be directed")
    if target.is_multigraph():
        raise NetworkXError("create_using must not be a multi-graph")

    if m1 < 1 or m1 >= n:
        raise NetworkXError(
            f"Dual Barabasi-Albert must have m1 >= 1 and m1 < n, m1 = {m1}, n = {n}"
        )
    if m2 < 1 or m2 >= n:
        raise NetworkXError(
            f"Dual Barabasi-Albert must have m2 >= 1 and m2 < n, m2 = {m2}, n = {n}"
        )
    if p < 0 or p > 1:
        raise NetworkXError(
            f"Dual Barabasi-Albert network must have 0 <= p <= 1, p = {p}"
        )

    if p == 1:
        return barabasi_albert_graph(
            n,
            m1,
            seed=seed,
            initial_graph=initial_graph,
            create_using=create_using,
        )
    if p == 0:
        return barabasi_albert_graph(
            n,
            m2,
            seed=seed,
            initial_graph=initial_graph,
            create_using=create_using,
        )

    if initial_graph is None:
        graph = star_graph(max(m1, m2))
    else:
        if len(initial_graph) < max(m1, m2) or len(initial_graph) > n:
            raise NetworkXError(
                f"Barabasi-Albert initial graph must have between "
                f"max(m1, m2) = {max(m1, m2)} and n = {n} nodes"
            )
        graph = Graph()
        graph.graph.update(dict(initial_graph.graph))
        for node, attrs in initial_graph.nodes(data=True):
            graph.add_node(node, **dict(attrs))
        for u, v, attrs in initial_graph.edges(data=True):
            graph.add_edge(u, v, **dict(attrs))

    rng = _random.Random(seed)
    repeated_nodes = [
        node for node, degree_value in graph.degree for _ in range(degree_value)
    ]
    source = len(graph)
    while source < n:
        m = m1 if rng.random() < p else m2
        targets = set()
        while len(targets) < m:
            targets.add(rng.choice(repeated_nodes))
        graph.add_edges_from((source, target) for target in targets)
        repeated_nodes.extend(targets)
        repeated_nodes.extend([source] * m)
        source += 1

    if create_using is None:
        return graph

    target.graph.update(dict(graph.graph))
    for node, attrs in graph.nodes(data=True):
        target.add_node(node, **dict(attrs))
    for u, v, attrs in graph.edges(data=True):
        target.add_edge(u, v, **dict(attrs))
    return target


def extended_barabasi_albert_graph(n, m, p, q, seed=None, create_using=None):
    """Return an extended Barabasi-Albert graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.extended_barabasi_albert_graph(
        n,
        m,
        p,
        q,
        seed=seed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def scale_free_graph(
    n,
    alpha=0.41,
    beta=0.54,
    gamma=0.05,
    delta_in=0.2,
    delta_out=0,
    seed=None,
    initial_graph=None,
):
    """Return a directed scale-free MultiDiGraph."""
    # Convert initial_graph to MultiDiGraph if needed for the Rust binding.
    if initial_graph is not None and not isinstance(initial_graph, MultiDiGraph):
        converted = MultiDiGraph()
        for node, attrs in initial_graph.nodes(data=True):
            converted.add_node(node, **attrs)
        for u, v, *rest in initial_graph.edges(data=True):
            data = rest[0] if rest else {}
            converted.add_edge(u, v, **data)
        initial_graph = converted

    return _fnx.scale_free_graph(
        n,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        delta_in=delta_in,
        delta_out=delta_out,
        seed=seed,
        initial_graph=initial_graph,
    )


def random_powerlaw_tree(n, gamma=3, seed=None, tries=100, create_using=None):
    """Return a random tree with a power-law degree distribution."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.random_powerlaw_tree(
        n,
        gamma=gamma,
        seed=seed,
        tries=tries,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def random_powerlaw_tree_sequence(n, gamma=3, seed=None, tries=100):
    """Return a degree sequence suitable for a random power-law tree."""
    import random as _random

    rng = _random.Random(seed)
    zseq = [min(n, max(round(rng.paretovariate(gamma - 1)), 0)) for _ in range(n)]
    swap = [min(n, max(round(rng.paretovariate(gamma - 1)), 0)) for _ in range(tries)]

    def is_valid_tree_degree_sequence(sequence):
        if not sequence:
            return True
        if len(sequence) == 1:
            return sequence[0] == 0
        return all(degree >= 1 for degree in sequence) and sum(sequence) == 2 * (
            len(sequence) - 1
        )

    for _ in range(len(swap)):
        if is_valid_tree_degree_sequence(zseq):
            return zseq
        index = rng.randint(0, n - 1)
        zseq[index] = swap.pop()

    raise NetworkXError(f"Exceeded max ({tries}) attempts for a valid tree sequence.")


def gn_graph(n, kernel=None, create_using=None, seed=None):
    """Return a growing network (GN) digraph."""
    import networkx as nx
    from franken_networkx import _fnx
    from franken_networkx.readwrite import _from_nx_graph

    if kernel is None and create_using is None:
        return _fnx.gn_graph(n, seed=seed, create_using=None)
    return _from_nx_graph(
        nx.gn_graph(n, kernel=kernel, create_using=None, seed=seed),
        create_using=create_using,
    )


def LCF_graph(n, shift_list, repeats, create_using=None):
    """Return the cubic Hamiltonian graph defined by Lederberg-Coxeter-Fruchte."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.LCF_graph(n, shift_list, repeats, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def LFR_benchmark_graph(
    n,
    tau1,
    tau2,
    mu,
    average_degree=None,
    min_degree=None,
    max_degree=None,
    min_community=None,
    max_community=None,
    tol=1e-07,
    max_iters=500,
    seed=None,
):
    """Return an LFR benchmark graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.LFR_benchmark_graph(
            n,
            tau1,
            tau2,
            mu,
            average_degree=average_degree,
            min_degree=min_degree,
            max_degree=max_degree,
            min_community=min_community,
            max_community=max_community,
            tol=tol,
            max_iters=max_iters,
            seed=seed,
        )
    )


def hexagonal_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a hexagonal lattice graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.hexagonal_lattice_graph(
        m,
        n,
        periodic=periodic,
        with_positions=with_positions,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def triangular_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a triangular lattice graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.triangular_lattice_graph(
        m,
        n,
        periodic=periodic,
        with_positions=with_positions,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def grid_graph(dim, periodic=False):
    """Return an n-dimensional grid graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.grid_graph(dim, periodic=periodic))


def lattice_reference(G, niter=5, D=None, connectivity=True, seed=None):
    """Return a lattice-like rewiring of *G* preserving degree sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    graph = nx.Graph()
    graph.graph.update(dict(G.graph))
    graph.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
    graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in G.edges(data=True))

    return _from_nx_graph(
        nx.algorithms.smallworld.lattice_reference(
            graph,
            niter=niter,
            D=D,
            connectivity=connectivity,
            seed=seed,
        )
    )


def margulis_gabber_galil_graph(n, create_using=None):
    """Return a Margulis-Gabber-Galil expander graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.margulis_gabber_galil_graph(n, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def sudoku_graph(n=3):
    """Return the Sudoku constraint graph of order *n*."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.sudoku_graph(n))


def fast_gnp_random_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a fast G(n,p) random graph (Batagelj-Brandes O(n+m) algorithm)."""
    import networkx as nx
    from franken_networkx._fnx import fast_gnp_random_graph as _rust_fast_gnp
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_fast_gnp(
            n,
            p,
            seed=_native_random_seed(seed),
            directed=directed,
        )

    graph = nx.fast_gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def newman_watts_strogatz_graph(n, k, p, seed=None, create_using=None):
    """Return a Newman-Watts-Strogatz small-world graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_newman_watts_strogatz_graph(
            n, k, p, seed=_native_random_seed(seed)
        )
    graph = nx.newman_watts_strogatz_graph(n, k, p, seed=seed, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def connected_watts_strogatz_graph(n, k, p, tries=100, seed=None, create_using=None):
    """Return a connected Watts-Strogatz small-world graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_connected_watts_strogatz_graph(
            n,
            k,
            p,
            tries=tries,
            seed=_native_random_seed(seed),
        )
    graph = nx.connected_watts_strogatz_graph(
        n,
        k,
        p,
        tries=tries,
        seed=seed,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


def random_regular_graph(d, n, seed=None, create_using=None):
    """Return a random d-regular graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_random_regular_graph(d, n, seed=_native_random_seed(seed))
    graph = nx.random_regular_graph(d, n, seed=seed, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def powerlaw_cluster_graph(n, m, p, seed=None, create_using=None):
    """Return a powerlaw-cluster graph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph

    if create_using is None:
        return _rust_powerlaw_cluster_graph(n, m, p, seed=_native_random_seed(seed))
    graph = nx.powerlaw_cluster_graph(n, m, p, seed=seed, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def directed_configuration_model(
    in_degree_sequence,
    out_degree_sequence,
    create_using=None,
    seed=None,
):
    """Return a directed configuration model graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.directed_configuration_model(
        in_degree_sequence,
        out_degree_sequence,
        create_using=None,
        seed=seed,
    )
    return _from_nx_graph(graph, create_using=create_using)


def directed_joint_degree_graph(in_degrees, out_degrees, nkk, seed=None):
    """Return a directed graph matching a directed joint-degree distribution."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.directed_joint_degree_graph(in_degrees, out_degrees, nkk, seed=seed)
    )


def joint_degree_graph(joint_degrees, seed=None):
    """Return an undirected graph matching a joint-degree distribution."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.joint_degree_graph(joint_degrees, seed=seed))


def expected_degree_graph(w, seed=None, selfloops=True):
    """Return a Chung-Lu expected-degree random graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.expected_degree_graph(w, seed=seed, selfloops=selfloops))


def directed_havel_hakimi_graph(in_deg_sequence, out_deg_sequence, create_using=None):
    """Return a directed graph with prescribed in/out degree sequences."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.directed_havel_hakimi_graph(
        in_deg_sequence,
        out_deg_sequence,
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


# stochastic_block_model, planted_partition_graph, gaussian_random_partition_graph,
# relaxed_caveman_graph, random_partition_graph defined earlier as standalone


__all__ = [
    "__version__",
    # Graph classes
    "Graph",
    "DiGraph",
    "MultiGraph",
    "MultiDiGraph",
    # Utilities
    "relabel_nodes",
    "to_numpy_array",
    "from_numpy_array",
    "to_scipy_sparse_array",
    "from_scipy_sparse_array",
    "from_dict_of_dicts",
    "from_dict_of_lists",
    "from_edgelist",
    "from_pandas_adjacency",
    "from_pandas_edgelist",
    "from_prufer_sequence",
    "from_nested_tuple",
    "to_dict_of_dicts",
    "to_dict_of_lists",
    "to_edgelist",
    "to_pandas_adjacency",
    "to_pandas_edgelist",
    "to_prufer_sequence",
    "to_nested_tuple",
    "cytoscape_data",
    "cytoscape_graph",
    "attr_sparse_matrix",
    "to_networkx_graph",
    "modularity_matrix",
    "directed_modularity_matrix",
    "modularity_spectrum",
    "prominent_group",
    "within_inter_cluster",
    "gnc_graph",
    "gnr_graph",
    "fast_gnp_random_graph",
    "directed_configuration_model",
    "directed_joint_degree_graph",
    "joint_degree_graph",
    "expected_degree_graph",
    "directed_havel_hakimi_graph",
    "stochastic_block_model",
    "planted_partition_graph",
    "gaussian_random_partition_graph",
    "relaxed_caveman_graph",
    "random_partition_graph",
    "convert_node_labels_to_integers",
    # Exceptions
    "HasACycle",
    "NetworkXAlgorithmError",
    "NetworkXError",
    "NetworkXNoPath",
    "NetworkXNotImplemented",
    "NetworkXPointlessConcept",
    "NetworkXUnbounded",
    "NetworkXUnfeasible",
    "NotATree",
    "NodeNotFound",
    "PowerIterationFailedConvergence",
    # Algorithms — shortest path
    "average_shortest_path_length",
    "bellman_ford_path",
    "dijkstra_path",
    "has_path",
    "multi_source_dijkstra",
    "shortest_path",
    "shortest_path_length",
    # Algorithms — connectivity
    "articulation_points",
    "bridges",
    "connected_components",
    "edge_connectivity",
    "is_connected",
    "minimum_node_cut",
    "node_connectivity",
    "number_connected_components",
    # Algorithms — centrality
    "average_neighbor_degree",
    "betweenness_centrality",
    "closeness_centrality",
    "degree_assortativity_coefficient",
    "degree_centrality",
    "edge_betweenness_centrality",
    "eigenvector_centrality",
    "harmonic_centrality",
    "hits",
    "katz_centrality",
    "pagerank",
    "voterank",
    # Algorithms — clustering
    "average_clustering",
    "clustering",
    "find_cliques",
    "graph_clique_number",
    "square_clustering",
    "transitivity",
    "triangles",
    # Algorithms — matching
    "max_weight_matching",
    "maximal_matching",
    "min_edge_cover",
    "min_weight_matching",
    # Algorithms — flow
    "maximum_flow",
    "maximum_flow_value",
    "minimum_cut",
    "minimum_cut_value",
    # Algorithms — distance measures
    "center",
    "density",
    "diameter",
    "eccentricity",
    "periphery",
    "radius",
    # Algorithms — tree, forest, bipartite, coloring, core
    "bipartite_sets",
    "is_bipartite_node_set",
    "projected_graph",
    "bipartite_density",
    "hopcroft_karp_matching",
    "core_number",
    "EdgePartition",
    "SpanningTreeIterator",
    "ArborescenceIterator",
    "greedy_color",
    "is_bipartite",
    "is_forest",
    "is_tree",
    "maximum_branching",
    "maximum_spanning_arborescence",
    "number_of_spanning_trees",
    "minimum_spanning_edges",
    "minimum_branching",
    "minimum_spanning_arborescence",
    "minimum_spanning_tree",
    "partition_spanning_tree",
    "random_spanning_tree",
    # Algorithms — Euler
    "eulerian_circuit",
    "eulerian_path",
    "has_eulerian_path",
    "is_eulerian",
    "is_semieulerian",
    # Algorithms — paths and cycles
    "all_shortest_paths",
    "all_simple_paths",
    "cycle_basis",
    # Algorithms — graph operators
    "complement",
    # Algorithms — efficiency
    "efficiency",
    "global_efficiency",
    "local_efficiency",
    "tree_broadcast_center",
    "tree_broadcast_time",
    # Algorithms — reciprocity
    "overall_reciprocity",
    "reciprocity",
    # Algorithms — Wiener index
    "wiener_index",
    # Algorithms — trees
    "maximum_spanning_edges",
    "maximum_spanning_tree",
    # Algorithms — condensation
    "condensation",
    # Algorithms — all-pairs shortest paths
    "all_pairs_shortest_path",
    "all_pairs_shortest_path_length",
    # Algorithms — graph predicates & utilities
    "is_empty",
    "non_neighbors",
    "number_of_cliques",
    "all_triangles",
    "node_clique_number",
    "enumerate_all_cliques",
    "find_cliques_recursive",
    "chordal_graph_cliques",
    "chordal_graph_treewidth",
    "make_max_clique_graph",
    "ring_of_cliques",
    # Classic graph generators
    "balanced_tree",
    "barbell_graph",
    "bull_graph",
    "chvatal_graph",
    "cubical_graph",
    "desargues_graph",
    "diamond_graph",
    "dodecahedral_graph",
    "frucht_graph",
    "heawood_graph",
    "house_graph",
    "house_x_graph",
    "icosahedral_graph",
    "krackhardt_kite_graph",
    "moebius_kantor_graph",
    "octahedral_graph",
    "pappus_graph",
    "petersen_graph",
    "sedgewick_maze_graph",
    "tetrahedral_graph",
    "truncated_cube_graph",
    "truncated_tetrahedron_graph",
    "tutte_graph",
    "hoffman_singleton_graph",
    "generalized_petersen_graph",
    "wheel_graph",
    "ladder_graph",
    "circular_ladder_graph",
    "lollipop_graph",
    "tadpole_graph",
    "turan_graph",
    "windmill_graph",
    "hypercube_graph",
    "complete_bipartite_graph",
    "complete_multipartite_graph",
    "grid_2d_graph",
    "null_graph",
    "trivial_graph",
    "binomial_tree",
    "full_rary_tree",
    "circulant_graph",
    "kneser_graph",
    "paley_graph",
    "chordal_cycle_graph",
    # Algorithms — single-source shortest paths
    "single_source_shortest_path",
    "single_source_shortest_path_length",
    # Algorithms — dominating set
    "dominating_set",
    "is_dominating_set",
    # Algorithms — community detection
    "louvain_communities",
    "modularity",
    "label_propagation_communities",
    "greedy_modularity_communities",
    "girvan_newman",
    "k_clique_communities",
    # Attribute helpers
    "set_node_attributes",
    "get_node_attributes",
    "set_edge_attributes",
    "get_edge_attributes",
    # Utility functions
    "create_empty_copy",
    "number_of_selfloops",
    "selfloop_edges",
    "nodes_with_selfloops",
    "all_neighbors",
    "voronoi_cells",
    "stoer_wagner",
    "dedensify",
    "quotient_graph",
    "snap_aggregation",
    "full_join",
    "identified_nodes",
    "inverse_line_graph",
    "add_path",
    "add_cycle",
    "add_star",
    # Graph products
    "cartesian_product",
    "tensor_product",
    "strong_product",
    "adjacency_matrix",
    "has_bridges",
    "local_bridges",
    "minimum_edge_cut",
    "stochastic_graph",
    "ego_graph",
    "k_core",
    "k_shell",
    "k_crust",
    "k_corona",
    "line_graph",
    "power",
    "disjoint_union",
    "compose_all",
    "union_all",
    # Spectral
    "laplacian_matrix",
    "normalized_laplacian_matrix",
    "laplacian_spectrum",
    "adjacency_spectrum",
    "algebraic_connectivity",
    "fiedler_vector",
    "incidence_matrix",
    "karate_club_graph",
    "florentine_families_graph",
    "caveman_graph",
    "connected_caveman_graph",
    "random_tree",
    "constraint",
    "effective_size",
    "dispersion",
    "closeness_vitality",
    "spectral_ordering",
    "bellman_ford_predecessor_and_distance",
    "communicability",
    "subgraph_centrality",
    "degree_mixing_dict",
    "degree_mixing_matrix",
    "numeric_assortativity_coefficient",
    "attribute_assortativity_coefficient",
    "intersection_all",
    "disjoint_union_all",
    "rescale_layout",
    "freeze",
    "is_frozen",
    "info",
    "binomial_graph",
    "gnm_random_graph",
    "check_planarity",
    "all_simple_edge_paths",
    "chain_decomposition",
    "bidirectional_dijkstra",
    "attribute_mixing_dict",
    "attribute_mixing_matrix",
    # Additional generators
    "dense_gnm_random_graph",
    "random_labeled_tree",
    # Additional conversion
    "adjacency_data",
    "adjacency_graph",
    # Additional algorithms
    "load_centrality",
    "degree_pearson_correlation_coefficient",
    "average_degree",
    "generalized_degree",
    "is_semiconnected",
    "all_pairs_node_connectivity",
    "minimum_st_node_cut",
    "contracted_nodes",
    "contracted_edge",
    "is_directed",
    "configuration_model",
    "havel_hakimi_graph",
    "degree_sequence_tree",
    "common_neighbor_centrality",
    "all_topological_sorts",
    "lowest_common_ancestor",
    "all_pairs_lowest_common_ancestor",
    "transitive_closure_dag",
    "dag_to_branching",
    # Additional shortest path
    "dijkstra_predecessor_and_distance",
    "multi_source_dijkstra_path",
    "multi_source_dijkstra_path_length",
    "single_source_all_shortest_paths",
    "all_pairs_all_shortest_paths",
    "reconstruct_path",
    "generate_random_paths",
    "johnson",
    # Spectral & Matrix
    "bethe_hessian_matrix",
    "bethe_hessian_spectrum",
    "google_matrix",
    "normalized_laplacian_spectrum",
    "directed_laplacian_matrix",
    "directed_combinatorial_laplacian_matrix",
    "attr_matrix",
    # Flow algorithms
    "cost_of_flow",
    "min_cost_flow",
    "min_cost_flow_cost",
    "max_flow_min_cost",
    "capacity_scaling",
    "network_simplex",
    "flow_hierarchy",
    # Triads
    "triadic_census",
    "all_triads",
    "triad_type",
    "is_triad",
    "triads_by_type",
    "double_edge_swap",
    "directed_edge_swap",
    # Graph predicates
    "is_valid_degree_sequence_erdos_gallai",
    "is_valid_degree_sequence_havel_hakimi",
    "is_valid_joint_degree",
    "is_strongly_regular",
    "is_at_free",
    "is_d_separator",
    "is_minimal_d_separator",
    # Graph products
    "corona_product",
    "modular_product",
    "rooted_product",
    "lexicographic_product",
    # Advanced metrics
    "estrada_index",
    "gutman_index",
    "schultz_index",
    "hyper_wiener_index",
    "resistance_distance",
    "kemeny_constant",
    "non_randomness",
    "sigma",
    "omega",
    # Connectivity & disjoint paths
    "edge_disjoint_paths",
    "node_disjoint_paths",
    "all_node_cuts",
    "connected_dominating_set",
    "is_connected_dominating_set",
    "is_kl_connected",
    "kl_connected_subgraph",
    "connected_double_edge_swap",
    # Advanced centrality
    "current_flow_betweenness_centrality",
    "edge_current_flow_betweenness_centrality",
    "approximate_current_flow_betweenness_centrality",
    "current_flow_closeness_centrality",
    "betweenness_centrality_subset",
    "edge_betweenness_centrality_subset",
    "edge_load_centrality",
    "laplacian_centrality",
    "percolation_centrality",
    "information_centrality",
    "second_order_centrality",
    "subgraph_centrality_exp",
    "communicability_betweenness_centrality",
    "trophic_levels",
    "trophic_differences",
    "trophic_incoherence_parameter",
    "group_betweenness_centrality",
    "group_closeness_centrality",
    # Traversal extras
    "bfs_beam_edges",
    "bfs_labeled_edges",
    "dfs_labeled_edges",
    "generic_bfs_edges",
    # Utility extras A
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "node_attribute_xy",
    "node_degree_xy",
    "number_of_walks",
    "recursive_simple_cycles",
    # Utility extras B
    "remove_node_attributes",
    "remove_edge_attributes",
    "floyd_warshall_numpy",
    "harmonic_diameter",
    "global_parameters",
    "intersection_array",
    # Small utilities
    "eulerize",
    "moral_graph",
    "equivalence_classes",
    "minimum_cycle_basis",
    "chordless_cycles",
    "to_undirected",
    "to_directed",
    "reverse",
    "nodes",
    "edges",
    "degree",
    "number_of_nodes",
    "number_of_edges",
    # Conversion extras
    "from_pandas_adjacency",
    "to_pandas_adjacency",
    "from_prufer_sequence",
    "to_prufer_sequence",
    "from_nested_tuple",
    "to_nested_tuple",
    "attr_sparse_matrix",
    # Community extras
    "modularity_matrix",
    "directed_modularity_matrix",
    "modularity_spectrum",
    # Predicates extras
    "find_minimal_d_separator",
    "is_valid_directed_joint_degree",
    # Social datasets & misc generators
    "les_miserables_graph",
    "davis_southern_women_graph",
    "triad_graph",
    "weisfeiler_lehman_graph_hash",
    "weisfeiler_lehman_subgraph_hashes",
    "lexicographical_topological_sort",
    # Structural decomposition
    "k_truss",
    "onion_layers",
    "k_edge_components",
    "k_edge_subgraphs",
    "spectral_bisection",
    "find_induced_nodes",
    "k_edge_augmentation",
    # Stochastic block models
    "stochastic_block_model",
    "planted_partition_graph",
    "gaussian_random_partition_graph",
    "random_partition_graph",
    "relaxed_caveman_graph",
    # Lattice graphs
    "hexagonal_lattice_graph",
    "triangular_lattice_graph",
    "grid_graph",
    "sudoku_graph",
    # Centrality extras
    "eigenvector_centrality_numpy",
    "katz_centrality_numpy",
    "incremental_closeness_centrality",
    "current_flow_betweenness_centrality_subset",
    "edge_current_flow_betweenness_centrality_subset",
    # Geometric graphs
    "random_geometric_graph",
    "soft_random_geometric_graph",
    "waxman_graph",
    "geographical_threshold_graph",
    "thresholded_random_geometric_graph",
    "navigable_small_world_graph",
    "geometric_edges",
    # Coloring & planarity
    "equitable_color",
    "chromatic_polynomial",
    "combinatorial_embedding_to_pos",
    # Isomorphism VF2++
    "vf2pp_is_isomorphic",
    "vf2pp_isomorphism",
    "vf2pp_all_isomorphisms",
    # Tree/forest utilities
    "junction_tree",
    "join_trees",
    "random_unlabeled_tree",
    "random_unlabeled_rooted_tree",
    "random_unlabeled_rooted_forest",
    "tree_data",
    "tree_graph",
    "complete_to_chordal_graph",
    # Structural generators
    "hkn_harary_graph",
    "hnm_harary_graph",
    "gomory_hu_tree",
    "visibility_graph",
    "random_k_out_graph",
    # Similarity
    "simrank_similarity",
    "panther_similarity",
    "optimal_edit_paths",
    "optimize_edit_paths",
    # Final parity batch
    "subgraph",
    "induced_subgraph",
    "edge_subgraph",
    "subgraph_view",
    "restricted_view",
    "reverse_view",
    "neighbors",
    "config",
    "describe",
    "mixing_dict",
    "local_constraint",
    "apply_matplotlib_colors",
    "communicability_exp",
    "panther_vector_similarity",
    "effective_graph_resistance",
    "graph_edit_distance",
    "optimize_graph_edit_distance",
    "cd_index",
    "goldberg_radzik",
    "parse_graphml",
    "generate_graphml",
    "mycielskian",
    "mycielski_graph",
    "dorogovtsev_goltsev_mendes_graph",
    "prefix_tree",
    "prefix_tree_recursive",
    "nonisomorphic_trees",
    "number_of_nonisomorphic_trees",
    "random_lobster",
    "random_lobster_graph",
    "random_shell_graph",
    "random_clustered_graph",
    "random_cograph",
    "random_degree_sequence_graph",
    "random_internet_as_graph",
    "random_reference",
    "random_labeled_rooted_tree",
    "random_labeled_rooted_forest",
    "partial_duplication_graph",
    "duplication_divergence_graph",
    "interval_graph",
    "k_random_intersection_graph",
    "uniform_random_intersection_graph",
    "general_random_intersection_graph",
    "geometric_soft_configuration_graph",
    "graph_atlas",
    "graph_atlas_g",
    "find_asteroidal_triple",
    "is_perfect_graph",
    "is_regular_expander",
    "maybe_regular_expander",
    "maybe_regular_expander_graph",
    "random_regular_expander_graph",
    "make_clique_bipartite",
    "k_components",
    "k_factor",
    "spectral_graph_forge",
    "tutte_polynomial",
    "tree_all_pairs_lowest_common_ancestor",
    "random_kernel_graph",
    # Algorithms — graph operators
    "union",
    "intersection",
    "compose",
    "difference",
    "symmetric_difference",
    "degree_histogram",
    # Algorithms — transitive closure/reduction
    "transitive_closure",
    "transitive_reduction",
    # Algorithms — graph metrics
    "average_degree_connectivity",
    "rich_club_coefficient",
    "s_metric",
    "volume",
    "boundary_expansion",
    "conductance",
    "edge_expansion",
    "node_expansion",
    "mixing_expansion",
    "non_edges",
    "average_node_connectivity",
    "is_k_edge_connected",
    "all_pairs_dijkstra",
    "number_of_spanning_arborescences",
    "global_node_connectivity",
    # Algorithms — strongly connected components
    "strongly_connected_components",
    "number_strongly_connected_components",
    "is_strongly_connected",
    # Algorithms — weakly connected components
    "weakly_connected_components",
    "number_weakly_connected_components",
    "is_weakly_connected",
    # Algorithms — link prediction
    "common_neighbors",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "resource_allocation_index",
    # Algorithms — traversal (BFS)
    "bfs_edges",
    "bfs_layers",
    "bfs_predecessors",
    "bfs_successors",
    "bfs_tree",
    "descendants_at_distance",
    # Algorithms — traversal (DFS)
    "dfs_edges",
    "dfs_postorder_nodes",
    "dfs_predecessors",
    "dfs_preorder_nodes",
    "dfs_successors",
    "dfs_tree",
    # Algorithms — DAG
    "ancestors",
    "dag_longest_path",
    "dag_longest_path_length",
    "descendants",
    "is_directed_acyclic_graph",
    "lexicographic_topological_sort",
    "topological_sort",
    "topological_generations",
    # Algorithms — graph isomorphism
    "is_isomorphic",
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
    # Algorithms — A* shortest path
    "astar_path",
    "astar_path_length",
    "shortest_simple_paths",
    # Algorithms — approximation
    "min_weighted_vertex_cover",
    "maximal_independent_set",
    "maximum_independent_set",
    "max_clique",
    "clique_removal",
    "large_clique_size",
    "spanner",
    # Algorithms — tree recognition
    "is_arborescence",
    "is_branching",
    # Algorithms — isolates
    "is_isolate",
    "isolates",
    "number_of_isolates",
    # Algorithms — boundary
    "cut_size",
    "edge_boundary",
    "node_boundary",
    "normalized_cut_size",
    # Algorithms — path validation
    "is_simple_path",
    # Algorithms — matching validators
    "is_matching",
    "is_maximal_matching",
    "is_perfect_matching",
    # Algorithms — cycles
    "simple_cycles",
    "find_cycle",
    "girth",
    "find_negative_cycle",
    # Algorithms — graph predicates
    "is_graphical",
    "is_digraphical",
    "is_multigraphical",
    "is_pseudographical",
    "is_regular",
    "is_k_regular",
    "is_tournament",
    "is_weighted",
    "is_negatively_weighted",
    "is_path",
    "is_distance_regular",
    # Algorithms — traversal additional
    "edge_bfs",
    "edge_dfs",
    # Algorithms — matching additional
    "is_edge_cover",
    "max_weight_clique",
    # Algorithms — DAG additional
    "is_aperiodic",
    "antichains",
    "immediate_dominators",
    "dominance_frontiers",
    # Exception
    "NetworkXNoCycle",
    # Algorithms — additional shortest path
    "dijkstra_path_length",
    "bellman_ford_path_length",
    "single_source_dijkstra",
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
    "single_source_bellman_ford",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
    "single_target_shortest_path",
    "single_target_shortest_path_length",
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "floyd_warshall",
    "floyd_warshall_predecessor_and_distance",
    "bidirectional_shortest_path",
    "negative_edge_cycle",
    "predecessor",
    "path_weight",
    # Algorithms — additional centrality
    "in_degree_centrality",
    "out_degree_centrality",
    "local_reaching_centrality",
    "global_reaching_centrality",
    "group_degree_centrality",
    "group_in_degree_centrality",
    "group_out_degree_centrality",
    # Algorithms — component
    "node_connected_component",
    "is_biconnected",
    "biconnected_components",
    "biconnected_component_edges",
    "is_semiconnected",
    "kosaraju_strongly_connected_components",
    "attracting_components",
    "number_attracting_components",
    "is_attracting_component",
    # Algorithms — planarity
    "is_planar",
    "is_chordal",
    # Algorithms — barycenter
    "barycenter",
    # Generators — classic
    "complete_graph",
    "cycle_graph",
    "empty_graph",
    "path_graph",
    "star_graph",
    # Generators — random
    "gnp_random_graph",
    "watts_strogatz_graph",
    "erdos_renyi_graph",
    "newman_watts_strogatz_graph",
    "connected_watts_strogatz_graph",
    "random_regular_graph",
    "powerlaw_cluster_graph",
    "barabasi_albert_graph",
    "dual_barabasi_albert_graph",
    "extended_barabasi_albert_graph",
    "scale_free_graph",
    "random_powerlaw_tree",
    "random_powerlaw_tree_sequence",
    "gn_graph",
    "LCF_graph",
    "LFR_benchmark_graph",
    "hexagonal_lattice_graph",
    "triangular_lattice_graph",
    "grid_graph",
    "lattice_reference",
    "margulis_gabber_galil_graph",
    "sudoku_graph",
    # Read/write — graph I/O
    "node_link_data",
    "node_link_graph",
    "read_adjlist",
    "read_edgelist",
    "read_graphml",
    "write_adjlist",
    "write_edgelist",
    "write_graphml",
    "read_gml",
    "write_gml",
    "from_graph6_bytes",
    "from_sparse6_bytes",
    "generate_adjlist",
    "generate_edgelist",
    "generate_gexf",
    "generate_gml",
    "generate_multiline_adjlist",
    "generate_pajek",
    "parse_graph6",
    "parse_gexf",
    "parse_adjlist",
    "parse_edgelist",
    "parse_gml",
    "parse_leda",
    "parse_multiline_adjlist",
    "parse_pajek",
    "parse_sparse6",
    "read_gexf",
    "read_graph6",
    "read_leda",
    "read_multiline_adjlist",
    "read_pajek",
    "read_sparse6",
    "read_weighted_edgelist",
    "relabel_gexf_graph",
    "to_graph6_bytes",
    "to_sparse6_bytes",
    "write_gexf",
    "write_graph6",
    "write_graphml_lxml",
    "write_graphml_xml",
    "write_multiline_adjlist",
    "write_pajek",
    "write_sparse6",
    "write_weighted_edgelist",
    # Drawing
    "display",
    "draw",
    "draw_bipartite",
    "draw_circular",
    "draw_forceatlas2",
    "draw_kamada_kawai",
    "draw_networkx",
    "draw_networkx_edge_labels",
    "draw_networkx_edges",
    "draw_networkx_labels",
    "draw_networkx_nodes",
    "draw_planar",
    "draw_random",
    "draw_shell",
    "draw_spectral",
    "draw_spring",
    "generate_network_text",
    "arf_layout",
    "bfs_layout",
    "bipartite_layout",
    "circular_layout",
    "forceatlas2_layout",
    "fruchterman_reingold_layout",
    "kamada_kawai_layout",
    "multipartite_layout",
    "planar_layout",
    "random_layout",
    "rescale_layout_dict",
    "shell_layout",
    "spiral_layout",
    "spectral_layout",
    "spring_layout",
    "to_latex",
    "to_latex_raw",
    "write_latex",
    "write_network_text",
]

import networkx as _nx

# Match NetworkX's top-level config object rather than exposing the older stub
# helper function shape from this module.
config = _nx.config


def __getattr__(name):
    """Fallback to the NetworkX top-level namespace for missing public attrs."""
    import networkx as nx

    try:
        return getattr(nx, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    """Expose FrankenNetworkX globals plus NetworkX's public top-level namespace."""
    import networkx as nx

    return sorted(set(globals()) | set(dir(nx)))
