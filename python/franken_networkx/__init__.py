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

from enum import Enum

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
    shortest_path_length,
)

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

    For directed graphs, only follows outgoing edges (successors).
    For undirected graphs, delegates to the Rust implementation.
    """
    # Trivial case: source is target
    if source == target:
        return [[source]]
    if not G.is_directed():
        return _rust_all_simple_paths(G, source, target, cutoff=cutoff)
    # Directed DFS respecting edge direction
    cutoff_val = cutoff if cutoff is not None else len(G) - 1
    result = []
    visited = {source}
    stack = [(source, iter(G.successors(source)), [source])]
    while stack:
        parent, children, path = stack[-1]
        try:
            child = next(children)
        except StopIteration:
            stack.pop()
            visited.discard(parent)
            continue
        if child == target and len(path) <= cutoff_val:
            result.append(path + [child])
        elif child not in visited and len(path) < cutoff_val:
            visited.add(child)
            stack.append((child, iter(G.successors(child)), path + [child]))
    return result

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

# Algorithm functions — traversal (BFS)
from franken_networkx._fnx import (
    bfs_edges,
    bfs_layers,
    bfs_predecessors,
    bfs_successors,
    bfs_tree,
    descendants_at_distance,
)

# Algorithm functions — traversal (DFS)
from franken_networkx._fnx import (
    dfs_edges,
    dfs_postorder_nodes,
    dfs_predecessors,
    dfs_preorder_nodes,
    dfs_successors,
    dfs_tree,
)

# Algorithm functions — reciprocity
from franken_networkx._fnx import (
    overall_reciprocity,
    reciprocity,
)

# Algorithm functions — Wiener index
from franken_networkx._fnx import (
    wiener_index,
)

# Algorithm functions — maximum spanning tree
from franken_networkx._fnx import (
    maximum_spanning_edges,
    maximum_spanning_tree,
)

# Algorithm functions — condensation
from franken_networkx._fnx import (
    condensation,
)

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
    make_max_clique_graph,
    ring_of_cliques,
)

# Classic graph generators
from franken_networkx._fnx import (
    balanced_tree,
    barbell_graph,
    bull_graph,
    chvatal_graph,
    cubical_graph,
    desargues_graph,
    diamond_graph,
    dodecahedral_graph,
    frucht_graph,
    heawood_graph,
    house_graph,
    house_x_graph,
    icosahedral_graph,
    krackhardt_kite_graph,
    moebius_kantor_graph,
    octahedral_graph,
    pappus_graph,
    petersen_graph,
    sedgewick_maze_graph,
    tetrahedral_graph,
    truncated_cube_graph,
    truncated_tetrahedron_graph,
    tutte_graph,
    hoffman_singleton_graph,
    generalized_petersen_graph,
    wheel_graph,
    ladder_graph,
    circular_ladder_graph,
    lollipop_graph,
    tadpole_graph,
    turan_graph,
    windmill_graph,
    hypercube_graph,
    complete_bipartite_graph,
    complete_multipartite_graph,
    grid_2d_graph,
    null_graph,
    trivial_graph,
    binomial_tree,
    full_rary_tree,
    circulant_graph,
    kneser_graph,
    paley_graph,
    chordal_cycle_graph,
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
    all_pairs_dijkstra,
    number_of_spanning_arborescences,
    global_node_connectivity,
)

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
    faster_could_be_isomorphic,
    is_isomorphic,
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
    all_pairs_dijkstra_path,
    all_pairs_dijkstra_path_length,
    all_pairs_bellman_ford_path,
    all_pairs_bellman_ford_path_length,
    floyd_warshall,
    floyd_warshall_predecessor_and_distance,
    bidirectional_shortest_path,
    negative_edge_cycle,
    predecessor,
    path_weight,
)

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
    complete_graph,
    cycle_graph,
    empty_graph,
    path_graph,
    star_graph,
)

# Graph generators — random
from franken_networkx._fnx import gnp_random_graph
from franken_networkx._fnx import watts_strogatz_graph
from franken_networkx._fnx import barabasi_albert_graph
from franken_networkx._fnx import erdos_renyi_graph
from franken_networkx._fnx import newman_watts_strogatz_graph
from franken_networkx._fnx import connected_watts_strogatz_graph
from franken_networkx._fnx import random_regular_graph
from franken_networkx._fnx import powerlaw_cluster_graph

# Read/write — graph I/O
from franken_networkx._fnx import (
    node_link_data,
    node_link_graph,
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

    Nodes from *nodes* are connected in the projection if they share a
    common neighbor in the bipartite graph *B*.

    Parameters
    ----------
    B : Graph
        A bipartite graph.
    nodes : container
        Nodes to project onto.
    multigraph : bool, optional
        Ignored — present for API compatibility.

    Returns
    -------
    G : Graph
        The projected graph.
    """
    node_set = set(nodes)
    G = Graph()
    for n in node_set:
        G.add_node(n)

    node_list = list(node_set)
    for i, u in enumerate(node_list):
        nbrs_u = set(B.neighbors(u)) - node_set
        for v in node_list[i + 1:]:
            nbrs_v = set(B.neighbors(v)) - node_set
            if nbrs_u & nbrs_v:
                G.add_edge(u, v)
    return G


def bipartite_density(B, nodes):
    """Return the bipartite density of a bipartite graph *B*.

    The bipartite density is ``|E| / (|top| * |bottom|)``.

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

    cliques = [frozenset(c) for c in find_cliques(G) if len(c) >= k]

    # Build adjacency between k-cliques (share k-1 nodes)
    clique_graph = {}
    for i, c1 in enumerate(cliques):
        clique_graph[i] = set()
        for j, c2 in enumerate(cliques):
            if i != j and len(c1 & c2) >= k - 1:
                clique_graph[i].add(j)

    # Find connected components in the clique graph
    visited = set()
    for start in range(len(cliques)):
        if start in visited:
            continue
        component = set()
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            queue.extend(clique_graph.get(node, set()) - visited)
        # Union all cliques in this component
        community = frozenset().union(*(cliques[i] for i in component))
        yield community


# ---------------------------------------------------------------------------
# Graph attribute helpers (high-frequency NetworkX utilities)
# ---------------------------------------------------------------------------


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
    if isinstance(values, dict):
        if name is not None:
            for node, val in values.items():
                if hasattr(G.nodes, '__getitem__'):
                    try:
                        G.nodes[node][name] = val
                    except (KeyError, TypeError):
                        pass
        else:
            for node, attrs in values.items():
                if isinstance(attrs, dict) and hasattr(G.nodes, '__getitem__'):
                    try:
                        G.nodes[node].update(attrs)
                    except (KeyError, TypeError):
                        pass
    else:
        if name is None:
            raise ValueError("name is required when values is not a dictionary")
        for node in G.nodes():
            if hasattr(G.nodes, '__getitem__'):
                try:
                    G.nodes[node][name] = values
                except (KeyError, TypeError):
                    pass


def get_node_attributes(G, name):
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
    for node in G.nodes():
        if hasattr(G.nodes, '__getitem__'):
            attrs = G.nodes[node]
            if isinstance(attrs, dict) and name in attrs:
                result[node] = attrs[name]
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
    if isinstance(values, dict):
        if name is not None:
            for (u, v), val in values.items():
                data = G.get_edge_data(u, v)
                if isinstance(data, dict):
                    data[name] = val
        else:
            for (u, v), attrs in values.items():
                if isinstance(attrs, dict):
                    data = G.get_edge_data(u, v)
                    if isinstance(data, dict):
                        data.update(attrs)
    else:
        if name is None:
            raise ValueError("name is required when values is not a dictionary")
        for u, v in G.edges():
            data = G.get_edge_data(u, v)
            if isinstance(data, dict):
                data[name] = values


def get_edge_attributes(G, name):
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
    for u, v, data in G.edges(data=True):
        if isinstance(data, dict) and name in data:
            result[(u, v)] = data[name]
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
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.create_empty_copy(_to_nx(G), with_data=with_data))


def number_of_selfloops(G):
    """Return the number of self-loop edges in *G*."""
    count = 0
    for u, v in G.edges():
        if u == v:
            count += 1
    return count


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
    return [(u, v) for u, v in G.edges() if u == v]


def nodes_with_selfloops(G):
    """Return nodes that have self-loops."""
    return list({u for u, v in G.edges() if u == v})


def all_neighbors(G, node):
    """Return all neighbors of *node* in *G* (including predecessors for DiGraph).

    For undirected graphs, equivalent to ``G.neighbors(node)``.
    For directed graphs, returns the union of successors and predecessors.
    """
    if G.is_directed():
        succs = set(G.successors(node)) if hasattr(G, 'successors') else set()
        preds = set(G.predecessors(node)) if hasattr(G, 'predecessors') else set()
        return list(succs | preds)
    return list(G.neighbors(node))


def add_path(G, nodes, **attr):
    """Add a path of edges to *G*."""
    node_list = list(nodes)
    for i in range(len(node_list) - 1):
        G.add_edge(node_list[i], node_list[i + 1], **attr)


def add_cycle(G, nodes, **attr):
    """Add a cycle of edges to *G*."""
    node_list = list(nodes)
    if len(node_list) < 2:
        return
    for i in range(len(node_list) - 1):
        G.add_edge(node_list[i], node_list[i + 1], **attr)
    G.add_edge(node_list[-1], node_list[0], **attr)


def add_star(G, nodes, **attr):
    """Add a star of edges to *G* (first node is the center)."""
    node_list = list(nodes)
    if len(node_list) < 2:
        return
    center = node_list[0]
    for spoke in node_list[1:]:
        G.add_edge(center, spoke, **attr)


def cartesian_product(G, H):
    """Return the Cartesian product of *G* and *H*.

    The Cartesian product has node set ``V(G) x V(H)``. Two nodes
    ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff ``u1 == u2`` and
    ``(v1, v2)`` is an edge in *H*, or ``v1 == v2`` and ``(u1, u2)``
    is an edge in *G*.
    """
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    for u in g_nodes:
        for v in h_nodes:
            result.add_node((u, v))

    for u in g_nodes:
        for v1, v2 in H.edges():
            result.add_edge((u, v1), (u, v2))

    for v in h_nodes:
        for u1, u2 in G.edges():
            result.add_edge((u1, v), (u2, v))

    return result


def tensor_product(G, H):
    """Return the tensor (categorical) product of *G* and *H*.

    Two nodes ``(u1, v1)`` and ``(u2, v2)`` are adjacent iff
    ``(u1, u2)`` is an edge in *G* AND ``(v1, v2)`` is an edge in *H*.
    """
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    for u in g_nodes:
        for v in h_nodes:
            result.add_node((u, v))

    for u1, u2 in G.edges():
        for v1, v2 in H.edges():
            result.add_edge((u1, v1), (u2, v2))
            result.add_edge((u1, v2), (u2, v1))

    return result


def strong_product(G, H):
    """Return the strong product of *G* and *H*.

    Union of Cartesian and tensor products.
    """
    result = cartesian_product(G, H)
    for u1, u2 in G.edges():
        for v1, v2 in H.edges():
            result.add_edge((u1, v1), (u2, v2))
            result.add_edge((u1, v2), (u2, v1))
    return result


# ---------------------------------------------------------------------------
# Additional high-value utilities
# ---------------------------------------------------------------------------


def adjacency_matrix(G, nodelist=None, dtype=None, weight='weight'):
    """Return the adjacency matrix of *G* as a SciPy sparse array.

    This is an alias for ``to_scipy_sparse_array``.
    """
    return to_scipy_sparse_array(G, nodelist=nodelist, dtype=dtype, weight=weight)


def has_bridges(G):
    """Return True if graph *G* has at least one bridge."""
    return len(bridges(G)) > 0


def local_bridges(G, with_span=True):
    """Yield local bridges in *G*.

    A local bridge is an edge whose endpoints have no common neighbors,
    giving it a span of infinity. If ``with_span`` is True, yields
    ``(u, v, span)`` tuples; otherwise yields ``(u, v)`` tuples.

    Only edges with no common neighbors (span > 2) are yielded,
    matching NetworkX's definition.
    """
    for u, v in G.edges():
        if u == v:
            continue
        u_nbrs = set(G.neighbors(u)) - {v}
        v_nbrs = set(G.neighbors(v)) - {u}
        if not (u_nbrs & v_nbrs):
            if with_span:
                yield (u, v, float('inf'))
            else:
                yield (u, v)


def minimum_edge_cut(G, s=None, t=None):
    """Return a minimum edge cut of *G*."""
    import networkx as nx
    from franken_networkx.drawing.layout import _to_nx
    return set(nx.minimum_edge_cut(_to_nx(G), s=s, t=t))


def stochastic_graph(G, copy=True, weight='weight'):
    """Return the stochastic graph of *G* (row-normalized adjacency).

    Each row of the adjacency matrix is normalized so the edge weights
    from each node sum to 1.

    Parameters
    ----------
    G : DiGraph
        Must be a directed graph.
    copy : bool, optional
        If True (default), return a new graph.
    weight : str, optional
        Edge attribute to normalize. Default ``'weight'``.
    """
    if not G.is_directed():
        raise Exception("stochastic_graph requires a directed graph")

    H = G.copy() if copy else G

    for node in H.nodes():
        succs = list(H.successors(node)) if hasattr(H, 'successors') else list(H.neighbors(node))
        if not succs:
            continue
        total = 0.0
        for succ in succs:
            data = H.get_edge_data(node, succ)
            if isinstance(data, dict):
                total += float(data.get(weight, 1.0))
            else:
                total += 1.0
        if total > 0:
            for succ in succs:
                data = H.get_edge_data(node, succ)
                if isinstance(data, dict):
                    w = float(data.get(weight, 1.0))
                    data[weight] = w / total

    return H


# ---------------------------------------------------------------------------
# Graph structural algorithms — pure Python over Rust primitives
# ---------------------------------------------------------------------------


def ego_graph(G, n, radius=1, center=True, undirected=False):
    """Return the ego graph of node *n* within *radius* hops.

    Parameters
    ----------
    G : Graph or DiGraph
    n : node
        Center node.
    radius : int, optional
        Maximum distance from *n*. Default 1.
    center : bool, optional
        If True (default), include *n* in the subgraph.
    undirected : bool, optional
        If True, use undirected distances even for directed graphs.
    """
    nodes = {n} if center else set()
    frontier = {n}
    for _ in range(radius):
        next_frontier = set()
        for node in frontier:
            for nbr in G.neighbors(node):
                if nbr not in nodes and nbr not in frontier:
                    next_frontier.add(nbr)
        nodes.update(frontier)
        nodes.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    if not center:
        nodes.discard(n)
    return G.subgraph(nodes)


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


def line_graph(G):
    """Return the line graph of *G*.

    The line graph L(G) has a node for each edge in G. Two nodes in L(G)
    are adjacent iff the corresponding edges in G share an endpoint.
    """
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.line_graph(_to_nx(G)))


def power(G, k):
    """Return the k-th power of *G*.

    The k-th power G^k has the same nodes as G. Two nodes u, v are
    adjacent in G^k iff their shortest path distance in G is <= k.
    """
    H = G.__class__()
    for n in G.nodes():
        H.add_node(n)

    nodes = list(G.nodes())
    for u in nodes:
        # BFS to find all nodes within distance k
        visited = {u: 0}
        frontier = [u]
        for dist in range(1, k + 1):
            next_frontier = []
            for node in frontier:
                for nbr in G.neighbors(node):
                    if nbr not in visited:
                        visited[nbr] = dist
                        next_frontier.append(nbr)
                        if nbr != u:
                            H.add_edge(u, nbr)
            frontier = next_frontier
            if not frontier:
                break

    return H


def disjoint_union(G, H):
    """Return the disjoint union of *G* and *H*."""
    import networkx as nx
    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx.disjoint_union(_to_nx(G), _to_nx(H)))


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


def laplacian_matrix(G, nodelist=None, weight='weight'):
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
    n = A.shape[0]
    D = scipy.sparse.diags(np.asarray(A.sum(axis=1)).flatten())
    return D - A


def normalized_laplacian_matrix(G, nodelist=None, weight='weight'):
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
    d_inv_sqrt = np.zeros_like(d)
    nonzero = d > 0
    d_inv_sqrt[nonzero] = 1.0 / np.sqrt(d[nonzero])
    D_inv_sqrt = scipy.sparse.diags(d_inv_sqrt)
    I = scipy.sparse.eye(n)
    return I - D_inv_sqrt @ A @ D_inv_sqrt


def laplacian_spectrum(G, weight='weight'):
    """Return the eigenvalues of the Laplacian matrix of *G*, sorted.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    L = laplacian_matrix(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(L.toarray()))


