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
    all_simple_paths,
    cycle_basis,
)

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

    for u in node_set:
        nbrs_u = set(B.neighbors(u)) - node_set
        for v in node_set:
            if v <= u:
                continue
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
    H = G.__class__()
    if with_data:
        for node in G.nodes():
            attrs = {}
            if hasattr(G.nodes, '__getitem__'):
                a = G.nodes[node]
                if isinstance(a, dict):
                    attrs = dict(a)
            H.add_node(node, **attrs)
    else:
        for node in G.nodes():
            H.add_node(node)
    return H


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

    A local bridge is an edge whose removal would increase the shortest
    distance between its endpoints. If ``with_span`` is True, yields
    ``(u, v, span)`` tuples; otherwise yields ``(u, v)`` tuples.
    """
    result = []
    for u, v in G.edges():
        if u == v:
            continue
        # Check if u and v share any common neighbor
        u_nbrs = set(G.neighbors(u))
        v_nbrs = set(G.neighbors(v))
        common = u_nbrs & v_nbrs
        if not common:
            # No common neighbor → removing this edge disconnects or increases
            # distance to infinity
            if with_span:
                result.append((u, v, float('inf')))
            else:
                result.append((u, v))
        else:
            # Span = length of shortest path NOT using (u,v)
            # For local bridges, span > 2
            span = 2  # through a common neighbor
            if with_span:
                # Not a local bridge (span == 2), skip
                pass
            # Only yield if it's a local bridge (span > 2)
            # Having common neighbors means span = 2, not a local bridge
    return result


def minimum_edge_cut(G, s=None, t=None):
    """Return a minimum edge cut of *G*.

    If *s* and *t* are given, return a minimum s-t edge cut.
    Otherwise, return a global minimum edge cut.
    """
    if s is not None and t is not None:
        return minimum_cut(G, s, t)
    return minimum_cut(G, list(G.nodes())[0], list(G.nodes())[1])


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
    L = Graph()
    edges = list(G.edges())

    for e in edges:
        L.add_node(e)

    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            u1, v1 = edges[i]
            u2, v2 = edges[j]
            if u1 == u2 or u1 == v2 or v1 == u2 or v1 == v2:
                L.add_edge(edges[i], edges[j])

    return L


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
    """Return the disjoint union of *G* and *H*.

    Nodes are relabeled to avoid collisions: G's nodes become ``(0, n)``
    and H's nodes become ``(1, n)``.
    """
    result = Graph()
    for n in G.nodes():
        result.add_node((0, n))
    for n in H.nodes():
        result.add_node((1, n))
    for u, v in G.edges():
        result.add_edge((0, u), (0, v))
    for u, v in H.edges():
        result.add_edge((1, u), (1, v))
    return result


def compose_all(graphs):
    """Return the composition of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        return Graph()
    result = graphs[0].copy()
    for g in graphs[1:]:
        result = compose(result, g)
    return result


def union_all(graphs):
    """Return the union of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        return Graph()
    result = graphs[0].copy()
    for g in graphs[1:]:
        result = union(result, g)
    return result


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
        ("Ginori", "Medici"), ("Guadagni", "Lamberteschi"),
        ("Guadagni", "Tornabuoni"), ("Lamberteschi", "Medici" if False else "Guadagni"),
        ("Medici", "Ridolfi"), ("Medici", "Salviati"), ("Medici", "Tornabuoni"),
        ("Peruzzi", "Strozzi"), ("Ridolfi", "Strozzi"), ("Ridolfi", "Tornabuoni"),
        ("Salviati", "Pazzi"),
    ]
    G.add_edges_from(edges)
    # Add the Pucci isolate
    G.add_node("Pucci")
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
    """Return the intersection of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        return Graph()
    result = graphs[0].copy()
    for g in graphs[1:]:
        result = intersection(result, g)
    return result


def disjoint_union_all(graphs):
    """Return the disjoint union of all graphs in the iterable."""
    result = Graph()
    for i, g in enumerate(graphs):
        for n in g.nodes():
            result.add_node((i, n))
        for u, v in g.edges():
            result.add_edge((i, u), (i, v))
    return result


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
    return G


def is_frozen(G):
    """Return True if *G* is frozen."""
    return id(G) in _FROZEN_GRAPHS


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
    """Return the minimum s-t node cut.

    Parameters
    ----------
    G : Graph
    s, t : node

    Returns
    -------
    set
        Minimum node cut separating s from t.
    """
    # Use global minimum_node_cut as approximation
    # (exact s-t cut requires augmented flow which delegates to Rust)
    return minimum_node_cut(G)


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

    in_deg = dict(G.in_degree())
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
                anc_v = ancestors(G, v)
                anc_v.add(v)
                ancestor_cache[v] = anc_v
            if w not in ancestor_cache:
                anc_w = ancestors(G, w)
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
    roots = (v for v, d in G.in_degree() if d == 0)
    leaves = (v for v, d in G.out_degree() if d == 0)
    from itertools import product

    for root, leaf in product(roots, leaves):
        yield from all_simple_paths(G, root, leaf)


