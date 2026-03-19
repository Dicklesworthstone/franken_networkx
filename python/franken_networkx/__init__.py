"""FrankenNetworkX — A high-performance Rust-backed drop-in replacement for NetworkX.

Usage::

    import franken_networkx as fnx

    G = fnx.Graph()
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
)


# Drawing — thin delegation to NetworkX/matplotlib (lazy import)
from franken_networkx.drawing import (
    draw,
    draw_circular,
    draw_kamada_kawai,
    draw_planar,
    draw_random,
    draw_shell,
    draw_spectral,
    draw_spring,
    circular_layout,
    kamada_kawai_layout,
    planar_layout,
    random_layout,
    shell_layout,
    spectral_layout,
    spring_layout,
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
            if not G.is_directed():
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
    "from_pandas_edgelist",
    "to_dict_of_dicts",
    "to_dict_of_lists",
    "to_edgelist",
    "to_pandas_edgelist",
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
    # Drawing
    "draw",
    "draw_circular",
    "draw_kamada_kawai",
    "draw_planar",
    "draw_random",
    "draw_shell",
    "draw_spectral",
    "draw_spring",
    "circular_layout",
    "kamada_kawai_layout",
    "planar_layout",
    "random_layout",
    "shell_layout",
    "spectral_layout",
    "spring_layout",
]