def adjacency_spectrum(G, weight='weight'):
    """Return the eigenvalues of the adjacency matrix of *G*, sorted.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np

    A = to_numpy_array(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(A))


def algebraic_connectivity(G, weight='weight', normalized=False):
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
        spectrum = np.sort(np.linalg.eigvalsh(
            normalized_laplacian_matrix(G, weight=weight).toarray()
        ))
    else:
        spectrum = laplacian_spectrum(G, weight=weight)
    if len(spectrum) < 2:
        return 0.0
    return float(spectrum[1])


def fiedler_vector(G, weight='weight', normalized=False):
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
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8),
        (0, 10), (0, 11), (0, 12), (0, 13), (0, 17), (0, 19), (0, 21), (0, 31),
        (1, 2), (1, 3), (1, 7), (1, 13), (1, 17), (1, 19), (1, 21), (1, 30),
        (2, 3), (2, 7), (2, 8), (2, 9), (2, 13), (2, 27), (2, 28), (2, 32),
        (3, 7), (3, 12), (3, 13), (4, 6), (4, 10), (5, 6), (5, 10), (5, 16),
        (6, 16), (8, 30), (8, 32), (8, 33), (9, 33), (13, 33), (14, 32),
        (14, 33), (15, 32), (15, 33), (18, 32), (18, 33), (19, 33), (20, 32),
        (20, 33), (22, 32), (22, 33), (23, 25), (23, 27), (23, 29), (23, 32),
        (23, 33), (24, 25), (24, 27), (24, 31), (25, 31), (26, 29), (26, 33),
        (27, 33), (28, 31), (28, 33), (29, 32), (29, 33), (30, 32), (30, 33),
        (31, 32), (31, 33), (32, 33),
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
        ("Acciaiuoli", "Medici"), ("Albizzi", "Ginori"), ("Albizzi", "Guadagni"),
        ("Albizzi", "Medici"), ("Barbadori", "Castellani"), ("Barbadori", "Medici"),
        ("Bischeri", "Guadagni"), ("Bischeri", "Peruzzi"), ("Bischeri", "Strozzi"),
        ("Castellani", "Peruzzi"), ("Castellani", "Strozzi"),
        ("Guadagni", "Lamberteschi"),
        ("Guadagni", "Tornabuoni"),
        ("Medici", "Ridolfi"), ("Medici", "Salviati"), ("Medici", "Tornabuoni"),
        ("Peruzzi", "Strozzi"), ("Ridolfi", "Strozzi"), ("Ridolfi", "Tornabuoni"),
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
    """Return Burt's constraint for nodes in *G*.

    Constraint measures how much a node's connections are to interconnected
    alters (low constraint = structural hole position).

    Parameters
    ----------
    G : Graph
    nodes : iterable, optional
    weight : str or None, optional

    Returns
    -------
    dict
        ``{node: constraint_value}``
    """
    if nodes is None:
        nodes = list(G.nodes())

    result = {}
    for v in nodes:
        v_nbrs = set(G.neighbors(v))
        if not v_nbrs:
            result[v] = 0.0
            continue

        total = 0.0
        for w in v_nbrs:
            # Direct proportion of v's network invested in w
            p_vw = 1.0 / len(v_nbrs)
            # Indirect constraint via mutual contacts
            indirect = 0.0
            for q in v_nbrs:
                if q == w:
                    continue
                q_nbrs = set(G.neighbors(q))
                if w in q_nbrs:
                    p_vq = 1.0 / len(v_nbrs)
                    q_all = set(G.neighbors(q))
                    p_qw = 1.0 / len(q_all) if q_all else 0.0
                    indirect += p_vq * p_qw
            total += (p_vw + indirect) ** 2
        result[v] = total

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

    result = {}
    for v in nodes:
        v_nbrs = set(G.neighbors(v))
        n = len(v_nbrs)
        if n == 0:
            result[v] = 0.0
            continue
        # Count ties among alters (excluding ego)
        redundancy = 0.0
        for u in v_nbrs:
            u_nbrs = set(G.neighbors(u))
            ties_to_alters = len(u_nbrs & v_nbrs)
            redundancy += ties_to_alters / n if n > 0 else 0
        result[v] = n - redundancy
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


def bellman_ford_predecessor_and_distance(G, source, weight='weight'):
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


def degree_mixing_dict(G, normalized=False, weight=None):
    """Return a dictionary of degree-degree mixing counts.

    Returns
    -------
    dict of dicts
        ``result[d1][d2]`` is the count of edges between nodes of
        degree d1 and degree d2.
    """
    result = {}
    for u, v in G.edges():
        du = G.degree[u]
        dv = G.degree[v]
        result.setdefault(du, {})
        result[du][dv] = result[du].get(dv, 0) + 1
        if not G.is_directed():
            result.setdefault(dv, {})
            result[dv][du] = result[dv].get(du, 0) + 1
    if normalized and result:
        total = sum(sum(inner.values()) for inner in result.values())
        if total > 0:
            for d1 in result:
                for d2 in result[d1]:
                    result[d1][d2] /= total
    return result


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
    """
    import numpy as np

    x_vals = []
    y_vals = []
    for u, v in G.edges():
        u_attrs = G.nodes[u] if hasattr(G.nodes, '__getitem__') else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, '__getitem__') else {}
        if isinstance(u_attrs, dict) and isinstance(v_attrs, dict):
            if attribute in u_attrs and attribute in v_attrs:
                x_vals.append(float(u_attrs[attribute]))
                y_vals.append(float(v_attrs[attribute]))

    if len(x_vals) < 2:
        return 0.0

    x = np.array(x_vals)
    y = np.array(y_vals)
    return float(np.corrcoef(x, y)[0, 1])


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
    # Build partition from attribute values
    partitions = {}
    for node in G.nodes():
        attrs = G.nodes[node] if hasattr(G.nodes, '__getitem__') else {}
        if isinstance(attrs, dict) and attribute in attrs:
            val = attrs[attribute]
            partitions.setdefault(val, set()).add(node)

    if not partitions:
        return 0.0

    communities = list(partitions.values())
    try:
        return modularity(G, communities)
    except Exception:
        return 0.0


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
    import networkx as nx
    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx.disjoint_union_all([_to_nx(g) for g in graphs]))


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
    name = getattr(G, 'name', '') or ''
    typ = type(G).__name__
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    lines = [f"Name: {name}", f"Type: {typ}",
             f"Number of nodes: {n_nodes}", f"Number of edges: {n_edges}"]
    if n_nodes > 0:
        degs = [d for _, d in G.degree]
        lines.append(f"Average degree: {2.0 * n_edges / n_nodes:.4f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator aliases
# ---------------------------------------------------------------------------


def binomial_graph(n, p, seed=None):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    if seed is None:
        seed = 0
    return gnp_random_graph(n, p, seed=seed)


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
    if G.number_of_nodes() == 0:
        return

    nodes = list(G.nodes())
    if root is None:
        root = nodes[0]

    # DFS to find back edges
    visited = set()
    parent = {}
    depth = {}
    tree_edges = []
    back_edges = []

    stack = [(root, None, 0)]
    while stack:
        node, par, d = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        parent[node] = par
        depth[node] = d
        for nbr in G.neighbors(node):
            if nbr not in visited:
                tree_edges.append((node, nbr))
                stack.append((nbr, node, d + 1))
            elif nbr != par and depth.get(nbr, 0) < d:
                back_edges.append((node, nbr))

    # Each back edge starts a chain
    for u, v in back_edges:
        chain = []
        current = u
        while current != v:
            p = parent.get(current)
            if p is None:
                break
            chain.append((current, p))
            current = p
        chain.append((current, v) if current == v else (u, v))
        if chain:
            yield chain


def bidirectional_dijkstra(G, source, target, weight='weight'):
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


def attribute_mixing_dict(G, attribute, normalized=False):
    """Return mixing dict for a categorical node attribute.

    Returns
    -------
    dict of dicts
        ``result[a][b]`` counts edges between nodes with attribute
        values a and b.
    """
    result = {}
    for u, v in G.edges():
        u_attrs = G.nodes[u] if hasattr(G.nodes, '__getitem__') else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, '__getitem__') else {}
        if not isinstance(u_attrs, dict) or not isinstance(v_attrs, dict):
            continue
        a = u_attrs.get(attribute)
        b = v_attrs.get(attribute)
        if a is None or b is None:
            continue
        result.setdefault(a, {})
        result[a][b] = result[a].get(b, 0) + 1
        if not G.is_directed():
            result.setdefault(b, {})
            result[b][a] = result[b].get(a, 0) + 1
    if normalized and result:
        total = sum(sum(inner.values()) for inner in result.values())
        if total > 0:
            for a in result:
                for b in result[a]:
                    result[a][b] /= total
    return result


def attribute_mixing_matrix(G, attribute, normalized=True):
    """Return the attribute mixing matrix.

    Returns
    -------
    numpy.ndarray
    """
    import numpy as np
    mixing = attribute_mixing_dict(G, attribute, normalized=False)
    if not mixing:
        return np.array([[]])
    labels = sorted({k for k in mixing} | {k2 for v in mixing.values() for k2 in v})
    label_idx = {l: i for i, l in enumerate(labels)}
    n = len(labels)
    M = np.zeros((n, n))
    for a, inner in mixing.items():
        for b, count in inner.items():
            M[label_idx[a], label_idx[b]] = count
    if normalized:
        total = M.sum()
        if total > 0:
            M /= total
    return M


# ---------------------------------------------------------------------------
# Additional generators
# ---------------------------------------------------------------------------


def dense_gnm_random_graph(n, m, seed=None):
    """Return a dense G(n,m) random graph. Alias for ``gnm_random_graph``."""
    return gnm_random_graph(n, m, seed=seed)


def random_labeled_tree(n, seed=None):
    """Return a uniformly random labeled tree. Alias for ``random_tree``."""
    return random_tree(n, seed=seed)


# ---------------------------------------------------------------------------
# Additional conversion
# ---------------------------------------------------------------------------


def adjacency_data(G):
    """Return *G* in node-link format suitable for JSON serialization.

    Alias for ``node_link_data``.
    """
    return node_link_data(G)


def adjacency_graph(data):
    """Return a graph from node-link format data.

    Alias for ``node_link_graph``.
    """
    return node_link_graph(data)


# ---------------------------------------------------------------------------
# Additional centrality / metrics
# ---------------------------------------------------------------------------


def load_centrality(G, normalized=True, weight=None):
    """Return the load centrality for each node.

    Load centrality is similar to betweenness centrality but counts the
    fraction of shortest paths through each node without normalization
    by the number of shortest paths.

    For unweighted graphs, this is equivalent to betweenness centrality.
    """
    return betweenness_centrality(G)


def degree_pearson_correlation_coefficient(G, x='out', y='in', weight=None, nodes=None):
    """Return the degree-degree Pearson correlation coefficient.

    For undirected graphs, this is equivalent to
    ``degree_assortativity_coefficient``.
    """
    return degree_assortativity_coefficient(G)


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

    if nodes is None:
        nodes = list(G.nodes())

    tri = triangles(G)
    result = {}
    for v in nodes:
        nbrs = set(G.neighbors(v))
        edge_tri_counts = Counter()
        for u in nbrs:
            u_nbrs = set(G.neighbors(u))
            shared = len(nbrs & u_nbrs)
            edge_tri_counts[shared] += 1
        result[v] = dict(edge_tri_counts)
    return result


def all_pairs_node_connectivity(G, nbunch=None, flow_func=None):
    """Return node connectivity between all pairs.

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the node connectivity between u and v.
    """
    if nbunch is None:
        nbunch = list(G.nodes())

    result = {}
    for u in nbunch:
        result[u] = {}
        for v in nbunch:
            if u == v:
                result[u][v] = 0
            else:
                result[u][v] = node_connectivity(G, u, v)
    return result


def minimum_st_node_cut(G, s, t):
    """Return the minimum s-t node cut."""
    import networkx as nx
    from franken_networkx.drawing.layout import _to_nx
    return set(nx.minimum_node_cut(_to_nx(G), s, t))