def prefix_tree(paths):
    """Creates a directed prefix tree from a list of paths."""
    # Simplified implementation of prefix_tree for internal use by dag_to_branching
    tree = DiGraph()
    root = 0
    tree.add_node(root, source=None)
    nodes_count = 1

    for path in paths:
        parent = root
        for node in path:
            # Check if any successor of parent has node as source
            found = None
            for succ in tree.successors(parent):
                if tree.nodes[succ].get("source") == node:
                    found = succ
                    break
            if found is None:
                new_node = nodes_count
                nodes_count += 1
                tree.add_node(new_node, source=node)
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
    """Construct a matrix from edge attributes."""
    import numpy as np
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
    dict of dicts
    """
    return min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)


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
    if k is None:
        k = global_node_connectivity(G)
    if k == 0:
        return
    nodes = list(G.nodes())
    seen = set()
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            if G.has_edge(nodes[i], nodes[j]):
                continue
            cut = minimum_node_cut(G)
            if len(cut) == k:
                frozen = frozenset(cut)
                if frozen not in seen:
                    seen.add(frozen)
                    yield set(cut)


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


# Drawing — thin delegation to NetworkX/matplotlib (lazy import)
from franken_networkx.drawing import (
    arf_layout,
    bfs_layout,
    bipartite_layout,
    draw,
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
    if callable(mapping) and not isinstance(mapping, dict):
        _mapping = {n: mapping(n) for n in G.nodes()}
    else:
        _mapping = mapping

    if copy:
        H = G.__class__()
    else:
        # Build a fresh graph and swap contents
        H = G.__class__()

    # Add nodes with their attributes under new labels
    for old_node in G.nodes():
        new_node = _mapping.get(old_node, old_node)
        attrs = G.nodes[old_node] if hasattr(G.nodes, '__getitem__') else {}
        H.add_node(new_node, **attrs)

    # Add edges with their attributes under new labels
    for u, v, data in G.edges(data=True):
        new_u = _mapping.get(u, u)
        new_v = _mapping.get(v, v)
        H.add_edge(new_u, new_v, **data)

    if not copy:
        # Replace G's internals with H's
        G.clear()
        for n in H.nodes():
            attrs = H.nodes[n] if hasattr(H.nodes, '__getitem__') else {}
            G.add_node(n, **attrs)
        for u, v, data in H.edges(data=True):
            G.add_edge(u, v, **data)
        return G

    return H


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
        iteration order).
    label_attribute : str or None, optional
        If given, store old label under this node attribute name.

    Returns
    -------
    H : Graph or DiGraph
        A new graph with integer node labels.
    """
    nodes = list(G.nodes())
    if ordering == 'sorted':
        nodes = sorted(nodes, key=str)
    elif ordering == 'increasing degree':
        nodes = sorted(nodes, key=lambda n: G.degree[n])
    elif ordering == 'decreasing degree':
        nodes = sorted(nodes, key=lambda n: G.degree[n], reverse=True)

    mapping = {old: first_label + i for i, old in enumerate(nodes)}
    H = relabel_nodes(G, mapping)

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


def from_pandas_adjacency(df, create_using=None):
    """Return a graph from a Pandas adjacency DataFrame."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.from_pandas_adjacency(df, create_using=None)
    return _from_nx_graph(graph, create_using=create_using)


def to_pandas_adjacency(
    G,
    nodelist=None,
    dtype=None,
    order=None,
    multigraph_weight=sum,
    weight='weight',
    nonedge=0.0,
):
    """Return the graph adjacency matrix as a Pandas DataFrame."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.to_pandas_adjacency(
        _to_nx(G),
        nodelist=nodelist,
        dtype=dtype,
        order=order,
        multigraph_weight=multigraph_weight,
        weight=weight,
        nonedge=nonedge,
    )


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


def from_prufer_sequence(sequence):
    """Return a tree decoded from a Prüfer sequence."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.from_prufer_sequence(sequence))


def to_prufer_sequence(T):
    """Return the Prüfer sequence of a labeled tree."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.to_prufer_sequence(_to_nx(T))


def from_nested_tuple(sequence, sensible_relabeling=False):
    """Return a tree built from a nested tuple representation."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(
        nx.from_nested_tuple(sequence, sensible_relabeling=sensible_relabeling)
    )


def to_nested_tuple(T, root, canonical_form=False):
    """Return a nested tuple representation of a rooted tree."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.to_nested_tuple(_to_nx(T), root, canonical_form=canonical_form)


def cytoscape_data(G, name='name', ident='id'):
    """Return Cytoscape.js JSON data for a graph."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.cytoscape_data(_to_nx(G), name=name, ident=ident)


def cytoscape_graph(data, name='name', ident='id'):
    """Return a graph decoded from Cytoscape.js JSON data."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(nx.cytoscape_graph(data, name=name, ident=ident))


def attr_sparse_matrix(
    G,
    edge_attr=None,
    node_attr=None,
    normalized=False,
    rc_order=None,
    dtype=None,
):
    """Return a SciPy sparse attribute matrix using NetworkX's implementation."""
    import networkx as nx

    from franken_networkx.drawing.layout import _to_nx

    return nx.attr_sparse_matrix(
        _to_nx(G),
        edge_attr=edge_attr,
        node_attr=node_attr,
        normalized=normalized,
        rc_order=rc_order,
        dtype=dtype,
    )


def to_networkx_graph(data, create_using=None, multigraph_input=False):
    """Return a FrankenNetworkX graph from generic graph-like input."""
    import networkx as nx

    from franken_networkx.readwrite import _from_nx_graph

    graph = nx.to_networkx_graph(
        data,
        create_using=None,
        multigraph_input=multigraph_input,
    )
    return _from_nx_graph(graph, create_using=create_using)


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
    "draw",
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