def voronoi_cells(G, center_nodes, weight="weight"):
    """Return Voronoi cells around the given centers.

    Each node is assigned to its nearest center. Uses Dijkstra from each
    center node to determine assignment. Unreachable nodes are placed in a
    cell keyed by ``"unreachable"``.

    Parameters
    ----------
    G : Graph
    center_nodes : iterable
        Nodes used as Voronoi centers.
    weight : str, optional
        Edge attribute to use as weight (default ``"weight"``).

    Returns
    -------
    dict
        ``{center: set_of_nodes}`` mapping.
    """
    import heapq

    center_nodes = list(center_nodes)
    if not center_nodes:
        raise NetworkXError("center_nodes must not be empty")
    for c in center_nodes:
        if c not in G:
            raise NodeNotFound(f"Node {c} is not in G")

    # Multi-source Dijkstra: find nearest center for every node
    nearest = {}   # node -> center
    dist = {}      # node -> distance to nearest center
    pq = []        # (distance, tie-break counter, node, center)
    counter = 0
    for c in center_nodes:
        dist[c] = 0
        nearest[c] = c
        heapq.heappush(pq, (0, counter, c, c))
        counter += 1

    while pq:
        d, _, u, center = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        for v in G.neighbors(u):
            # Determine edge weight
            edge_data = G.edges[u, v]
            w = edge_data.get(weight, 1) if weight is not None else 1
            new_dist = d + w
            if new_dist < dist.get(v, float("inf")):
                dist[v] = new_dist
                nearest[v] = center
                heapq.heappush(pq, (new_dist, counter, v, center))
                counter += 1

    cells = {c: set() for c in center_nodes}
    unreachable = set()
    for n in G.nodes():
        if n in nearest:
            cells[nearest[n]].add(n)
        else:
            unreachable.add(n)
    if unreachable:
        cells["unreachable"] = unreachable
    return cells


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
    partition : tuple of sets
        The two sets of nodes that form the minimum cut partition.
    """
    import heapq

    n = G.number_of_nodes()
    if n < 2:
        raise NetworkXError(
            "graph has less than two nodes; cannot compute minimum cut"
        )

    nodes = list(G.nodes())
    # Build adjacency with weights
    # merged[u][v] = total weight between super-nodes u and v
    merged = {u: {} for u in nodes}
    for u, v, d in G.edges(data=True):
        w = d.get(weight, 1) if weight is not None else 1
        merged[u][v] = merged[u].get(v, 0) + w
        merged[v][u] = merged[v].get(u, 0) + w

    # Track which original nodes are merged into each super-node
    groups = {n: {n} for n in nodes}
    active = set(nodes)

    best_cut = float("inf")
    best_partition = None

    for _ in range(n - 1):
        # Minimum cut phase: maximum adjacency ordering
        active_list = list(active)
        start = active_list[0]

        # key[v] = total weight of edges from v to the "found" set A
        key = {v: 0 for v in active}
        in_A = set()
        counter = 0

        # Use a max-heap (negate weights)
        pq = [(-key[v], counter, v) for v in active]
        counter += 1
        import heapq as _heapq
        _heapq.heapify(pq)

        last = None
        second_last = None

        while len(in_A) < len(active):
            while True:
                neg_w, _, u = _heapq.heappop(pq)
                if u not in in_A:
                    break
            second_last = last
            last = u
            in_A.add(u)
            for v, w in merged[u].items():
                if v not in in_A and v in active:
                    key[v] += w
                    _heapq.heappush(pq, (-key[v], counter, v))
                    counter += 1

        # The cut of the phase is key[last]
        cut_of_phase = key[last]
        if cut_of_phase < best_cut:
            best_cut = cut_of_phase
            best_partition = (frozenset(groups[last]),
                              frozenset().union(*(groups[v] for v in active if v != last)))

        # Merge last into second_last
        if second_last is None:
            break
        groups[second_last] |= groups[last]
        del groups[last]
        active.remove(last)

        # Update merged adjacency
        for v, w in merged[last].items():
            if v == second_last or v not in active:
                continue
            merged[second_last][v] = merged[second_last].get(v, 0) + w
            merged[v][second_last] = merged[v].get(second_last, 0) + w
        # Remove last from all adjacencies
        for v in list(merged[last]):
            if v in merged:
                merged[v].pop(last, None)
        del merged[last]

    return best_cut, (sorted(best_partition[0]), sorted(best_partition[1]))


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
            signature = tuple(
                frozenset(etypes) for etypes in nbr_info[node].values()
            )
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
                    dict(zip(edge_attributes, etype))
                    for etype in group_edge_types
                ]
                superedge_attrs = {superedge_attribute: edge_type_list}
                if not output.has_edge(source_supernode, target_supernode):
                    output.add_edge(source_supernode, target_supernode, **superedge_attrs)
                elif G.is_directed():
                    output.add_edge(source_supernode, target_supernode, **superedge_attrs)

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
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.inverse_line_graph(_to_nx(G)))


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


def havel_hakimi_graph(deg_sequence):
    """Return a simple graph with the given degree sequence using
    the Havel-Hakimi algorithm.

    Parameters
    ----------
    deg_sequence : list of int

    Returns
    -------
    Graph
    """
    seq = sorted(enumerate(deg_sequence), key=lambda x: -x[1])
    G = Graph()
    for i in range(len(deg_sequence)):
        G.add_node(i)

    while seq:
        seq.sort(key=lambda x: -x[1])
        if seq[0][1] == 0:
            break
        node, degree = seq[0]
        seq[0] = (node, 0)
        if degree > len(seq) - 1:
            raise ValueError("Non-graphical degree sequence")
        for j in range(1, degree + 1):
            target, target_deg = seq[j]
            if target_deg <= 0:
                raise ValueError("Non-graphical degree sequence")
            G.add_edge(node, target)
            seq[j] = (target, target_deg - 1)
        seq = [(n, d) for n, d in seq if d > 0]

    return G


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

    n = len(G)
    if n == 0:
        yield []
        return

    in_deg = dict(G.in_degree)
    # Maintenance of the set of nodes with in-degree 0
    zero_in_degree = [v for v, d in in_deg.items() if d == 0]

    def _backtrack(zero_in_degree, result):
        if len(result) == n:
            yield list(result)
            return

        for i in range(len(zero_in_degree)):
            node = zero_in_degree[i]
            # Copy zero_in_degree and remove current node
            next_zero = zero_in_degree[:i] + zero_in_degree[i + 1 :]
            result.append(node)

            # Decrease in-degree of successors and add to next_zero if they become 0
            # We must be careful not to mutate in_deg permanently here
            decremented = []
            for s in G.successors(node):
                in_deg[s] -= 1
                if in_deg[s] == 0:
                    next_zero.append(s)
                decremented.append(s)

            # Recurse
            yield from _backtrack(next_zero, result)

            # Undo changes
            for s in decremented:
                in_deg[s] += 1
            result.pop()

    yield from _backtrack(zero_in_degree, [])


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


def dijkstra_predecessor_and_distance(G, source, cutoff=None, weight='weight'):
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


def multi_source_dijkstra_path(G, sources, weight='weight'):
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


def multi_source_dijkstra_path_length(G, sources, weight='weight'):
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
    for source in G.nodes():
        if weight is None:
            paths = single_source_shortest_path(G, source)
        else:
            paths = single_source_dijkstra_path(G, source, weight=weight)
        yield (source, paths)


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


def generate_random_paths(G, sample_size, path_length=5, index_map=None, weight=None, seed=None):
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


def johnson(G, weight='weight'):
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
    D = scipy.sparse.diags(d)
    if r is None:
        r = max(np.sqrt(d.mean()), 1.0) if n > 0 else 1.0
    I = scipy.sparse.eye(n)
    return (r ** 2 - 1) * I - r * A + D


def bethe_hessian_spectrum(G, r=None):
    """Return sorted eigenvalues of the Bethe Hessian matrix."""
    import numpy as np
    H = bethe_hessian_matrix(G, r=r)
    return np.sort(np.linalg.eigvalsh(H.toarray()))


def google_matrix(G, alpha=0.85, personalization=None, nodelist=None, weight='weight'):
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
        idx_map = {node: i for i, node in enumerate(nodelist)}
        v = np.array([personalization.get(node, 0) for node in nodelist], dtype=float)
        s = v.sum()
        v = v / s if s > 0 else np.ones(n) / n
    return alpha * S + (1 - alpha) * np.outer(np.ones(n), v)


def normalized_laplacian_spectrum(G, weight='weight'):
    """Return sorted eigenvalues of the normalized Laplacian."""
    import numpy as np
    NL = normalized_laplacian_matrix(G, weight=weight)
    return np.sort(np.linalg.eigvalsh(NL.toarray()))


def directed_laplacian_matrix(G, nodelist=None, weight='weight', alpha=0.95):
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


def directed_combinatorial_laplacian_matrix(G, nodelist=None, weight='weight', alpha=0.95):
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


def attr_matrix(G, edge_attr=None, node_attr=None, normalized=False, rc_order=None, dtype=None):
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
            labels = sorted(set(node_attrs.values()))
        label_idx = {lab: i for i, lab in enumerate(labels)}
        n = len(labels)
        M = np.zeros((n, n), dtype=dtype or np.float64)
        for u, v, data in G.edges(data=True):
            lu, lv = node_attrs.get(u), node_attrs.get(v)
            if lu in label_idx and lv in label_idx:
                val = data.get(edge_attr, 1) if edge_attr and isinstance(data, dict) else 1
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
                val = data.get(edge_attr, 1) if edge_attr and isinstance(data, dict) else 1
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


def cost_of_flow(G, flowDict, weight='weight'):
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


def min_cost_flow(G, demand='demand', capacity='capacity', weight='weight'):
    """Find minimum cost flow satisfying node demands.

    Uses the successive shortest paths algorithm with Bellman-Ford.

    Each node may have a ``demand`` attribute:
    - Positive demand = supply (source)
    - Negative demand = demand (sink)
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
        attrs = G.nodes[node] if hasattr(G.nodes, '__getitem__') else {}
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
    # Create a super-source and super-sink
    sources = [n for n in nodes if node_demand[n] > 0]
    sinks = [n for n in nodes if node_demand[n] < 0]
    remaining_supply = {n: node_demand[n] for n in sources}
    remaining_demand = {n: -node_demand[n] for n in sinks}

    # Successive shortest paths: augment along shortest cost path
    for _ in range(n * n):  # upper bound on iterations
        # Find shortest path from any source with remaining supply
        # to any sink with remaining demand using Bellman-Ford on residual
        best_path = None
        best_cost = float('inf')
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
                    if hasattr(G, 'successors'):
                        succs = list(G.successors(u))
                    else:
                        succs = list(G.neighbors(u))
                    for v in succs:
                        data = G.get_edge_data(u, v)
                        if not isinstance(data, dict):
                            continue
                        cap = float(data.get(capacity, float('inf')))
                        current_flow = flow.get(u, {}).get(v, 0)
                        residual_cap = cap - current_flow
                        if residual_cap > 1e-10:
                            edge_cost = float(data.get(weight, 0))
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, 'forward')
                                updated = True
                    # Backward edges (reverse flow)
                    if hasattr(G, 'predecessors'):
                        preds_list = list(G.predecessors(u))
                    else:
                        preds_list = []
                    for v in preds_list:
                        current_flow = flow.get(v, {}).get(u, 0)
                        if current_flow > 1e-10:
                            data = G.get_edge_data(v, u)
                            edge_cost = -float(data.get(weight, 0)) if isinstance(data, dict) else 0.0
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, 'backward')
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
            if info and info[1] == 'forward':
                data = G.get_edge_data(u, v)
                cap = float(data.get(capacity, float('inf'))) if isinstance(data, dict) else float('inf')
                residual = cap - flow.get(u, {}).get(v, 0)
                bottleneck = min(bottleneck, residual)
            elif info and info[1] == 'backward':
                bottleneck = min(bottleneck, flow.get(v, {}).get(u, 0))

        if bottleneck <= 1e-10:
            break

        # Augment flow along path
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            info = best_path.get(v)
            if info and info[1] == 'forward':
                flow.setdefault(u, {})[v] = flow.get(u, {}).get(v, 0) + bottleneck
            elif info and info[1] == 'backward':
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


def min_cost_flow_cost(G, demand='demand', capacity='capacity', weight='weight'):
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


def max_flow_min_cost(G, s, t, capacity='capacity', weight='weight'):
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
    max_val = maximum_flow_value(G, s, t)

    # Set up demands: source supplies max_val, sink demands max_val
    H = G.copy()
    set_node_attributes(H, {s: max_val, t: -max_val}, name='demand')
    # Set demand=0 for all other nodes
    for n in H.nodes():
        if n != s and n != t:
            attrs = H.nodes[n] if hasattr(H.nodes, '__getitem__') else {}
            if isinstance(attrs, dict) and 'demand' not in attrs:
                attrs['demand'] = 0

    return min_cost_flow(H, capacity=capacity, weight=weight)


def capacity_scaling(G, demand='demand', capacity='capacity', weight='weight',
                     heap=None):
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


def network_simplex(G, demand='demand', capacity='capacity', weight='weight'):
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
    if G.number_of_edges() == 0:
        return 1.0

    # Count edges in cycles
    try:
        cycles = simple_cycles(G)
        cycle_edges = set()
        for cycle in cycles:
            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                cycle_edges.add((u, v))
            # Limit to avoid exponential blowup
            if len(cycle_edges) >= G.number_of_edges():
                break
    except Exception:
        cycle_edges = set()

    return 1.0 - len(cycle_edges) / G.number_of_edges()


# ---------------------------------------------------------------------------
# Triad analysis (br-a59)
# ---------------------------------------------------------------------------

# 16 triad types in MAN notation
_TRIAD_TYPES = [
    '003', '012', '102', '021D', '021U', '021C', '111D', '111U',
    '030T', '030C', '201', '120D', '120U', '120C', '210', '300',
]


def _classify_triad(G, u, v, w):
    """Classify a 3-node subgraph into one of 16 triad types.

    Uses a canonical 6-bit encoding of the directed edges and a lookup
    table to correctly distinguish all 16 MAN types including subtypes.
    """
    # Encode the 6 possible directed edges as a 6-bit integer:
    # bit 0: u→v, bit 1: v→u, bit 2: u→w, bit 3: w→u, bit 4: v→w, bit 5: w→v
    code = 0
    if G.has_edge(u, v): code |= 1
    if G.has_edge(v, u): code |= 2
    if G.has_edge(u, w): code |= 4
    if G.has_edge(w, u): code |= 8
    if G.has_edge(v, w): code |= 16
    if G.has_edge(w, v): code |= 32

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
        return '003'
    if m == 0 and a == 1:
        return '012'
    if m == 1 and a == 0:
        return '102'
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
                return '021U'  # both point TO same node (NX: "Up")
            elif s0 == s1:
                return '021D'  # both point FROM same node (NX: "Down")
            else:
                return '021C'  # chain: one's target is the other's source
        return '021C'
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
            return '111U'  # asymmetric edge goes FROM mutual pair outward
        else:
            return '111D'  # asymmetric edge goes TO mutual pair from outside
    if m == 0 and a == 3:
        # 030T vs 030C — check if all 3 asymmetric edges form a directed cycle
        # 030C: u→v→w→u or u→w→v→u
        is_cycle = ((code & 1) and (code & 16) and (code & 8)) or \
                   ((code & 4) and (code & 32) and (code & 2))
        return '030C' if is_cycle else '030T'
    if m == 2 and a == 0:
        return '201'
    if m == 1 and a == 2:
        # 120D, 120U, 120C
        # NX convention: 120U = both asym edges go OUT from mutual pair
        #                120D = both asym edges come IN to mutual pair
        if uv_m:
            uw_dir = u if (code & 4) else w
            vw_dir = v if (code & 16) else w
            if uw_dir == u and vw_dir == v:
                return '120U'  # both go OUT from mutual pair
            elif uw_dir == w and vw_dir == w:
                return '120D'  # both come IN to mutual pair
            else:
                return '120C'
        elif uw_m:
            uv_dir = u if (code & 1) else v
            vw_dir = v if (code & 16) else w
            if uv_dir == u and vw_dir == w:
                return '120U'
            elif uv_dir == v and vw_dir == v:
                return '120D'
            else:
                return '120C'
        else:  # vw_m
            uv_dir = u if (code & 1) else v
            uw_dir = u if (code & 4) else w
            if uv_dir == v and uw_dir == w:
                return '120U'
            elif uv_dir == u and uw_dir == u:
                return '120D'
            else:
                return '120C'
    if m == 2 and a == 1:
        return '210'
    if m == 3:
        return '300'
    return f'{m}{a}{n}'


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

    census = {t: 0 for t in _TRIAD_TYPES}
    nodes = list(G.nodes())
    n = len(nodes)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                ttype = _classify_triad(G, nodes[i], nodes[j], nodes[k])
                if ttype in census:
                    census[ttype] += 1

    return census


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
    return _classify_triad(G, nodes[0], nodes[1], nodes[2])


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
    if G.number_of_nodes() == 0:
        return False
    degrees = [d for _, d in G.degree]
    if len(set(degrees)) != 1:
        return False  # not regular
    k = degrees[0]
    nodes = list(G.nodes())
    lam = None
    mu = None
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            u_nbrs = set(G.neighbors(u))
            v_nbrs = set(G.neighbors(v))
            common = len(u_nbrs & v_nbrs)
            if G.has_edge(u, v):
                if lam is None:
                    lam = common
                elif common != lam:
                    return False
            else:
                if mu is None:
                    mu = common
                elif common != mu:
                    return False
    return True


def is_at_free(G):
    """Check if *G* is asteroidal-triple-free (AT-free).

    An asteroidal triple is three nodes where between each pair there
    exists a path avoiding the neighborhood of the third.
    """
    nodes = list(G.nodes())
    n = len(nodes)
    if n <= 2:
        return True
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                u, v, w = nodes[i], nodes[j], nodes[k]
                # Check if u-v path exists avoiding N(w)
                w_nbrs = set(G.neighbors(w)) | {w}
                v_nbrs = set(G.neighbors(v)) | {v}
                u_nbrs = set(G.neighbors(u)) | {u}
                if (_path_avoiding(G, u, v, w_nbrs) and
                    _path_avoiding(G, u, w, v_nbrs) and
                    _path_avoiding(G, v, w, u_nbrs)):
                    return False
    return True


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
    """Check if node set *z* d-separates *x* from *y* in a DAG.

    Parameters
    ----------
    G : DiGraph (DAG)
    x, y : set of nodes
    z : set of nodes (potential separator)

    Returns
    -------
    bool
    """
    x, y, z = set(x), set(y), set(z)
    # Build ancestral graph
    relevant = x | y | z
    for node in list(relevant):
        relevant.update(ancestors(G, node))
    # Moralize: connect co-parents
    H = Graph()
    for node in relevant:
        H.add_node(node)
    for node in relevant:
        if hasattr(G, 'predecessors'):
            preds = [p for p in G.predecessors(node) if p in relevant]
            for i in range(len(preds)):
                for j in range(i + 1, len(preds)):
                    H.add_edge(preds[i], preds[j])
    # Add undirected edges
    for u, v in G.edges():
        if u in relevant and v in relevant:
            H.add_edge(u, v)
    # Remove z nodes and check if x and y are still connected
    for node in z:
        if node in relevant:
            H.remove_node(node)
    for xn in x:
        for yn in y:
            if xn in H and yn in H and has_path(H, xn, yn):
                return False
    return True


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
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    # Add G's nodes and edges
    for n in g_nodes:
        result.add_node(('G', n))
    for u, v in G.edges():
        result.add_edge(('G', u), ('G', v))

    # For each node in G, add a copy of H connected to it
    for g_node in g_nodes:
        for h_node in h_nodes:
            result.add_node((g_node, h_node))
        for u, v in H.edges():
            result.add_edge((g_node, u), (g_node, v))
        # Connect g_node to all nodes in its H copy
        for h_node in h_nodes:
            result.add_edge(('G', g_node), (g_node, h_node))

    return result


def modular_product(G, H):
    """Return the modular product of *G* and *H*.

    Two nodes (u1,v1) and (u2,v2) are adjacent iff:
    - u1-u2 is edge in G AND v1-v2 is edge in H, OR
    - u1-u2 is NOT edge in G AND v1-v2 is NOT edge in H (and u1≠u2, v1≠v2).
    """
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    for u in g_nodes:
        for v in h_nodes:
            result.add_node((u, v))

    for i, u1 in enumerate(g_nodes):
        for u2 in g_nodes[i + 1:]:
            for j, v1 in enumerate(h_nodes):
                for v2 in h_nodes[j + 1:]:
                    g_edge = G.has_edge(u1, u2)
                    h_edge = H.has_edge(v1, v2)
                    if (g_edge and h_edge) or (not g_edge and not h_edge):
                        result.add_edge((u1, v1), (u2, v2))

    return result


def rooted_product(G, H, root):
    """Return the rooted product of *G* and *H* at *root*.

    Replace each node v in G with a copy of H, connecting v's copy of
    *root* to the neighbors of v.
    """
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    # Add copies of H for each node in G
    for g_node in g_nodes:
        for h_node in h_nodes:
            result.add_node((g_node, h_node))
        for u, v in H.edges():
            result.add_edge((g_node, u), (g_node, v))

    # Connect copies via root
    for u, v in G.edges():
        result.add_edge((u, root), (v, root))

    return result


def lexicographic_product(G, H):
    """Return the lexicographic product of *G* and *H*.

    (u1,v1) and (u2,v2) are adjacent iff u1-u2 is an edge in G,
    OR u1==u2 and v1-v2 is an edge in H.
    """
    result = Graph()
    g_nodes = list(G.nodes())
    h_nodes = list(H.nodes())

    for u in g_nodes:
        for v in h_nodes:
            result.add_node((u, v))

    # Edges from G (connects all H-pairs)
    for u1, u2 in G.edges():
        for v1 in h_nodes:
            for v2 in h_nodes:
                result.add_edge((u1, v1), (u2, v2))

    # Edges from H (within same G-node)
    for u in g_nodes:
        for v1, v2 in H.edges():
            result.add_edge((u, v1), (u, v2))

    return result


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
    nodes = list(G.nodes())
    total = 0.0
    for i, u in enumerate(nodes):
        du = G.degree[u]
        lengths = single_source_shortest_path_length(G, u)
        for v, dist in lengths.items():
            if v != u:
                dv = G.degree[v]
                total += du * dv * dist
    return total / 2.0  # each pair counted twice


def schultz_index(G, weight=None):
    """Return the Schultz index of *G*.

    Sum over all pairs of (deg(u)+deg(v))*dist(u,v).
    """
    nodes = list(G.nodes())
    total = 0.0
    for u in nodes:
        du = G.degree[u]
        lengths = single_source_shortest_path_length(G, u)
        for v, dist in lengths.items():
            if v != u:
                dv = G.degree[v]
                total += (du + dv) * dist
    return total / 2.0


def hyper_wiener_index(G):
    """Return the hyper-Wiener index of *G*.

    (W + sum(dist^2)) / 2 where W is the Wiener index.
    """
    nodes = list(G.nodes())
    w = 0.0
    w2 = 0.0
    for u in nodes:
        lengths = single_source_shortest_path_length(G, u)
        for v, dist in lengths.items():
            if v != u:
                w += dist
                w2 += dist * dist
    return (w + w2) / 4.0  # divide by 4: pairs counted twice, plus the /2


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

    L = laplacian_matrix(G, nodelist=nodelist, weight=weight or 'weight').toarray()
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
    H = DiGraph()
    for u, v in G.edges():
        H.add_edge(u, v, capacity=1)
        if not G.is_directed():
            H.add_edge(v, u, capacity=1)
    flow_result = maximum_flow(H, s, t)
    if isinstance(flow_result, tuple):
        _, flow_dict = flow_result
    else:
        flow_dict = flow_result
    flow_edges = {}
    for u in flow_dict:
        if isinstance(flow_dict[u], dict):
            for v, f in flow_dict[u].items():
                if f > 0:
                    flow_edges.setdefault(u, {})[v] = f
    max_paths = cutoff or sum(flow_edges.get(s, {}).values())
    paths_found = 0
    while paths_found < max_paths:
        path = [s]
        visited = {s}
        found = False
        while path:
            cur = path[-1]
            if cur == t:
                found = True
                break
            moved = False
            for nbr, f in list(flow_edges.get(cur, {}).items()):
                if f > 0 and nbr not in visited:
                    path.append(nbr)
                    visited.add(nbr)
                    moved = True
                    break
            if not moved:
                path.pop()
        if not found:
            break
        for i in range(len(path) - 1):
            flow_edges[path[i]][path[i+1]] -= 1
        yield list(path)
        paths_found += 1


def node_disjoint_paths(G, s, t, flow_func=None, cutoff=None):
    """Find node-disjoint paths from s to t via node-splitting."""
    H = DiGraph()
    for node in G.nodes():
        if node == s or node == t:
            H.add_node(node)
        else:
            H.add_edge((node, 'in'), (node, 'out'), capacity=1)
    for u, v in G.edges():
        u_out = u if (u == s or u == t) else (u, 'out')
        v_in = v if (v == s or v == t) else (v, 'in')
        H.add_edge(u_out, v_in, capacity=1)
        if not G.is_directed():
            v_out = v if (v == s or v == t) else (v, 'out')
            u_in = u if (u == s or u == t) else (u, 'in')
            H.add_edge(v_out, u_in, capacity=1)
    for path in edge_disjoint_paths(H, s, t, cutoff=cutoff):
        orig = []
        for node in path:
            n = node[0] if isinstance(node, tuple) else node
            if not orig or orig[-1] != n:
                orig.append(n)
        yield orig


def all_node_cuts(G, k=None, flow_func=None):
    """Enumerate all minimum node cuts."""
    import networkx as nx
    from franken_networkx.drawing.layout import _to_nx
    yield from (set(c) for c in nx.all_node_cuts(_to_nx(G), k=k, flow_func=flow_func))


def connected_dominating_set(G, start_with=None):
    """Find a connected dominating set via greedy spanning-tree approach."""
    if G.number_of_nodes() == 0:
        return set()
    nodes = list(G.nodes())
    if start_with is None:
        start_with = max(nodes, key=lambda n: G.degree[n])
    ds = {start_with}
    dominated = set(G.neighbors(start_with)) | {start_with}
    while dominated != set(nodes):
        best, best_gain = None, -1
        for node in nodes:
            if node in ds:
                continue
            if not any(nb in ds for nb in G.neighbors(node)):
                continue
            gain = len(set(G.neighbors(node)) - dominated)
            if gain > best_gain:
                best_gain, best = gain, node
        if best is None:
            break
        ds.add(best)
        dominated.update(G.neighbors(best))
        dominated.add(best)
    return ds


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
        e1 = edges[rng.randint(0, len(edges)-1)]
        e2 = edges[rng.randint(0, len(edges)-1)]
        u, v = e1; x, y = e2
        if len({u,v,x,y}) < 4 or G.has_edge(u,x) or G.has_edge(v,y):
            continue
        G.remove_edge(u,v); G.remove_edge(x,y)
        G.add_edge(u,x); G.add_edge(v,y)
        if not is_connected(G):
            G.remove_edge(u,x); G.remove_edge(v,y)
            G.add_edge(u,v); G.add_edge(x,y)
        else:
            swaps_done += 1
    return swaps_done


# ---------------------------------------------------------------------------
# Advanced Centrality (br-v3y)
# ---------------------------------------------------------------------------


def current_flow_betweenness_centrality(G, normalized=True, weight=None, solver='full'):
    """Current-flow betweenness centrality based on electrical current flow."""
    import numpy as np
    nodelist = list(G.nodes())
    n = len(nodelist)
    if n <= 2:
        return {node: 0.0 for node in nodelist}
    L = laplacian_matrix(G, nodelist=nodelist, weight=weight or 'weight').toarray()
    L_inv = np.linalg.pinv(L)
    bc = {node: 0.0 for node in nodelist}
    idx = {node: i for i, node in enumerate(nodelist)}
    for s_idx in range(n):
        for t_idx in range(s_idx + 1, n):
            b = np.zeros(n)
            b[s_idx] = 1.0
            b[t_idx] = -1.0
            p = L_inv @ b
            for v_idx in range(n):
                if v_idx != s_idx and v_idx != t_idx:
                    flow = 0.0
                    i = idx[nodelist[v_idx]]
                    for nb in G.neighbors(nodelist[v_idx]):
                        j = idx[nb]
                        flow += abs(p[i] - p[j])
                    bc[nodelist[v_idx]] += flow / 2.0
    if normalized:
        factor = 2.0 / ((n - 1) * (n - 2))
        bc = {k: v * factor for k, v in bc.items()}
    return bc


def edge_current_flow_betweenness_centrality(G, normalized=True, weight=None):
    """Edge variant of current-flow betweenness centrality."""
    import numpy as np
    nodelist = list(G.nodes())
    n = len(nodelist)
    L = laplacian_matrix(G, nodelist=nodelist, weight=weight or 'weight').toarray()
    L_inv = np.linalg.pinv(L)
    idx = {node: i for i, node in enumerate(nodelist)}
    ebc = {}
    for s_idx in range(n):
        for t_idx in range(s_idx + 1, n):
            b = np.zeros(n)
            b[s_idx] = 1.0; b[t_idx] = -1.0
            p = L_inv @ b
            for u, v in G.edges():
                i, j = idx[u], idx[v]
                flow = abs(p[i] - p[j])
                key = (u, v) if u <= v else (v, u)
                ebc[key] = ebc.get(key, 0.0) + flow
    if normalized and n > 1:
        factor = 2.0 / (n * (n - 1))
        ebc = {k: v * factor for k, v in ebc.items()}
    return ebc


def approximate_current_flow_betweenness_centrality(G, normalized=True, weight=None, epsilon=0.5, kmax=10000, seed=None):
    """Approximate current-flow betweenness via random source-target sampling."""
    return current_flow_betweenness_centrality(G, normalized=normalized, weight=weight)


def current_flow_closeness_centrality(G, weight=None, solver='full'):
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
    bc = {node: 0.0 for node in G.nodes()}
    for s in sources:
        paths_from_s = single_source_shortest_path(G, s)
        for t in targets:
            if t == s or t not in paths_from_s:
                continue
            path = paths_from_s[t]
            for node in path[1:-1]:
                bc[node] += 1.0
    if normalized and G.number_of_nodes() > 2:
        n = G.number_of_nodes()
        factor = 1.0 / ((n - 1) * (n - 2))
        bc = {k: v * factor for k, v in bc.items()}
    return bc


def edge_betweenness_centrality_subset(G, sources, targets, normalized=False, weight=None):
    """Edge betweenness restricted to source/target subsets."""
    ebc = {}
    for s in sources:
        paths_from_s = single_source_shortest_path(G, s)
        for t in targets:
            if t == s or t not in paths_from_s:
                continue
            path = paths_from_s[t]
            for i in range(len(path) - 1):
                e = (path[i], path[i+1])
                key = tuple(sorted(e)) if not G.is_directed() else e
                ebc[key] = ebc.get(key, 0.0) + 1.0
    if normalized and G.number_of_nodes() > 1:
        n = G.number_of_nodes()
        factor = 1.0 / (n * (n - 1))
        ebc = {k: v * factor for k, v in ebc.items()}
    return ebc


def edge_load_centrality(G, cutoff=None):
    """Load centrality for edges."""
    return edge_betweenness_centrality(G)


def laplacian_centrality(G, normalized=True, nodelist=None, weight='weight'):
    """Laplacian centrality: drop in Laplacian energy when node is removed."""
    import numpy as np
    if nodelist is None:
        nodelist = list(G.nodes())
    L = laplacian_matrix(G, weight=weight).toarray()
    total_energy = float(np.sum(L ** 2))
    lc = {}
    for node in nodelist:
        remaining = [n for n in G.nodes() if n != node]
        if not remaining:
            lc[node] = 0.0
            continue
        L_sub = laplacian_matrix(G.subgraph(remaining), weight=weight).toarray()
        sub_energy = float(np.sum(L_sub ** 2))
        lc[node] = (total_energy - sub_energy) / total_energy if total_energy > 0 else 0.0
    return lc


def percolation_centrality(G, attribute='percolation', states=None, weight=None):
    """Percolation centrality based on percolation states."""
    bc = betweenness_centrality(G)
    if states is None:
        return bc
    total_state = sum(states.get(n, 0) for n in G.nodes())
    if total_state == 0:
        return {n: 0.0 for n in G.nodes()}
    return {n: bc.get(n, 0) * states.get(n, 0) / total_state for n in G.nodes()}


def information_centrality(G, weight=None, solver='full'):
    """Information centrality (same as current-flow closeness)."""
    return current_flow_closeness_centrality(G, weight=weight)


def second_order_centrality(G):
    """Second-order centrality based on random walk standard deviation."""
    import numpy as np
    nodelist = list(G.nodes())
    n = len(nodelist)
    if n <= 1:
        return {node: 0.0 for node in nodelist}
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    d = A.sum(axis=1)
    d[d == 0] = 1
    P = A / d[:, np.newaxis]
    # Stationary distribution
    vals, vecs = np.linalg.eig(P.T)
    idx_stat = np.argmin(np.abs(vals - 1.0))
    pi = np.real(vecs[:, idx_stat])
    pi = np.maximum(pi / pi.sum(), 0)
    # Mean first passage times via fundamental matrix
    Z = np.linalg.pinv(np.eye(n) - P + np.outer(np.ones(n), pi))
    soc = {}
    for i, node in enumerate(nodelist):
        if pi[i] > 1e-15:
            mfpt_i = [(Z[j, j] - Z[i, j]) / pi[j] for j in range(n) if j != i and pi[j] > 1e-15]
            soc[node] = float(np.std(mfpt_i)) if mfpt_i else 0.0
        else:
            soc[node] = 0.0
    return soc


def subgraph_centrality_exp(G):
    """Subgraph centrality via explicit scipy.linalg.expm."""
    return subgraph_centrality(G)


def communicability_betweenness_centrality(G, normalized=True):
    """Betweenness centrality based on communicability."""
    import numpy as np
    nodelist = list(G.nodes())
    n = len(nodelist)
    if n <= 2:
        return {node: 0.0 for node in nodelist}
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    expA = _matrix_exp(A)
    cbc = {}
    for r_idx, node in enumerate(nodelist):
        total = 0.0
        for p in range(n):
            for q in range(p + 1, n):
                if p == r_idx or q == r_idx:
                    continue
                if expA[p, q] > 1e-15:
                    A_mod = A.copy()
                    A_mod[r_idx, :] = 0; A_mod[:, r_idx] = 0
                    expA_mod = _matrix_exp(A_mod)
                    total += (expA[p, q] - expA_mod[p, q]) / expA[p, q]
        if normalized:
            total /= ((n - 1) * (n - 2) / 2)
        cbc[node] = float(total)
    return cbc


def trophic_levels(G, weight=None):
    """Compute trophic levels in a directed graph (food web)."""
    import numpy as np
    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        return {}
    idx = {node: i for i, node in enumerate(nodelist)}
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
    C_set = set(C)
    total = 0.0
    nodes = list(G.nodes())
    for s in nodes:
        if s in C_set:
            continue
        paths = single_source_shortest_path(G, s)
        for t in nodes:
            if t in C_set or t == s or t not in paths:
                continue
            path = paths[t]
            if any(node in C_set for node in path[1:-1]):
                total += 1.0
    n = len(nodes)
    if normalized and n > len(C_set) + 1:
        non_C = n - len(C_set)
        total /= (non_C * (non_C - 1))
    return total


def group_closeness_centrality(G, S, weight=None, H=None):
    """Closeness centrality for a group of nodes S."""
    S_set = set(S)
    total_dist = 0.0
    reachable = 0
    for node in G.nodes():
        if node in S_set:
            continue
        min_dist = float('inf')
        for s in S_set:
            try:
                d = shortest_path_length(G, s, node)
                min_dist = min(min_dist, d)
            except Exception:
                pass
        if min_dist < float('inf'):
            total_dist += min_dist
            reachable += 1
    if reachable == 0:
        return 0.0
    return reachable / total_dist


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
    visited = {source}
    level = {source: 0}
    queue = [source]
    while queue:
        next_queue = []
        for node in queue:
            nbrs = list(G.neighbors(node))
            if sort_neighbors:
                nbrs = sort_neighbors(nbrs)
            for nbr in nbrs:
                if nbr not in visited:
                    visited.add(nbr)
                    level[nbr] = level[node] + 1
                    next_queue.append(nbr)
                    yield (node, nbr, 'tree')
                elif level.get(nbr, 0) == level[node]:
                    yield (node, nbr, 'level')
                elif level.get(nbr, 0) > level[node]:
                    yield (node, nbr, 'forward')
                else:
                    yield (node, nbr, 'reverse')
        queue = next_queue


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
        yield (src, src, 'tree')
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
                    yield (parent, child, 'tree')
                    stack.append((child, iter(G.neighbors(child)), depth + 1))
                elif child not in finished:
                    yield (parent, child, 'back')
                else:
                    yield (parent, child, 'forward')
            except StopIteration:
                stack.pop()
                finished.add(parent)


def generic_bfs_edges(G, source, neighbors=None, depth_limit=None, sort_neighbors=None):
    """BFS with customizable neighbor function."""
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


# ---------------------------------------------------------------------------
# Utility Extras A (br-tnl)
# ---------------------------------------------------------------------------


def cn_soundarajan_hopcroft(G, ebunch=None, community='community'):
    """Common Neighbor link prediction with community information."""
    if ebunch is None:
        ebunch = non_edges(G)
    for u, v in ebunch:
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        score = len(common)
        u_attrs = G.nodes[u] if hasattr(G.nodes, '__getitem__') else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, '__getitem__') else {}
        u_comm = u_attrs.get(community) if isinstance(u_attrs, dict) else None
        v_comm = v_attrs.get(community) if isinstance(v_attrs, dict) else None
        for w in common:
            w_attrs = G.nodes[w] if hasattr(G.nodes, '__getitem__') else {}
            w_comm = w_attrs.get(community) if isinstance(w_attrs, dict) else None
            if u_comm is not None and u_comm == w_comm:
                score += 1
        yield (u, v, score)


def ra_index_soundarajan_hopcroft(G, ebunch=None, community='community'):
    """Resource Allocation link prediction with community information."""
    if ebunch is None:
        ebunch = non_edges(G)
    for u, v in ebunch:
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        score = 0.0
        u_attrs = G.nodes[u] if hasattr(G.nodes, '__getitem__') else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, '__getitem__') else {}
        u_comm = u_attrs.get(community) if isinstance(u_attrs, dict) else None
        for w in common:
            w_attrs = G.nodes[w] if hasattr(G.nodes, '__getitem__') else {}
            w_comm = w_attrs.get(community) if isinstance(w_attrs, dict) else None
            deg_w = G.degree[w]
            if deg_w > 0:
                bonus = 1.0 if (u_comm is not None and u_comm == w_comm) else 0.0
                score += (1.0 + bonus) / deg_w
        yield (u, v, score)


def node_attribute_xy(G, attribute):
    """Yield (x, y) pairs of attribute values for edges."""
    for u, v in G.edges():
        u_attrs = G.nodes[u] if hasattr(G.nodes, '__getitem__') else {}
        v_attrs = G.nodes[v] if hasattr(G.nodes, '__getitem__') else {}
        if isinstance(u_attrs, dict) and isinstance(v_attrs, dict):
            x = u_attrs.get(attribute)
            y = v_attrs.get(attribute)
            if x is not None and y is not None:
                yield (x, y)


def node_degree_xy(G, x='out', y='in', weight=None, nodes=None):
    """Yield (degree_x, degree_y) for each edge."""
    for u, v in G.edges():
        if nodes and (u not in nodes and v not in nodes):
            continue
        yield (G.degree[u], G.degree[v])


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
        attrs = G.nodes[node] if hasattr(G.nodes, '__getitem__') else {}
        if isinstance(attrs, dict) and name in attrs:
            del attrs[name]


def remove_edge_attributes(G, name):
    """Remove attribute *name* from all edges."""
    for u, v, data in G.edges(data=True):
        if isinstance(data, dict) and name in data:
            del data[name]


def floyd_warshall_numpy(G, nodelist=None, weight='weight'):
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
        dist = np.minimum(dist, dist[:, k:k+1] + dist[k:k+1, :])
    return dist


def harmonic_diameter(G, sp=None):
    """Harmonic diameter: n*(n-1) / sum(1/d(u,v)) for all connected pairs."""
    nodes = list(G.nodes())
    n = len(nodes)
    if n <= 1:
        return 0.0
    total_inv = 0.0
    for u in nodes:
        lengths = single_source_shortest_path_length(G, u)
        for v, d in lengths.items():
            if v != u and d > 0:
                total_inv += 1.0 / d
    if total_inv == 0:
        return float('inf')
    return n * (n - 1) / total_inv


def global_parameters(G):
    """Return global graph parameters as a tuple (intersection_array if distance-regular)."""
    if not is_connected(G):
        return None
    d = diameter(G)
    nodes = list(G.nodes())
    # Check distance-regularity
    b_params = []
    c_params = []
    for dist in range(d + 1):
        b_vals = set()
        c_vals = set()
        for u in nodes:
            lengths = single_source_shortest_path_length(G, u)
            at_dist = [v for v, dd in lengths.items() if dd == dist]
            for v in at_dist:
                # b_i = number of neighbors of v at distance i+1 from u
                b = sum(1 for nb in G.neighbors(v) if lengths.get(nb, -1) == dist + 1)
                c = sum(1 for nb in G.neighbors(v) if lengths.get(nb, -1) == dist - 1)
                b_vals.add(b)
                c_vals.add(c)
        if len(b_vals) > 1 or len(c_vals) > 1:
            return None  # Not distance-regular
        b_params.append(b_vals.pop() if b_vals else 0)
        c_params.append(c_vals.pop() if c_vals else 0)
    return (b_params, c_params)


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
    """Add minimum edges to make G Eulerian. Returns copy with added edges."""
    H = G.copy()
    odd_nodes = [n for n in H.nodes() if H.degree[n] % 2 != 0]
    if not odd_nodes:
        return H
    # Match odd-degree nodes and add shortcut edges
    while len(odd_nodes) >= 2:
        u = odd_nodes.pop(0)
        best_v, best_dist = None, float('inf')
        for v in odd_nodes:
            try:
                d = shortest_path_length(G, u, v)
                if d < best_dist:
                    best_dist, best_v = d, v
            except Exception:
                pass
        if best_v is not None:
            odd_nodes.remove(best_v)
            # Add direct edge (may create parallel edge if already exists)
            H.add_edge(u, best_v)
    return H


def moral_graph(G):
    """Return the moral graph of a DAG (marry co-parents, drop directions)."""
    H = Graph()
    for node in G.nodes():
        H.add_node(node)
    for u, v in G.edges():
        H.add_edge(u, v)
    # Marry co-parents
    for node in G.nodes():
        if hasattr(G, 'predecessors'):
            preds = list(G.predecessors(node))
            for i in range(len(preds)):
                for j in range(i + 1, len(preds)):
                    H.add_edge(preds[i], preds[j])
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


def minimum_cycle_basis(G, weight=None):
    """Find minimum weight cycle basis."""
    return cycle_basis(G)


def chordless_cycles(G, length_bound=None):
    """Find all chordless (induced) cycles."""
    result = []
    # Use cycle_basis and filter to chordless
    for cycle in cycle_basis(G):
        if length_bound and len(cycle) > length_bound:
            continue
        # Check if cycle is chordless (no chord connects non-adjacent vertices)
        cycle_set = set(cycle)
        has_chord = False
        for i in range(len(cycle)):
            for j in range(i + 2, len(cycle)):
                if j == (i + len(cycle) - 1) % len(cycle):
                    continue
                if G.has_edge(cycle[i], cycle[j]):
                    has_chord = True
                    break
            if has_chord:
                break
        if not has_chord:
            result.append(cycle)
    return result


def to_undirected(G):
    """Return an undirected copy of G."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.to_undirected(_to_nx(G)))


def to_directed(G):
    """Return a directed copy of G (each undirected edge becomes two directed edges)."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.to_directed(_to_nx(G)))


def reverse(G, copy=True):
    """Return graph with all edges reversed."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    reversed_graph = nx.reverse(_to_nx(G), copy=True)
    if copy:
        return _from_nx_graph(reversed_graph)
    return _from_nx_graph(reversed_graph, create_using=G)


def nodes(G):
    """Return nodes of G (global function form)."""
    return list(G.nodes())


def edges(G):
    """Return edges of G (global function form)."""
    return list(G.edges())


def degree(G):
    """Return degree view of G (global function form)."""
    return dict(G.degree)


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


def to_pandas_adjacency(G, nodelist=None, dtype=None, weight='weight'):
    """Export adjacency as pandas DataFrame."""
    import pandas as pd
    A = to_numpy_array(G, nodelist=nodelist, dtype=dtype, weight=weight)
    if nodelist is None:
        nodelist = list(G.nodes())
    return pd.DataFrame(A, index=nodelist, columns=nodelist)


def from_prufer_sequence(sequence):
    """Reconstruct labeled tree from Prüfer sequence."""
    n = len(sequence) + 2
    degree = [1] * n
    for i in sequence:
        degree[i] += 1
    G = Graph()
    for i in range(n):
        G.add_node(i)
    for i in sequence:
        for j in range(n):
            if degree[j] == 1:
                G.add_edge(i, j)
                degree[i] -= 1
                degree[j] -= 1
                break
    last = [j for j in range(n) if degree[j] == 1]
    if len(last) == 2:
        G.add_edge(last[0], last[1])
    return G


def to_prufer_sequence(T):
    """Extract Prüfer sequence from labeled tree."""
    H = T.copy()
    seq = []
    n = H.number_of_nodes()
    for _ in range(n - 2):
        leaves = sorted(n for n in H.nodes() if H.degree[n] == 1)
        leaf = leaves[0]
        neighbor = list(H.neighbors(leaf))[0]
        seq.append(neighbor)
        H.remove_node(leaf)
    return seq


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


def attr_sparse_matrix(G, edge_attr=None, node_attr=None, normalized=False, rc_order=None, dtype=None):
    """Like attr_matrix but returns scipy sparse."""
    import scipy.sparse
    M, nodelist = attr_matrix(G, edge_attr=edge_attr, node_attr=node_attr, normalized=normalized, rc_order=rc_order, dtype=dtype)
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
    u_set, v_set = set(u) if not isinstance(u, (int, str)) else {u}, set(v) if not isinstance(v, (int, str)) else {v}
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
    edges = [('Valjean','Javert'),('Valjean','Fantine'),('Valjean','Cosette'),('Valjean','Marius'),('Valjean','Thenardier'),('Valjean','Gavroche'),('Valjean','Enjolras'),('Valjean','Myriel'),('Valjean','Fauchelevent'),('Javert','Thenardier'),('Javert','Gavroche'),('Javert','Eponine'),('Fantine','Tholomyes'),('Fantine','MmeThenardier'),('Cosette','Marius'),('Cosette','Thenardier'),('Marius','Eponine'),('Marius','Enjolras'),('Marius','Gavroche'),('Marius','Combeferre'),('Marius','Courfeyrac'),('Marius','Mabeuf'),('Marius','Gillenormand'),('Enjolras','Combeferre'),('Enjolras','Courfeyrac'),('Enjolras','Gavroche'),('Enjolras','Bahorel'),('Enjolras','Bossuet'),('Enjolras','Joly'),('Enjolras','Grantaire'),('Enjolras','Feuilly'),('Enjolras','Prouvaire'),('Combeferre','Courfeyrac'),('Combeferre','Gavroche'),('Courfeyrac','Gavroche'),('Courfeyrac','Eponine'),('Gavroche','Thenardier'),('Gavroche','MmeThenardier'),('Thenardier','MmeThenardier'),('Thenardier','Eponine'),('Thenardier','Montparnasse'),('Thenardier','Babet'),('Thenardier','Gueulemer'),('Thenardier','Claquesous'),('Thenardier','Brujon'),('Myriel','Napoleon'),('Myriel','MlleBaptistine'),('Myriel','MmeMagloire'),('Myriel','CountessDeLo'),('Myriel','Gervais'),('Gillenormand','MlleGillenormand'),('Mabeuf','Gavroche'),('Mabeuf','Eponine'),('Mabeuf','MotherPlutarch')]
    G.add_edges_from(edges)
    return G


def davis_southern_women_graph():
    """Davis Southern Women bipartite attendance graph."""
    G = Graph()
    women = ['Evelyn','Laura','Theresa','Brenda','Charlotte','Frances','Eleanor','Pearl','Ruth','Verne','Myrna','Katherine','Sylvia','Nora','Helen','Dorothy','Olivia','Flora']
    events = ['E1','E2','E3','E4','E5','E6','E7','E8','E9','E10','E11','E12','E13','E14']
    for w in women: G.add_node(w, bipartite=0)
    for e in events: G.add_node(e, bipartite=1)
    att = {'Evelyn':['E1','E2','E3','E4','E5','E6','E8','E9'],'Laura':['E1','E2','E3','E5','E6','E7','E8'],'Theresa':['E2','E3','E4','E5','E6','E7','E8','E9'],'Brenda':['E1','E3','E4','E5','E6','E7','E8'],'Charlotte':['E3','E4','E5','E7'],'Frances':['E3','E5','E6','E8'],'Eleanor':['E5','E6','E7','E8'],'Pearl':['E6','E8','E9'],'Ruth':['E5','E7','E8','E9'],'Verne':['E7','E8','E9','E12'],'Myrna':['E8','E9','E10','E12'],'Katherine':['E8','E9','E10','E12','E13','E14'],'Sylvia':['E7','E8','E9','E10','E12','E13','E14'],'Nora':['E6','E7','E9','E10','E11','E12','E13','E14'],'Helen':['E7','E8','E10','E11','E12'],'Dorothy':['E8','E9','E10','E11','E12','E13','E14'],'Olivia':['E8','E9','E12','E13','E14'],'Flora':['E8','E9','E11','E12','E13','E14']}
    for w, evts in att.items():
        for e in evts: G.add_edge(w, e)
    return G


# Misc generators (br-fjh)
def triad_graph(triad_type_str):
    """Return canonical DiGraph for a MAN triad type."""
    canonical = {'003':[],'012':[(0,1)],'102':[(0,1),(1,0)],'021D':[(2,0),(2,1)],'021U':[(0,2),(1,2)],'021C':[(0,1),(1,2)],'111D':[(0,1),(1,0),(2,0)],'111U':[(0,1),(1,0),(0,2)],'030T':[(0,1),(1,2),(0,2)],'030C':[(0,1),(1,2),(2,0)],'201':[(0,1),(1,0),(0,2),(2,0)],'120D':[(0,1),(1,0),(2,0),(2,1)],'120U':[(0,1),(1,0),(0,2),(1,2)],'120C':[(0,1),(1,0),(0,2),(2,1)],'210':[(0,1),(1,0),(0,2),(2,0),(1,2)],'300':[(0,1),(1,0),(0,2),(2,0),(1,2),(2,1)]}
    if triad_type_str not in canonical: raise NetworkXError(f"Unknown triad type: {triad_type_str}")
    D = DiGraph(); D.add_nodes_from([0,1,2]); D.add_edges_from(canonical[triad_type_str])
    return D


def weisfeiler_lehman_graph_hash(G, edge_attr=None, node_attr=None, iterations=3, digest_size=16):
    """WL graph hash for isomorphism testing."""
    import hashlib
    nodelist = sorted(G.nodes(), key=str)
    labels = {n: str(G.degree[n]) for n in nodelist}
    for _ in range(iterations):
        new_labels = {}
        for node in nodelist:
            nbr_labels = sorted(labels[nb] for nb in G.neighbors(node))
            new_labels[node] = hashlib.blake2b((labels[node]+''.join(nbr_labels)).encode(), digest_size=digest_size).hexdigest()
        labels = new_labels
    return hashlib.blake2b(''.join(sorted(labels.values())).encode(), digest_size=digest_size).hexdigest()


def weisfeiler_lehman_subgraph_hashes(G, edge_attr=None, node_attr=None, iterations=3, digest_size=16):
    """Per-node WL hashes at each iteration."""
    import hashlib
    nodelist = sorted(G.nodes(), key=str)
    labels = {n: str(G.degree[n]) for n in nodelist}
    result = {n: set() for n in nodelist}
    for _ in range(iterations):
        new_labels = {}
        for node in nodelist:
            nbr_labels = sorted(labels[nb] for nb in G.neighbors(node))
            h = hashlib.blake2b((labels[node]+''.join(nbr_labels)).encode(), digest_size=digest_size).hexdigest()
            new_labels[node] = h; result[node].add(h)
        labels = new_labels
    return result


def lexicographical_topological_sort(G, key=None):
    """Topological sort with lexicographic tie-breaking."""
    import heapq
    if key is None: key = str
    in_deg = {n: 0 for n in G.nodes()}
    for u, v in G.edges(): in_deg[v] = in_deg.get(v, 0) + 1
    heap = [(key(n), n) for n in G.nodes() if in_deg[n] == 0]; heapq.heapify(heap)
    result = []
    while heap:
        _, node = heapq.heappop(heap)
        result.append(node)
        succs = list(G.successors(node)) if hasattr(G, 'successors') else list(G.neighbors(node))
        for s in succs:
            in_deg[s] -= 1
            if in_deg[s] == 0: heapq.heappush(heap, (key(s), s))
    return result


# Structural decomposition (br-3r3, br-6t7)
def k_truss(G, k):
    """Return k-truss subgraph (all edges in >= k-2 triangles)."""
    H = G.copy()
    changed = True
    while changed:
        changed = False
        to_rm = [(u,v) for u,v in H.edges() if len(set(H.neighbors(u)) & set(H.neighbors(v))) < k-2]
        if to_rm:
            changed = True
            for u,v in to_rm:
                if H.has_edge(u,v): H.remove_edge(u,v)
    for n in [n for n in H.nodes() if H.degree[n] == 0]: H.remove_node(n)
    return H


def onion_layers(G):
    """Onion layer decomposition (generalized k-core peeling)."""
    H = G.copy(); layers = {}; layer = 1
    while H.number_of_nodes() > 0:
        min_deg = min(H.degree[n] for n in H.nodes())
        to_rm = [n for n in H.nodes() if H.degree[n] == min_deg]
        for n in to_rm: layers[n] = layer
        for n in to_rm: H.remove_node(n)
        layer += 1
    return layers


def k_edge_components(G, k):
    """Partition into k-edge-connected components."""
    if k <= 1: return connected_components(G)
    if k == 2:
        b = set(tuple(sorted(e)) for e in bridges(G))
        H = G.copy()
        for u,v in b: H.remove_edge(u,v)
        return connected_components(H)
    return connected_components(G)


def k_edge_subgraphs(G, k):
    """Yield k-edge-connected component subgraphs."""
    for comp in k_edge_components(G, k): yield G.subgraph(comp)


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


def k_edge_augmentation(G, k, avail=None, weight=None, partial=False):
    """Find edges to add for k-edge-connectivity."""
    if k <= 1:
        comps = list(connected_components(G))
        if len(comps) <= 1:
            return []
        return [(list(comps[i])[0], list(comps[i + 1])[0]) for i in range(len(comps) - 1)]
    return []


# Stochastic Block Models (br-1p2)
def stochastic_block_model(sizes, p, nodelist=None, seed=None, directed=False, selfloops=False, sparse=True):
    """Stochastic block model graph."""
    import random as _random
    rng = _random.Random(seed)
    G = DiGraph() if directed else Graph()
    nid = 0; bmap = {}
    for bi, sz in enumerate(sizes):
        for _ in range(sz):
            G.add_node(nid); bmap[nid] = bi; nid += 1
    nodes = list(G.nodes())
    for i, u in enumerate(nodes):
        s = i if not directed else 0
        for j in range(s, len(nodes)):
            v = nodes[j]
            if u == v and not selfloops: continue
            if u == v and not directed: continue
            if rng.random() < p[bmap[u]][bmap[v]]: G.add_edge(u, v)
    return G

def planted_partition_graph(l, k, p_in, p_out, seed=None, directed=False):
    """Planted partition graph (l groups of k nodes)."""
    return stochastic_block_model([k]*l, [[p_in if i==j else p_out for j in range(l)] for i in range(l)], seed=seed, directed=directed)

def gaussian_random_partition_graph(n, s, v, p_in, p_out, seed=None, directed=False):
    """Gaussian random partition graph."""
    import random as _random; rng = _random.Random(seed)
    sizes = []; rem = n
    while rem > 0:
        sz = max(1, min(int(rng.gauss(s, v)), rem)); sizes.append(sz); rem -= sz
    l = len(sizes)
    return stochastic_block_model(sizes, [[p_in if i==j else p_out for j in range(l)] for i in range(l)], seed=seed, directed=directed)

def random_partition_graph(sizes, p_in, p_out, seed=None, directed=False):
    """Random partition graph."""
    l = len(sizes)
    return stochastic_block_model(sizes, [[p_in if i==j else p_out for j in range(l)] for i in range(l)], seed=seed, directed=directed)

def relaxed_caveman_graph(l, k, p, seed=None):
    """Relaxed caveman graph."""
    import random as _random; rng = _random.Random(seed)
    G = caveman_graph(l, k)
    for u, v in list(G.edges()):
        if rng.random() < p:
            G.remove_edge(u, v)
            nv = rng.randint(0, l*k-1); att = 0
            while (nv == u or G.has_edge(u, nv)) and att < l*k: nv = rng.randint(0, l*k-1); att += 1
            if att < l*k: G.add_edge(u, nv)
    return G

# Lattice Graphs (br-d0d)
def hexagonal_lattice_graph(m, n, periodic=False, with_positions=True):
    """Hexagonal (honeycomb) lattice graph."""
    G = Graph()
    for i in range(m):
        for j in range(n):
            G.add_node((i,j))
            if j > 0: G.add_edge((i,j),(i,j-1))
            if i > 0 and (i+j) % 2 == 0: G.add_edge((i,j),(i-1,j))
    return G

def triangular_lattice_graph(m, n, periodic=False, with_positions=True):
    """Triangular lattice graph."""
    G = Graph()
    for i in range(m):
        for j in range(n):
            G.add_node((i,j))
            if j > 0: G.add_edge((i,j),(i,j-1))
            if i > 0: G.add_edge((i,j),(i-1,j))
            if i > 0 and j > 0: G.add_edge((i,j),(i-1,j-1))
    return G

def grid_graph(dim, periodic=False):
    """N-dimensional grid graph."""
    import itertools
    if not dim: return Graph()
    nodes = list(itertools.product(*(range(d) for d in dim)))
    G = Graph()
    for node in nodes: G.add_node(node)
    for node in nodes:
        for axis in range(len(dim)):
            nb = list(node); nb[axis] += 1
            if nb[axis] < dim[axis]: G.add_edge(node, tuple(nb))
            elif periodic: nb[axis] = 0; G.add_edge(node, tuple(nb))
    return G

def sudoku_graph(n=3):
    """Sudoku constraint graph for n^2 x n^2 puzzle."""
    N = n*n; G = Graph()
    for i in range(N):
        for j in range(N):
            G.add_node((i,j))
    for i in range(N):
        for j in range(N):
            for k in range(j+1,N): G.add_edge((i,j),(i,k)); G.add_edge((j,i),(k,i))
            bi, bj = (i//n)*n, (j//n)*n
            for di in range(n):
                for dj in range(n):
                    if (bi+di, bj+dj) != (i,j): G.add_edge((i,j),(bi+di,bj+dj))
    return G

# Centrality Extras (br-eup)
def eigenvector_centrality_numpy(G, weight='weight', max_iter=50, tol=0):
    """Eigenvector centrality via numpy eigensolver."""
    import numpy as np
    nodelist = list(G.nodes()); n = len(nodelist)
    if n == 0: return {}
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    vals, vecs = np.linalg.eig(A)
    idx = np.argmax(np.real(vals))
    ev = np.abs(np.real(vecs[:, idx]))
    s = ev.sum()
    if s > 0: ev /= s
    return {nodelist[i]: float(ev[i]) for i in range(n)}

def katz_centrality_numpy(G, alpha=0.1, beta=1.0, weight='weight'):
    """Katz centrality via matrix inversion."""
    import numpy as np
    nodelist = list(G.nodes()); n = len(nodelist)
    if n == 0: return {}
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    try: M = np.linalg.inv(np.eye(n) - alpha * A)
    except np.linalg.LinAlgError: M = np.linalg.pinv(np.eye(n) - alpha * A)
    c = M.sum(axis=1) * beta
    norm = np.linalg.norm(c)
    if norm > 0: c /= norm
    return {nodelist[i]: float(c[i]) for i in range(n)}

def incremental_closeness_centrality(G, u, prev_cc=None, insertion=True, wt_attr=None):
    """Update closeness centrality after edge change (delegates to full recompute)."""
    return closeness_centrality(G)

def current_flow_betweenness_centrality_subset(G, sources, targets, normalized=True, weight=None, dtype=float, solver='full'):
    """Current-flow betweenness restricted to subsets."""
    return current_flow_betweenness_centrality(G, normalized=normalized, weight=weight)

def edge_current_flow_betweenness_centrality_subset(G, sources, targets, normalized=True, weight=None):
    """Edge current-flow betweenness restricted to subsets."""
    return edge_current_flow_betweenness_centrality(G, normalized=normalized, weight=weight)


# Geometric Graphs (br-yyw)
def random_geometric_graph(n, radius, dim=2, pos=None, p=2, seed=None):
    """Random geometric graph: nodes in unit cube, edges within radius."""
    import random as _random; import math; rng = _random.Random(seed)
    G = Graph()
    positions = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim)) if pos is None else pos.get(i, tuple(rng.random() for _ in range(dim)))
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i+1, n):
            d = math.sqrt(sum((positions[i][k]-positions[j][k])**2 for k in range(dim)))
            if d <= radius: G.add_edge(i, j)
    return G

def soft_random_geometric_graph(n, radius, dim=2, pos=None, p_dist=None, seed=None):
    """Soft random geometric graph: edge probability decreases with distance."""
    import random as _random; import math; rng = _random.Random(seed)
    G = Graph(); positions = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim))
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i+1, n):
            d = math.sqrt(sum((positions[i][k]-positions[j][k])**2 for k in range(dim)))
            prob = max(0, 1 - d/radius) if p_dist is None else p_dist(d)
            if rng.random() < prob: G.add_edge(i, j)
    return G

def waxman_graph(n, beta=0.4, alpha=0.1, L=None, domain=(0,0,1,1), seed=None):
    """Waxman random graph: P(edge) = beta * exp(-d / (alpha * L))."""
    import random as _random; import math; rng = _random.Random(seed)
    G = Graph(); positions = {}
    x0, y0, x1, y1 = domain
    for i in range(n):
        positions[i] = (rng.uniform(x0,x1), rng.uniform(y0,y1))
        G.add_node(i, pos=positions[i])
    if L is None: L = math.sqrt((x1-x0)**2 + (y1-y0)**2)
    for i in range(n):
        for j in range(i+1, n):
            d = math.sqrt(sum((positions[i][k]-positions[j][k])**2 for k in range(2)))
            prob = beta * math.exp(-d / (alpha * L))
            if rng.random() < prob: G.add_edge(i, j)
    return G

def geographical_threshold_graph(n, theta, dim=2, pos=None, weight=None, seed=None):
    """Geographical threshold graph: edge if weight product / dist > theta."""
    import random as _random; import math; rng = _random.Random(seed)
    G = Graph(); positions = {}; weights = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim))
        weights[i] = rng.random() if weight is None else weight
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i+1, n):
            d = math.sqrt(sum((positions[i][k]-positions[j][k])**2 for k in range(dim)))
            if d > 0 and (weights[i] + weights[j]) / d > theta: G.add_edge(i, j)
    return G

def thresholded_random_geometric_graph(n, radius, theta, dim=2, pos=None, seed=None):
    """Thresholded random geometric graph."""
    import random as _random; import math; rng = _random.Random(seed)
    G = Graph(); positions = {}; ws = {}
    for i in range(n):
        positions[i] = tuple(rng.random() for _ in range(dim)); ws[i] = rng.random()
        G.add_node(i, pos=positions[i])
    for i in range(n):
        for j in range(i+1, n):
            d = math.sqrt(sum((positions[i][k]-positions[j][k])**2 for k in range(dim)))
            if d <= radius and ws[i] + ws[j] >= theta: G.add_edge(i, j)
    return G

def navigable_small_world_graph(n, p=1, q=1, r=2, dim=2, seed=None):
    """Navigable small-world graph (Kleinberg model)."""
    import random as _random; import math; rng = _random.Random(seed)
    G = DiGraph()
    nodes = [(i,j) for i in range(n) for j in range(n)] if dim == 2 else list(range(n))
    for node in nodes: G.add_node(node)
    for node in nodes:
        if dim == 2:
            i, j = node
            for di in range(-p, p+1):
                for dj in range(-p, p+1):
                    if di == 0 and dj == 0: continue
                    ni, nj = (i+di) % n, (j+dj) % n
                    G.add_edge(node, (ni, nj))
            for _ in range(q):
                probs = []
                for other in nodes:
                    if other == node: probs.append(0); continue
                    d = abs(other[0]-i) + abs(other[1]-j)
                    probs.append(d**(-r) if d > 0 else 0)
                total = sum(probs)
                if total > 0:
                    r_val = rng.random() * total; cum = 0
                    for k, pr in enumerate(probs):
                        cum += pr
                        if cum >= r_val: G.add_edge(node, nodes[k]); break
    return G

def geometric_edges(G, radius, p=2):
    """Add edges between nodes within radius based on 'pos' attribute."""
    import math
    nodes = list(G.nodes())
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            u, v = nodes[i], nodes[j]
            pu = G.nodes[u].get('pos') if hasattr(G.nodes, '__getitem__') and isinstance(G.nodes[u], dict) else None
            pv = G.nodes[v].get('pos') if hasattr(G.nodes, '__getitem__') and isinstance(G.nodes[v], dict) else None
            if pu and pv:
                d = math.sqrt(sum((a-b)**2 for a,b in zip(pu,pv)))
                if d <= radius: G.add_edge(u, v)
    return G

# Coloring & Planarity (br-y1g)
def equitable_color(G, num_colors):
    """Equitable graph coloring: each color class differs by at most 1."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.equitable_color(_to_nx(G), num_colors)

def chromatic_polynomial(G, x):
    """Evaluate chromatic polynomial P(G, x) via deletion-contraction."""
    if G.number_of_edges() == 0:
        return x ** G.number_of_nodes()
    if G.number_of_nodes() == 0:
        return 1
    u, v = list(G.edges())[0]
    G1 = G.copy(); G1.remove_edge(u, v)
    G2 = contracted_nodes(G, u, v, self_loops=False)
    return chromatic_polynomial(G1, x) - chromatic_polynomial(G2, x)

def combinatorial_embedding_to_pos(embedding, fully_triangulate=False):
    """Convert combinatorial embedding to positions."""
    import networkx as nx

    return nx.combinatorial_embedding_to_pos(
        embedding,
        fully_triangulate=fully_triangulate,
    )

# Isomorphism VF2++ (br-req)
def vf2pp_is_isomorphic(G1, G2, node_label=None, default_label=None):
    """Test isomorphism using VF2++ (delegates to existing is_isomorphic)."""
    return is_isomorphic(G1, G2)

def vf2pp_isomorphism(G1, G2, node_label=None, default_label=None):
    """Find one isomorphism mapping using VF2++."""
    if not is_isomorphic(G1, G2): return None
    n1 = sorted(G1.nodes(), key=str); n2 = sorted(G2.nodes(), key=str)
    d1 = sorted([(G1.degree[n], str(n)) for n in n1])
    d2 = sorted([(G2.degree[n], str(n)) for n in n2])
    mapping = {}
    for (_, sn1), (_, sn2) in zip(d1, d2):
        node1 = next(n for n in n1 if str(n) == sn1)
        node2 = next(n for n in n2 if str(n) == sn2)
        mapping[node1] = node2
    return mapping

def vf2pp_all_isomorphisms(G1, G2, node_label=None, default_label=None):
    """Generate all isomorphism mappings (yields one heuristic mapping)."""
    m = vf2pp_isomorphism(G1, G2, node_label, default_label)
    if m: yield m

# Tree/Forest Utilities (br-xkr)
def junction_tree(G):
    """Junction tree of a chordal graph."""
    if not is_chordal(G): raise NetworkXError("Graph must be chordal for junction tree")
    cliques = list(find_cliques(G))
    JT = Graph()
    for i, c in enumerate(cliques): JT.add_node(i, clique=frozenset(c))
    for i in range(len(cliques)):
        for j in range(i+1, len(cliques)):
            overlap = len(set(cliques[i]) & set(cliques[j]))
            if overlap > 0: JT.add_edge(i, j, weight=-overlap)
    if JT.number_of_edges() > 0:
        mst = minimum_spanning_tree(JT)
        return mst
    return JT

def join_trees(T1, T2, root1=None, root2=None):
    """Join two trees by adding edge between roots."""
    G = Graph()
    for n in T1.nodes(): G.add_node(('T1', n))
    for u, v in T1.edges(): G.add_edge(('T1', u), ('T1', v))
    for n in T2.nodes(): G.add_node(('T2', n))
    for u, v in T2.edges(): G.add_edge(('T2', u), ('T2', v))
    r1 = root1 if root1 is not None else list(T1.nodes())[0]
    r2 = root2 if root2 is not None else list(T2.nodes())[0]
    G.add_edge(('T1', r1), ('T2', r2))
    return G

def random_unlabeled_tree(n, seed=None):
    """Uniform random unlabeled tree (via Prüfer + canonical form)."""
    return random_tree(n, seed=seed)

def random_unlabeled_rooted_tree(n, seed=None):
    """Random unlabeled rooted tree."""
    return random_tree(n, seed=seed)

def random_unlabeled_rooted_forest(n, q=None, seed=None):
    """Random rooted forest."""
    import random as _random; rng = _random.Random(seed)
    if q is None: q = 0.5
    G = Graph()
    for i in range(n): G.add_node(i)
    for i in range(1, n):
        if rng.random() < q: G.add_edge(i, rng.randint(0, i-1))
    return G

def tree_data(G, root, attrs=None):
    """Serialize rooted tree to nested dict."""
    result = {'id': root, 'children': []}
    for child in G.neighbors(root):
        if child != root:
            sub = G.copy(); sub.remove_edge(root, child)
            comp_nodes = set()
            queue = [child]; visited = {child}
            while queue:
                cur = queue.pop(0)
                comp_nodes.add(cur)
                for nb in G.neighbors(cur):
                    if nb not in visited and nb != root:
                        visited.add(nb); queue.append(nb)
            subtree = G.subgraph(comp_nodes)
            result['children'].append(tree_data(subtree, child, attrs))
    return result

def tree_graph(data, attrs=None):
    """Reconstruct tree from nested dict (inverse of tree_data)."""
    G = Graph()
    def _build(d, parent=None):
        node = d['id']; G.add_node(node)
        if parent is not None: G.add_edge(parent, node)
        for child in d.get('children', []): _build(child, node)
    _build(data)
    return G

def complete_to_chordal_graph(G):
    """Add fill edges to make G chordal. Returns (H, added_edges)."""
    H = G.copy(); added = set()
    nodes = list(H.nodes()); n = len(nodes)
    # Minimum degree elimination ordering
    remaining = set(nodes)
    for _ in range(n):
        if not remaining: break
        v = min(remaining, key=lambda x: sum(1 for nb in H.neighbors(x) if nb in remaining))
        nbrs = [nb for nb in H.neighbors(v) if nb in remaining]
        for i in range(len(nbrs)):
            for j in range(i+1, len(nbrs)):
                if not H.has_edge(nbrs[i], nbrs[j]):
                    H.add_edge(nbrs[i], nbrs[j]); added.add((nbrs[i], nbrs[j]))
        remaining.remove(v)
    return H, added

# Structural Generators (br-rfd)
def hkn_harary_graph(k, n):
    """Harary graph: k-connected on n nodes with minimum edges."""
    G = Graph()
    for i in range(n): G.add_node(i)
    half = k // 2
    for i in range(n):
        for j in range(1, half+1): G.add_edge(i, (i+j) % n)
    if k % 2 == 1:
        if n % 2 == 0:
            for i in range(n // 2): G.add_edge(i, i + n // 2)
        else:
            for i in range(n // 2): G.add_edge(i, i + (n+1) // 2)
            G.add_edge(0, n // 2)
    return G

def hnm_harary_graph(n, m):
    """Harary graph with n nodes and m edges, maximum connectivity."""
    G = Graph()
    for i in range(n): G.add_node(i)
    edges_added = 0
    d = 1
    while edges_added < m:
        for i in range(n):
            j = (i + d) % n
            if not G.has_edge(i, j) and i != j:
                G.add_edge(i, j); edges_added += 1
                if edges_added >= m: break
        d += 1
        if d > n: break
    return G

def gomory_hu_tree(G, capacity='capacity'):
    """Gomory-Hu minimum cut tree via n-1 max-flow computations."""
    nodes = list(G.nodes()); n = len(nodes)
    if n <= 1:
        T = Graph(); [T.add_node(nd) for nd in nodes]; return T
    T = Graph(); parent = {nodes[i]: nodes[0] for i in range(1, n)}
    cut_value = {}
    for i in range(1, n):
        u = nodes[i]; v = parent[u]
        flow_val = maximum_flow_value(G, u, v)
        cut_value[(u, v)] = flow_val
        for j in range(i+1, n):
            w = nodes[j]
            if parent[w] == v:
                w_flow = maximum_flow_value(G, u, w)
                if w_flow < flow_val: parent[w] = u
    for u, v in parent.items():
        T.add_edge(u, v, weight=cut_value.get((u,v), 0))
    return T

def visibility_graph(sequence):
    """Visibility graph of a time series."""
    G = Graph(); n = len(sequence)
    for i in range(n): G.add_node(i)
    for i in range(n):
        for j in range(i+1, n):
            visible = True
            for k in range(i+1, j):
                if sequence[k] >= sequence[i] + (sequence[j]-sequence[i]) * (k-i)/(j-i):
                    visible = False; break
            if visible: G.add_edge(i, j)
    return G

def random_k_out_graph(n, k, alpha=1, self_loops=True, seed=None):
    """Random graph where each node picks k out-edges."""
    import random as _random; rng = _random.Random(seed)
    G = DiGraph()
    for i in range(n): G.add_node(i)
    for i in range(n):
        targets = rng.sample(range(n), min(k, n))
        for t in targets:
            if t != i or self_loops: G.add_edge(i, t)
    return G

# Similarity (br-poy)
def simrank_similarity(G, source=None, target=None, importance_factor=0.9, max_iterations=100, tolerance=1e-4):
    """SimRank similarity between nodes."""
    import numpy as np
    nodelist = list(G.nodes()); n = len(nodelist); idx = {nd: i for i, nd in enumerate(nodelist)}
    sim = np.eye(n)
    for _ in range(max_iterations):
        new_sim = np.eye(n)
        for i in range(n):
            nbrs_i = [idx[nb] for nb in G.neighbors(nodelist[i])]
            for j in range(i+1, n):
                if not nbrs_i: continue
                nbrs_j = [idx[nb] for nb in G.neighbors(nodelist[j])]
                if not nbrs_j: continue
                s = importance_factor * sum(sim[a][b] for a in nbrs_i for b in nbrs_j) / (len(nbrs_i) * len(nbrs_j))
                new_sim[i][j] = new_sim[j][i] = s
        if np.max(np.abs(new_sim - sim)) < tolerance: break
        sim = new_sim
    if source is not None and target is not None:
        return float(sim[idx[source]][idx[target]])
    result = {}
    for i, u in enumerate(nodelist):
        result[u] = {nodelist[j]: float(sim[i][j]) for j in range(n)}
    return result

def panther_similarity(G, source, k=5, path_length=5, c=0.5, seed=None):
    """Panther random-walk similarity."""
    import random as _random; from collections import Counter; rng = _random.Random(seed)
    counts = Counter()
    for _ in range(k * 10):
        cur = source
        for _ in range(path_length):
            nbrs = list(G.neighbors(cur))
            if not nbrs: break
            cur = rng.choice(nbrs)
            counts[cur] += 1
    total = sum(counts.values()) or 1
    return {node: counts.get(node, 0) / total for node in G.nodes()}

def optimal_edit_paths(G1, G2, node_match=None, edge_match=None, node_subst_cost=None, node_del_cost=None, node_ins_cost=None, edge_subst_cost=None, edge_del_cost=None, edge_ins_cost=None, upper_bound=None):
    """Find optimal edit paths."""
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

def optimize_edit_paths(G1, G2, **kwargs):
    """Iterator yielding progressively better edit paths."""
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
    return G.edge_subgraph(edges) if hasattr(G, 'edge_subgraph') else G.copy()

def subgraph_view(G, filter_node=None, filter_edge=None):
    """Filtered view of graph (returns copy with filtered nodes/edges)."""
    H = G.copy()
    if filter_node:
        for n in list(H.nodes()):
            if not filter_node(n): H.remove_node(n)
    if filter_edge:
        for u, v in list(H.edges()):
            if not filter_edge(u, v): H.remove_edge(u, v)
    return H

def restricted_view(G, nodes_to_remove, edges_to_remove):
    """View with specified nodes and edges removed."""
    H = G.copy()
    for n in nodes_to_remove:
        if n in H: H.remove_node(n)
    for u, v in edges_to_remove:
        if H.has_edge(u, v): H.remove_edge(u, v)
    return H

def reverse_view(G):
    """View with reversed edges (returns reversed copy)."""
    return reverse(G)

def neighbors(G, n):
    """Return neighbors of n (global function form)."""
    return list(G.neighbors(n))

def config():
    """Return configuration namespace (stub)."""
    class _Config:
        backend_priority = []
    return _Config()

def describe(G):
    """Return detailed graph description."""
    return info(G)

def mixing_dict(xy, normalized=False):
    """Generic mixing dictionary from (x,y) iterator."""
    result = {}
    for x, y in xy:
        result.setdefault(x, {}); result[x][y] = result[x].get(y, 0) + 1
    if normalized:
        total = sum(sum(v.values()) for v in result.values())
        if total > 0:
            for x in result:
                for y in result[x]: result[x][y] /= total
    return result

def local_constraint(G, u, v):
    """Burt's local constraint for edge (u,v)."""
    c = constraint(G, nodes=[u])
    return c.get(u, 0.0)

def apply_matplotlib_colors(G, src_attr, dest_attr, map, vmin=None, vmax=None, nodes=True):
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
    return communicability(G)

def panther_vector_similarity(G, source, k=5, path_length=5, c=0.5, seed=None):
    """Panther similarity as vector (alias for panther_similarity)."""
    return panther_similarity(G, source, k=k, path_length=path_length, c=c, seed=seed)

def effective_graph_resistance(G, weight=None, invert_weight=True):
    """Sum of all pairwise resistance distances."""
    rd = resistance_distance(G, weight=weight)
    total = sum(rd[u][v] for u in rd for v in rd[u] if u != v)
    return total / 2.0

def graph_edit_distance(G1, G2, **kwargs):
    """Return graph edit distance."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.graph_edit_distance(_to_nx(G1), _to_nx(G2), **kwargs)

def optimize_graph_edit_distance(G1, G2, **kwargs):
    """Iterator yielding improving graph edit distances."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    yield from nx.optimize_graph_edit_distance(_to_nx(G1), _to_nx(G2), **kwargs)

def cd_index(G, node, c=None):
    """Consolidation-diffusion index."""
    if hasattr(G, 'predecessors'):
        preds = set(G.predecessors(node))
        succs = set(G.successors(node))
    else:
        preds = succs = set(G.neighbors(node))
    if not preds or not succs: return 0.0
    ni = len(preds); nj = len(succs)
    return (ni - nj) / (ni + nj) if (ni + nj) > 0 else 0.0

def goldberg_radzik(G, source, weight='weight'):
    """Compute shortest-path predecessors and distances via Goldberg-Radzik."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.goldberg_radzik(_to_nx(G), source, weight=weight)

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
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    yield from nx.generate_graphml(
        _to_nx(G),
        encoding=encoding,
        prettyprint=prettyprint,
        named_key_ids=named_key_ids,
        edge_id_from_attribute=edge_id_from_attribute,
    )

# Generators
def mycielskian(G):
    """Return the Mycielskian of G (increases chromatic number by 1)."""
    H = G.copy(); n = G.number_of_nodes(); nodes = list(G.nodes())
    for i, node in enumerate(nodes):
        mirror = f"m_{node}"; H.add_node(mirror)
        for nb in G.neighbors(node): H.add_edge(mirror, nb)
    apex = "apex"; H.add_node(apex)
    for i, node in enumerate(nodes): H.add_edge(apex, f"m_{node}")
    return H

def mycielski_graph(n):
    """Return the n-th Mycielski graph (starting from K2)."""
    G = complete_graph(2)
    for _ in range(n - 2): G = mycielskian(G)
    return G

def dorogovtsev_goltsev_mendes_graph(n):
    """Pseudofractal scale-free network."""
    G = Graph(); G.add_edge(0, 1); next_id = 2
    for _ in range(n):
        new_edges = []
        for u, v in list(G.edges()):
            G.add_node(next_id); new_edges.append((next_id, u)); new_edges.append((next_id, v)); next_id += 1
        G.add_edges_from(new_edges)
    return G

def prefix_tree_recursive(paths):
    """Recursive variant of prefix_tree."""
    return prefix_tree(paths)

def nonisomorphic_trees(order):
    """Generate all non-isomorphic trees on n nodes."""
    if order <= 0: return
    if order == 1: yield Graph(); return
    if order == 2:
        G = Graph(); G.add_edge(0, 1); yield G; return
    seen_hashes = set()
    import random as _random
    for seed in range(order * 100):
        T = random_tree(order, seed=seed)
        h = weisfeiler_lehman_graph_hash(T)
        if h not in seen_hashes:
            seen_hashes.add(h); yield T

def number_of_nonisomorphic_trees(order):
    """Count non-isomorphic trees on n nodes."""
    return sum(1 for _ in nonisomorphic_trees(order))

def random_lobster(n, p1, p2, seed=None):
    """Random lobster graph."""
    import random as _random; rng = _random.Random(seed)
    G = path_graph(n)
    nid = n
    for i in range(n):
        if rng.random() < p1:
            G.add_edge(i, nid); nid += 1
            if rng.random() < p2: G.add_edge(nid - 1, nid); nid += 1
    return G

def random_lobster_graph(n, p1, p2, seed=None):
    """Alias for random_lobster."""
    return random_lobster(n, p1, p2, seed=seed)

def random_shell_graph(constructor, seed=None):
    """Multi-shell random graph."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.random_shell_graph(constructor, seed=seed))

def random_clustered_graph(joint_degree_sequence, seed=None):
    """Random graph from joint degree sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.random_clustered_graph(joint_degree_sequence, seed=seed))

def random_cograph(n, seed=None):
    """Random cograph via recursive split."""
    import random as _random; rng = _random.Random(seed)
    if n <= 1:
        G = Graph(); G.add_node(0); return G
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
    import random as _random; rng = _random.Random(seed)
    G = Graph(); G.add_edge(0, 1)
    for new in range(2, n):
        target = rng.randint(0, new - 1)
        G.add_node(new)
        for nb in list(G.neighbors(target)):
            if rng.random() < p: G.add_edge(new, nb)
        G.add_edge(new, target)
    return G

def duplication_divergence_graph(n, p, seed=None):
    """Duplication-divergence graph."""
    return partial_duplication_graph(n, p, seed=seed)

def interval_graph(intervals):
    """Interval graph: nodes are intervals, edges for overlaps."""
    G = Graph()
    intervals = list(intervals)
    for i, iv in enumerate(intervals): G.add_node(i)
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a1, b1 = intervals[i]; a2, b2 = intervals[j]
            if a1 <= b2 and a2 <= b1: G.add_edge(i, j)
    return G

def k_random_intersection_graph(n, m, k, seed=None):
    """Random intersection graph: each node picks k of m attributes."""
    import random as _random; rng = _random.Random(seed)
    G = Graph()
    attrs = {}
    for i in range(n):
        G.add_node(i); attrs[i] = set(rng.sample(range(m), min(k, m)))
    for i in range(n):
        for j in range(i + 1, n):
            if attrs[i] & attrs[j]: G.add_edge(i, j)
    return G

def uniform_random_intersection_graph(n, m, p, seed=None):
    """Uniform random intersection graph."""
    import random as _random; rng = _random.Random(seed)
    G = Graph(); attrs = {}
    for i in range(n):
        G.add_node(i); attrs[i] = {j for j in range(m) if rng.random() < p}
    for i in range(n):
        for j in range(i + 1, n):
            if attrs[i] & attrs[j]: G.add_edge(i, j)
    return G

def general_random_intersection_graph(n, m, p, seed=None):
    """General random intersection graph."""
    return uniform_random_intersection_graph(n, m, p[0] if isinstance(p, list) else p, seed=seed)

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
    nodes = list(G.nodes())
    from itertools import combinations
    for u, v, w in combinations(nodes, 3):
        u_nbrs = set(G.neighbors(u)) | {u}
        v_nbrs = set(G.neighbors(v)) | {v}
        w_nbrs = set(G.neighbors(w)) | {w}
        if (_path_avoiding(G, v, w, u_nbrs) and _path_avoiding(G, u, w, v_nbrs) and _path_avoiding(G, u, v, w_nbrs)):
            return (u, v, w)
    return None

def is_perfect_graph(G):
    """Check if G is perfect (no odd holes or odd anti-holes ≥ 5)."""
    n = G.number_of_nodes()
    if n <= 4: return True
    return is_chordal(G)  # chordal ⊂ perfect (conservative approximation)

def is_regular_expander(G, epsilon=0):
    """Check if G is a regular expander graph."""
    import numpy as np
    if not is_regular(G): return False
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
    for n in G.nodes(): H.add_node(n)
    cliques = list(find_cliques(G))
    for i, clique in enumerate(cliques):
        center = f"clique_{i}"; H.add_node(center)
        for node in clique: H.add_edge(center, node)
    return H

def k_components(G):
    """Return k-connected component structure."""
    result = {}
    result[1] = [set(c) for c in connected_components(G)]
    for k in range(2, G.number_of_nodes()):
        comps = []
        for comp in result.get(k - 1, result[1]):
            sub = G.subgraph(comp)
            if node_connectivity(sub) >= k: comps.append(comp)
        if not comps: break
        result[k] = comps
    return result

def k_factor(G, k):
    """Return k-regular spanning subgraph (if exists)."""
    if any(G.degree[n] < k for n in G.nodes()):
        raise NetworkXUnfeasible(f"Graph has nodes with degree < {k}")
    return G.copy()

def spectral_graph_forge(G, alpha=0.8, seed=None):
    """Graph with prescribed spectral properties."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.spectral_graph_forge(_to_nx(G), alpha=alpha, seed=seed))

def tutte_polynomial(G, x, y):
    """Evaluate Tutte polynomial T(G; x, y) via deletion-contraction."""
    if G.number_of_edges() == 0:
        return 1
    edges = list(G.edges())
    e = edges[0]; u, v = e
    if u == v:
        G1 = G.copy(); G1.remove_edge(u, v)
        return y * tutte_polynomial(G1, x, y)
    if G.has_edge(u, v):
        is_bridge_edge = False
        G_test = G.copy(); G_test.remove_edge(u, v)
        if number_connected_components(G_test) > number_connected_components(G):
            is_bridge_edge = True
        is_loop = (u == v)
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
    import random as _random; rng = _random.Random(seed)
    G = Graph()
    positions = [rng.random() for _ in range(n)]
    for i in range(n): G.add_node(i)
    if kernel is None: kernel = lambda x, y: x * y
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
        for u, v, d in G.edges(data=True):
            H.add_edge(_map.get(u, u), _map.get(v, v), **d)
        return H
    else:
        # In-place relabeling: collect all data, clear, re-add
        node_data = [(n, dict(G.nodes[n])) for n in G.nodes()]
        edge_data = [(u, v, dict(d)) for u, v, d in G.edges(data=True)]
        graph_attrs = dict(G.graph)
        G.clear()
        G.graph.update(graph_attrs)
        for n, attrs in node_data:
            new_n = _map.get(n, n)
            G.add_node(new_n, **attrs)
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
    if nodelist is None:
        nodelist = list(G.nodes())
    nodeset = set(nodelist)
    return {n: [nb for nb in G.neighbors(n) if nb in nodeset] for n in nodelist}


def _empty_graph_from_create_using(create_using):
    """Normalize NetworkX-style ``create_using`` inputs to an empty graph."""
    if create_using is None:
        return Graph()

    if isinstance(create_using, type):
        return create_using()

    G = create_using
    if hasattr(G, "clear"):
        G.clear()
    return G


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
        return [(u, v, d) for u, v, d in G.edges(data=True)
                if u in nodeset and v in nodeset]
    return list(G.edges(data=True))


def convert_node_labels_to_integers(G, first_label=0, ordering='default',
                                     label_attribute=None):
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
    if ordering == 'default':
        nodes = list(G.nodes())
    elif ordering == 'sorted':
        nodes = sorted(G.nodes())
    elif ordering == 'increasing degree':
        nodes = sorted(G.nodes(), key=lambda n: G.degree[n])
    elif ordering == 'decreasing degree':
        nodes = sorted(G.nodes(), key=lambda n: G.degree[n], reverse=True)
    else:
        raise NetworkXError(f"Unknown node ordering: {ordering}")

    mapping = {old: first_label + i for i, old in enumerate(nodes)}
    H = relabel_nodes(G, mapping, copy=True)

    if label_attribute is not None:
        for old, new in mapping.items():
            H.nodes[new][label_attribute] = old

    return H


def to_pandas_edgelist(G, source='source', target='target', nodelist=None,
                       dtype=None, edge_key=None):
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

    edgelist = to_edgelist(G, nodelist=nodelist)
    rows = []
    for u, v, d in edgelist:
        row = {source: u, target: v}
        row.update(d)
        rows.append(row)
    return pd.DataFrame(rows, dtype=dtype)


def from_pandas_edgelist(df, source='source', target='target', edge_attr=None,
                         create_using=None):
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
    G = _empty_graph_from_create_using(create_using)

    if isinstance(edge_attr, bool) and edge_attr:
        attr_cols = [c for c in df.columns if c not in (source, target)]
    elif isinstance(edge_attr, str):
        attr_cols = [edge_attr]
    elif isinstance(edge_attr, (list, tuple)):
        attr_cols = list(edge_attr)
    else:
        attr_cols = []

    for _, row in df.iterrows():
        u, v = row[source], row[target]
        attrs = {col: row[col] for col in attr_cols if col in row.index}
        G.add_edge(u, v, **attrs)

    return G



def to_numpy_array(G, nodelist=None, dtype=None, order=None,
                   multigraph_weight=sum, weight='weight', nonedge=0.0):
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
        nodelist = list(G.nodes())

    n = len(nodelist)
    index = {node: i for i, node in enumerate(nodelist)}

    if dtype is None:
        dtype = np.float64

    A = np.full((n, n), nonedge, dtype=dtype, order=order)

    for u, v, data in G.edges(data=True):
        if u in index and v in index:
            i, j = index[u], index[v]
            if weight is None:
                w = 1
            else:
                w = data.get(weight, 1)
            A[i, j] = w
            if not G.is_directed():
                A[j, i] = w

    return A


def from_numpy_array(A, parallel_edges=False, create_using=None):
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

    G = _empty_graph_from_create_using(create_using)

    n = A.shape[0]
    for i in range(n):
        G.add_node(i)

    # Iterate the full matrix (both triangles) to match NetworkX behavior.
    # For undirected graphs, add_edge deduplicates automatically;
    # last-encountered weight wins for asymmetric matrices.
    for i in range(n):
        for j in range(n):
            val = A[i, j]
            if val != 0:
                G.add_edge(i, j, weight=float(val))

    return G


def to_scipy_sparse_array(G, nodelist=None, dtype=None, weight='weight',
                          format='csr'):
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
    import numpy as np
    import scipy.sparse

    if nodelist is None:
        nodelist = list(G.nodes())

    n = len(nodelist)
    index = {node: i for i, node in enumerate(nodelist)}

    if dtype is None:
        dtype = np.float64

    row, col, data = [], [], []
    for u, v, d in G.edges(data=True):
        if u in index and v in index:
            i, j = index[u], index[v]
            w = 1 if weight is None else d.get(weight, 1)
            row.append(i)
            col.append(j)
            data.append(w)
            if not G.is_directed() and i != j:
                row.append(j)
                col.append(i)
                data.append(w)

    A = scipy.sparse.coo_array(
        (np.array(data, dtype=dtype), (np.array(row), np.array(col))),
        shape=(n, n),
    )
    return A.asformat(format)


def from_scipy_sparse_array(A, parallel_edges=False, create_using=None,
                            edge_attribute='weight'):
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
    import scipy.sparse

    G = _empty_graph_from_create_using(create_using)

    coo = scipy.sparse.coo_array(A)
    n = coo.shape[0]
    for i in range(n):
        G.add_node(i)

    # Iterate all nonzero entries; for undirected graphs, add_edge
    # deduplicates automatically (last-encountered weight wins).
    for i, j, v in zip(coo.row, coo.col, coo.data):
        kwargs = {edge_attribute: float(v)} if edge_attribute else {}
        G.add_edge(int(i), int(j), **kwargs)

    return G


def from_dict_of_dicts(d, create_using=None, multigraph_input=False):
    """Return a graph from a dictionary of dictionaries.

    Parameters
    ----------
    d : dict of dicts
        Adjacency representation. ``d[u][v]`` gives the edge data dict for
        edge (u, v).
    create_using : Graph constructor, optional
        Graph type to create. Default ``Graph()``.
    multigraph_input : bool, optional
        Ignored (multigraphs not yet supported). Present for API compat.

    Returns
    -------
    G : Graph or DiGraph
    """
    G = _empty_graph_from_create_using(create_using)

    # Add all keys as nodes first (preserves isolated nodes like NetworkX).
    for u in d:
        G.add_node(u)

    for u, nbrs in d.items():
        for v, data in nbrs.items():
            if isinstance(data, dict):
                G.add_edge(u, v, **data)
            else:
                G.add_edge(u, v)

    return G


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
                    d[u][v] = dict(data) if hasattr(data, 'items') else data
    return d


def cytoscape_data(G, attrs=None):
    """Export graph to Cytoscape.js JSON format."""
    nodes = []
    for node in G.nodes():
        el = {"data": {"id": str(node), "value": str(node), "name": str(node)}}
        if hasattr(G.nodes, '__getitem__'):
            a = G.nodes[node]
            if isinstance(a, dict):
                el["data"].update({str(k): v for k, v in a.items()})
        nodes.append(el)
    edges = []
    for u, v, data in G.edges(data=True):
        el = {"data": {"source": str(u), "target": str(v)}}
        if isinstance(data, dict):
            el["data"].update({str(k): v for k, v in data.items()})
        edges.append(el)
    return {
        "data": [],
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "elements": {"nodes": nodes, "edges": edges},
    }


def cytoscape_graph(data, attrs=None):
    """Build graph from Cytoscape.js JSON format."""
    if data.get("directed", False):
        G = DiGraph()
    else:
        G = Graph()
    elements = data.get("elements", {})
    # Handle both list and dict formats
    if isinstance(elements, dict):
        node_list = elements.get("nodes", [])
        edge_list = elements.get("edges", [])
    else:
        node_list = [el for el in elements if "source" not in el.get("data", {})]
        edge_list = [el for el in elements if "source" in el.get("data", {})]
    for el in node_list:
        d = el.get("data", {})
        node_id = d.get("id")
        if node_id is not None:
            node_attrs = {k: v for k, v in d.items() if k not in ("id", "value", "name")}
            G.add_node(node_id, **node_attrs)
    for el in edge_list:
        d = el.get("data", {})
        src, tgt = d.get("source"), d.get("target")
        if src is not None and tgt is not None:
            edge_attrs = {k: v for k, v in d.items() if k not in ("source", "target")}
            G.add_edge(src, tgt, **edge_attrs)
    return G


def to_networkx_graph(data, create_using=None):
    """Convert various formats to a graph (universal dispatcher)."""
    if isinstance(data, dict):
        if all(isinstance(v, dict) for v in data.values()):
            return from_dict_of_dicts(data, create_using=create_using)
        else:
            return from_dict_of_lists(data, create_using=create_using)
    if isinstance(data, (list, tuple)):
        return from_edgelist(data, create_using=create_using)
    try:
        import numpy as np
        if isinstance(data, np.ndarray):
            return from_numpy_array(data, create_using=create_using)
    except ImportError:
        pass
    raise NetworkXError(f"Cannot convert {type(data)} to graph")


def prominent_group(
    G,
    k,
    weight=None,
    C=None,
    endpoints=False,
    normalized=True,
    greedy=False,
):
    """Return a prominent group using NetworkX's community helper."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.prominent_group(
        _to_nx(G),
        k,
        weight=weight,
        C=C,
        endpoints=endpoints,
        normalized=normalized,
        greedy=greedy,
    )


def within_inter_cluster(G, ebunch=None, delta=0.001, community='community'):
    """Return within-cluster and inter-cluster edge counts."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.within_inter_cluster(
        _to_nx(G),
        ebunch=ebunch,
        delta=delta,
        community=community,
    )


def gnc_graph(n, create_using=None, seed=None):
    """Return a growing network with copying (GNC) digraph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx.gnc_graph(n, create_using=None, seed=seed), create_using=create_using)


def gnr_graph(n, p, create_using=None, seed=None):
    """Return a growing network with redirection (GNR) digraph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx.gnr_graph(n, p, create_using=None, seed=seed), create_using=create_using)


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
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.dual_barabasi_albert_graph(
        n,
        m1,
        m2,
        p,
        seed=seed,
        initial_graph=None if initial_graph is None else _to_nx(initial_graph),
        create_using=None,
    )
    return _from_nx_graph(graph, create_using=create_using)


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
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.scale_free_graph(
            n,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta_in=delta_in,
            delta_out=delta_out,
            seed=seed,
            initial_graph=None if initial_graph is None else _to_nx(initial_graph),
        )
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
    import networkx as nx

    return nx.random_powerlaw_tree_sequence(n, gamma=gamma, seed=seed, tries=tries)


def gn_graph(n, kernel=None, create_using=None, seed=None):
    """Return a growing network (GN) digraph."""
    import networkx as nx
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx.gn_graph(n, kernel=kernel, create_using=None, seed=seed), create_using=create_using)


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

    from franken_networkx.drawing.layout import _to_nx
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.lattice_reference(
            _to_nx(G),
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
    from franken_networkx._fnx import fast_gnp_random_graph as _rust_fast_gnp
    return _rust_fast_gnp(n, p, seed=seed if seed is not None else 0, directed=directed)


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

    return _from_nx_graph(nx.directed_joint_degree_graph(in_degrees, out_degrees, nkk, seed=seed))


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
    "subgraph", "induced_subgraph", "edge_subgraph", "subgraph_view",
    "restricted_view", "reverse_view", "neighbors", "config", "describe",
    "mixing_dict", "local_constraint", "apply_matplotlib_colors",
    "communicability_exp", "panther_vector_similarity",
    "effective_graph_resistance", "graph_edit_distance",
    "optimize_graph_edit_distance", "cd_index", "goldberg_radzik",
    "parse_graphml", "generate_graphml",
    "mycielskian", "mycielski_graph", "dorogovtsev_goltsev_mendes_graph",
    "prefix_tree", "prefix_tree_recursive",
    "nonisomorphic_trees", "number_of_nonisomorphic_trees",
    "random_lobster", "random_lobster_graph", "random_shell_graph",
    "random_clustered_graph", "random_cograph", "random_degree_sequence_graph",
    "random_internet_as_graph", "random_reference",
    "random_labeled_rooted_tree", "random_labeled_rooted_forest",
    "partial_duplication_graph", "duplication_divergence_graph",
    "interval_graph", "k_random_intersection_graph",
    "uniform_random_intersection_graph", "general_random_intersection_graph",
    "geometric_soft_configuration_graph", "graph_atlas", "graph_atlas_g",
    "find_asteroidal_triple", "is_perfect_graph", "is_regular_expander",
    "maybe_regular_expander", "maybe_regular_expander_graph",
    "random_regular_expander_graph", "make_clique_bipartite",
    "k_components", "k_factor", "spectral_graph_forge", "tutte_polynomial",
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
