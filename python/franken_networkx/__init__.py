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

import base64
from collections import Counter, defaultdict, deque
from collections.abc import Collection, Generator, Iterable, Iterator, Mapping
from copy import deepcopy
from enum import Enum
import gzip
from heapq import heappop, heappush
import io
import itertools
from itertools import combinations, count
import math
import numbers
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
    average_shortest_path_length as _raw_average_shortest_path_length,
    bellman_ford_path,
    dijkstra_path as _raw_dijkstra_path,
    has_path,
    multi_source_dijkstra as _raw_multi_source_dijkstra,
    shortest_path as _raw_shortest_path,
    shortest_path_length as _shortest_path_length_raw,
)


def _networkx_graph_for_parity(G):
    if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        from franken_networkx.backend import _fnx_to_nx

        return _fnx_to_nx(G)
    return G


def _has_negative_edge_weight_for_dijkstra(G, weight):
    if not isinstance(weight, str):
        return False

    if G.is_multigraph():
        edge_iter = G.edges(keys=True, data=True)
        attrs_iter = (attrs for _, _, _, attrs in edge_iter)
    else:
        edge_iter = G.edges(data=True)
        attrs_iter = (attrs for _, _, attrs in edge_iter)

    for attrs in attrs_iter:
        value = attrs.get(weight, 1)
        if isinstance(value, numbers.Real) and math.isfinite(value) and value < 0:
            return True
    return False


def _should_delegate_dijkstra_to_networkx(G, weight):
    return _has_negative_edge_weight_for_dijkstra(G, weight)


def _raise_translated_networkx_exception(exc):
    import networkx as nx

    if isinstance(exc, nx.NetworkXException):
        translated_type = globals().get(type(exc).__name__)
        if (
            isinstance(translated_type, type)
            and issubclass(translated_type, Exception)
            and translated_type is not type(exc)
        ):
            raise translated_type(*exc.args) from exc
    raise exc


def _call_networkx_for_parity(name, G, /, *args, **kwargs):
    import networkx as nx

    try:
        result = getattr(nx, name)(_networkx_graph_for_parity(G), *args, **kwargs)
    except Exception as exc:
        _raise_translated_networkx_exception(exc)

    if isinstance(result, Iterator):
        def _wrapped_iterator():
            try:
                yield from result
            except Exception as exc:
                _raise_translated_networkx_exception(exc)

        return _wrapped_iterator()

    return result


def average_shortest_path_length(G, weight=None, method=None):
    """Return the average shortest path length.

    Matches ``networkx.average_shortest_path_length`` signature.
    """
    if method not in (None, "unweighted", "dijkstra", "bellman-ford"):
        raise ValueError(f"method not supported: {method}")
    if weight is not None and method in (None, "dijkstra") and _should_delegate_dijkstra_to_networkx(G, weight):
        kwargs = {"weight": weight}
        if method is not None:
            kwargs["method"] = method
        return _call_networkx_for_parity("average_shortest_path_length", G, **kwargs)
    return _raw_average_shortest_path_length(G, weight=weight, method=method)


def dijkstra_path(G, source, target, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "dijkstra_path", G, source, target, weight=weight
        )
    return _raw_dijkstra_path(G, source, target, weight=weight)


def shortest_path(G, source=None, target=None, weight=None, method="dijkstra"):
    if method not in ("dijkstra", "bellman-ford"):
        raise ValueError(f"method not supported: {method}")
    if weight is not None and method == "dijkstra" and _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "shortest_path",
            G,
            source=source,
            target=target,
            weight=weight,
            method=method,
        )
    return _raw_shortest_path(G, source=source, target=target, weight=weight, method=method)


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

    if weight is not None and method == "dijkstra" and _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "shortest_path_length",
            G,
            source=source,
            target=target,
            weight=weight,
            method=method,
        )

    if source is not None and target is not None:
        if weight is not None and method == "bellman-ford":
            return bellman_ford_path_length(G, source, target, weight=weight)
        return _shortest_path_length_raw(G, source, target, weight=weight)
    
    if source is not None:
        if weight is not None:
            if method == "bellman-ford":
                return dict(single_source_bellman_ford_path_length(G, source, weight=weight))
            return dict(single_source_dijkstra_path_length(G, source, weight=weight))
        return dict(single_source_shortest_path_length(G, source))

    if target is not None:
        if weight is not None:
            if method == "bellman-ford":
                if G.is_directed():
                    return dict(
                        single_source_bellman_ford_path_length(
                            G.reverse(), target, weight=weight
                        )
                    )
                return dict(single_source_bellman_ford_path_length(G, target, weight=weight))
            if G.is_directed():
                all_pairs = dict(all_pairs_dijkstra_path_length(G, weight=weight))
                return {node: dists[target] for node, dists in all_pairs.items() if target in dists}
            return dict(single_source_dijkstra_path_length(G, target, weight=weight))
        return dict(single_target_shortest_path_length(G, target))
        
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
    closeness_vitality as _rust_closeness_vitality,
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
    average_clustering as _raw_average_clustering,
    clustering,
    find_cliques,
    graph_clique_number,
    square_clustering,
    triangles as _raw_triangles,
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


def density(G):
    r"""Returns the density of a graph."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    if m == 0 or n <= 1:
        return 0
    result = m / (n * (n - 1))
    if not G.is_directed():
        result *= 2
    return result


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
    all_shortest_paths as _raw_all_shortest_paths,
    all_simple_paths as _rust_all_simple_paths,
    cycle_basis,
)


def all_shortest_paths(G, source, target, weight=None, method=None):
    if weight is not None and method in (None, "dijkstra") and _should_delegate_dijkstra_to_networkx(G, weight):
        kwargs = {"weight": weight}
        if method is not None:
            kwargs["method"] = method
        return _call_networkx_for_parity("all_shortest_paths", G, source, target, **kwargs)
    return _raw_all_shortest_paths(G, source, target, weight=weight, method=method)


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
def overall_reciprocity(G):
    """Compute the reciprocity for the whole graph."""
    if G.is_multigraph() and not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected multigraph type")

    n_all_edge = G.number_of_edges()
    if n_all_edge == 0:
        raise NetworkXError("Not defined for empty graphs")

    n_overlap_edge = (n_all_edge - G.to_undirected().number_of_edges()) * 2
    return n_overlap_edge / n_all_edge


def _reciprocity_value_for_node(G, node):
    pred = set(G.predecessors(node))
    succ = set(G.successors(node))
    overlap = pred & succ
    n_total = len(pred) + len(succ)
    if n_total == 0:
        return None
    return 2 * len(overlap) / n_total


def reciprocity(G, nodes=None):
    """Compute reciprocity for a directed graph.

    If *nodes* is None, return the overall reciprocity of the graph (float).
    If *nodes* is a single node, return the reciprocity for that node (float).
    If *nodes* is an iterable of nodes, return a dict mapping each node to
    its reciprocity.  Matches ``networkx.reciprocity``.
    """
    if nodes is None:
        return overall_reciprocity(G)

    if G.is_multigraph() and not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected multigraph type")
    if not G.is_directed():
        raise AttributeError(f"'{type(G).__name__}' object has no attribute 'predecessors'")

    try:
        if nodes in G:
            reciprocity_value = _reciprocity_value_for_node(G, nodes)
            if reciprocity_value is None:
                raise NetworkXError("Not defined for isolated nodes.")
            return reciprocity_value
    except TypeError:
        pass

    try:
        iterator = iter(nodes)
    except TypeError:
        raise NetworkXError(f"Node {nodes} is not in the graph.") from None

    result = {}
    for node in iterator:
        if node not in G:
            continue
        result[node] = _reciprocity_value_for_node(G, node)
    return result


# Algorithm functions — Wiener index
def wiener_index(G, weight=None):
    """Returns the Wiener index of the given graph."""
    connected = is_strongly_connected(G) if G.is_directed() else is_connected(G)
    if not connected:
        return float("inf")

    def _single_source_unweighted_lengths(source):
        lengths = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            next_distance = lengths[node] + 1
            for neighbor in G.neighbors(node):
                if neighbor in lengths:
                    continue
                lengths[neighbor] = next_distance
                queue.append(neighbor)
        return lengths

    def _single_source_weighted_lengths(source):
        distances = {source: 0.0}
        queue = [(0.0, next(counter), source)]

        while queue:
            distance, _, node = heappop(queue)
            if distance > distances[node]:
                continue

            for neighbor in G.neighbors(node):
                edge_data = G.get_edge_data(node, neighbor)
                if G.is_multigraph():
                    edge_weight = min(
                        attrs.get(weight, 1) for attrs in edge_data.values()
                    )
                else:
                    edge_weight = edge_data.get(weight, 1)

                candidate = distance + edge_weight
                if candidate < distances.get(neighbor, float("inf")):
                    distances[neighbor] = candidate
                    heappush(queue, (candidate, next(counter), neighbor))

        return distances

    if weight is None:
        total = sum(sum(_single_source_unweighted_lengths(node).values()) for node in G)
    else:
        counter = count()
        total = sum(sum(_single_source_weighted_lengths(node).values()) for node in G)

    return total if G.is_directed() else total / 2

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
    all_triangles as _rust_all_triangles,
    node_clique_number,
    enumerate_all_cliques,
    find_cliques_recursive,
    chordal_graph_cliques,
    chordal_graph_treewidth,
    make_max_clique_graph as _rust_make_max_clique_graph,
    ring_of_cliques,
)


def all_triangles(G, nbunch=None):
    """Yield unique triangles in an undirected graph."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    if nbunch is None:
        yield from _rust_all_triangles(G)
        return

    nbunch_nodes = _global_nbunch_nodes(G, nbunch)
    nbunch_lookup = dict.fromkeys(nbunch_nodes)
    relevant_nodes = itertools.chain(
        nbunch_lookup,
        (
            neighbor
            for node in nbunch_lookup
            for neighbor in G.neighbors(node)
            if neighbor not in nbunch_lookup
        ),
    )
    node_to_id = {node: index for index, node in enumerate(relevant_nodes)}

    for u in nbunch_lookup:
        u_id = node_to_id[u]
        u_neighbors = G.adj[u].keys()
        for v in u_neighbors:
            v_id = node_to_id.get(v, -1)
            if v_id <= u_id:
                continue
            v_neighbors = G.adj[v].keys()
            for w in v_neighbors & u_neighbors:
                if node_to_id.get(w, -1) > v_id:
                    yield (u, v, w)

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
    grid_graph as _rust_grid_graph,
    dorogovtsev_goltsev_mendes_graph as _rust_dorogovtsev_goltsev_mendes_graph,
    null_graph as _rust_null_graph,
    trivial_graph as _rust_trivial_graph,
    binomial_tree as _rust_binomial_tree,
    full_rary_tree as _rust_full_rary_tree,
    circulant_graph as _rust_circulant_graph,
    kneser_graph,
    paley_graph as _rust_paley_graph,
    chordal_cycle_graph as _rust_chordal_cycle_graph,
    sudoku_graph as _rust_sudoku_graph,
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
    degree_histogram as _raw_degree_histogram,
)

# Algorithm functions — transitive closure/reduction
from franken_networkx._fnx import (
    transitive_closure,
    transitive_reduction,
)


def degree_histogram(G):
    """Returns a list of the frequency of each degree value."""
    degree_view = G.degree
    if callable(degree_view):
        degree_view = degree_view()
    counts = Counter(degree for _node, degree in degree_view)
    return [counts.get(i, 0) for i in range(max(counts) + 1 if counts else 0)]

def _adc_iter_nodes(G, nodes):
    if nodes is None:
        return list(G.nodes())
    try:
        if nodes in G:
            return [nodes]
    except TypeError:
        pass
    try:
        return [node for node in nodes if node in G]
    except TypeError:
        return []


def _adc_weighted_degree(G, node, *, incoming=False, outgoing=False, weight=None):
    if not incoming and not outgoing:
        incoming = True
        outgoing = True

    def edge_total(edge_data):
        if weight is None:
            if G.is_multigraph():
                return len(edge_data)
            return 1
        if G.is_multigraph():
            return sum(attrs.get(weight, 1) for attrs in edge_data.values())
        return edge_data.get(weight, 1)

    total = 0
    if outgoing:
        for nbr, edge_data in G[node].items():
            contribution = edge_total(edge_data)
            if not G.is_directed() and nbr == node:
                contribution *= 2
            total += contribution
    if incoming and G.is_directed():
        for nbr in G.predecessors(node):
            total += edge_total(G[nbr][node])
    return total


def average_degree_connectivity(
    G, source="in+out", target="in+out", nodes=None, weight=None
):
    """Compute the average degree connectivity of graph."""
    if G.is_directed():
        if source not in ("in", "out", "in+out"):
            raise NetworkXError('source must be one of "in", "out", or "in+out"')
        if target not in ("in", "out", "in+out"):
            raise NetworkXError('target must be one of "in", "out", or "in+out"')

        def source_degree(node, *, weighted):
            return _adc_weighted_degree(
                G,
                node,
                incoming=source in ("in", "in+out"),
                outgoing=source in ("out", "in+out"),
                weight=weight if weighted else None,
            )

        def target_degree(node):
            return _adc_weighted_degree(
                G,
                node,
                incoming=target in ("in", "in+out"),
                outgoing=target in ("out", "in+out"),
                weight=None,
            )

        if source == "in":
            neighbors = lambda node: G.predecessors(node)
        elif source == "out":
            neighbors = lambda node: G.successors(node)
        else:
            neighbors = lambda node: G.neighbors(node)
        reverse = source == "in"
    else:
        if source != "in+out" or target != "in+out":
            raise NetworkXError(
                "source and target arguments are only supported for directed graphs"
            )

        def source_degree(node, *, weighted):
            return _adc_weighted_degree(G, node, weight=weight if weighted else None)

        def target_degree(node):
            return _adc_weighted_degree(G, node)

        neighbors = lambda node: G.neighbors(node)
        reverse = False

    dsum = defaultdict(int)
    dnorm = defaultdict(int)
    source_nodes = _adc_iter_nodes(G, nodes)

    for node in source_nodes:
        degree_key = source_degree(node, weighted=False)
        if weight is None:
            total = sum(target_degree(neighbor) for neighbor in neighbors(node))
        else:
            if reverse:
                total = sum(
                    G[neighbor][node].get(weight, 1) * target_degree(neighbor)
                    for neighbor in neighbors(node)
                )
            else:
                total = sum(
                    G[node][neighbor].get(weight, 1) * target_degree(neighbor)
                    for neighbor in neighbors(node)
                )
        dnorm[degree_key] += source_degree(node, weighted=True)
        dsum[degree_key] += total

    return {k: avg if dnorm[k] == 0 else avg / dnorm[k] for k, avg in dsum.items()}


def _compute_rich_club_coefficients(G):
    """Return the rich-club coefficient by degree threshold."""
    deghist = degree_histogram(G)
    total = sum(deghist)
    nks = (total - cs for cs in itertools.accumulate(deghist) if total - cs > 1)

    degree_view = G.degree
    if callable(degree_view):
        degree_of = degree_view
    else:
        degree_of = degree_view.__getitem__

    edge_degrees = sorted(
        (sorted((degree_of(u), degree_of(v))) for u, v in G.edges()),
        reverse=True,
    )
    ek = G.number_of_edges()
    if ek == 0:
        return {}

    k1, k2 = edge_degrees.pop()
    rc = {}
    for d, nk in enumerate(nks):
        while k1 <= d:
            if not edge_degrees:
                ek = 0
                break
            k1, k2 = edge_degrees.pop()
            ek -= 1
        rc[d] = 2 * ek / (nk * (nk - 1))
    return rc


def _rich_club_double_edge_swap(G, nswap=1, max_tries=100, seed=None):
    """NetworkX-style swap loop used for rich-club normalization."""
    import bisect

    if nswap > max_tries:
        raise NetworkXError("Number of swaps > number of tries allowed.")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if G.number_of_edges() < 2:
        raise NetworkXError("Graph has fewer than 2 edges")

    rng = _generator_random_state(seed)

    def choice(seq):
        if hasattr(rng, "choice"):
            return rng.choice(seq)
        return seq[rng.randint(0, len(seq) - 1)]

    degree_view = G.degree
    if callable(degree_view):
        degree_items = degree_view()
    else:
        degree_items = degree_view
    keys, degrees = zip(*degree_items)
    total_degree = sum(degrees)
    cumulative = 0.0
    cdf = []
    for degree in degrees:
        cumulative += degree
        cdf.append(cumulative / total_degree)

    n = 0
    swapcount = 0
    while swapcount < nswap:
        ui = bisect.bisect_left(cdf, rng.random())
        xi = bisect.bisect_left(cdf, rng.random())
        if ui == xi:
            continue

        u = keys[ui]
        x = keys[xi]
        v = choice(list(G[u]))
        y = choice(list(G[x]))
        if v == y:
            continue

        if (x not in G[u]) and (y not in G[v]):
            G.add_edge(u, x)
            G.add_edge(v, y)
            G.remove_edge(u, v)
            G.remove_edge(x, y)
            swapcount += 1

        if n >= max_tries:
            raise NetworkXAlgorithmError(
                f"Maximum number of swap attempts ({n}) exceeded "
                f"before desired swaps achieved ({nswap})."
            )
        n += 1
    return G


def rich_club_coefficient(G, normalized=True, Q=100, seed=None):
    """Return the rich-club coefficient of the graph."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if number_of_selfloops(G) > 0:
        raise Exception(
            "rich_club_coefficient is not implemented for graphs with self loops."
        )

    rc = _compute_rich_club_coefficients(G)
    if normalized:
        randomized = G.copy()
        edge_count = randomized.number_of_edges()
        _rich_club_double_edge_swap(
            randomized,
            Q * edge_count,
            max_tries=Q * edge_count * 10,
            seed=seed,
        )
        randomized_rc = _compute_rich_club_coefficients(randomized)
        rc = {k: v / randomized_rc[k] for k, v in rc.items()}
    return rc


def s_metric(G):
    """Return the s-metric of the graph."""
    degree_view = G.degree
    if callable(degree_view):
        degree_of = degree_view
    else:
        degree_of = degree_view.__getitem__
    return float(sum(degree_of(u) * degree_of(v) for (u, v) in G.edges()))

# Algorithm functions — graph metrics (expansion, conductance, volume)
from franken_networkx._fnx import (
    volume,
    boundary_expansion,
    conductance,
    edge_expansion,
    node_expansion,
    mixing_expansion,
    non_edges as _raw_non_edges,
    average_node_connectivity,
    is_k_edge_connected,
    all_pairs_dijkstra as _raw_all_pairs_dijkstra,
    number_of_spanning_arborescences,
    global_node_connectivity,
)

def all_pairs_dijkstra(G, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        yield from _call_networkx_for_parity("all_pairs_dijkstra", G, weight=weight)
        return
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
    common_neighbors as _raw_common_neighbors,
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


def volume(G, S, weight=None):
    """Return the volume of a set of nodes."""
    return sum(
        _adc_weighted_degree(
            G,
            node,
            incoming=not G.is_directed(),
            outgoing=True,
            weight=weight,
        )
        for node in S
    )


def edge_expansion(G, S, T=None, weight=None):
    """Return the edge expansion between two node sets."""
    if T is None:
        T = list(set(G) - set(S))
    num_cut_edges = cut_size(G, S, nbunch2=T, weight=weight)
    denominator = min(len(S), len(T))
    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    return num_cut_edges / denominator


def mixing_expansion(G, S, T=None, weight=None):
    """Return the mixing expansion between two node sets."""
    num_cut_edges = cut_size(G, S, nbunch2=T, weight=weight)
    num_total_edges = G.number_of_edges()
    return num_cut_edges / (2 * num_total_edges)


def node_expansion(G, S):
    """Return the node expansion of a set."""
    neighborhood = set(itertools.chain.from_iterable(G.neighbors(v) for v in S))
    return len(neighborhood) / len(S)


def boundary_expansion(G, S):
    """Return the boundary expansion of a set."""
    return len(node_boundary(G, S)) / len(S)


def conductance(G, S, T=None, weight=None):
    """Return the conductance between two node sets."""
    if T is None:
        T = list(set(G) - set(S))
    num_cut_edges = cut_size(G, S, T, weight=weight)
    volume_s = volume(G, S, weight=weight)
    volume_t = volume(G, T, weight=weight)
    denominator = min(volume_s, volume_t)
    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    return num_cut_edges / denominator

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
    is_digraphical as _raw_is_digraphical,
    is_multigraphical,
    is_pseudographical,
    is_k_regular,
    is_weighted,
    is_negatively_weighted,
    is_distance_regular as _raw_is_distance_regular,
)


def _make_list_of_ints(sequence):
    if not isinstance(sequence, list):
        result = []
        for value in sequence:
            errmsg = f"sequence is not all integers: {value}"
            try:
                int_value = int(value)
            except ValueError:
                raise NetworkXError(errmsg) from None
            if int_value != value:
                raise NetworkXError(errmsg)
            result.append(int_value)
        return result

    for idx, value in enumerate(sequence):
        if isinstance(value, int):
            continue
        errmsg = f"sequence is not all integers: {value}"
        try:
            int_value = int(value)
        except ValueError:
            raise NetworkXError(errmsg) from None
        if int_value != value:
            raise NetworkXError(errmsg)
        sequence[idx] = int_value
    return sequence


def is_graphical(sequence, method="eg"):
    """Returns True if sequence is a valid degree sequence."""
    deg_sequence = _make_list_of_ints(sequence)
    if any(degree < 0 for degree in deg_sequence):
        return False
    if method == "eg":
        return is_valid_degree_sequence_erdos_gallai(deg_sequence)
    if method == "hh":
        return is_valid_degree_sequence_havel_hakimi(deg_sequence)
    raise _nx.NetworkXException("`method` must be 'eg' or 'hh'")


def is_digraphical(in_sequence, out_sequence):
    """Returns True if some directed graph can realize the in/out sequences."""
    try:
        in_deg_sequence = _make_list_of_ints(in_sequence)
        out_deg_sequence = _make_list_of_ints(out_sequence)
    except NetworkXError:
        return False

    max_len = max(len(in_deg_sequence), len(out_deg_sequence))
    if max_len == 0:
        return True

    degree_pairs = []
    for idx in range(max_len):
        in_degree = in_deg_sequence[idx] if idx < len(in_deg_sequence) else 0
        out_degree = out_deg_sequence[idx] if idx < len(out_deg_sequence) else 0
        if in_degree < 0 or out_degree < 0:
            return False
        degree_pairs.append((in_degree, out_degree))
    return _raw_is_digraphical(degree_pairs)


def is_pseudographical(sequence):
    """Returns True if some pseudograph can realize the sequence."""
    try:
        deg_sequence = _make_list_of_ints(sequence)
    except NetworkXError:
        return False
    return sum(deg_sequence) % 2 == 0 and min(deg_sequence) >= 0


def is_multigraphical(sequence):
    """Returns True if some multigraph can realize the sequence."""
    try:
        deg_sequence = _make_list_of_ints(sequence)
    except NetworkXError:
        return False

    degree_sum = 0
    max_degree = 0
    for degree in deg_sequence:
        if degree < 0:
            return False
        degree_sum += degree
        max_degree = max(max_degree, degree)
    if degree_sum % 2 != 0 or degree_sum < 2 * max_degree:
        return False
    return True


def is_tournament(G):
    """Returns True if and only if ``G`` is a tournament."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return (
        all((v in G[u]) ^ (u in G[v]) for u, v in combinations(G, 2))
        and number_of_selfloops(G) == 0
    )


def is_regular(G):
    """Determines whether a graph is regular."""
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")

    node = next(iter(G))
    degree_view = G.degree
    if callable(degree_view):
        degree = degree_view(node)
        degree_items = degree_view()
    else:
        degree = degree_view[node]
        degree_items = degree_view

    if not G.is_directed():
        return all(degree == current_degree for _node, current_degree in degree_items)

    in_degree_view = G.in_degree
    if callable(in_degree_view):
        in_degree = in_degree_view(node)
        in_degree_items = in_degree_view()
    else:
        in_degree = in_degree_view[node]
        in_degree_items = in_degree_view

    out_degree_view = G.out_degree
    if callable(out_degree_view):
        out_degree = out_degree_view(node)
        out_degree_items = out_degree_view()
    else:
        out_degree = out_degree_view[node]
        out_degree_items = out_degree_view

    return all(
        in_degree == current_degree for _node, current_degree in in_degree_items
    ) and all(out_degree == current_degree for _node, current_degree in out_degree_items)


def is_weighted(G, edge=None, weight="weight"):
    """Returns True if ``G`` has weighted edges."""
    if edge is not None:
        data = G.get_edge_data(*edge)
        if data is None:
            msg = f"Edge {edge!r} does not exist."
            raise NetworkXError(msg)
        return weight in data

    if G.number_of_edges() == 0:
        return False

    return all(weight in data for _u, _v, data in G.edges(data=True))


def is_negatively_weighted(G, edge=None, weight="weight"):
    """Returns True if ``G`` has negatively weighted edges."""
    if edge is not None:
        data = G.get_edge_data(*edge)
        if data is None:
            msg = f"Edge {edge!r} does not exist."
            raise NetworkXError(msg)
        return weight in data and data[weight] < 0

    return any(weight in data and data[weight] < 0 for _u, _v, data in G.edges(data=True))


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
    is_aperiodic as _raw_is_aperiodic,
    antichains,
    immediate_dominators,
    dominance_frontiers,
)

# Algorithm functions — additional shortest path
from franken_networkx._fnx import (
    dijkstra_path_length as _raw_dijkstra_path_length,
    bellman_ford_path_length,
    single_source_dijkstra as _raw_single_source_dijkstra,
    single_source_dijkstra_path as _raw_single_source_dijkstra_path,
    single_source_dijkstra_path_length as _raw_single_source_dijkstra_path_length,
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


def is_aperiodic(G):
    """Returns True if ``G`` is aperiodic."""
    if not G.is_directed():
        raise NetworkXError("is_aperiodic not defined for undirected graphs")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")
    if not is_strongly_connected(G):
        raise NetworkXError("Graph is not strongly connected.")

    source = next(iter(G))
    levels = {source: 0}
    this_level = [source]
    gcd_cycle = 0
    level = 1
    while this_level:
        next_level = []
        for u in this_level:
            for v in G[u]:
                if v in levels:
                    gcd_cycle = math.gcd(gcd_cycle, levels[u] - levels[v] + 1)
                else:
                    next_level.append(v)
                    levels[v] = level
        this_level = next_level
        level += 1
    return gcd_cycle == 1


def dijkstra_path_length(G, source, target, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "dijkstra_path_length", G, source, target, weight=weight
        )
    return _raw_dijkstra_path_length(G, source, target, weight=weight)


def single_source_dijkstra(G, source, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "single_source_dijkstra", G, source, weight=weight
        )
    return _raw_single_source_dijkstra(G, source, weight=weight)


def single_source_dijkstra_path(G, source, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "single_source_dijkstra_path", G, source, weight=weight
        )
    return _raw_single_source_dijkstra_path(G, source, weight=weight)


def single_source_dijkstra_path_length(G, source, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "single_source_dijkstra_path_length", G, source, weight=weight
        )
    return _raw_single_source_dijkstra_path_length(G, source, weight=weight)


def all_pairs_dijkstra_path(G, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        yield from _call_networkx_for_parity(
            "all_pairs_dijkstra_path", G, weight=weight
        )
        return
    for k, v in _raw_all_pairs_dijkstra_path(G, weight=weight).items():
        yield (k, v)


def all_pairs_dijkstra_path_length(G, weight="weight"):
    if _should_delegate_dijkstra_to_networkx(G, weight):
        yield from _call_networkx_for_parity(
            "all_pairs_dijkstra_path_length", G, weight=weight
        )
        return
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
    is_semiconnected as _raw_is_semiconnected,
    kosaraju_strongly_connected_components,
    attracting_components as _raw_attracting_components,
    number_attracting_components as _raw_number_attracting_components,
    is_attracting_component as _raw_is_attracting_component,
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


def is_semiconnected(G):
    """Returns True if the graph is semiconnected, False otherwise."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Connectivity is undefined for the null graph.")
    return _raw_is_semiconnected(G)


def attracting_components(G):
    """Generates the attracting components in ``G``."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return (set(component) for component in _raw_attracting_components(G))


def number_attracting_components(G):
    """Returns the number of attracting components in ``G``."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return _raw_number_attracting_components(G)


def is_attracting_component(G):
    """Returns True if ``G`` consists of a single attracting component."""
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    components = list(attracting_components(G))
    if len(components) == 1:
        return len(components[0]) == len(G)
    return False


def complete_graph(n, create_using=None):
    """Return the complete graph K_n."""
    n, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n, numbers.Integral):
        return _rust_complete_graph(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if len(nodes) > 1:
        edges = itertools.permutations(nodes, 2) if graph.is_directed() else combinations(nodes, 2)
        for u, v in edges:
            graph.add_edge(u, v)
    return graph


def cycle_graph(n, create_using=None):
    """Return the cycle graph C_n."""
    n, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n, numbers.Integral):
        return _rust_cycle_graph(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if nodes:
        for u, v in itertools.pairwise(nodes):
            graph.add_edge(u, v)
        graph.add_edge(nodes[-1], nodes[0])
    return graph


def empty_graph(n=0, create_using=None, default=Graph):
    """Return the empty graph with n nodes and zero edges."""
    n, nodes = _nodes_or_number_local(n)
    default_graph_type = _classic_default_graph_type(default)
    if create_using is None and default_graph_type is Graph and isinstance(n, numbers.Integral):
        return _rust_empty_graph(int(n))

    graph = _classic_graph_from_create_using(create_using, default=default_graph_type)
    _add_nodes_in_order(graph, nodes)
    return graph


def path_graph(n, create_using=None):
    """Return the path graph P_n."""
    n, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n, numbers.Integral):
        return _rust_path_graph(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    for u, v in itertools.pairwise(nodes):
        graph.add_edge(u, v)
    return graph


def star_graph(n, create_using=None):
    """Return the star graph on n + 1 nodes."""
    n, nodes = _nodes_or_number_local(n)
    if isinstance(n, numbers.Integral):
        nodes.append(int(n))
        if create_using is None:
            return _rust_star_graph(int(n))

    graph = _classic_graph_from_create_using(create_using)
    _add_nodes_in_order(graph, nodes)
    if len(nodes) > 1:
        hub, *spokes = nodes
        for node in spokes:
            graph.add_edge(hub, node)
    return graph


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
    if with_data:
        H.graph.update(dict(G.graph))
        H.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
    else:
        H.add_nodes_from(G.nodes())
    return H


def number_of_selfloops(G):
    """Return the number of self-loop edges in *G*."""
    return sum(1 for _ in selfloop_edges(G))


def selfloop_edges(G, data=False, keys=False, default=None):
    """Return an iterator over self-loop edges.

    Parameters
    ----------
    G : Graph
        The input graph.
    data : string or bool, optional
        Return self-loop edges as ``(u, u)`` tuples when ``False``, or include
        edge data when ``True`` or an attribute value when set to a string.
    keys : bool, optional
        If True, include edge keys for multigraphs.
    default : Any, optional
        Default attribute value used when ``data`` names a missing attribute.

    Returns
    -------
    iterator
        Iterator over self-loop edges.
    """
    def adjacency_entries():
        for node in G.adj:
            nbrs = G.adj[node]
            if node in nbrs:
                yield node, nbrs

    if data is True:
        if G.is_multigraph():
            if keys is True:
                return (
                    (n, n, key, attrs)
                    for n, nbrs in adjacency_entries()
                    for key, attrs in nbrs[n].items()
                )
            return (
                (n, n, attrs)
                for n, nbrs in adjacency_entries()
                for attrs in nbrs[n].values()
            )
        return ((n, n, nbrs[n]) for n, nbrs in adjacency_entries())

    if data is not False:
        if G.is_multigraph():
            if keys is True:
                return (
                    (n, n, key, attrs.get(data, default))
                    for n, nbrs in adjacency_entries()
                    for key, attrs in nbrs[n].items()
                )
            return (
                (n, n, attrs.get(data, default))
                for n, nbrs in adjacency_entries()
                for attrs in nbrs[n].values()
            )
        return (
            (n, n, nbrs[n].get(data, default))
            for n, nbrs in adjacency_entries()
        )

    if G.is_multigraph():
        if keys is True:
            return (
                (n, n, key)
                for n, nbrs in adjacency_entries()
                for key in nbrs[n]
            )
        return (
            (n, n)
            for n, nbrs in adjacency_entries()
            for _ in range(len(nbrs[n]))
        )
    return ((n, n) for n, nbrs in adjacency_entries())


def nodes_with_selfloops(G):
    """Return nodes that have self-loops."""
    return (node for node in G.adj if node in G.adj[node])


def all_neighbors(G, node):
    """Return all neighbors of *node* in *G* (including predecessors for DiGraph).

    For undirected graphs, equivalent to ``G.neighbors(node)``.
    For directed graphs, returns predecessors followed by successors.
    """
    if G.is_directed():
        return itertools.chain(G.predecessors(node), G.successors(node))
    return G.neighbors(node)


def is_path(G, path):
    """Return whether or not the specified path exists in *G*."""
    try:
        return all(nbr in G[node] for node, nbr in itertools.pairwise(path))
    except (KeyError, TypeError):
        return False


def path_weight(G, path, weight):
    """Return the total cost associated with *path* using edge attribute *weight*."""
    if not is_path(G, path):
        raise NetworkXNoPath("path does not exist")

    cost = 0
    if G.is_multigraph():
        for node, nbr in itertools.pairwise(path):
            cost += min(attrs[weight] for attrs in G[node][nbr].values())
        return cost

    for node, nbr in itertools.pairwise(path):
        cost += G[node][nbr][weight]
    return cost


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


def _cross_product_edge_key(g_is_multigraph, h_is_multigraph, g_key, h_key):
    if g_is_multigraph and h_is_multigraph:
        return (g_key, h_key)
    if g_is_multigraph:
        return g_key
    if h_is_multigraph:
        return h_key
    return None


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
                edge_key = _cross_product_edge_key(G.is_multigraph(), H.is_multigraph(), gk, hk)
                P.add_edge((gu, hu), (gv, hv), key=edge_key, **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), key=edge_key, **edge_attrs)
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
                edge_key = _cross_product_edge_key(G.is_multigraph(), H.is_multigraph(), gk, hk)
                P.add_edge((gu, hu), (gv, hv), key=edge_key, **edge_attrs)
                if not G.is_directed():
                    P.add_edge((gu, hv), (gv, hu), key=edge_key, **edge_attrs)
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
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if k <= 0:
        raise ValueError("k must be a positive integer")

    if isinstance(k, numbers.Integral):
        raw_graph = _fnx.power_rust(G, int(k))
        canonical_to_node = {str(node): node for node in G.nodes()}

        graph = G.__class__()
        for raw_node in raw_graph.nodes():
            graph.add_node(canonical_to_node.get(raw_node, raw_node))
        for raw_u, raw_v in raw_graph.edges():
            graph.add_edge(
                canonical_to_node.get(raw_u, raw_u),
                canonical_to_node.get(raw_v, raw_v),
            )
        return graph

    graph = G.__class__()
    graph.add_nodes_from(G)
    for node in G:
        seen = {}
        level = 1
        nextlevel = G[node]
        while nextlevel:
            thislevel = nextlevel
            nextlevel = {}
            for neighbor in thislevel:
                if neighbor == node:
                    continue
                if neighbor not in seen:
                    seen[neighbor] = level
                    nextlevel.update(G[neighbor])
            if k <= level:
                break
            level += 1
        graph.add_edges_from((node, neighbor) for neighbor in seen)
    return graph


def disjoint_union(G, H):
    """Return the disjoint union of *G* and *H*."""
    return disjoint_union_all([G, H])


def compose_all(graphs):
    """Return the composition of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply compose_all to an empty list")
    _validate_same_graph_family(graphs)
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
    rename : iterable of str or None, optional
        Prefixes to apply to node names of each graph. Shorter iterables
        leave the remaining graphs unchanged. Default ``()`` means no renaming.
    """
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply union_all to an empty list")
    _validate_same_graph_family(graphs)

    R = graphs[0].__class__()
    rename_iter = itertools.chain(rename, itertools.repeat(None))
    for G, prefix in zip(graphs, rename_iter):
        R.graph.update(G.graph)

        def _rename(n, _prefix=prefix):
            return f"{_prefix}{n}" if _prefix is not None else n

        for n in G.nodes():
            new_n = _rename(n)
            if new_n in R:
                raise NetworkXError(
                    "The node sets of the graphs are not disjoint.\n"
                    "Use `rename` to specify prefixes for the graphs or use\n"
                    "disjoint_union(G1, G2, ..., GN)."
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

    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")

    if nodes is None:
        requested_nodes = list(G)
    else:
        requested_nodes = list(nodes)
        for node in requested_nodes:
            if node not in G:
                raise KeyError(node)

    result = _rust_constraint(G)
    constrained = {}
    for node in requested_nodes:
        if all(neighbor == node for neighbor in G[node]):
            constrained[node] = float("nan")
        else:
            constrained[node] = result[node]
    return constrained


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
    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")

    if nodes is None:
        requested_nodes = list(G.nodes())
    else:
        requested_nodes = list(nodes)
        for node in requested_nodes:
            if node not in G:
                raise KeyError(node)

    from franken_networkx._fnx import effective_size_rust as _rust_eff_size

    result = _rust_eff_size(G)
    effective = {}
    for node in requested_nodes:
        if all(neighbor == node for neighbor in G[node]):
            effective[node] = float("nan")
        else:
            effective[node] = result[node]
    return effective


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
    wi = (
        wiener_index
        if wiener_index is not None
        else globals()["wiener_index"](G, weight=weight)
    )
    if node is not None:
        after = globals()["wiener_index"](G.subgraph(set(G) - {node}), weight=weight)
        return wi - after
    return {
        v: closeness_vitality(G, node=v, weight=weight, wiener_index=wi) for v in G
    }


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

    The intersection contains nodes and edges present in all graphs.
    """
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply intersection_all to an empty sequence")
    _validate_same_graph_family(graphs)

    R = graphs[0].__class__()
    for node in graphs[0].nodes():
        if all(node in G for G in graphs[1:]):
            R.add_node(node)

    if graphs[0].is_multigraph():
        for u, v, key in graphs[0].edges(keys=True):
            if u in R and v in R and all(G.has_edge(u, v, key) for G in graphs[1:]):
                R.add_edge(u, v, key=key)
    else:
        for u, v in graphs[0].edges():
            if u in R and v in R and all(G.has_edge(u, v) for G in graphs[1:]):
                R.add_edge(u, v)
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


def freeze(G):
    """Modify *G* so that mutation raises an error. Returns *G*."""
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
    return getattr(G, "frozen", False)


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


def binomial_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    return gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=create_using,
    )


def gnp_random_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a G(n,p) random graph."""
    if not directed and create_using is None:
        return _rust_gnp_random_graph(n, p, seed=_native_random_seed(seed))

    rng = _generator_random_state(seed)
    default = DiGraph if directed else Graph
    graph = _checked_create_using(
        create_using,
        directed=directed,
        multigraph=False,
        default=default,
    )
    if p >= 1:
        return complete_graph(n, create_using=graph)

    graph = empty_graph(n, create_using=graph, default=default)
    if p <= 0:
        return graph

    edge_pairs = itertools.permutations(range(n), 2) if directed else combinations(range(n), 2)
    for u, v in edge_pairs:
        if rng.random() < p:
            graph.add_edge(u, v)
    return graph


def erdos_renyi_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    return gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=create_using,
    )


def watts_strogatz_graph(n, k, p, seed=None, create_using=None):
    """Return a Watts-Strogatz small-world graph."""
    graph = _rust_watts_strogatz_graph(n, k, p, seed=_native_random_seed(seed))
    if create_using is None:
        return graph
    return _copy_graph_into(
        graph,
        _checked_create_using(
            create_using,
            directed=False,
            multigraph=False,
            default=Graph,
        ),
    )


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
    if create_using is None:
        return _rust_balanced_tree(r, h)

    if r == 1:
        n = h + 1
    else:
        n = (1 - r ** (h + 1)) // (1 - r)
    return full_rary_tree(r, n, create_using=create_using)


def full_rary_tree(r, n, create_using=None):
    """Return a full r-ary tree with n nodes."""
    if create_using is None:
        return _rust_full_rary_tree(r, n)

    G = empty_graph(n, create_using)
    G.add_edges_from(_tree_edges_local(n, r))
    return G


def binomial_tree(n, create_using=None):
    """Return the binomial tree of order n."""
    if create_using is None:
        return _rust_binomial_tree(n)

    G = empty_graph(1, create_using)

    N = 1
    for _ in range(n):
        edges = [(u + N, v + N) for u, v in G.edges()]
        _add_nodes_in_order(G, range(N, 2 * N))
        G.add_edges_from(edges)
        G.add_edge(0, N)
        N *= 2
    return G


def complete_bipartite_graph(n1, n2, create_using=None):
    """Return the complete bipartite graph K_(n1,n2)."""
    n1_value, top = _nodes_or_number_local(n1)
    n2_value, bottom = _nodes_or_number_local(n2)

    if (
        create_using is None
        and isinstance(n1_value, numbers.Integral)
        and isinstance(n2_value, numbers.Integral)
    ):
        return _rust_complete_bipartite_graph(n1, n2)

    G = empty_graph(0, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    if isinstance(n1_value, numbers.Integral) and isinstance(n2_value, numbers.Integral):
        bottom = [n1_value + i for i in bottom]

    for node in top:
        G.add_node(node, bipartite=0)
    for node in bottom:
        G.add_node(node, bipartite=1)
    if len(G) != len(top) + len(bottom):
        raise NetworkXError("Inputs n1 and n2 must contain distinct nodes")
    G.add_edges_from((u, v) for u in top for v in bottom)
    G.graph["name"] = f"complete_bipartite_graph({len(top)}, {len(bottom)})"
    return G


def grid_2d_graph(m, n, periodic=False, create_using=None):
    """Return the two-dimensional grid graph."""
    m_value, rows = _nodes_or_number_local(m)
    n_value, cols = _nodes_or_number_local(n)

    if (
        not periodic
        and create_using is None
        and isinstance(m_value, numbers.Integral)
        and isinstance(n_value, numbers.Integral)
    ):
        return _rust_grid_2d_graph(m, n)

    G = empty_graph(0, create_using)
    for i in rows:
        for j in cols:
            G.add_node((i, j))
    G.add_edges_from(((i, j), (pi, j)) for pi, i in itertools.pairwise(rows) for j in cols)
    G.add_edges_from(((i, j), (i, pj)) for i in rows for pj, j in itertools.pairwise(cols))

    try:
        periodic_r, periodic_c = periodic
    except TypeError:
        periodic_r = periodic_c = periodic

    if periodic_r and len(rows) > 2:
        first = rows[0]
        last = rows[-1]
        G.add_edges_from(((first, j), (last, j)) for j in cols)
    if periodic_c and len(cols) > 2:
        first = cols[0]
        last = cols[-1]
        G.add_edges_from(((i, first), (i, last)) for i in rows)
    if G.is_directed():
        G.add_edges_from((v, u) for u, v in list(G.edges()))
    return G


def barbell_graph(m1, m2, create_using=None):
    """Return the barbell graph."""
    if create_using is None:
        return _rust_barbell_graph(m1, m2)

    if m1 < 2:
        raise NetworkXError("Invalid graph description, m1 should be >=2")
    if m2 < 0:
        raise NetworkXError("Invalid graph description, m2 should be >=0")

    G = complete_graph(m1, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    G.add_nodes_from(range(m1, m1 + m2 - 1))
    if m2 > 1:
        G.add_edges_from(itertools.pairwise(range(m1, m1 + m2)))

    G.add_edges_from(
        (u, v) for u in range(m1 + m2, 2 * m1 + m2) for v in range(u + 1, 2 * m1 + m2)
    )
    G.add_edge(m1 - 1, m1)
    if m2 > 0:
        G.add_edge(m1 + m2 - 1, m1 + m2)
    return G


def bull_graph(create_using=None):
    """Return the bull graph."""
    if create_using is None:
        return _rust_bull_graph()
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 2, 3], 2: [0, 1, 4], 3: [1], 4: [2]},
        create_using=create_using,
        name="Bull Graph",
    )


def circular_ladder_graph(n, create_using=None):
    """Return the circular ladder graph."""
    if create_using is None:
        return _rust_circular_ladder_graph(n)

    G = ladder_graph(n, create_using)
    G.add_edge(0, n - 1)
    G.add_edge(n, 2 * n - 1)
    return G


def ladder_graph(n, create_using=None):
    """Return the ladder graph."""
    if create_using is None:
        return _rust_ladder_graph(n)

    G = empty_graph(2 * n, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")
    G.add_edges_from(itertools.pairwise(range(n)))
    G.add_edges_from(itertools.pairwise(range(n, 2 * n)))
    G.add_edges_from((v, v + n) for v in range(n))
    return G


def lollipop_graph(m, n, create_using=None):
    """Return the lollipop graph."""
    m_value, m_nodes = _nodes_or_number_local(m)
    M = len(m_nodes)
    if M < 2:
        raise NetworkXError("Invalid description: m should indicate at least 2 nodes")

    n_value, n_nodes = _nodes_or_number_local(n)
    if (
        create_using is None
        and isinstance(m_value, numbers.Integral)
        and isinstance(n_value, numbers.Integral)
    ):
        return _rust_lollipop_graph(m_value, n_value)

    if isinstance(m_value, numbers.Integral) and isinstance(n_value, numbers.Integral):
        n_nodes = list(range(M, M + n_value))
    N = len(n_nodes)

    G = complete_graph(m_nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    _add_nodes_in_order(G, n_nodes)
    if N > 1:
        G.add_edges_from(itertools.pairwise(n_nodes))

    if len(G) != M + N:
        raise NetworkXError("Nodes must be distinct in containers m and n")

    if M > 0 and N > 0:
        G.add_edge(m_nodes[-1], n_nodes[0])
    return G


def tadpole_graph(m, n, create_using=None):
    """Return the tadpole graph."""
    m_value, m_nodes = _nodes_or_number_local(m)
    M = len(m_nodes)
    if M < 2:
        raise NetworkXError("Invalid description: m should indicate at least 2 nodes")

    n_value, n_nodes = _nodes_or_number_local(n)
    if (
        create_using is None
        and isinstance(m_value, numbers.Integral)
        and isinstance(n_value, numbers.Integral)
    ):
        return _rust_tadpole_graph(m_value, n_value)

    if isinstance(m_value, numbers.Integral) and isinstance(n_value, numbers.Integral):
        n_nodes = list(range(M, M + n_value))

    G = cycle_graph(m_nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    G.add_edges_from(itertools.pairwise([m_nodes[-1], *n_nodes]))
    return G


def wheel_graph(n, create_using=None):
    """Return the wheel graph."""
    n_value, nodes = _nodes_or_number_local(n)
    if create_using is None and isinstance(n_value, numbers.Integral):
        return _rust_wheel_graph(n_value)

    G = empty_graph(nodes, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    if len(nodes) > 1:
        hub, *rim = nodes
        G.add_edges_from((hub, node) for node in rim)
        if len(rim) > 1:
            G.add_edges_from(itertools.pairwise(rim))
            G.add_edge(rim[-1], rim[0])
    return G


def diamond_graph(create_using=None):
    """Return the diamond graph."""
    if create_using is None:
        return _rust_diamond_graph()
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 2, 3], 2: [0, 1, 3], 3: [1, 2]},
        create_using=create_using,
        name="Diamond Graph",
    )


def house_graph(create_using=None):
    """Return the house graph."""
    if create_using is None:
        return _rust_house_graph()
    return _classic_named_graph_from_adjlist(
        {0: [1, 2], 1: [0, 3], 2: [0, 3, 4], 3: [1, 2, 4], 4: [2, 3]},
        create_using=create_using,
        name="House Graph",
    )


def house_x_graph(create_using=None):
    """Return the house-X graph."""
    if create_using is None:
        return _rust_house_x_graph()
    graph = house_graph(create_using=create_using)
    graph.add_edges_from([(0, 3), (1, 2)])
    graph.graph["name"] = "House-with-X-inside Graph"
    return graph


def cubical_graph(create_using=None):
    """Return the cubical graph."""
    if create_using is None:
        return _rust_cubical_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 3, 4],
            1: [0, 2, 7],
            2: [1, 3, 6],
            3: [0, 2, 5],
            4: [0, 5, 7],
            5: [3, 4, 6],
            6: [2, 5, 7],
            7: [1, 4, 6],
        },
        create_using=create_using,
        name="Platonic Cubical Graph",
    )


def petersen_graph(create_using=None):
    """Return the Petersen graph."""
    if create_using is None:
        return _rust_petersen_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 4, 5],
            1: [0, 2, 6],
            2: [1, 3, 7],
            3: [2, 4, 8],
            4: [3, 0, 9],
            5: [0, 7, 8],
            6: [1, 8, 9],
            7: [2, 5, 9],
            8: [3, 5, 6],
            9: [4, 6, 7],
        },
        create_using=create_using,
        name="Petersen Graph",
    )


def tetrahedral_graph(create_using=None):
    """Return the tetrahedral graph."""
    if create_using is None:
        return _rust_tetrahedral_graph()
    graph = complete_graph(4, create_using=create_using)
    graph.graph["name"] = "Platonic Tetrahedral Graph"
    return graph


def desargues_graph(create_using=None):
    """Return the Desargues graph."""
    if create_using is None:
        return _rust_desargues_graph()
    graph = LCF_graph(20, [5, -5, 9, -9], 5, create_using=create_using)
    graph.graph["name"] = "Desargues Graph"
    return graph


def dodecahedral_graph(create_using=None):
    """Return the dodecahedral graph."""
    if create_using is None:
        return _rust_dodecahedral_graph()
    graph = LCF_graph(
        20,
        [10, 7, 4, -4, -7, 10, -4, 7, -7, 4],
        2,
        create_using=create_using,
    )
    graph.graph["name"] = "Dodecahedral Graph"
    return graph


def heawood_graph(create_using=None):
    """Return the Heawood graph."""
    if create_using is None:
        return _rust_heawood_graph()
    graph = LCF_graph(14, [5, -5], 7, create_using=create_using)
    graph.graph["name"] = "Heawood Graph"
    return graph


def moebius_kantor_graph(create_using=None):
    """Return the Moebius-Kantor graph."""
    if create_using is None:
        return _rust_moebius_kantor_graph()
    graph = LCF_graph(16, [5, -5], 8, create_using=create_using)
    graph.graph["name"] = "Moebius-Kantor Graph"
    return graph


def octahedral_graph(create_using=None):
    """Return the octahedral graph."""
    if create_using is None:
        return _rust_octahedral_graph()
    return _classic_named_graph_from_adjlist(
        {0: [1, 2, 3, 4], 1: [2, 3, 5], 2: [4, 5], 3: [4, 5], 4: [5]},
        create_using=create_using,
        name="Platonic Octahedral Graph",
    )


def truncated_cube_graph(create_using=None):
    """Return the truncated cube graph."""
    if create_using is None:
        return _rust_truncated_cube_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 4],
            1: [11, 14],
            2: [3, 4],
            3: [6, 8],
            4: [5],
            5: [16, 18],
            6: [7, 8],
            7: [10, 12],
            8: [9],
            9: [17, 20],
            10: [11, 12],
            11: [14],
            12: [13],
            13: [21, 22],
            14: [15],
            15: [19, 23],
            16: [17, 18],
            17: [20],
            18: [19],
            19: [23],
            20: [21],
            21: [22],
            22: [23],
        },
        create_using=create_using,
        name="Truncated Cube Graph",
    )


def truncated_tetrahedron_graph(create_using=None):
    """Return the truncated tetrahedron graph."""
    if create_using is None:
        return _rust_truncated_tetrahedron_graph()
    graph = path_graph(12, create_using=create_using)
    graph.add_edges_from([(0, 2), (0, 9), (1, 6), (3, 11), (4, 11), (5, 7), (8, 10)])
    graph.graph["name"] = "Truncated Tetrahedron Graph"
    return graph


def chvatal_graph(create_using=None):
    """Return the Chvatal graph."""
    if create_using is None:
        return _rust_chvatal_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 4, 6, 9],
            1: [2, 5, 7],
            2: [3, 6, 8],
            3: [4, 7, 9],
            4: [5, 8],
            5: [10, 11],
            6: [10, 11],
            7: [8, 11],
            8: [10],
            9: [10, 11],
        },
        create_using=create_using,
        name="Chvatal Graph",
    )


def frucht_graph(create_using=None):
    """Return the Frucht graph."""
    if create_using is None:
        return _rust_frucht_graph()
    graph = cycle_graph(7, create_using=create_using)
    graph.add_edges_from(
        [
            (0, 7),
            (1, 7),
            (2, 8),
            (3, 9),
            (4, 9),
            (5, 10),
            (6, 10),
            (7, 11),
            (8, 11),
            (8, 9),
            (10, 11),
        ]
    )
    graph.graph["name"] = "Frucht Graph"
    return graph


def icosahedral_graph(create_using=None):
    """Return the icosahedral graph."""
    if create_using is None:
        return _rust_icosahedral_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 5, 7, 8, 11],
            1: [2, 5, 6, 8],
            2: [3, 6, 8, 9],
            3: [4, 6, 9, 10],
            4: [5, 6, 10, 11],
            5: [6, 11],
            7: [8, 9, 10, 11],
            8: [9],
            9: [10],
            10: [11],
        },
        create_using=create_using,
        name="Platonic Icosahedral Graph",
    )


def krackhardt_kite_graph(create_using=None):
    """Return the Krackhardt kite graph."""
    if create_using is None:
        return _rust_krackhardt_kite_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 3, 5],
            1: [0, 3, 4, 6],
            2: [0, 3, 5],
            3: [0, 1, 2, 4, 5, 6],
            4: [1, 3, 6],
            5: [0, 2, 3, 6, 7],
            6: [1, 3, 4, 5, 7],
            7: [5, 6, 8],
            8: [7, 9],
            9: [8],
        },
        create_using=create_using,
        name="Krackhardt Kite Social Network",
    )


def null_graph(create_using=None):
    """Return the null graph."""
    if create_using is None:
        return _rust_null_graph()
    return empty_graph(0, create_using=create_using)


def trivial_graph(create_using=None):
    """Return the trivial graph."""
    if create_using is None:
        return _rust_trivial_graph()
    return empty_graph(1, create_using=create_using)


def circulant_graph(n, offsets, create_using=None):
    """Return the circulant graph on n nodes with the given offsets."""
    if create_using is None:
        return _rust_circulant_graph(n, offsets)

    G = empty_graph(n, create_using)
    G.add_edges_from((i, (i - j) % n) for i in range(n) for j in offsets)
    G.add_edges_from((i, (i + j) % n) for i in range(n) for j in offsets)
    return G


def paley_graph(p, create_using=None):
    """Return the Paley graph or digraph of order p."""
    if create_using is None:
        return _rust_paley_graph(p)

    graph = empty_graph(0, create_using=create_using, default=DiGraph)
    if graph.is_multigraph():
        raise NetworkXError("`create_using` cannot be a multigraph.")

    square_set = {(x**2) % p for x in range(1, p) if (x**2) % p != 0}
    for x in range(p):
        for square in square_set:
            graph.add_edge(x, (x + square) % p)
    graph.graph["name"] = f"paley({p})"
    return graph


def chordal_cycle_graph(p, create_using=None):
    """Return the chordal cycle graph on p nodes."""
    if create_using is None:
        return _rust_chordal_cycle_graph(p)

    graph = empty_graph(0, create_using=create_using, default=MultiGraph)
    if graph.is_directed() or not graph.is_multigraph():
        raise NetworkXError("`create_using` must be an undirected multigraph.")

    for x in range(p):
        left = (x - 1) % p
        right = (x + 1) % p
        chord = pow(x, p - 2, p) if x > 0 else 0
        for y in (left, right, chord):
            graph.add_edge(x, y)
    graph.graph["name"] = f"chordal_cycle_graph({p})"
    return graph


def tutte_graph(create_using=None):
    """Return the Tutte graph."""
    if create_using is None:
        return _rust_tutte_graph()
    return _classic_named_graph_from_adjlist(
        {
            0: [1, 2, 3],
            1: [4, 26],
            2: [10, 11],
            3: [18, 19],
            4: [5, 33],
            5: [6, 29],
            6: [7, 27],
            7: [8, 14],
            8: [9, 38],
            9: [10, 37],
            10: [39],
            11: [12, 39],
            12: [13, 35],
            13: [14, 15],
            14: [34],
            15: [16, 22],
            16: [17, 44],
            17: [18, 43],
            18: [45],
            19: [20, 45],
            20: [21, 41],
            21: [22, 23],
            22: [40],
            23: [24, 27],
            24: [25, 32],
            25: [26, 31],
            26: [33],
            27: [28],
            28: [29, 32],
            29: [30],
            30: [31, 33],
            31: [32],
            34: [35, 38],
            35: [36],
            36: [37, 39],
            37: [38],
            40: [41, 44],
            41: [42],
            42: [43, 45],
            43: [44],
        },
        create_using=create_using,
        name="Tutte's Graph",
    )


def generalized_petersen_graph(n, k, create_using=None):
    """Return the generalized Petersen graph G(n, k)."""
    if create_using is None:
        return _rust_generalized_petersen_graph(n, k)

    if n <= 2:
        raise NetworkXError(f"n >= 3 required. Got {n=}")
    if k < 1 or k > n / 2:
        raise NetworkXError(f" Got {n=} {k=}. Need 1 <= k <= n/2")

    G = cycle_graph(range(n), create_using=create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported in create_using")
    for i in range(n):
        G.add_edge(i, n + i)
        G.add_edge(n + i, n + (i + k) % n)
    G.graph["name"] = f"Generalized Petersen Graph GP({n}, {k})"
    return G


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


def _planarity_graph_for_certificate(G):
    import networkx as nx

    try:
        from franken_networkx.backend import _fnx_to_nx

        return _fnx_to_nx(G)
    except AttributeError:
        if hasattr(G, "nodes") and hasattr(G, "edges"):
            return G
        graph = nx.Graph()
        graph.add_nodes_from(G)
        return graph


def _check_planarity_certificate(G, counterexample=False):
    import networkx as nx

    graph = _planarity_graph_for_certificate(G)
    return nx.check_planarity(graph, counterexample=counterexample)


def check_planarity(G, counterexample=False):
    """Check if *G* is planar and return a NetworkX-style certificate tuple.

    Parameters
    ----------
    G : Graph
    counterexample : bool, optional
        If True and the graph is not planar, return a Kuratowski subgraph as
        the certificate. Otherwise planar graphs return a PlanarEmbedding.

    Returns
    -------
    (bool, certificate)
    """
    return _check_planarity_certificate(G, counterexample=counterexample)


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
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "bidirectional_dijkstra", G, source, target, weight=weight
        )
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
    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    mmax = n * (n - 1) // 2
    if m >= mmax:
        return complete_graph(n, create_using=graph)

    graph = empty_graph(n, create_using=graph)
    if n == 1:
        return graph

    u = 0
    v = 1
    t = 0
    k = 0
    while True:
        if rng.randrange(mmax - t) < m - k:
            graph.add_edge(u, v)
            k += 1
            if k == m:
                return graph
        t += 1
        v += 1
        if v == n:
            u += 1
            v = u + 1


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


def _json_graph_from_flags(directed=False, multigraph=False):
    """Return the graph class implied by JSON graph payload flags."""
    if multigraph:
        return MultiDiGraph() if directed else MultiGraph()
    return DiGraph() if directed else Graph()


def _json_graph_to_tuple(value):
    """Convert JSON list nodes into tuple nodes, including nested lists."""
    if not isinstance(value, (tuple, list)):
        return value
    return tuple(_json_graph_to_tuple(item) for item in value)


def _add_json_multiedge(graph, source, target, edge_key, edge_attrs):
    """Add a multiedge while matching FNX's current non-integer-key contract."""
    if isinstance(edge_key, int) and not isinstance(edge_key, bool):
        graph.add_edge(source, target, key=edge_key)
        graph[source][target][edge_key].update(edge_attrs)
    else:
        actual_key = graph.add_edge(source, target)
        graph[source][target][actual_key].update(edge_attrs)


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
    attrs = {"id": "id", "key": "key"} if attrs is None else attrs
    multigraph = data.get("multigraph", multigraph)
    directed = data.get("directed", directed)
    graph = _json_graph_from_flags(directed=directed, multigraph=multigraph)
    id_ = attrs["id"]
    key = None if not multigraph else attrs["key"]
    graph.graph.update(dict(data.get("graph", [])))

    mapping = []
    for node_payload in data["nodes"]:
        node_data = node_payload.copy()
        node = node_data.pop(id_)
        mapping.append(node)
        graph.add_node(node)
        graph.nodes[node].update(node_data)

    for index, adjacency in enumerate(data["adjacency"]):
        source = mapping[index]
        for target_payload in adjacency:
            target_data = target_payload.copy()
            target = target_data.pop(id_)
            if not multigraph:
                graph.add_edge(source, target)
                graph[source][target].update(target_data)
            else:
                edge_key = target_data.pop(key, None)
                _add_json_multiedge(graph, source, target, edge_key, target_data)
    return graph


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
    multigraph = data.get("multigraph", multigraph)
    directed = data.get("directed", directed)
    graph = _json_graph_from_flags(directed=directed, multigraph=multigraph)
    key = None if not multigraph else key
    graph.graph.update(dict(data.get("graph", {})))

    counter = count()
    for node_payload in data[nodes]:
        node = _json_graph_to_tuple(node_payload.get(name, next(counter)))
        node_data = {str(k): v for k, v in node_payload.items() if k != name}
        graph.add_node(node, **node_data)

    for edge_payload in data[edges]:
        source_node = _json_graph_to_tuple(edge_payload[source])
        target_node = _json_graph_to_tuple(edge_payload[target])
        if not multigraph:
            edge_data = {
                str(k): v
                for k, v in edge_payload.items()
                if k != source and k != target
            }
            graph.add_edge(source_node, target_node, **edge_data)
        else:
            edge_key = edge_payload.get(key, None)
            edge_data = {
                str(k): v
                for k, v in edge_payload.items()
                if k != source and k != target and k != key
            }
            _add_json_multiedge(
                graph,
                source_node,
                target_node,
                edge_key,
                edge_data,
            )
    return graph


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
    R = union_all([G, H], rename=rename)

    def add_prefix(graph, prefix):
        if prefix is None:
            return graph
        return relabel_nodes(graph, lambda node: f"{prefix}{node}")

    G = add_prefix(G, rename[0])
    H = add_prefix(H, rename[1])

    for gn in G:
        for hn in H:
            R.add_edge(gn, hn)
    if R.is_directed():
        for hn in H:
            for gn in G:
                R.add_edge(hn, gn)

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

    def add_node_with_deferred_contraction(graph, node, attrs):
        attrs = dict(attrs)
        deferred_contraction = None
        if store_contraction_as:
            deferred_contraction = attrs.pop(store_contraction_as, None)
        graph.add_node(node, **attrs)
        if deferred_contraction is not None:
            graph.nodes[node][store_contraction_as] = deferred_contraction

    def add_edge_with_deferred_contraction(graph, source, target, attrs):
        attrs = dict(attrs)
        deferred_contraction = None
        if store_contraction_as:
            deferred_contraction = attrs.pop(store_contraction_as, None)
        graph.add_edge(source, target, **attrs)
        if deferred_contraction is not None:
            graph.edges[source, target][store_contraction_as] = deferred_contraction

    # Add all nodes except v, preserving insertion order from G
    for n in G.nodes():
        if n == v:
            continue
        attrs = dict(G.nodes[n])
        if n == u and store_contraction_as:
            contraction = attrs.get(store_contraction_as, {})
            contraction[v] = v_data
            attrs[store_contraction_as] = contraction
        add_node_with_deferred_contraction(H, n, attrs)

    def add_or_contract_edge(src, dst, d):
        new_src = u if src == v else src
        new_dst = u if dst == v else dst
        if {src, dst} == {u, v} and not self_loops:
            return
        if H.has_edge(new_src, new_dst) and not G.is_multigraph():
            if store_contraction_as:
                contraction = H.edges[new_src, new_dst].get(store_contraction_as, {})
                if not G.is_directed() and (src == v or dst == v):
                    other = dst if src == v else src
                    contraction_edge = (v, other)
                else:
                    contraction_edge = (src, dst)
                contraction[contraction_edge] = dict(d)
                H.edges[new_src, new_dst][store_contraction_as] = contraction
            return
        add_edge_with_deferred_contraction(H, new_src, new_dst, d)

    # Add stable edges first, then remap v's edges. NetworkX preserves the
    # existing edge attributes and records remapped duplicates as contractions.
    edges = list(G.edges(data=True))
    for src, dst, d in edges:
        if src != v and dst != v:
            add_edge_with_deferred_contraction(H, src, dst, d)
    for src, dst, d in edges:
        if src == v or dst == v:
            add_or_contract_edge(src, dst, d)

    if not copy:
        G.clear()
        for n in H.nodes():
            add_node_with_deferred_contraction(G, n, H.nodes[n])
        for s, t, d_attr in H.edges(data=True):
            add_edge_with_deferred_contraction(G, s, t, d_attr)
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


def contracted_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
):
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
    return identified_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
    )


def contracted_edge(
    G,
    edge,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
):
    """Contract an edge in *G* by merging its endpoints.

    Parameters
    ----------
    G : Graph
    edge : tuple (u, v)
    self_loops : bool, optional
    copy : bool, optional
    """
    u, v = edge[:2]
    if not G.has_edge(u, v):
        raise ValueError(f"Edge {edge} does not exist in graph G; cannot contract it")
    return contracted_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
    )


# ---------------------------------------------------------------------------
# Global type predicates (function form)
# ---------------------------------------------------------------------------


def is_directed(G):
    """Return True if *G* is a directed graph."""
    return G.is_directed()


# ---------------------------------------------------------------------------
# Degree sequence generators
# ---------------------------------------------------------------------------


def _degree_sequence_stublist(degree_sequence):
    return [
        node
        for node, degree in enumerate(degree_sequence)
        for _ in range(int(degree))
    ]


def _configuration_model_local(
    degree_sequence,
    create_using,
    *,
    directed=False,
    in_degree_sequence=None,
    seed=None,
):
    graph = _empty_graph_from_create_using(create_using)
    graph.add_nodes_from(range(len(degree_sequence)))
    if len(degree_sequence) == 0:
        return graph

    rng = _generator_random_state(seed)
    if directed:
        pairs = itertools.zip_longest(degree_sequence, in_degree_sequence, fillvalue=0)
        out_degrees, in_degrees = zip(*pairs)
        out_stubs = _degree_sequence_stublist(out_degrees)
        in_stubs = _degree_sequence_stublist(in_degrees)
        rng.shuffle(out_stubs)
        rng.shuffle(in_stubs)
    else:
        stubs = _degree_sequence_stublist(degree_sequence)
        rng.shuffle(stubs)
        half = len(stubs) // 2
        out_stubs = stubs[:half]
        in_stubs = stubs[half:]

    graph.add_edges_from(zip(out_stubs, in_stubs))
    return graph


def _is_graphical_degree_sequence(degree_sequence):
    try:
        sequence = [int(degree) for degree in degree_sequence]
    except (TypeError, ValueError):
        return False
    if any(degree < 0 for degree in sequence):
        return False
    return is_valid_degree_sequence_erdos_gallai(sequence)


def _random_weighted_sample(mapping, k, rng):
    if k > len(mapping):
        raise ValueError("sample larger than population")
    sample = set()
    while len(sample) < k:
        sample.add(_weighted_choice(mapping, rng))
    return list(sample)


def _weighted_choice(mapping, rng):
    threshold = rng.random() * sum(mapping.values())
    for key, weight in mapping.items():
        threshold -= weight
        if threshold < 0:
            return key
    return next(reversed(mapping))


class _DegreeSequenceRandomGraph:
    def __init__(self, degree, rng):
        self.rng = rng
        self.degree = list(degree)
        if not _is_graphical_degree_sequence(self.degree):
            raise NetworkXUnfeasible("degree sequence is not graphical")
        self.m = sum(self.degree) / 2.0
        self.dmax = max(self.degree, default=0)

    def generate(self):
        self.remaining_degree = dict(enumerate(self.degree))
        self.graph = Graph()
        self.graph.add_nodes_from(self.remaining_degree)
        for node, degree in list(self.remaining_degree.items()):
            if degree == 0:
                del self.remaining_degree[node]
        if self.remaining_degree:
            self._phase1()
            self._phase2()
            self._phase3()
        return self.graph

    def _update_remaining(self, u, v, aux_graph=None):
        if aux_graph is not None:
            aux_graph.remove_edge(u, v)
        if self.remaining_degree[u] == 1:
            del self.remaining_degree[u]
            if aux_graph is not None:
                aux_graph.remove_node(u)
        else:
            self.remaining_degree[u] -= 1
        if self.remaining_degree[v] == 1:
            del self.remaining_degree[v]
            if aux_graph is not None:
                aux_graph.remove_node(v)
        else:
            self.remaining_degree[v] -= 1

    def _degree_probability(self, u, v):
        return 1 - self.degree[u] * self.degree[v] / (4.0 * self.m)

    def _remaining_probability(self, u, v):
        norm = max(self.remaining_degree.values()) ** 2
        return self.remaining_degree[u] * self.remaining_degree[v] / norm

    def _has_suitable_edge(self):
        nodes = iter(self.remaining_degree)
        u = next(nodes)
        return any(not self.graph.has_edge(u, v) for v in nodes)

    def _phase1(self):
        remaining = self.remaining_degree
        while sum(remaining.values()) >= 2 * self.dmax**2:
            u, v = sorted(_random_weighted_sample(remaining, 2, self.rng))
            if self.graph.has_edge(u, v):
                continue
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v)

    def _phase2(self):
        remaining = self.remaining_degree
        while len(remaining) >= 2 * self.dmax:
            while True:
                u, v = sorted(self.rng.sample(list(remaining.keys()), 2))
                if self.graph.has_edge(u, v):
                    continue
                if self.rng.random() < self._remaining_probability(u, v):
                    break
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v)

    def _phase3(self):
        aux_graph = Graph()
        aux_graph.add_edges_from(
            (u, v)
            for u, v in combinations(self.remaining_degree, 2)
            if not self.graph.has_edge(u, v)
        )
        while self.remaining_degree:
            if not self._has_suitable_edge():
                raise NetworkXUnfeasible("no suitable edges left")
            while True:
                u, v = sorted(self.rng.choice(list(aux_graph.edges())))
                if self.rng.random() < self._remaining_probability(u, v):
                    break
            if self.rng.random() < self._degree_probability(u, v):
                self.graph.add_edge(u, v)
                self._update_remaining(u, v, aux_graph=aux_graph)


def _neighbor_switch_local(graph, w, unsat, residual, avoid_node_id=None):
    if avoid_node_id is None or residual[avoid_node_id] > 1:
        w_prime = next(iter(unsat))
    else:
        iterator = iter(unsat)
        while True:
            w_prime = next(iterator)
            if w_prime != avoid_node_id:
                break

    for switch_node in graph.neighbors(w):
        if not graph.has_edge(w_prime, switch_node) and switch_node != w_prime:
            graph.remove_edge(w, switch_node)
            graph.add_edge(w_prime, switch_node)
            residual[w] += 1
            residual[w_prime] -= 1
            if residual[w_prime] == 0:
                unsat.remove(w_prime)
            return


def _directed_neighbor_switch_local(
    graph,
    w,
    unsat,
    residual_out,
    chords,
    partition_in,
    partition,
):
    w_prime = unsat.pop()
    unsat.add(w_prime)
    w_prime_neighbors = set(graph.successors(w_prime))
    for v in list(graph.successors(w)):
        if v not in w_prime_neighbors and w_prime != v:
            graph.remove_edge(w, v)
            graph.add_edge(w_prime, v)
            if partition_in[v] == partition:
                chords.add((w, v))
                chords.discard((w_prime, v))
            residual_out[w] += 1
            residual_out[w_prime] -= 1
            if residual_out[w_prime] == 0:
                unsat.remove(w_prime)
            return None
    return w_prime


def _directed_neighbor_switch_rev_local(
    graph,
    w,
    unsat,
    residual_in,
    chords,
    partition_out,
    partition,
):
    w_prime = unsat.pop()
    unsat.add(w_prime)
    w_prime_predecessors = set(graph.predecessors(w_prime))
    for v in list(graph.predecessors(w)):
        if v not in w_prime_predecessors and w_prime != v:
            graph.remove_edge(v, w)
            graph.add_edge(v, w_prime)
            if partition_out[v] == partition:
                chords.add((v, w))
                chords.discard((v, w_prime))
            residual_in[w] += 1
            residual_in[w_prime] -= 1
            if residual_in[w_prime] == 0:
                unsat.remove(w_prime)
            return None
    return w_prime


def configuration_model(deg_sequence, create_using=None, seed=None):
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
    if sum(deg_sequence) % 2 != 0:
        raise NetworkXError("Invalid degree sequence: sum of degrees must be even, not odd")

    graph = _checked_create_using(create_using, directed=False, default=MultiGraph)
    return _configuration_model_local(deg_sequence, graph, seed=seed)


def havel_hakimi_graph(deg_sequence, create_using=None):
    """Return a simple graph with the given degree sequence."""
    if not _is_graphical_degree_sequence(deg_sequence):
        raise NetworkXError("Invalid degree sequence")

    degree_sequence = list(deg_sequence)
    p = len(degree_sequence)
    graph = _checked_create_using(create_using, directed=False, default=Graph)
    graph.add_nodes_from(range(p))

    degree_buckets = [[] for _ in range(p)]
    dmax = 0
    active = 0
    for node, degree in enumerate(degree_sequence):
        if degree > 0:
            degree_buckets[degree].append(node)
            dmax = max(dmax, degree)
            active += 1
    if active == 0:
        return graph

    modified = [(0, 0)] * (dmax + 1)
    while active > 0:
        while not degree_buckets[dmax]:
            dmax -= 1
        if dmax > active - 1:
            raise NetworkXError("Non-graphical integer sequence")

        source = degree_buckets[dmax].pop()
        active -= 1
        modified_len = 0
        k = dmax
        for _ in range(dmax):
            while not degree_buckets[k]:
                k -= 1
            target = degree_buckets[k].pop()
            graph.add_edge(source, target)
            active -= 1
            if k > 1:
                modified[modified_len] = (k - 1, target)
                modified_len += 1

        for i in range(modified_len):
            stub_value, stub_target = modified[i]
            degree_buckets[stub_value].append(stub_target)
            active += 1

    return graph


def degree_sequence_tree(deg_sequence, create_using=None):
    """Return a tree with the given degree sequence, if possible.

    Parameters
    ----------
    deg_sequence : list of int
    create_using : graph constructor, optional

    Returns
    -------
    Graph
        A tree with the given degree sequence.
    """
    deg_sequence = list(deg_sequence)
    number_of_nodes = len(deg_sequence)
    twice_number_of_edges = sum(deg_sequence)

    if 2 * number_of_nodes - twice_number_of_edges != 2:
        raise NetworkXError("tree must have one more node than number of edges")
    if deg_sequence != [0] and any(degree <= 0 for degree in deg_sequence):
        raise NetworkXError("nontrivial tree must have strictly positive node degrees")

    graph = empty_graph(0, create_using=create_using)
    if graph.is_directed():
        raise NetworkXError("Directed Graph not supported")

    if deg_sequence == [0]:
        graph.add_node(0)
        return graph

    degrees = sorted((degree for degree in deg_sequence if degree > 1), reverse=True)
    backbone_nodes = len(degrees) + 2
    add_path(graph, range(backbone_nodes))
    last = backbone_nodes

    for source in range(1, backbone_nodes - 1):
        extra_edges = degrees.pop() - 2
        graph.add_edges_from((source, target) for target in range(last, last + extra_edges))
        last += extra_edges
    return graph


def common_neighbor_centrality(G, ebunch=None, alpha=0.8):
    """Return the CCPA score for each pair of nodes."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    if alpha == 1:

        def predict(u, v):
            if u == v:
                raise NetworkXAlgorithmError("Self loops are not supported")
            return len(common_neighbors(G, u, v))

    else:
        shortest_path_lengths = dict(shortest_path_length(G))
        infinity = float("inf")

        def predict(u, v):
            if u == v:
                raise NetworkXAlgorithmError("Self loops are not supported")
            path_length = shortest_path_lengths[u].get(v, infinity)
            common_neighbor_count = len(common_neighbors(G, u, v))
            return alpha * common_neighbor_count + (1 - alpha) * len(G) / path_length

    if ebunch is None:
        ebunch = non_edges(G)
    else:
        for u, v in ebunch:
            if u not in G:
                raise NodeNotFound(f"Node {u} not in G.")
            if v not in G:
                raise NodeNotFound(f"Node {v} not in G.")

    return ((u, v, predict(u, v)) for u, v in ebunch)


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
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("LCA only defined on directed acyclic graphs.")
    if len(G) == 0:
        raise NetworkXPointlessConcept("LCA meaningless on null graphs.")

    if pairs is None:
        from itertools import combinations_with_replacement

        pairs = combinations_with_replacement(G, 2)
    else:
        pairs = dict.fromkeys(pairs)
        nodeset = set(G)
        for pair in pairs:
            missing = set(pair) - nodeset
            if missing:
                raise NodeNotFound(f"Node(s) {missing} from pair {pair} not in G.")

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


def multi_source_dijkstra(G, sources, weight="weight"):
    """Return shortest path lengths and paths from any source in *sources*."""
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _call_networkx_for_parity(
            "multi_source_dijkstra", G, sources, weight=weight
        )
    return _raw_multi_source_dijkstra(G, sources, weight=weight)


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
    # Convert generator to dict for NetworkX API compatibility
    return dict(all_pairs_dijkstra_path_length(G, weight=weight))


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
            raise NetworkXUnfeasible("no flow satisfies all node demands")
    for sink in sinks:
        if remaining_demand.get(sink, 0) > 1e-10:
            raise NetworkXUnfeasible("no flow satisfies all node demands")

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
        raise NetworkXNotImplemented("not implemented for undirected type")

    nodes = list(G.nodes())
    n = len(nodes)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                yield G.subgraph([nodes[i], nodes[j], nodes[k]]).copy()


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
    return (
        G.is_directed()
        and G.number_of_nodes() == 3
        and not any((node, node) in G.edges() for node in G.nodes())
    )


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
    sequence = _make_list_of_ints(sequence)
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
    sequence = _make_list_of_ints(sequence)
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
    degree_count = {}
    for degree in joint_degrees:
        if degree > 0:
            degree_size = sum(joint_degrees[degree].values()) / degree
            if not degree_size.is_integer():
                return False
            degree_count[degree] = degree_size

    for degree_left in joint_degrees:
        for degree_right in joint_degrees[degree_left]:
            edge_count = joint_degrees[degree_left][degree_right]
            if not float(edge_count).is_integer():
                return False

            if (
                degree_left != degree_right
                and edge_count > degree_count[degree_left] * degree_count[degree_right]
            ):
                return False
            if degree_left == degree_right:
                if edge_count > degree_count[degree_left] * (
                    degree_count[degree_left] - 1
                ):
                    return False
                if edge_count % 2 != 0:
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
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    _validate_product_graph_types(G, H, allow_multigraph=True)

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
            # Match NetworkX's add_edges_from(H.edges.data()) behavior by letting the
            # product graph assign fresh integer keys for copied multiedges.
            for u, v, attrs in H.edges(data=True):
                P.add_edge((g, u), (g, v), **dict(attrs))
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
    if G.is_directed() or H.is_directed():
        raise NetworkXNotImplemented("Modular product not implemented for directed graphs")
    if G.is_multigraph() or H.is_multigraph():
        raise NetworkXNotImplemented("Modular product not implemented for multigraphs")
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
    if G.is_multigraph():
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


def _simple_graph_weighted_shortest_path_lengths(G, source, weight):
    distances = {source: 0.0}
    counter = count()
    queue = [(0.0, next(counter), source)]

    while queue:
        distance, _, node = heappop(queue)
        if distance > distances[node]:
            continue

        for neighbor in G.neighbors(node):
            edge_weight = G.get_edge_data(node, neighbor).get(weight, 1)
            candidate = distance + edge_weight
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                heappush(queue, (candidate, next(counter), neighbor))

    return distances


def gutman_index(G, weight=None):
    """Return the Gutman index (degree-distance) of *G*.

    Sum over all pairs of deg(u)*deg(v)*dist(u,v).
    """
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not is_connected(G):
        return float("inf")

    degrees = dict(G.degree)
    if weight is None:
        spl = shortest_path_length(G)
        return sum(
            dist * degrees[u] * degrees[v]
            for u, vinfo in spl
            for v, dist in vinfo.items()
        ) / 2

    return sum(
        dist * degrees[u] * degrees[v]
        for u in G
        for v, dist in _simple_graph_weighted_shortest_path_lengths(
            G, u, weight
        ).items()
    ) / 2


def schultz_index(G, weight=None):
    """Return the Schultz index of *G*.

    Sum over all pairs of (deg(u)+deg(v))*dist(u,v).
    """
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not is_connected(G):
        return float("inf")

    degrees = dict(G.degree)
    if weight is None:
        spl = shortest_path_length(G)
        return sum(
            dist * (degrees[u] + degrees[v])
            for u, vinfo in spl
            for v, dist in vinfo.items()
        ) / 2

    return sum(
        dist * (degrees[u] + degrees[v])
        for u in G
        for v, dist in _simple_graph_weighted_shortest_path_lengths(
            G, u, weight
        ).items()
    ) / 2


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

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        raise NetworkXError("Graph G must contain at least one node.")

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


def non_randomness(G, k=None, weight="weight"):
    """Compute the non-randomness of a graph."""
    import numpy as np

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.number_of_edges() == 0:
        raise NetworkXError("non_randomness not applicable to empty graphs")
    if not is_connected(G):
        raise _nx.NetworkXException("Non connected graph.")
    if len(list(selfloop_edges(G))) > 0:
        raise NetworkXError("Graph must not contain self-loops")

    n = G.number_of_nodes()
    m = G.number_of_edges()

    if k is None:
        community_graph = _nx.Graph()
        community_graph.add_nodes_from(G.nodes(data=True))
        community_graph.add_edges_from(G.edges(data=True))
        k = len(tuple(_nx.community.label_propagation_communities(community_graph)))

    p = (2 * k * m) / (n * (n - k))
    if not 1 <= k < n or not 0 < p < 1:
        raise ValueError(
            f"invalid number of communities for graph with {n} nodes and {m} edges: {k}"
        )

    eigenvalues = np.linalg.eigvals(to_numpy_array(G, weight=weight))
    nr = float(np.real(np.sum(eigenvalues[:k])))
    nr_rd = (nr - ((n - 2 * k) * p + k)) / math.sqrt(2 * k * p * (1 - p))
    return nr, nr_rd


def is_distance_regular(G):
    """Returns True if the graph is distance regular, False otherwise."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")
    return _raw_is_distance_regular(G)


def sigma(G, niter=100, nrand=10, seed=None):
    """Return the small-world sigma coefficient.

    sigma = (C/C_rand) / (L/L_rand) where C is clustering, L is avg path.
    sigma > 1 indicates small-world structure.
    """
    import numpy as np
    import random as _random

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")

    rng = _random.Random(seed)
    rand_metrics = {"C": [], "L": []}
    for _ in range(nrand):
        reference = random_reference(G, niter=niter, seed=rng.randint(0, 2**31))
        rand_metrics["C"].append(transitivity(reference))
        rand_metrics["L"].append(average_shortest_path_length(reference))

    C = transitivity(G)
    L = average_shortest_path_length(G)
    Cr = np.mean(rand_metrics["C"])
    Lr = np.mean(rand_metrics["L"])

    return float((C / Cr) / (L / Lr))


def omega(G, niter=5, nrand=5, seed=None):
    """Return the small-world omega coefficient.

    omega = L_rand/L - C/C_lattice.
    omega near 0 = small-world, near -1 = lattice, near 1 = random.
    """
    import numpy as np

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) == 0:
        raise ZeroDivisionError("division by zero")

    rng = _generator_random_state(seed)
    rand_metrics = {"L": []}
    Cl = average_clustering(G)

    niter_lattice_reference = niter
    niter_random_reference = niter * 2

    for _ in range(nrand):
        reference_random = random_reference(
            G,
            niter=niter_random_reference,
            seed=rng.randint(0, 2**31 - 1),
        )
        rand_metrics["L"].append(average_shortest_path_length(reference_random))

        reference_lattice = lattice_reference(
            G,
            niter=niter_lattice_reference,
            seed=rng.randint(0, 2**31 - 1),
        )
        Cl_temp = average_clustering(reference_lattice)
        if Cl_temp > Cl:
            Cl = Cl_temp

    C = average_clustering(G)
    L = average_shortest_path_length(G)
    Lr = np.mean(rand_metrics["L"])

    return float((Lr / L) - (C / Cl))


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

    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")
    if walk_length < 0:
        raise ValueError(f"`walk_length` cannot be negative: {walk_length}")
    if not isinstance(walk_length, numbers.Integral):
        raise ValueError("exponent must be an integer")

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
    """Return a frozen live undirected view of G."""
    if G.is_multigraph():
        return _UndirectedMultiGraphConversionView(G)
    return _UndirectedGraphConversionView(G)


def to_directed(G):
    """Return a frozen live directed view of G."""
    if G.is_multigraph():
        return _DirectedMultiGraphConversionView(G)
    return _DirectedGraphConversionView(G)


class _ReverseDirectedView:
    def __init__(self, graph):
        self._graph = graph
        self.graph = graph.graph
        self.frozen = True

    def __iter__(self):
        return iter(self._graph)

    def __len__(self):
        return len(self._graph)

    def __contains__(self, node):
        return node in self._graph

    def is_directed(self):
        return True

    def is_multigraph(self):
        return self._graph.is_multigraph()

    def nodes(self, data=False):
        return self._graph.nodes(data=data)

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self._graph.nodes())
        if nbunch in self._graph:
            return [nbunch]
        try:
            return [node for node in nbunch if node in self._graph]
        except TypeError:
            return []

    def edges(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        result = []
        if self._graph.is_multigraph():
            for source in nodes:
                for target, keyed_attrs in self._graph.pred[source].items():
                    for key, attrs in keyed_attrs.items():
                        if data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
        else:
            for source in nodes:
                for target, attrs in self._graph.pred[source].items():
                    if data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
        return result

    def number_of_edges(self):
        return self._graph.number_of_edges()

    def has_edge(self, u, v, key=None):
        if self._graph.is_multigraph():
            return self._graph.has_edge(v, u, key)
        return self._graph.has_edge(v, u)

    def neighbors(self, node):
        return self._graph.predecessors(node)

    def successors(self, node):
        return self._graph.predecessors(node)

    def predecessors(self, node):
        return self._graph.successors(node)

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        raise AttributeError(name)


_FILTERED_VIEW_MUTATORS = (
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
)


class _FilteredNeighborMap(Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._view = view
        self._node = node
        self._reverse = reverse

    def _raw_neighbors(self):
        if self._view.is_directed():
            if self._reverse:
                return self._view._graph.pred[self._node]
            return self._view._graph.succ[self._node]
        return self._view._graph.adj[self._node]

    def _edge_visible(self, neighbor, key=None):
        if self._reverse:
            return self._view._edge_visible(neighbor, self._node, key)
        return self._view._edge_visible(self._node, neighbor, key)

    def __iter__(self):
        for neighbor, edge_data in self._raw_neighbors().items():
            if not self._view._node_visible(neighbor):
                continue
            if self._view.is_multigraph():
                if any(self._edge_visible(neighbor, key) for key in edge_data):
                    yield neighbor
            elif self._edge_visible(neighbor):
                yield neighbor

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, neighbor):
        if not self._view._node_visible(neighbor):
            raise KeyError(f"Key {neighbor} not found")

        if self._view.is_multigraph():
            keydict = self._raw_neighbors()[neighbor]
            filtered = {
                key: attrs
                for key, attrs in keydict.items()
                if self._edge_visible(neighbor, key)
            }
            if filtered:
                return filtered
        else:
            if self._edge_visible(neighbor):
                return self._raw_neighbors()[neighbor]

        raise KeyError(f"Key {neighbor} not found")


class _FilteredAdjacencyView(Mapping):
    def __init__(self, view, *, reverse=False):
        self._view = view
        self._reverse = reverse

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        if not self._view._node_visible(node):
            raise KeyError(f"Key {node} not found")
        return _FilteredNeighborMap(self._view, node, reverse=self._reverse)


class _FilteredGraphView:
    def __init__(self, graph, *, filter_node=None, filter_edge=None):
        self._graph = graph
        self.graph = graph.graph
        self._filter_node = filter_node or (lambda node: True)
        self._filter_edge = filter_edge or (lambda *args: True)
        self.frozen = True
        self.adj = _FilteredAdjacencyView(self)
        if graph.is_directed():
            self.succ = _FilteredAdjacencyView(self)
            self.pred = _FilteredAdjacencyView(self, reverse=True)

    def __iter__(self):
        for node in self._graph:
            if self._node_visible(node):
                yield node

    def __len__(self):
        return sum(1 for _ in self)

    def __contains__(self, node):
        return self._node_visible(node)

    def __getitem__(self, node):
        return self.adj[node]

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        return getattr(self.copy(), name)

    def is_directed(self):
        return self._graph.is_directed()

    def is_multigraph(self):
        return self._graph.is_multigraph()

    def _node_visible(self, node):
        return node in self._graph and self._filter_node(node)

    def _edge_visible(self, u, v, key=None):
        if not (self._node_visible(u) and self._node_visible(v)):
            return False
        if self.is_multigraph():
            return self._filter_edge(u, v, key)
        return self._filter_edge(u, v)

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self)
        if self._node_visible(nbunch):
            return [nbunch]
        try:
            return [node for node in nbunch if self._node_visible(node)]
        except TypeError:
            return []

    def nodes(self, data=False):
        if data:
            return [(node, self._graph.nodes[node]) for node in self]
        return list(self)

    def edges(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        result = []
        if self.is_directed():
            for source in nodes:
                for target in self.adj[source]:
                    if self.is_multigraph():
                        for key, attrs in self.adj[source][target].items():
                            if data and keys:
                                result.append((source, target, key, attrs))
                            elif data:
                                result.append((source, target, attrs))
                            elif keys:
                                result.append((source, target, key))
                            else:
                                result.append((source, target))
                    else:
                        attrs = self.adj[source][target]
                        if data:
                            result.append((source, target, attrs))
                        else:
                            result.append((source, target))
            return result

        seen = set()
        for source in nodes:
            for target in self.adj[source]:
                if target in seen:
                    continue
                if self.is_multigraph():
                    for key, attrs in self.adj[source][target].items():
                        if data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
                else:
                    attrs = self.adj[source][target]
                    if data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
            seen.add(source)
        return result

    def neighbors(self, node):
        if not self._node_visible(node):
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.adj[node])

    def successors(self, node):
        return self.neighbors(node)

    def predecessors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if not self._node_visible(node):
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.pred[node])

    def has_edge(self, u, v, key=None):
        if self.is_multigraph():
            if not self._graph.has_edge(u, v, key):
                return False
            if key is not None:
                return self._edge_visible(u, v, key)
            return any(self._edge_visible(u, v, edge_key) for edge_key in self._graph[u][v])
        if not self._graph.has_edge(u, v):
            return False
        return self._edge_visible(u, v)

    def number_of_nodes(self):
        return len(self)

    def number_of_edges(self):
        return len(self.edges(keys=True)) if self.is_multigraph() else len(self.edges())

    def copy(self):
        result = self._graph.__class__()
        result.graph.update(dict(self.graph))
        result.add_nodes_from((node, dict(attrs)) for node, attrs in self.nodes(data=True))
        if self.is_multigraph():
            for u, v, key, attrs in self.edges(keys=True, data=True):
                result.add_edge(u, v, key=key, **dict(attrs))
        else:
            for u, v, attrs in self.edges(data=True):
                result.add_edge(u, v, **dict(attrs))
        return result


class _ConversionNodeView(Mapping):
    def __init__(self, view):
        self._view = view

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        return self._view._graph.nodes[node]

    def __call__(self, data=False):
        if data:
            return [(node, self[node]) for node in self]
        return list(self)


class _ConversionEdgeView:
    def __init__(self, view):
        self._view = view

    def __iter__(self):
        return iter(self())

    def __len__(self):
        return len(self())

    def __call__(self, nbunch=None, data=False, keys=False):
        return self._view._edges(nbunch=nbunch, data=data, keys=keys)


class _UnionKeyAtlas(Mapping):
    def __init__(self, primary, secondary):
        self._primary = primary
        self._secondary = secondary

    def __iter__(self):
        yielded = set()
        for key in self._primary:
            yielded.add(key)
            yield key
        for key in self._secondary:
            if key not in yielded:
                yield key

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, key):
        if key in self._primary:
            return self._primary[key]
        return self._secondary[key]


class _ConversionNeighborMap(Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._view = view
        self._node = node
        self._reverse = reverse

    def __iter__(self):
        if self._reverse:
            yield from self._view._pred_neighbors(self._node)
        else:
            yield from self._view._adj_neighbors(self._node)

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, neighbor):
        if self._reverse:
            return self._view._pred_neighbor_value(self._node, neighbor)
        return self._view._adj_neighbor_value(self._node, neighbor)


class _ConversionAdjacencyView(Mapping):
    def __init__(self, view, *, reverse=False):
        self._view = view
        self._reverse = reverse

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        if node not in self._view._graph:
            raise KeyError(f"Key {node} not found")
        return _ConversionNeighborMap(self._view, node, reverse=self._reverse)


class _ConversionGraphViewBase:
    _directed = False
    _multigraph = False

    def __init__(self, graph):
        self._graph = graph
        self.graph = graph.graph
        self.frozen = True
        self.nodes = _ConversionNodeView(self)
        self.edges = _ConversionEdgeView(self)
        self.adj = _ConversionAdjacencyView(self)
        if self.is_directed():
            self.succ = self.adj
            self.pred = _ConversionAdjacencyView(self, reverse=True)

    def __iter__(self):
        return iter(self._graph)

    def __len__(self):
        return len(self._graph)

    def __contains__(self, node):
        return node in self._graph

    def __getitem__(self, node):
        return self.adj[node]

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        return getattr(self.copy(), name)

    def is_directed(self):
        return self._directed

    def is_multigraph(self):
        return self._multigraph

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self)
        if nbunch in self._graph:
            return [nbunch]
        try:
            return [node for node in nbunch if node in self._graph]
        except TypeError:
            return []

    def _adj_neighbors(self, node):
        raise NotImplementedError

    def _adj_neighbor_value(self, node, neighbor):
        raise NotImplementedError

    def _pred_neighbors(self, node):
        yield from self._adj_neighbors(node)

    def _pred_neighbor_value(self, node, neighbor):
        return self._adj_neighbor_value(node, neighbor)

    def _edges(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        result = []
        if self.is_directed():
            for source in nodes:
                for target in self.adj[source]:
                    if self.is_multigraph():
                        for key, attrs in self.adj[source][target].items():
                            if data and keys:
                                result.append((source, target, key, attrs))
                            elif data:
                                result.append((source, target, attrs))
                            elif keys:
                                result.append((source, target, key))
                            else:
                                result.append((source, target))
                    else:
                        attrs = self.adj[source][target]
                        if data:
                            result.append((source, target, attrs))
                        else:
                            result.append((source, target))
            return result

        seen = set()
        for source in nodes:
            for target in self.adj[source]:
                if self.is_multigraph():
                    for key, attrs in self.adj[source][target].items():
                        marker = (frozenset((source, target)), key)
                        if marker in seen:
                            continue
                        seen.add(marker)
                        if data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
                else:
                    marker = frozenset((source, target))
                    if marker in seen:
                        continue
                    seen.add(marker)
                    attrs = self.adj[source][target]
                    if data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
        return result

    def neighbors(self, node):
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.adj[node])

    def successors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.succ[node])

    def predecessors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.pred[node])

    def number_of_nodes(self):
        return len(self)

    def number_of_edges(self):
        if self.is_multigraph():
            return len(self.edges(keys=True))
        return len(self.edges())

    def copy(self):
        result = self._copy_type()()
        result.graph.update(dict(self.graph))
        result.add_nodes_from((node, dict(attrs)) for node, attrs in self.nodes(data=True))
        if self.is_multigraph():
            for u, v, key, attrs in self.edges(keys=True, data=True):
                result.add_edge(u, v, key=key, **dict(attrs))
        else:
            for u, v, attrs in self.edges(data=True):
                result.add_edge(u, v, **dict(attrs))
        return result

    def _copy_type(self):
        if self.is_directed():
            return MultiDiGraph if self.is_multigraph() else DiGraph
        return MultiGraph if self.is_multigraph() else Graph


class _DirectedGraphConversionView(_ConversionGraphViewBase):
    _directed = True

    def _adj_neighbors(self, node):
        return iter(self._graph[node])

    def _adj_neighbor_value(self, node, neighbor):
        return self._graph[node][neighbor]

    def _pred_neighbors(self, node):
        if self._graph.is_directed():
            return iter(self._graph.pred[node])
        return iter(self._graph[node])

    def _pred_neighbor_value(self, node, neighbor):
        if self._graph.is_directed():
            return self._graph.pred[node][neighbor]
        return self._graph[node][neighbor]

    def has_edge(self, u, v, key=None):
        return self._graph.has_edge(u, v)


class _DirectedMultiGraphConversionView(_ConversionGraphViewBase):
    _directed = True
    _multigraph = True

    def _adj_neighbors(self, node):
        return iter(self._graph[node])

    def _adj_neighbor_value(self, node, neighbor):
        return self._graph[node][neighbor]

    def _pred_neighbors(self, node):
        if self._graph.is_directed():
            return iter(self._graph.pred[node])
        return iter(self._graph[node])

    def _pred_neighbor_value(self, node, neighbor):
        if self._graph.is_directed():
            return self._graph.pred[node][neighbor]
        return self._graph[node][neighbor]

    def has_edge(self, u, v, key=None):
        return self._graph.has_edge(u, v, key)


class _UndirectedGraphConversionView(_ConversionGraphViewBase):
    def _adj_neighbors(self, node):
        if not self._graph.is_directed():
            return iter(self._graph[node])

        def merged():
            yielded = set()
            for neighbor in self._graph.succ[node]:
                yielded.add(neighbor)
                yield neighbor
            for neighbor in self._graph.pred[node]:
                if neighbor not in yielded:
                    yield neighbor

        return merged()

    def _adj_neighbor_value(self, node, neighbor):
        if not self._graph.is_directed():
            return self._graph[node][neighbor]
        if self._graph.has_edge(node, neighbor):
            return self._graph.succ[node][neighbor]
        return self._graph.pred[node][neighbor]

    def has_edge(self, u, v, key=None):
        if not self._graph.is_directed():
            return self._graph.has_edge(u, v)
        return self._graph.has_edge(u, v) or self._graph.has_edge(v, u)


class _UndirectedMultiGraphConversionView(_ConversionGraphViewBase):
    _multigraph = True

    def _adj_neighbors(self, node):
        if not self._graph.is_directed():
            return iter(self._graph[node])

        def merged():
            yielded = set()
            for neighbor in self._graph.succ[node]:
                yielded.add(neighbor)
                yield neighbor
            for neighbor in self._graph.pred[node]:
                if neighbor not in yielded:
                    yield neighbor

        return merged()

    def _adj_neighbor_value(self, node, neighbor):
        if not self._graph.is_directed():
            return self._graph[node][neighbor]

        outgoing = self._graph.succ[node].get(neighbor)
        incoming = self._graph.pred[node].get(neighbor)
        if outgoing is not None and incoming is not None:
            return _UnionKeyAtlas(outgoing, incoming)
        if outgoing is not None:
            return outgoing
        if incoming is not None:
            return incoming
        raise KeyError(f"Key {neighbor} not found")

    def has_edge(self, u, v, key=None):
        if not self._graph.is_directed():
            return self._graph.has_edge(u, v, key)
        return self._graph.has_edge(u, v, key) or self._graph.has_edge(v, u, key)


def reverse(G, copy=True):
    """Return graph with all edges reversed."""
    if not G.is_directed():
        raise NetworkXError("Cannot reverse an undirected graph.")
    if copy:
        return G.reverse()
    return _ReverseDirectedView(G)


def nodes(G):
    """Return nodes of G (global function form)."""
    return G.nodes


def _global_nbunch_nodes(G, nbunch):
    if nbunch is None:
        return None
    try:
        if nbunch in G:
            return [nbunch]
    except TypeError:
        pass
    try:
        nodes = []
        for node in nbunch:
            try:
                hash(node)
            except TypeError as exc:
                raise NetworkXError(
                    f"Node {node} in sequence nbunch is not a valid node."
                ) from exc
            if node in G:
                nodes.append(node)
        return nodes
    except TypeError as exc:
        message = exc.args[0] if exc.args else ""
        if "object is not iterable" in message:
            raise NetworkXError(f"Node {nbunch} is not in the graph.") from exc
        raise NetworkXError("nbunch is not a node or a sequence of nodes.") from exc


def _triangle_selection(G, nodes):
    if nodes is None:
        return None, False

    try:
        if nodes in G:
            return [nodes], True
    except TypeError:
        pass

    return _global_nbunch_nodes(G, nodes), False


def _triangles_and_degree_iter_local(G, nodes=None):
    node_iter = G if nodes is None else nodes
    nodes_neighbors = ((node, G[node]) for node in node_iter)

    for node, node_neighbors in nodes_neighbors:
        neighbor_set = set(node_neighbors) - {node}
        generalized_degree = Counter(
            len(neighbor_set & (set(G[neighbor]) - {neighbor})) for neighbor in neighbor_set
        )
        triangle_count = sum(size * count for size, count in generalized_degree.items())
        yield (node, len(neighbor_set), triangle_count, generalized_degree)


def _weighted_triangles_and_degree_iter_local(G, nodes=None, weight="weight"):
    if weight is None or G.number_of_edges() == 0:
        max_weight = 1
    else:
        max_weight = max(
            attrs.get(weight, 1) for _, _, attrs in G.edges(data=True)
        )

    node_iter = G if nodes is None else nodes
    nodes_neighbors = ((node, G[node]) for node in node_iter)

    def normalized_weight(u, v):
        return G[u][v].get(weight, 1) / max_weight

    for node, node_neighbors in nodes_neighbors:
        neighbor_set = set(node_neighbors) - {node}
        weighted_triangle_sum = 0.0
        seen_neighbors = set()
        for neighbor in neighbor_set:
            seen_neighbors.add(neighbor)
            neighbor_neighbors = set(G[neighbor]) - seen_neighbors
            edge_weight = normalized_weight(node, neighbor)
            for shared_neighbor in neighbor_set & neighbor_neighbors:
                weighted_triangle_sum += math.cbrt(
                    edge_weight
                    * normalized_weight(neighbor, shared_neighbor)
                    * normalized_weight(shared_neighbor, node)
                )
        yield (node, len(neighbor_set), 2.0 * weighted_triangle_sum)


def _directed_triangles_and_degree_iter_local(G, nodes=None):
    node_iter = G if nodes is None else nodes
    nodes_neighbors = ((node, G.pred[node], G.succ[node]) for node in node_iter)

    for node, predecessors, successors in nodes_neighbors:
        predecessor_set = set(predecessors) - {node}
        successor_set = set(successors) - {node}

        directed_triangle_count = 0
        for neighbor in itertools.chain(predecessor_set, successor_set):
            neighbor_predecessors = set(G.pred[neighbor]) - {neighbor}
            neighbor_successors = set(G.succ[neighbor]) - {neighbor}
            directed_triangle_count += sum(
                1
                for third_node in itertools.chain(
                    predecessor_set & neighbor_predecessors,
                    predecessor_set & neighbor_successors,
                    successor_set & neighbor_predecessors,
                    successor_set & neighbor_successors,
                )
            )

        total_degree = len(predecessor_set) + len(successor_set)
        reciprocal_degree = len(predecessor_set & successor_set)
        yield (node, total_degree, reciprocal_degree, directed_triangle_count)


def _directed_weighted_triangles_and_degree_iter_local(G, nodes=None, weight="weight"):
    if weight is None or G.number_of_edges() == 0:
        max_weight = 1
    else:
        max_weight = max(
            attrs.get(weight, 1) for _, _, attrs in G.edges(data=True)
        )

    node_iter = G if nodes is None else nodes
    nodes_neighbors = ((node, G.pred[node], G.succ[node]) for node in node_iter)

    def normalized_weight(u, v):
        return G[u][v].get(weight, 1) / max_weight

    for node, predecessors, successors in nodes_neighbors:
        predecessor_set = set(predecessors) - {node}
        successor_set = set(successors) - {node}

        directed_triangle_sum = 0.0
        for neighbor in predecessor_set:
            neighbor_predecessors = set(G.pred[neighbor]) - {neighbor}
            neighbor_successors = set(G.succ[neighbor]) - {neighbor}
            for third_node in predecessor_set & neighbor_predecessors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(neighbor, node)
                    * normalized_weight(third_node, node)
                    * normalized_weight(third_node, neighbor)
                )
            for third_node in predecessor_set & neighbor_successors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(neighbor, node)
                    * normalized_weight(third_node, node)
                    * normalized_weight(neighbor, third_node)
                )
            for third_node in successor_set & neighbor_predecessors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(neighbor, node)
                    * normalized_weight(node, third_node)
                    * normalized_weight(third_node, neighbor)
                )
            for third_node in successor_set & neighbor_successors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(neighbor, node)
                    * normalized_weight(node, third_node)
                    * normalized_weight(neighbor, third_node)
                )

        for neighbor in successor_set:
            neighbor_predecessors = set(G.pred[neighbor]) - {neighbor}
            neighbor_successors = set(G.succ[neighbor]) - {neighbor}
            for third_node in predecessor_set & neighbor_predecessors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(node, neighbor)
                    * normalized_weight(third_node, node)
                    * normalized_weight(third_node, neighbor)
                )
            for third_node in predecessor_set & neighbor_successors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(node, neighbor)
                    * normalized_weight(third_node, node)
                    * normalized_weight(neighbor, third_node)
                )
            for third_node in successor_set & neighbor_predecessors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(node, neighbor)
                    * normalized_weight(node, third_node)
                    * normalized_weight(third_node, neighbor)
                )
            for third_node in successor_set & neighbor_successors:
                directed_triangle_sum += math.cbrt(
                    normalized_weight(node, neighbor)
                    * normalized_weight(node, third_node)
                    * normalized_weight(neighbor, third_node)
                )

        total_degree = len(predecessor_set) + len(successor_set)
        reciprocal_degree = len(predecessor_set & successor_set)
        yield (node, total_degree, reciprocal_degree, directed_triangle_sum)


def clustering(G, nodes=None, weight=None):
    """Compute the clustering coefficient for nodes."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    selected_nodes, single_node = _triangle_selection(G, nodes)

    if G.is_directed():
        if weight is not None:
            triangle_data = _directed_weighted_triangles_and_degree_iter_local(
                G, selected_nodes, weight
            )
        else:
            triangle_data = _directed_triangles_and_degree_iter_local(G, selected_nodes)
        clustering_coefficients = {
            node: 0 if triangle_count == 0 else triangle_count / ((total_degree * (total_degree - 1) - 2 * reciprocal_degree) * 2)
            for node, total_degree, reciprocal_degree, triangle_count in triangle_data
        }
    else:
        if weight is not None:
            triangle_data = _weighted_triangles_and_degree_iter_local(
                G, selected_nodes, weight
            )
            clustering_coefficients = {
                node: 0 if triangle_count == 0 else triangle_count / (degree * (degree - 1))
                for node, degree, triangle_count in triangle_data
            }
        else:
            triangle_data = _triangles_and_degree_iter_local(G, selected_nodes)
            clustering_coefficients = {
                node: 0 if triangle_count == 0 else triangle_count / (degree * (degree - 1))
                for node, degree, triangle_count, _ in triangle_data
            }

    if single_node:
        return clustering_coefficients[nodes]
    return clustering_coefficients


def average_clustering(G, nodes=None, weight=None, count_zeros=True):
    """Compute the average clustering coefficient for the graph."""
    clustering_values = clustering(G, nodes, weight=weight).values()
    if not count_zeros:
        clustering_values = [value for value in clustering_values if abs(value) > 0]
    return sum(clustering_values) / len(clustering_values)


def transitivity(G):
    """Compute graph transitivity."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    triangles_contributions = [
        (triangle_count, degree * (degree - 1))
        for _, degree, triangle_count, _ in _triangles_and_degree_iter_local(G)
    ]
    if len(triangles_contributions) == 0:
        return 0
    triangles, contributions = map(sum, zip(*triangles_contributions))
    return 0 if triangles == 0 else triangles / contributions


def square_clustering(G, nodes=None):
    """Compute the squares clustering coefficient for nodes."""
    single_node = False
    if nodes is None:
        node_iter = G
    elif nodes in G:
        node_iter = [nodes]
        single_node = True
    else:
        node_iter = _global_nbunch_nodes(G, nodes)

    square_coefficients = {}
    graph_adj = G.adj

    class CachedNeighborSets(dict):
        def __missing__(self, node):
            neighbors = self[node] = set(graph_adj[node])
            neighbors.discard(node)
            return neighbors

    neighbor_sets = CachedNeighborSets()

    for node in node_iter:
        node_neighbors = neighbor_sets[node]
        neighbor_count_minus_one = len(node_neighbors) - 1
        if neighbor_count_minus_one <= 0:
            square_coefficients[node] = 0
            continue

        neighbor_pair_degrees = 0
        neighbor_pair_count = len(node_neighbors) * neighbor_count_minus_one
        triangle_count = 0
        square_count = 0

        for neighbor in node_neighbors:
            neighbor_neighbors = neighbor_sets[neighbor]
            neighbor_pair_degrees += len(neighbor_neighbors) * neighbor_count_minus_one
            shared_neighbors = len(neighbor_neighbors & node_neighbors)
            triangle_count += shared_neighbors
            square_count += shared_neighbors * (shared_neighbors - 1)

        two_hop_neighbors = set.union(
            *(neighbor_sets[neighbor] for neighbor in node_neighbors)
        )
        two_hop_neighbors -= node_neighbors
        two_hop_neighbors.discard(node)

        for opposite_corner in two_hop_neighbors:
            shared_neighbors = len(node_neighbors & neighbor_sets[opposite_corner])
            square_count += shared_neighbors * (shared_neighbors - 1)

        square_count //= 2
        potential = (
            neighbor_pair_degrees - neighbor_pair_count - triangle_count - square_count
        )
        square_coefficients[node] = square_count / potential if potential > 0 else 0

    if single_node:
        return square_coefficients[nodes]
    return square_coefficients


def triangles(G, nodes=None):
    """Compute the number of triangles."""
    if nodes is None:
        return _raw_triangles(G)

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    if nodes in G:
        return _raw_triangles(G)[nodes]

    triangle_counts = _raw_triangles(G)
    nbunch_nodes = _global_nbunch_nodes(G, nodes)
    return {node: triangle_counts[node] for node in nbunch_nodes}


def edges(G, nbunch=None):
    """Return edges of G (global function form)."""
    if nbunch is None:
        return G.edges

    nbunch_nodes = _global_nbunch_nodes(G, nbunch)
    if G.is_directed():
        result = []
        if G.is_multigraph():
            for u in nbunch_nodes:
                if u not in G:
                    continue
                for v, keydict in G[u].items():
                    for _key in keydict:
                        result.append((u, v))
            return result

        for u in nbunch_nodes:
            if u not in G:
                continue
            for v in G[u]:
                result.append((u, v))
        return result

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
        try:
            if nbunch in G:
                return G.degree[nbunch]
        except TypeError:
            pass

        nbunch_nodes = _global_nbunch_nodes(G, nbunch)
        return ((node, G.degree[node]) for node in nbunch_nodes)

    def edge_weight(attrs):
        return attrs.get(weight, 1)

    def weighted_degree(node):
        if G.is_multigraph():
            if G.is_directed():
                total = 0
                for keydict in G.succ[node].values():
                    for attrs in keydict.values():
                        total += edge_weight(attrs)
                for keydict in G.pred[node].values():
                    for attrs in keydict.values():
                        total += edge_weight(attrs)
                return total

            total = 0
            for neighbor, keydict in G.adj[node].items():
                edge_total = 0
                for attrs in keydict.values():
                    edge_total += edge_weight(attrs)
                total += edge_total * 2 if neighbor == node else edge_total
            return total

        if G.is_directed():
            total = 0
            for attrs in G.succ[node].values():
                total += edge_weight(attrs)
            for attrs in G.pred[node].values():
                total += edge_weight(attrs)
            return total

        total = 0
        for neighbor, attrs in G.adj[node].items():
            edge_total = edge_weight(attrs)
            total += edge_total * 2 if neighbor == node else edge_total
        return total

    if nbunch is None:
        return ((node, weighted_degree(node)) for node in G.nodes)

    try:
        if nbunch in G:
            return weighted_degree(nbunch)
    except TypeError:
        pass

    nbunch_nodes = _global_nbunch_nodes(G, nbunch)
    return ((node, weighted_degree(node)) for node in nbunch_nodes)


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
    try:
        df = df[df.index]
    except Exception as err:
        missing = list(set(df.index).difference(set(df.columns)))
        msg = f"{missing} not in columns"
        raise NetworkXError("Columns must match Indices.", msg) from err

    return from_numpy_array(df.values, create_using=create_using, nodelist=df.columns)


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


def is_valid_directed_joint_degree(in_degrees, out_degrees, nkk):
    """Check if directed joint degree inputs are realizable."""
    if len(in_degrees) != len(out_degrees):
        return False

    partition_count = {}
    forbidden = {}
    for idx, in_degree in enumerate(in_degrees):
        out_degree = out_degrees[idx]
        partition_count[(in_degree, 0)] = partition_count.get((in_degree, 0), 0) + 1
        partition_count[(out_degree, 1)] = partition_count.get((out_degree, 1), 0) + 1
        forbidden[(out_degree, in_degree)] = forbidden.get((out_degree, in_degree), 0) + 1

    edge_sums = {}
    for out_degree in nkk:
        for in_degree in nkk[out_degree]:
            edge_count = nkk[out_degree][in_degree]
            if not float(edge_count).is_integer():
                return False
            if edge_count > 0:
                edge_sums[(out_degree, 1)] = (
                    edge_sums.get((out_degree, 1), 0) + edge_count
                )
                edge_sums[(in_degree, 0)] = (
                    edge_sums.get((in_degree, 0), 0) + edge_count
                )
                if (
                    edge_count + forbidden.get((out_degree, in_degree), 0)
                    > partition_count[(out_degree, 1)]
                    * partition_count[(in_degree, 0)]
                ):
                    return False

    return all(edge_sums[key] / key[0] == partition_count[key] for key in edge_sums)


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


def _k_edge_degree(G, node):
    return G.degree[node]


def _k_edge_complement_edges(G):
    nodes = list(G.nodes())
    for u, v in combinations(nodes, 2):
        if not G.has_edge(u, v):
            yield (u, v)


def _k_edge_avail_weight(raw_weight, weight):
    if raw_weight is None:
        return 1
    if isinstance(raw_weight, Mapping):
        key = "weight" if weight is None else weight
        return raw_weight[key]
    return raw_weight


def _k_edge_unpack_available_edges(avail, weight=None, G=None):
    if isinstance(avail, Mapping):
        available = list(avail.items())
        edges = [edge for edge, _ in available]
        weights = [raw_weight for _, raw_weight in available]
    else:
        edges = []
        weights = []
        for edge in avail:
            u, v = edge[:2]
            edges.append((u, v))
            weights.append(1 if len(edge) == 2 else _k_edge_avail_weight(edge[-1], weight))

    if G is None:
        return edges, weights

    filtered_edges = []
    filtered_weights = []
    for (u, v), edge_weight in zip(edges, weights):
        if not G.has_edge(u, v):
            filtered_edges.append((u, v))
            filtered_weights.append(edge_weight)
    return filtered_edges, filtered_weights


def _k_edge_is_locally_connected(G, source, target, k):
    if source == target:
        return True
    try:
        return edge_connectivity(G, source, target) >= k
    except (NetworkXError, NetworkXUnbounded, ValueError):
        return False


def _k_edge_greedy_augmentation(G, k, avail=None, weight=None, seed=0):
    if is_k_edge_connected(G, k):
        return []

    if avail is None:
        avail_edges = list(_k_edge_complement_edges(G))
        avail_weights = [1] * len(avail_edges)
    else:
        avail_edges, avail_weights = _k_edge_unpack_available_edges(
            avail,
            weight=weight,
            G=G,
        )

    weighted_edges = sorted(
        (
            edge_weight,
            _k_edge_degree(G, u) + _k_edge_degree(G, v),
            (u, v),
        )
        for (u, v), edge_weight in zip(avail_edges, avail_weights)
    )

    H = G.copy()
    aug_edges = []
    done = False
    for _, _, (u, v) in weighted_edges:
        if not _k_edge_is_locally_connected(H, u, v, k):
            aug_edges.append((u, v))
            H.add_edge(u, v)
            if _k_edge_degree(H, u) >= k and _k_edge_degree(H, v) >= k:
                done = is_k_edge_connected(H, k)
        if done:
            break

    if not done:
        raise NetworkXUnfeasible("not able to k-edge-connect with available edges")

    import random as _random

    if not (k == 2 and avail is not None):
        rng = _random.Random(seed)
        rng.shuffle(aug_edges)
        for u, v in list(aug_edges):
            if _k_edge_degree(H, u) <= k or _k_edge_degree(H, v) <= k:
                continue
            H.remove_edge(u, v)
            aug_edges.remove((u, v))
            if not is_k_edge_connected(H, k):
                H.add_edge(u, v)
                aug_edges.append((u, v))

    return aug_edges


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
    that connects components. For remaining cases, uses the same
    greedy augmentation policy as the upstream reference: add light
    candidate edges between node pairs that are not yet locally
    k-edge-connected, then prune redundant additions deterministically.
    """
    if k <= 0:
        return []

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.number_of_nodes() < k + 1:
        msg = f"impossible to {k} connect in graph with less than {k + 1} nodes"
        if partial:
            return list(_k_edge_complement_edges(G))
        raise NetworkXUnfeasible(msg)
    if avail is not None and len(avail) == 0:
        if not is_k_edge_connected(G, k):
            if partial:
                return []
            raise NetworkXUnfeasible("no available edges")
        return []

    # Fast native path for k=1 (connect components)
    if k == 1 and avail is None and weight is None:
        comps = list(connected_components(G))
        if len(comps) <= 1:
            return []
        return [
            (list(comps[i])[0], list(comps[i + 1])[0]) for i in range(len(comps) - 1)
        ]

    try:
        return _k_edge_greedy_augmentation(G, k, avail=avail, weight=weight, seed=0)
    except NetworkXUnfeasible:
        if not partial:
            raise
        if avail is None:
            return list(_k_edge_complement_edges(G))
        avail_edges, _ = _k_edge_unpack_available_edges(avail, weight=weight, G=G)
        return avail_edges


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


def _embedding_connected_components(embedding):
    nodes = list(embedding.nodes())
    unseen = set(nodes)
    components = []
    while unseen:
        start = next(iter(unseen))
        unseen.remove(start)
        component = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in embedding.neighbors_cw_order(node):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _embedding_set_position(parent, tree, remaining_nodes, delta_x, y_coordinate, pos):
    child = tree[parent]
    if child is not None:
        pos[child] = (pos[parent][0] + delta_x[child], y_coordinate[child])
        remaining_nodes.append(child)


def _embedding_make_bi_connected(embedding, starting_node, outgoing_node, edges_counted):
    if (starting_node, outgoing_node) in edges_counted:
        return []
    edges_counted.add((starting_node, outgoing_node))

    v1 = starting_node
    v2 = outgoing_node
    face_list = [starting_node]
    face_set = set(face_list)
    _, v3 = embedding.next_face_half_edge(v1, v2)

    while v2 != starting_node or v3 != outgoing_node:
        if v1 == v2:
            raise NetworkXError("Invalid half-edge")
        if v2 in face_set:
            embedding.add_half_edge(v1, v3, ccw=v2)
            embedding.add_half_edge(v3, v1, cw=v2)
            edges_counted.add((v2, v3))
            edges_counted.add((v3, v1))
            v2 = v1
        else:
            face_set.add(v2)
            face_list.append(v2)

        v1 = v2
        v2, v3 = embedding.next_face_half_edge(v2, v3)
        edges_counted.add((v1, v2))

    return face_list


def _embedding_triangulate_face(embedding, v1, v2):
    _, v3 = embedding.next_face_half_edge(v1, v2)
    _, v4 = embedding.next_face_half_edge(v2, v3)
    if v1 in (v2, v3):
        return
    while v1 != v4:
        if embedding.has_edge(v1, v3):
            v1, v2, v3 = v2, v3, v4
        else:
            embedding.add_half_edge(v1, v3, ccw=v2)
            embedding.add_half_edge(v3, v1, cw=v2)
            v1, v2, v3 = v1, v3, v4
        _, v4 = embedding.next_face_half_edge(v2, v3)


def _embedding_triangulate(embedding, fully_triangulate=True):
    nodes = list(embedding.nodes())
    if len(nodes) <= 1:
        return embedding, nodes

    embedding = embedding.copy()
    component_nodes = [next(iter(component)) for component in _embedding_connected_components(embedding)]
    for index in range(len(component_nodes) - 1):
        embedding.connect_components(component_nodes[index], component_nodes[index + 1])

    outer_face = []
    face_list = []
    edges_visited = set()
    for v in embedding.nodes():
        for w in embedding.neighbors_cw_order(v):
            new_face = _embedding_make_bi_connected(embedding, v, w, edges_visited)
            if new_face:
                face_list.append(new_face)
                if len(new_face) > len(outer_face):
                    outer_face = new_face

    for face in face_list:
        if face is not outer_face or fully_triangulate:
            _embedding_triangulate_face(embedding, face[0], face[1])

    if fully_triangulate:
        v1 = outer_face[0]
        v2 = outer_face[1]
        v3 = embedding[v2][v1]["ccw"]
        outer_face = [v1, v2, v3]

    return embedding, outer_face


def _embedding_canonical_ordering(embedding, outer_face):
    v1 = outer_face[0]
    v2 = outer_face[1]
    chords = defaultdict(int)
    marked_nodes = set()
    ready_to_pick = set(outer_face)

    outer_face_ccw_nbr = {}
    prev_nbr = v2
    for index in range(2, len(outer_face)):
        outer_face_ccw_nbr[prev_nbr] = outer_face[index]
        prev_nbr = outer_face[index]
    outer_face_ccw_nbr[prev_nbr] = v1

    outer_face_cw_nbr = {}
    prev_nbr = v1
    for index in range(len(outer_face) - 1, 0, -1):
        outer_face_cw_nbr[prev_nbr] = outer_face[index]
        prev_nbr = outer_face[index]

    def is_outer_face_nbr(x, y):
        if x not in outer_face_ccw_nbr:
            return outer_face_cw_nbr[x] == y
        if x not in outer_face_cw_nbr:
            return outer_face_ccw_nbr[x] == y
        return outer_face_ccw_nbr[x] == y or outer_face_cw_nbr[x] == y

    def is_on_outer_face(x):
        return x not in marked_nodes and (x in outer_face_ccw_nbr or x == v1)

    for v in outer_face:
        for neighbor in embedding.neighbors_cw_order(v):
            if is_on_outer_face(neighbor) and not is_outer_face_nbr(v, neighbor):
                chords[v] += 1
                ready_to_pick.discard(v)

    canonical_ordering = [None] * len(list(embedding.nodes()))
    canonical_ordering[0] = (v1, [])
    canonical_ordering[1] = (v2, [])
    ready_to_pick.discard(v1)
    ready_to_pick.discard(v2)

    for k in range(len(list(embedding.nodes())) - 1, 1, -1):
        v = ready_to_pick.pop()
        marked_nodes.add(v)

        wp = None
        wq = None
        neighbor_iterator = iter(embedding.neighbors_cw_order(v))
        while True:
            neighbor = next(neighbor_iterator)
            if neighbor in marked_nodes:
                continue
            if is_on_outer_face(neighbor):
                if neighbor == v1:
                    wp = v1
                elif neighbor == v2:
                    wq = v2
                elif outer_face_cw_nbr[neighbor] == v:
                    wp = neighbor
                else:
                    wq = neighbor
            if wp is not None and wq is not None:
                break

        wp_wq = [wp]
        neighbor = wp
        while neighbor != wq:
            next_neighbor = embedding[v][neighbor]["ccw"]
            wp_wq.append(next_neighbor)
            outer_face_cw_nbr[neighbor] = next_neighbor
            outer_face_ccw_nbr[next_neighbor] = neighbor
            neighbor = next_neighbor

        if len(wp_wq) == 2:
            chords[wp] -= 1
            if chords[wp] == 0:
                ready_to_pick.add(wp)
            chords[wq] -= 1
            if chords[wq] == 0:
                ready_to_pick.add(wq)
        else:
            new_face_nodes = set(wp_wq[1:-1])
            for w in new_face_nodes:
                ready_to_pick.add(w)
                for neighbor in embedding.neighbors_cw_order(w):
                    if is_on_outer_face(neighbor) and not is_outer_face_nbr(w, neighbor):
                        chords[w] += 1
                        ready_to_pick.discard(w)
                        if neighbor not in new_face_nodes:
                            chords[neighbor] += 1
                            ready_to_pick.discard(neighbor)
        canonical_ordering[k] = (v, wp_wq)

    return canonical_ordering


def combinatorial_embedding_to_pos(embedding, fully_triangulate=False):
    """Convert combinatorial embedding to positions."""
    nodes = list(embedding.nodes())
    if len(nodes) < 4:
        default_positions = [(0, 0), (2, 0), (1, 1)]
        return {node: default_positions[index] for index, node in enumerate(nodes)}

    embedding, outer_face = _embedding_triangulate(embedding, fully_triangulate)

    left_t_child = {}
    right_t_child = {}
    delta_x = {}
    y_coordinate = {}

    node_list = _embedding_canonical_ordering(embedding, outer_face)

    v1, v2, v3 = node_list[0][0], node_list[1][0], node_list[2][0]

    delta_x[v1] = 0
    y_coordinate[v1] = 0
    right_t_child[v1] = v3
    left_t_child[v1] = None

    delta_x[v2] = 1
    y_coordinate[v2] = 0
    right_t_child[v2] = None
    left_t_child[v2] = None

    delta_x[v3] = 1
    y_coordinate[v3] = 1
    right_t_child[v3] = v2
    left_t_child[v3] = None

    for k in range(3, len(node_list)):
        vk, contour_neighbors = node_list[k]
        wp = contour_neighbors[0]
        wp1 = contour_neighbors[1]
        wq = contour_neighbors[-1]
        wq1 = contour_neighbors[-2]
        adds_multiple_triangles = len(contour_neighbors) > 2

        delta_x[wp1] += 1
        delta_x[wq] += 1

        delta_x_wp_wq = sum(delta_x[node] for node in contour_neighbors[1:])
        delta_x[vk] = (-y_coordinate[wp] + delta_x_wp_wq + y_coordinate[wq]) // 2
        y_coordinate[vk] = (y_coordinate[wp] + delta_x_wp_wq + y_coordinate[wq]) // 2
        delta_x[wq] = delta_x_wp_wq - delta_x[vk]
        if adds_multiple_triangles:
            delta_x[wp1] -= delta_x[vk]

        right_t_child[wp] = vk
        right_t_child[vk] = wq
        if adds_multiple_triangles:
            left_t_child[vk] = wp1
            right_t_child[wq1] = None
        else:
            left_t_child[vk] = None

    pos = {v1: (0, y_coordinate[v1])}
    remaining_nodes = [v1]
    while remaining_nodes:
        parent_node = remaining_nodes.pop()
        _embedding_set_position(
            parent_node,
            left_t_child,
            remaining_nodes,
            delta_x,
            y_coordinate,
            pos,
        )
        _embedding_set_position(
            parent_node,
            right_t_child,
            remaining_nodes,
            delta_x,
            y_coordinate,
            pos,
        )
    return pos


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
def _edge_attrs_between(G, u, v):
    """Return edge attribute payloads between two nodes."""
    if G.is_multigraph():
        return [dict(attrs) for attrs in G[u][v].values()]
    return [dict(G[u][v])]


def _edge_attrs_match(left_attrs, right_attrs, edge_match):
    """Return whether edge attribute payloads can be matched pairwise."""
    if edge_match is None:
        return True
    if len(left_attrs) != len(right_attrs):
        return False

    used = [False] * len(right_attrs)
    for left in left_attrs:
        for index, right in enumerate(right_attrs):
            if not used[index] and edge_match(left, right):
                used[index] = True
                break
        else:
            return False
    return True


def _isomorphic_mapping_matches_callbacks(G1, G2, mapping, node_match, edge_match):
    """Filter a structural isomorphism mapping through NetworkX-style callbacks."""
    if node_match is not None:
        for node, mapped in mapping.items():
            if not node_match(G1.nodes[node], G2.nodes[mapped]):
                return False

    if edge_match is not None:
        edge_iter = (
            ((u, v) for u, v, _key in G1.edges(keys=True))
            if G1.is_multigraph()
            else G1.edges()
        )
        seen = set()
        for u, v in edge_iter:
            mapped_u = mapping[u]
            mapped_v = mapping[v]
            edge_key = (
                frozenset((u, v))
                if not G1.is_directed()
                else (u, v)
            )
            if not G1.is_multigraph() and edge_key in seen:
                continue
            seen.add(edge_key)
            left_attrs = _edge_attrs_between(G1, u, v)
            right_attrs = _edge_attrs_between(G2, mapped_u, mapped_v)
            if not _edge_attrs_match(left_attrs, right_attrs, edge_match):
                return False
    return True


def is_isomorphic(G1, G2, node_match=None, edge_match=None):
    """Test graph isomorphism, preserving NetworkX callback semantics."""
    if node_match is None and edge_match is None:
        return _is_isomorphic_rust(G1, G2)

    if G1.is_directed() != G2.is_directed():
        raise NetworkXError("G1 and G2 must have the same directedness")
    if G1.is_multigraph() != G2.is_multigraph():
        return False

    return any(
        _isomorphic_mapping_matches_callbacks(
            G1,
            G2,
            mapping,
            node_match,
            edge_match,
        )
        for mapping in _vf2pp_all_isomorphisms_rust(G1, G2)
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
    if G.number_of_nodes() != G.number_of_edges() + 1:
        raise TypeError("G is not a tree.")
    if not G.is_directed():
        raise TypeError("G is not directed.")
    if not _tree_data_is_weakly_connected(G):
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


def _tree_data_is_weakly_connected(G):
    nodes = list(G.nodes)
    if not nodes:
        return False

    seen = {nodes[0]}
    stack = [nodes[0]]
    while stack:
        node = stack.pop()
        neighbors = itertools.chain(G[node], G.predecessors(node))
        for neighbor in neighbors:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(nodes)


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


def _numpy_random_state(seed):
    import numpy as np

    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, np.random.RandomState | np.random.Generator):
        return seed
    if isinstance(seed, int):
        return np.random.RandomState(seed)
    raise ValueError(
        f"{seed} cannot be used to create a numpy.random.RandomState or Generator",
    )


def _panther_isolates(G):
    return {node for node in G if G.degree[node] == 0}


def _panther_induced_ordered_copy(G, nodes):
    node_set = set(nodes)
    graph = G.__class__()
    graph.graph.update(dict(G.graph))
    graph.add_nodes_from((node, dict(G.nodes[node])) for node in G if node in node_set)
    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            if u in node_set and v in node_set:
                graph.add_edge(u, v, key=key, **dict(attrs))
    else:
        for u, v, attrs in G.edges(data=True):
            if u in node_set and v in node_set:
                graph.add_edge(u, v, **dict(attrs))
    return graph


def _panther_generate_random_paths(
    G,
    sample_size,
    path_length=5,
    index_map=None,
    weight="weight",
    seed=None,
    *,
    source=None,
):
    import numpy as np

    rng = _numpy_random_state(seed)
    randint_fn = rng.integers if isinstance(rng, np.random.Generator) else rng.randint

    node_map = list(G)
    node_index = {node: index for index, node in enumerate(node_map)}
    num_nodes = G.number_of_nodes()
    adjacency = to_numpy_array(G, nodelist=node_map, weight=weight)

    row_sums = adjacency.sum(axis=1).reshape(-1, 1)
    transition_probabilities = adjacency * np.reciprocal(row_sums)

    for path_index in range(sample_size):
        if source is None:
            current_index = int(randint_fn(num_nodes))
            node = node_map[current_index]
        else:
            if source not in node_index:
                raise NodeNotFound(f"Initial node {source} not in G")
            node = source
            current_index = node_index[node]

        path = [node]
        if index_map is not None:
            index_map.setdefault(node, set()).add(path_index)

        for _ in range(path_length):
            neighbor_index = int(
                rng.choice(num_nodes, p=transition_probabilities[current_index]),
            )
            current_index = neighbor_index
            neighbor = node_map[neighbor_index]
            path.append(neighbor)
            if index_map is not None:
                index_map.setdefault(neighbor, set()).add(path_index)

        yield path


def _prepare_panther_paths(
    G,
    source,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    remove_isolates=True,
    k=None,
    seed=None,
):
    import numpy as np

    if source not in G:
        raise NodeNotFound(f"Source node {source} not in G")

    isolates = _panther_isolates(G)
    if source in isolates:
        raise NetworkXUnfeasible(
            f"Panther similarity is not defined for the isolated source node {source}.",
        )

    if remove_isolates:
        G = _panther_induced_ordered_copy(
            G,
            (node for node in G if node not in isolates),
        )

    if eps is None:
        eps = np.sqrt(1.0 / G.number_of_edges())

    num_nodes = G.number_of_nodes()
    if k is not None and not remove_isolates and num_nodes < k:
        raise NetworkXUnfeasible(
            f"The number of requested nodes {k} is greater than the number of nodes {num_nodes}.",
        )

    inv_node_map = {name: index for index, name in enumerate(G)}
    t_choose_2 = math.comb(path_length, 2)
    sample_size = int((c / eps**2) * (np.log2(t_choose_2) + 1 + np.log(1 / delta)))
    index_map = {}

    remaining_isolates = _panther_isolates(G)
    if remaining_isolates:
        raise NetworkXUnfeasible(
            f"Cannot generate random paths with isolated nodes present: {remaining_isolates}",
        )

    for _ in _panther_generate_random_paths(
        G,
        sample_size,
        path_length=path_length,
        index_map=index_map,
        weight=weight,
        seed=seed,
    ):
        pass

    return G, inv_node_map, index_map, 1 / sample_size, eps


def panther_similarity(
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
    import numpy as np

    G, inv_node_map, index_map, inv_sample_size, _eps = _prepare_panther_paths(
        G,
        source,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        k=k,
        seed=seed,
    )

    num_nodes = G.number_of_nodes()
    if num_nodes < k:
        raise NetworkXUnfeasible(
            f"The number of requested nodes {k} is greater than the number of nodes {num_nodes}.",
        )

    node_list = list(G.nodes)
    scores = np.zeros(num_nodes)
    source_paths = set(index_map[source])
    for node, paths in index_map.items():
        scores[inv_node_map[node]] = len(source_paths.intersection(paths)) * inv_sample_size

    partition_k = min(k + 1, num_nodes)
    top_k_unsorted = np.argpartition(scores, -partition_k)[-partition_k:]
    top_k_sorted = top_k_unsorted[np.argsort(scores[top_k_unsorted])][::-1]
    result = dict(zip((node_list[index] for index in top_k_sorted), scores[top_k_sorted].tolist()))
    result.pop(source, None)
    return result


_PY_GRAPH_EDIT_DISTANCE_MAX_NODES = 8


def _graph_edit_node_subst_cost(
    G1,
    G2,
    left,
    right,
    node_match,
    node_subst_cost,
):
    left_attrs = G1.nodes[left]
    right_attrs = G2.nodes[right]
    if node_subst_cost is not None:
        return node_subst_cost(left_attrs, right_attrs)
    if node_match is not None:
        return 0 if node_match(left_attrs, right_attrs) else 1
    return 0


def _graph_edit_node_del_cost(G, node, node_del_cost):
    return 1 if node_del_cost is None else node_del_cost(G.nodes[node])


def _graph_edit_node_ins_cost(G, node, node_ins_cost):
    return 1 if node_ins_cost is None else node_ins_cost(G.nodes[node])


def _graph_edit_edge_attrs(G, edge):
    u, v = edge
    return G.get_edge_data(u, v)


def _graph_edit_edge_subst_cost(
    G1,
    G2,
    left_edge,
    right_edge,
    edge_match,
    edge_subst_cost,
):
    left_attrs = _graph_edit_edge_attrs(G1, left_edge)
    right_attrs = _graph_edit_edge_attrs(G2, right_edge)
    if edge_subst_cost is not None:
        return edge_subst_cost(left_attrs, right_attrs)
    if edge_match is not None:
        return 0 if edge_match(left_attrs, right_attrs) else 1
    return 0


def _graph_edit_edge_del_cost(G, edge, edge_del_cost):
    return 1 if edge_del_cost is None else edge_del_cost(_graph_edit_edge_attrs(G, edge))


def _graph_edit_edge_ins_cost(G, edge, edge_ins_cost):
    return 1 if edge_ins_cost is None else edge_ins_cost(_graph_edit_edge_attrs(G, edge))


def _graph_edit_exact_paths_python(
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
):
    if G1.is_multigraph() or G2.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G1.is_directed() != G2.is_directed():
        raise NetworkXError("G1 and G2 must be both directed or both undirected")
    if G1.number_of_nodes() + G2.number_of_nodes() > _PY_GRAPH_EDIT_DISTANCE_MAX_NODES:
        raise NetworkXNotImplemented(
            "local optimal_edit_paths is bounded to small simple graphs",
        )

    left_nodes = list(G1.nodes())
    right_nodes = list(G2.nodes())
    left_edges = list(G1.edges())
    right_edges = list(G2.edges())
    best_cost = math.inf
    best_mappings = []

    def evaluate(mapping):
        matched_right_nodes = set(mapping.values())
        cost = 0
        for left, right in mapping.items():
            cost += _graph_edit_node_subst_cost(
                G1,
                G2,
                left,
                right,
                node_match,
                node_subst_cost,
            )
        for left in left_nodes:
            if left not in mapping:
                cost += _graph_edit_node_del_cost(G1, left, node_del_cost)
        for right in right_nodes:
            if right not in matched_right_nodes:
                cost += _graph_edit_node_ins_cost(G2, right, node_ins_cost)

        matched_right_edges = set()
        for left_edge in left_edges:
            left_u, left_v = left_edge
            right_u = mapping.get(left_u)
            right_v = mapping.get(left_v)
            if right_u is not None and right_v is not None and G2.has_edge(right_u, right_v):
                right_edge = (right_u, right_v)
                cost += _graph_edit_edge_subst_cost(
                    G1,
                    G2,
                    left_edge,
                    right_edge,
                    edge_match,
                    edge_subst_cost,
                )
                matched_right_edges.add(_graph_edit_distance_edge_key(G2, right_edge))
            else:
                cost += _graph_edit_edge_del_cost(G1, left_edge, edge_del_cost)

        for right_edge in right_edges:
            if _graph_edit_distance_edge_key(G2, right_edge) not in matched_right_edges:
                cost += _graph_edit_edge_ins_cost(G2, right_edge, edge_ins_cost)
        return cost

    def search(index, available_right, mapping):
        nonlocal best_cost, best_mappings
        if index == len(left_nodes):
            cost = evaluate(mapping)
            if upper_bound is not None and cost > upper_bound:
                return
            if cost < best_cost:
                best_cost = cost
                best_mappings = [dict(mapping)]
            elif cost == best_cost:
                best_mappings.append(dict(mapping))
            return

        left = left_nodes[index]
        search(index + 1, available_right, mapping)
        for right_index, right in enumerate(available_right):
            mapping[left] = right
            search(
                index + 1,
                available_right[:right_index] + available_right[right_index + 1 :],
                mapping,
            )
            del mapping[left]

    search(0, tuple(right_nodes), {})
    if not best_mappings:
        return [], None
    return [
        _graph_edit_distance_paths_from_mapping(G1, G2, mapping)
        for mapping in best_mappings
    ], best_cost


def optimal_edit_paths(
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

    return _graph_edit_exact_paths_python(
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


def optimize_edit_paths(G1, G2, **kwargs):
    """Iterator yielding final edit paths from the local optimal-path wrapper."""
    if kwargs.get("roots") is not None or kwargs.get("timeout") is not None:
        raise NetworkXNotImplemented(
            "roots and timeout are not supported by local optimize_edit_paths",
        )
    paths, cost = optimal_edit_paths(
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
    if cost is None:
        return
    if kwargs.get("strictly_decreasing", True):
        node_path, edge_path = paths[0]
        yield node_path, edge_path, cost
        return
    for node_path, edge_path in paths:
        yield node_path, edge_path, cost


# ---------------------------------------------------------------------------
# Final parity batch — remaining 60 functions
# ---------------------------------------------------------------------------


# Simple aliases and trivial implementations
def _subgraph_filter_from_nbunch(G, nbunch):
    if nbunch is None:
        return None
    if nbunch in G:
        allowed_nodes = {nbunch}
    else:
        try:
            allowed_nodes = set()
            for node in nbunch:
                try:
                    hash(node)
                except TypeError as exc:
                    raise NetworkXError(
                        f"Node {node} in sequence nbunch is not a valid node."
                    ) from exc
                if node in G:
                    allowed_nodes.add(node)
        except TypeError as exc:
            message = exc.args[0] if exc.args else ""
            if "object is not iterable" in message:
                raise NetworkXError(f"Node {nbunch} is not in the graph.") from exc
            raise NetworkXError("nbunch is not a node or a sequence of nodes.") from exc

    return lambda node: node in allowed_nodes


def subgraph(G, nbunch):
    """Return subgraph induced by nbunch."""
    return subgraph_view(
        G,
        filter_node=_subgraph_filter_from_nbunch(G, nbunch),
    )


def induced_subgraph(G, nbunch):
    """Return induced subgraph (alias for subgraph)."""
    return subgraph(
        G,
        nbunch,
    )


def edge_subgraph(G, edges):
    """Return subgraph induced by edges."""
    edges = set(edges)
    nodes = set()
    for edge in edges:
        nodes.update(edge[:2])

    def filter_node(node):
        return node in nodes

    if G.is_multigraph():
        if G.is_directed():
            visible_edges = {(u, v, k) for u, v, k in edges}

            def filter_edge(u, v, key):
                return (u, v, key) in visible_edges

        else:
            visible_edges = edges | {(v, u, k) for u, v, k in edges}

            def filter_edge(u, v, key):
                return (u, v, key) in visible_edges

    else:
        if G.is_directed():
            visible_edges = {(u, v) for u, v in edges}

            def filter_edge(u, v):
                return (u, v) in visible_edges

        else:
            visible_edges = edges | {(v, u) for u, v in edges}

            def filter_edge(u, v):
                return (u, v) in visible_edges

    return subgraph_view(
        G,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )


def subgraph_view(G, filter_node=None, filter_edge=None):
    """Filtered live view of graph."""
    return _FilteredGraphView(
        G,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )


def restricted_view(G, nodes_to_remove, edges_to_remove):
    """View with specified nodes and edges removed."""
    hidden_nodes = set(nodes_to_remove)

    def filter_node(node):
        return node not in hidden_nodes

    if G.is_multigraph():
        if G.is_directed():
            hidden_edges = set(edges_to_remove)

            def filter_edge(u, v, key):
                return (u, v, key) not in hidden_edges

        else:
            hidden_edges = {
                (frozenset((u, v)), key) for u, v, key in edges_to_remove
            }

            def filter_edge(u, v, key):
                return (frozenset((u, v)), key) not in hidden_edges

    else:
        if G.is_directed():
            hidden_edges = set(edges_to_remove)

            def filter_edge(u, v):
                return (u, v) not in hidden_edges

        else:
            hidden_edges = {frozenset((u, v)) for u, v in edges_to_remove}

            def filter_edge(u, v):
                return frozenset((u, v)) not in hidden_edges

    return subgraph_view(
        G,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )


def reverse_view(G):
    """View with reversed edges."""
    return reverse(G, copy=False)


def non_neighbors(graph, node):
    """Returns the non-neighbors of the node in the graph."""
    hash(node)
    if node not in graph:
        raise KeyError(node)
    return set(graph.adj) - set(graph.adj[node]) - {node}


def non_edges(graph):
    """Returns the nonexistent edges in the graph."""
    if graph.is_directed():
        for u in graph:
            for v in non_neighbors(graph, u):
                yield (u, v)
        return

    nodes = set(graph)
    while nodes:
        u = nodes.pop()
        for v in nodes - set(graph[u]):
            yield (u, v)


def common_neighbors(G, u, v):
    """Returns the common neighbors of two nodes in a graph."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if u not in G:
        raise NetworkXError("u is not in the graph.")
    if v not in G:
        raise NetworkXError("v is not in the graph.")
    return set(G.adj[u]) & set(G.adj[v]) - {u, v}


def neighbors(G, n):
    """Return neighbors of n (global function form)."""
    try:
        hash(n)
    except TypeError:
        raise
    if n not in G:
        graph_name = "digraph" if G.is_directed() else "graph"
        raise NetworkXError(f"The node {n} is not in the {graph_name}.")
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
    result = {}
    total = 0.0
    for x, y in xy:
        if x not in result:
            result[x] = {}
        if y not in result:
            result[y] = {}
        result[x][y] = result[x].get(y, 0) + 1
        total += 1

    if normalized:
        for row in result.values():
            for key in row:
                row[key] /= total
    return result


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
    import matplotlib as mpl

    if nodes:
        items = list(G.nodes())
        values = [G.nodes[node][src_attr] for node in items]
    else:
        if G.is_multigraph():
            items = list(G.edges(keys=True))
            values = [G[u][v][key][src_attr] for u, v, key in items]
        else:
            items = list(G.edges())
            values = [G[u][v][src_attr] for u, v in items]

    if vmin is None or vmax is None:
        if vmin is None:
            vmin = min(values)
        if vmax is None:
            vmax = max(values)

    mapper = mpl.cm.ScalarMappable(cmap=map)
    mapper.set_clim(vmin, vmax)

    def do_map(value):
        return tuple(float(component) for component in mapper.to_rgba(value))

    if nodes:
        for node in items:
            G.nodes[node][dest_attr] = do_map(G.nodes[node][src_attr])
    elif G.is_multigraph():
        for u, v, key in items:
            G[u][v][key][dest_attr] = do_map(G[u][v][key][src_attr])
    else:
        for u, v in items:
            G[u][v][dest_attr] = do_map(G[u][v][src_attr])


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


def panther_vector_similarity(
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
    import numpy as np
    import scipy as sp

    G, inv_node_map, index_map, inv_sample_size, eps = _prepare_panther_paths(
        G,
        source,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        remove_isolates=False,
        k=k,
        seed=seed,
    )
    num_nodes = G.number_of_nodes()
    if num_nodes < D:
        raise NetworkXUnfeasible(
            f"The number of requested similarity scores {D} is greater than the number of nodes {num_nodes}.",
        )

    node_list = list(G.nodes)
    similarities = np.zeros((num_nodes, num_nodes))
    theta = np.zeros((num_nodes, D))
    index_map_sets = {node: set(paths) for node, paths in index_map.items()}

    for vi_idx, vi in enumerate(G.nodes):
        vi_paths = index_map_sets[vi]
        for node, node_paths in index_map_sets.items():
            similarities[vi_idx, inv_node_map[node]] = (
                len(vi_paths.intersection(node_paths)) * inv_sample_size
            )
        theta[vi_idx] = np.sort(np.partition(similarities[vi_idx], -D)[-D:])[::-1]

    kdtree = sp.spatial.KDTree(theta)
    query_k = min(k + 1, num_nodes)
    neighbor_distances, nearest_neighbors = kdtree.query(
        theta[inv_node_map[source]],
        k=query_k,
    )

    neighbor_distances = np.atleast_1d(neighbor_distances)
    nearest_neighbors = np.atleast_1d(nearest_neighbors)
    neighbor_distances = np.maximum(neighbor_distances, eps)
    scores = 1 / neighbor_distances
    if len(scores) > 0 and (max_score := np.max(scores)) > 0:
        scores /= max_score

    result = dict(zip((node_list[index] for index in nearest_neighbors), scores.tolist()))
    result.pop(source, None)
    if len(result) > k:
        result = dict(sorted(result.items(), key=lambda item: item[1], reverse=True)[:k])
    return result


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


def graph_edit_distance(G1, G2, **kwargs):
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

    if kwargs.get("roots") is not None or kwargs.get("timeout") is not None:
        raise NetworkXNotImplemented(
            "roots and timeout are not supported by local graph_edit_distance",
        )
    _, cost = optimal_edit_paths(
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
    return cost


def optimize_graph_edit_distance(G1, G2, **kwargs):
    """Iterator yielding the final graph edit distance from the local wrapper."""
    cost = graph_edit_distance(G1, G2, **kwargs)
    if cost is not None:
        yield cost


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
    if isinstance(graphml_string, str):
        payload = graphml_string.encode("utf-8")
    else:
        payload = graphml_string

    graph = read_graphml(io.BytesIO(payload))

    if node_type is not str:
        mapping = {node: node_type(node) for node in list(graph.nodes())}
        graph = relabel_nodes(graph, mapping, copy=True)

    if force_multigraph and not graph.is_multigraph():
        graph_type = MultiDiGraph if graph.is_directed() else MultiGraph
        graph = _copy_graph_into(graph, graph_type())

    if graph.is_multigraph() and edge_key_type is not int:
        converted = MultiDiGraph() if graph.is_directed() else MultiGraph()
        converted.graph.update(dict(graph.graph))
        for node, attrs in graph.nodes(data=True):
            converted.add_node(node, **dict(attrs))
        for u, v, key, attrs in graph.edges(keys=True, data=True):
            converted.add_edge(u, v, key=edge_key_type(key), **dict(attrs))
        graph = converted

    return graph


_GRAPHML_XML_TYPES = {
    int: "long",
    str: "string",
    float: "double",
    bool: "boolean",
}


def _graphml_xml_type(value):
    value_type = type(value)
    if value_type in _GRAPHML_XML_TYPES:
        return _GRAPHML_XML_TYPES[value_type]
    raise TypeError(f"GraphML does not support type {value_type} as data values.")


def _graphml_make_data_element(element_factory, key_id, value):
    data_element = element_factory("data", {"key": key_id})
    data_element.text = str(value)
    return data_element


def _graphml_indent(element, level=0):
    indent = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        if not element.tail or not element.tail.strip():
            element.tail = indent
        for child in element:
            _graphml_indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    elif level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def _graphml_string(
    G,
    encoding,
    prettyprint,
    named_key_ids,
    edge_id_from_attribute,
):
    from xml.etree.ElementTree import Element, tostring

    root = Element(
        "graphml",
        {
            "xmlns": "http://graphml.graphdrawing.org/xmlns",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://graphml.graphdrawing.org/xmlns "
                "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
            ),
        },
    )
    keys = {}
    attributes = defaultdict(list)

    def get_key(name, attr_type, scope, default):
        keys_key = (name, attr_type, scope)
        if keys_key in keys:
            return keys[keys_key]
        key_id = name if named_key_ids else f"d{len(keys)}"
        keys[keys_key] = key_id
        key_element = Element(
            "key",
            {
                "id": key_id,
                "for": scope,
                "attr.name": name,
                "attr.type": attr_type,
            },
        )
        if default is not None:
            default_element = Element("default")
            default_element.text = str(default)
            key_element.append(default_element)
        root.insert(0, key_element)
        return key_id

    def add_attributes(scope, xml_obj, data, default):
        for name, value in data.items():
            attributes[xml_obj].append((str(name), value, scope, default.get(name)))

    graph_element_attrs = {
        "edgedefault": "directed" if G.is_directed() else "undirected",
    }
    graph_id = G.graph.get("id")
    if graph_id is not None:
        graph_element_attrs["id"] = graph_id
    graph_element = Element("graph", graph_element_attrs)

    graph_data = {
        key: value
        for key, value in G.graph.items()
        if key not in {"id", "node_default", "edge_default"}
    }
    add_attributes("graph", graph_element, graph_data, {})

    node_default = G.graph.get("node_default", {})
    for node, data in G.nodes(data=True):
        node_element = Element("node", {"id": str(node)})
        add_attributes("node", node_element, data, node_default)
        graph_element.append(node_element)

    edge_default = G.graph.get("edge_default", {})
    if G.is_multigraph():
        edge_iter = G.edges(data=True, keys=True)
        for u, v, key, data in edge_iter:
            edge_id = (
                str(data[edge_id_from_attribute])
                if edge_id_from_attribute and edge_id_from_attribute in data
                else str(key)
            )
            edge_element = Element(
                "edge",
                {"source": str(u), "target": str(v), "id": edge_id},
            )
            add_attributes("edge", edge_element, data, edge_default)
            graph_element.append(edge_element)
    else:
        for u, v, data in G.edges(data=True):
            edge_attrs = {"source": str(u), "target": str(v)}
            if edge_id_from_attribute and edge_id_from_attribute in data:
                edge_attrs["id"] = str(data[edge_id_from_attribute])
            edge_element = Element("edge", edge_attrs)
            add_attributes("edge", edge_element, data, edge_default)
            graph_element.append(edge_element)

    for xml_obj, data_entries in attributes.items():
        for name, value, scope, default in data_entries:
            key_id = get_key(name, _graphml_xml_type(value), scope, default)
            xml_obj.append(_graphml_make_data_element(Element, key_id, value))

    root.append(graph_element)
    if prettyprint:
        _graphml_indent(root)
    return tostring(root).decode(encoding)


def generate_graphml(
    G,
    encoding="utf-8",
    prettyprint=True,
    named_key_ids=False,
    edge_id_from_attribute=None,
):
    """Generate GraphML lines."""
    yield from _graphml_string(
        G,
        encoding=encoding,
        prettyprint=prettyprint,
        named_key_ids=named_key_ids,
        edge_id_from_attribute=edge_id_from_attribute,
    ).splitlines()


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
    """Return the Dorogovtsev-Goltsev-Mendes graph.

    A hierarchically constructed scale-free graph with deterministic structure.
    After n generations: (3^n + 3)/2 nodes, 3^n edges.
    """
    if n < 0:
        raise NetworkXError("n must be greater than or equal to 0")

    if create_using is None:
        return _rust_dorogovtsev_goltsev_mendes_graph(n)

    target = _empty_graph_from_create_using(create_using, default=Graph)
    if target.is_directed():
        raise NetworkXError("directed graph not supported")
    if target.is_multigraph():
        raise NetworkXError("multigraph not supported")

    graph = _rust_dorogovtsev_goltsev_mendes_graph(n)
    return _copy_graph_into(graph, target)


def prefix_tree_recursive(paths):
    """Recursive variant of prefix_tree."""
    return prefix_tree(paths)


def _nonisomorphic_split_tree(layout):
    """Split a level-sequence tree into its left subtree and remainder."""
    one_found = False
    split_at = None
    for index, level in enumerate(layout):
        if level == 1:
            if one_found:
                split_at = index
                break
            one_found = True

    if split_at is None:
        split_at = len(layout)

    left = [layout[index] - 1 for index in range(1, split_at)]
    rest = [0] + [layout[index] for index in range(split_at, len(layout))]
    return left, rest


def _nonisomorphic_next_rooted_tree(predecessor, pivot=None):
    """Advance one Beyer-Hedetniemi rooted-tree layout step."""
    if pivot is None:
        pivot = len(predecessor) - 1
        while predecessor[pivot] == 1:
            pivot -= 1
    if pivot == 0:
        return None

    q = pivot - 1
    while predecessor[q] != predecessor[pivot] - 1:
        q -= 1

    result = list(predecessor)
    for index in range(pivot, len(result)):
        result[index] = result[index - pivot + q]
    return result


def _nonisomorphic_next_tree(candidate):
    """Advance one Wright-Richmond-Odlyzko-McKay free-tree step."""
    left, rest = _nonisomorphic_split_tree(candidate)
    left_height = max(left)
    rest_height = max(rest)
    valid = rest_height >= left_height

    if valid and rest_height == left_height:
        if len(left) > len(rest):
            valid = False
        elif len(left) == len(rest) and left > rest:
            valid = False

    if valid:
        return candidate

    pivot = len(left)
    new_candidate = _nonisomorphic_next_rooted_tree(candidate, pivot)
    if candidate[pivot] > 2:
        new_left, _new_rest = _nonisomorphic_split_tree(new_candidate)
        suffix = range(1, max(new_left) + 2)
        new_candidate[-len(suffix) :] = suffix
    return new_candidate


def _nonisomorphic_layout_to_graph(layout):
    """Create a graph from a non-isomorphic tree level sequence."""
    graph = Graph()
    stack = []
    for node, level in enumerate(layout):
        if stack:
            parent = stack[-1]
            parent_level = layout[parent]
            while parent_level >= level:
                stack.pop()
                parent = stack[-1]
                parent_level = layout[parent]
            graph.add_edge(node, parent)
        stack.append(node)
    return graph


def nonisomorphic_trees(order):
    """Generate all non-isomorphic trees on n nodes."""
    if order < 0:
        raise ValueError("order must be non-negative")
    if order == 0:
        return
        yield
    if order == 1:
        yield empty_graph(1)
        return

    layout = list(range(order // 2 + 1)) + list(range(1, (order + 1) // 2))
    while layout is not None:
        layout = _nonisomorphic_next_tree(layout)
        if layout is not None:
            yield _nonisomorphic_layout_to_graph(layout)
            layout = _nonisomorphic_next_rooted_tree(layout)


def number_of_nonisomorphic_trees(order):
    """Count non-isomorphic trees on n nodes."""
    return sum(1 for _ in nonisomorphic_trees(order))


def random_lobster(n, p1, p2, seed=None):
    """Random lobster graph."""
    rng = _generator_random_state(seed)
    p1, p2 = abs(p1), abs(p2)
    if any(p >= 1 for p in [p1, p2]):
        raise NetworkXError("Probability values for `p1` and `p2` must both be < 1.")

    backbone_length = int(2 * rng.random() * n + 0.5)
    graph = path_graph(backbone_length)
    current_node = backbone_length - 1
    for backbone_node in range(backbone_length):
        while rng.random() < p1:
            current_node += 1
            graph.add_edge(backbone_node, current_node)
            caterpillar_node = current_node
            while rng.random() < p2:
                current_node += 1
                graph.add_edge(caterpillar_node, current_node)
    return graph


def random_lobster_graph(n, p1, p2, seed=None, create_using=None):
    """Return a random lobster graph."""
    graph = random_lobster(n, p1, p2, seed=seed)
    if create_using is None:
        return graph
    return _copy_graph_into(
        graph,
        _checked_create_using(
            create_using,
            directed=False,
            multigraph=False,
            default=Graph,
        ),
    )


def random_shell_graph(constructor, seed=None, create_using=None):
    """Multi-shell random graph."""
    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )

    shell_nodes = []
    inter_shell_edges = []
    next_label = 0

    for shell_size, shell_edges, ratio in constructor:
        within_shell_edges = int(shell_edges * ratio)
        inter_shell_edges.append(shell_edges - within_shell_edges)

        nodes = list(range(next_label, next_label + shell_size))
        for node in nodes:
            graph.add_node(node)

        if shell_size > 1:
            max_edges = shell_size * (shell_size - 1) // 2
            target_edges = min(within_shell_edges, max_edges)
            added_edges = set()
            while len(added_edges) < target_edges:
                left = nodes[rng.randint(0, shell_size - 1)]
                right = nodes[rng.randint(0, shell_size - 1)]
                if left == right:
                    continue
                edge = (min(left, right), max(left, right))
                if edge in added_edges:
                    continue
                added_edges.add(edge)
                graph.add_edge(left, right)

        shell_nodes.append(nodes)
        next_label += shell_size

    for shell_index in range(len(shell_nodes) - 1):
        left_shell = shell_nodes[shell_index]
        right_shell = shell_nodes[shell_index + 1]
        total_edges = inter_shell_edges[shell_index]
        edge_count = 0
        while edge_count < total_edges:
            left = rng.choice(left_shell)
            right = rng.choice(right_shell)
            if left == right or graph.has_edge(left, right):
                continue
            graph.add_edge(left, right)
            edge_count += 1

    return graph


def random_clustered_graph(joint_degree_sequence, seed=None, create_using=None):
    """Random graph from joint degree sequence."""
    joint_degree_sequence = list(joint_degree_sequence)
    graph = _checked_create_using(create_using, directed=False, default=MultiGraph)
    graph.add_nodes_from(range(len(joint_degree_sequence)))

    independent_stubs = []
    triangle_stubs = []
    for node in graph:
        independent_degree, triangle_degree = joint_degree_sequence[node]
        independent_stubs.extend([node] * independent_degree)
        triangle_stubs.extend([node] * triangle_degree)

    if len(independent_stubs) % 2 != 0 or len(triangle_stubs) % 3 != 0:
        raise NetworkXError("Invalid degree sequence")

    rng = _generator_random_state(seed)
    rng.shuffle(independent_stubs)
    rng.shuffle(triangle_stubs)
    while independent_stubs:
        graph.add_edge(independent_stubs.pop(), independent_stubs.pop())
    while triangle_stubs:
        first = triangle_stubs.pop()
        second = triangle_stubs.pop()
        third = triangle_stubs.pop()
        graph.add_edges_from([(first, second), (first, third), (second, third)])
    return graph


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
    generator = _DegreeSequenceRandomGraph(sequence, _generator_random_state(seed))
    for _ in range(tries):
        try:
            return generator.generate()
        except NetworkXUnfeasible:
            pass
    raise NetworkXError(f"failed to generate graph in {tries} tries")


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


_GRAPH_ATLAS_NUM_GRAPHS = 1253
_GRAPH_ATLAS_DATA_GZ = (
    "H4sICM2lO1cAA2F0bGFzLmRhdACtXUGS7aBunfcq/hJsMNgepiqpZJSkkv3vJff9btuSzjkC98vo1esLAiQhxJGE"
    "//1//uW//+Mfy9d//te//tv/fv7993/+f/35//rz//Lz//Lz/3r/f7nbbD9/qz//b/f/17tfv//2p99y/32Hvz99"
    "jp/ftp//n/f/yz3Wutx/XD9/ND+s9w9/KJsfiulRYq9qetX44+ZILm6Baws9gXSnvU2DPTQorNEhG4XhLm61S5LL"
    "/Yd6s7Ss9x//kHuWU4r5odge1fXwEivb/eM1G9OzmZ5b/LHDRMyPuyFbGOkjTCqyrZxu7PWf42+GQl1CgzhEXcMQ"
    "WxiiFsoYQwE5hxOtG5lojZNthBLMpwdKjHF1D2yvbsifRpG7z1CG0gkiuBi5uslvC0iaD7tF3ayCHVvkvOLbFiVQ"
    "xWK2zWm/bXhN46dho0wWw1uJePaQxjtluu1gGh/D+Rq+5pLCqbRFsk10iHuFTQc64f6Z7HhJtV9/2O4/bLf5a+3+"
    "4x+y5od+/3CN8/PDDj88u6sdjtzyT3t8kzzNj9/m9hmvL4Zs+5C09rivjuyfcU3PQsc0DSo0qL7B5ib2jH83sFxi"
    "ZrB306DcjDEU9jBE5FznnDOuwgkUPAf3xc3hmugzh32lQ3he7MXI4VlmaFQdP0SjLTCNWdo9cvbZPKaR5a6ytHvk"
    "8CNEM6fDUbqG+258iWI/w3DfW+5a4Y8XthBK1x68G61udQt1AI4iKNnteNQwp3ZTMY02EDDupaORRiXw6ehCVaKQ"
    "jx12BjdHx0G1Ac+34wQ1vij5oc8lsEQdW+cK8uRDn0WoEAyNFmUN8/xpGPdAE5vlbERTyhd6ZGcP7Kmhw6XF505N"
    "0kPxHvqgFNGGnWeg+M07y6Lr9hFF43fQZlpym4QauS5FcCjup3WpdNehvNdlo4bFiulq2WD/WUWz8+zpPG3LnXKJ"
    "nw/rchAtVpq8LtGGZX7SunJ5fbduP7Tvea/rcM+bVa7MvG2G7uZo11QZi1PIdeVHjJ2NnUkLM8FZ2Nbx0MErpW2t"
    "ZLndttq2jrLcgC9WOvw8sg694UlZhtpvaJeVWIntlniQZSnS5JJ5F7YPpcaWuBdLSrsl1i2e+muJRtPzJFivspPW"
    "3tJY2lGWzw5mrXFfxtZmJlXty8JsacVzzmos2ck1kyfVlxr9EH4EWeiIyTXd1TXaWm7p7Dq4g3j1IPpT437l9tFy"
    "F+2v74Xc1bIWdnjj8n6sLIyxjfdv0JItypyfOrYHkznOyEhw26ZskB0DZR73hndj142ds5esqVeyRZlb2k8POysm"
    "cy/B2CPKvI7W0Zi9Ts+xFvc5Wskg8xZl3lwPIo8WZb6RXn4dcZ83qo12jCjzGVhjbfm5LPyKps/nZAc3Ztu5fbTr"
    "in5yXA/dl13b+jg724vdMPkusL2UDUg1tXM7MNgRndl/32NF3ejMHvBzxvaKuhF7+B1y9YrnPR8nzpBdm3wPohud"
    "+XLDvUWgnQl7t6OdYNINurFzn2A0w6gb9WvCvu7cN/CeOfZidmNobQBEmgVS1z3ajryXHZPbD2Xj7ZjKdxju7SPa"
    "Ee0LxZ7r1D4g63QQlt4LRCqAayF37Ixtz6g7uZ6afXHkvgbTvqsn6lCc5bNOz1v0N7OZ2p4jH0Se4YCk1dmeAK2h"
    "zRazJVgb2y9x7Ks3P5dUz+B1nswG5bvNznx8T/G9/bqZTjE95lyL91PvM+Oa/czHOJK1G7E3v9d4ayORvpP5u2wf"
    "sZkXgRNm1tVzrixa35Qd8Z5hWZjOjddv56DuxHr8yAeOfWS7Nc5hzl8azUOfkW/mwvRxLA9GienmnHQZtUtX9+sv"
    "N+65f7V/9Puv6/3XkC5xY5n7Z3wbRi03brnf632wrXLjlPvXdTdazHgNqNrZdJiN/XU3fb/v5PbXI/T9w6PuWpyu"
    "xWXZzcrK4uZud/bVYoUW10hXi0JauEyVwvlnZlo4Dw2Xi+fj+nM3sDS6aVF/RvEz3QONEu4YpRxhHj5P4Gr18NVq"
    "ZeB+XWDV15rMiFXz19IqsDZMzCi1htmzgFmpltcqllpqI5rxp3W3e6Z20LBnrz6z30Orh46dV9Tny491e7GeVOur"
    "16dtCZzotzW0rVapMbZVMSPaG4hvVQm/vqVjW0U9f2RpWzUq7aDNW5f7ztLSOm9beb2/WmxhjdGeXHIEnjVmV1hk"
    "oDSUQcQbrpZF7rqgI43vA2L/2hb2qPXa3T5tDbRT7PsW94RHh4wE2x649M3PazWW5uG4ZM/FNYx+Ep32c/1p2Zd0"
    "noZmxzPz2gFhnr0ImsClXuU8gzS72jOwu7qVEXLdtkS7pVYUZXTpJbaMZ4eKE5XOZETt2L6E3duNvrsV7ewcoXLf"
    "8byOcrpaapsWZLRvKU07zwaWRuyj3dq3eGfw89wD531uqKWpznewrvtJ5U6szbHQvUk4f3Bbd/HAzPPg5z3h0oEy"
    "Erp06LMnriie/XIXHz3Q7Ernj7iPnnMoaPIRZSTP3OOEluIUPMfnkTlpTisnPBXCGXIWOgseBSxnPJvSU+eM51Nq"
    "0U/ms8W46tM6+g/sPv603onNiqfws8rcjw76dkY5Yh71I8u6+HMr9wXqsqa2wWOAdbHnVx3SjveaTnl+tc59De9/"
    "16Wl8/ZITV3iPszyK+pi/fHuVvncrB9+H0QHlcbWJfqI9gYfbVJdo58es0QdT8Ld3SMV8Tyua/RFvB2JrSudN7el"
    "Fe78HrtYfnTlam1liVjp6vZOXa0s249WNTPv7mYSz75rFv1eteXgQa0wP4Hrin4Km/tP66JleWmZmUmJ+9JLfvM6"
    "6DCGGOUCWZZoY3HutjX3XQRPijobmUWuBe9o+jStBW2s9rlqYbL0dsrSVja2fKFHVesymInjYOU29kJZv3fy0zrH"
    "Mq4b5dWanZeetp0J25dPlp73H2qNNhaLaGzraGOjrXLSqejvWGQk0kafJ+4G2/qU9oRoFWAh/vQLtDcmSyvHZmW5"
    "WVk+Z5rlh6Wt9yWb95bqSdDYjckSb3ZX6yjLWA/kabN96fe9nfdB5y18iI3LUpw7Ld+XgYMt+rG4J23r/M4RZxJl"
    "iZ6/bR33pd1p0a+vTcuS++C1cf/HZw74HvzcTM7l5vFJlWFs18HvJzFmZ2bVI2bsfQoitZ7Z3sJm1fn9X8cBa49+"
    "boUZxTHYmZrls9TeBHelX9rVHsY49tXD7+OZWTHfF097u/ITLKLnLPDKYTwzuT91j35wzGnAMXBvD+42O+JzzNex"
    "PdBesxuinVXc51dUvN9rCdx1mBDKg6087vNRdmQFjOjywR9bGLzTPfOtqK98xDM55gJjj7jPeWtbwTzys8DCHbjP"
    "4z25eu4e7IzGGdkxGrUlF3fZGNyHjtIz8jiUbZceLGBOF9Zazd5wmuiwp+uu9fRAXKueGJN6uEvHOGdlfusuYFGI"
    "Mgbf5owyH96uTmbb21fctUbmZ9znPuuHzQpjuYhPOXt1RpmjzxB7RJlbTOa5s9p15DjVhc4/Y2xLlDnrYTNWNoJX"
    "sRnZMaLMeY9qemjb/kjSSnBb9L2KRxS3hcUwEYu068jvV9b2Xj2izHEf1tBD4//c99+WGAcY7fMNMC1/B0V/d1tZ"
    "XCDDFbY18+E6sYnbGuMEfMfaWTGf3csjyHzlcWuGpV09cJ9f2R1x9VeP3G/H+9i26njC92xQHhz30l7fBtjXI/NL"
    "K4MmAv7Fdm1zPeb2uZ1VvKM9s+E5GFtRd+7LSoOWFIZTX2c68wC2wva5PwWCvSoMS/GZJnFWiI3FFYf9AfjYM6tr"
    "NkFLIL+nGg5fPZ3M63ifhx1VVWxJ3SY2gpcxRN2s3GFm8dSk3HW4mdYp20PJvEvuot9uxyHnIGBo1m9nnv5Wo8y9"
    "B0DWsS2EV1kUYoMcI1yHxwC2jfntaA/tGCzfxe/YGnpgvp0/Nbd4qgl8TfuJG2BsF2fjOM/Kc/yb2N2N51zEfW57"
    "RJl7LcGMs60x/NRiV09c5uqR++1kHU377TpOvQEGN1MttwEWN1MttwEmN1MttzV/X2d5RpjLuwE2N1Mtt7kcqdmK"
    "mg0wuplqua3r8z7eMs1YFKsbVcttHc/9cbXc1jnWnlfLbZ3nG+TVclvXd3pdV7QBfjdTLbc5DG+2Wm6D3KyZarmt"
    "8/veYIY7u/ONquW2nenGqFpu25ndGFXLbTu3G9FjvWR39cpj3vEOcvVS/qG1No+/e/VC3eDZLO5WRPLAMLII9hDw"
    "Po6TBU8ZMD+G7df7JP3pRXE/b3ftrezqpWLlPsMo+HXHXF5SOO0OFW/tX8npALllrIYDeBiwQHbbJ7sScs6sHnY5"
    "Q36mMO015zLJRVOvPFjO57ohvJ9zSblhOWFmCBiheoHD+RskZy3ufMxd2yB3De/GRKNOjh0xbbIzzHXDcsNw/uS6"
    "wT2Hpxdih7yu0GEXFD/k73nYdXF/I/bwSFcDHNHuSt+zml5KN9BreGbYAE/Unp7tZXUjfxVkM700rujvbvaEbUub"
    "GqsGHs6fKXZdOxlrFJtsgDPi+Y8WoC2jM4XdrdvK4oeItIaxHOZoOZ7V0baV+aJo5721aav2RRMprxtZF8oraNSq"
    "cgfwrLQz5HdV5q/ZsXhskfWyYzG7EdeHPGR2w/bqjIcJLhm5btZVUDf4TnH7C/BJfYuqZqz8nsIjSg3qBWP2LbPz"
    "rTC74SOVeHdoBK9UPoCRV1FxZ8y3tTwcY1isF2IarEewh5XphtfBC9My64JcP8wyfhCRZ6xcN4T2ApapY/dGyjQH"
    "sNKz0vZCu2HHUzPswopyO3X1wpq8sd/bSI4gRxP9DNWZ4uUVbBTkDOq9bHgocwe9VYtjRd3Q91fbS9X4+dta4OE2"
    "d6YE7QXsU/tRlhvMbiCCHWeY+aIRB3jG0nZDZ7o0wEIvK4oepRkL8FA7lsIcmsNEbY9u9D1mQDTARfUt0faKvqj2"
    "a2wvphtcLyw3IvbFtBd0vqHdiLgoRpYbwUV9Bgm1vS3msDErijOMusFvhqEX4KJe53kGQwNcdCYK1QguGiM3GFdq"
    "gIuiR0S4ATWoel3Gc+iqhifL1WuAi0aNonrYxzlPGHdoDhf1NwB/6nnOZ76oyuptO8td5nie7cXPlCfKylCsBrho"
    "tDi8F/NFe9CqiDk0wEUxT4JIGXDRmK3MMhPazvKieIaF7ZXFUlWkrKW1stJuAC6Kfi8ZC3DRjcgKvBTARaO3zDJh"
    "msyL9K8ZBB5SXHQmSteSutvBbfvgMTfttTxjqjvLKB7WACfVuHbsyXOlx5GgRvBS9QJQ6HnyHIw4HvFHKG46805c"
    "EzmWyksz5wGp/Y3re2breAsY6uwLcw1yL2dfmGsplppF2xrgqbMvzDWBqaqI9hP7aRJXZZEVG//pFFvFeDjGZbrE"
    "V0fxkk5yNrMY/IOX9CWrbcyw1h7qj7NYvD8XO61F5qh6CT3H8X9+2+2Q28kqeh5PuZl1Zrh8FnPoyznNocBbmvOp"
    "MxbMmKvKFeH23fa0OjS277bnXPwXbV8f1D1rxK6v77A3owmAzeYZGmavAD6L0QWeqdEpRosn0vqPiKt3itPq2Lrp"
    "CVhtnrFh1klySTMOGU0osX5T53sEmwC4baF8xXyWXmKOiX6P8fKCr55v7dCzzvlck6C3gOPmOTuWt9oO5ThaL7GG"
    "TOfTBKlQTFfnaNieulaUWRSzzjqnQxiD6jXWntg9wn2iqyf3qRli632TXt/lKhmpQA6rxZWzuEOHXNY808nydiZW"
    "xG5UvUYdYrxl3lsH7JdrPJEn4L8884n15PkIaNvhLBM15WNkvEMObJ5XZ8d8kwvZXU9ev4hxl3jT6YAL56eD0T7A"
    "hnPe2p6z+W8xY7+TnFnlWYTTnubOzsRVu8ihHUdxOs2jzW5Yz5hWh1jcR/q3IZ+WzZDjFx1q3SvhLbvzdlHzPrNO"
    "jgVNnJ8iv1ZZTCNPWguP+wRvrr3Hsyy38XbMeJbNRok74Mo6uhk0gb5vOBMt7oAv5/I0OkRzb3W2qe3JdGgmAtRF"
    "Di7zGP0rs53U1McIBkdZ+56/p8DGvXrOxqtAbyX27OseMNrVaV6uxaNUhW2nublcKrEnu5fNrVPlU3GdNToEeLSW"
    "ikd5+j6OZfH3jzrg0siheJ799BQ5u/5UopaavvfIIx7B74Pc3RJ0VaH23eHUiPPHmdqe/A1u1FvsmcUyrO0D7+3Q"
    "/pC/KQP6ccQ6AK1DsaeKlfegQ+C9HbwuFC1XjGJ1qP23+Zux9tHd7eEtyqeX9+EBtTtVnAPrwoNUAKe+oj5YoRnH"
    "RDvExiTaBzi1usnBzqY4NUYjL7tge6pYB88hsT1V3ZmvMiD7k+DUzL6jH7+nOcARS7Bj7glO/bwsyHb2Dji1src4"
    "Jr4xwDIq0PbtkBP8xByj1sXZqrrUGM2Op+AOucH5Oq1UMn/IYxixJ38nzEdI/Fqvnlm8DH14w6HBe5txTNsTY614"
    "2lNNgJzh7P7pZ8t9ahbj9XZoF9/k8HpEdQjyh3V9c5AKxalxXDbmXHyeSQX9IaX1YZcBTp3ZPjdbwKlz79/2RH8I"
    "z+t265LhLeQWR+1TXs0O3x5ht0iG9+3kmyQYRWR+wg449Wy2yw449WyOxz54O9SegFEqWe5gdpbt9E1Rhg2BBQOc"
    "WutQ2Nn0rVHui2FexA55yBGNyFDnHfKRx/kYduYzdde2d3O9R3F8dpY/ve33DvRpKGwixa/jProoRi9rTzFsxu/N"
    "8TzTMd7brFvkMWfSMlpK8WzdO/hrgGnr3ojQ7Mlbqdkd8uqt4iM8N93jobvMd56JS+807zmPTdt1j/OPdH73TrBu"
    "trfV2MqvmolT701jTRF5xAjIDrj3eOaG543F4HgeFBs7wy45321v9maAzsEK9py89TrK/TISC3nU3K7J+0KCh6vY"
    "kbFMkFcdkdAs/2ynuDjmn/GIxU7zrHOumXWTfGuGhoo9RvOu+dl58d/2ntM1nnWwA1aeZ+0Fqzj5ToXwXsV7s1ke"
    "nu3Ncvfz3D/be+bdOumnTbxjwbCHn97wnsU4U9LsUJq/nfc2Mwcsfcw1Ozbz/Xm0lfhrgKlnJzD442l+N8/YtL35"
    "XRK9LT7zvIYoj0ft5D0MtUPJWbLnuSt5RGt3WPuDoNiTV78ZtkM+OK9OFusmmPsoU9aOncVusHewayJHPNeYZ2xe"
    "Z5LtsWp6Mwx+WtfouxqY68uj4Dtg8bYCbZQVvcMbvGNtMb0dJv98Z8XXAEjfgeSPK3+JnESDb0YpFObqHbFVXt+m"
    "Zs5jhVmWjh1b3w0ylO3q/e5dn2BTzxjzibnAiJra3qM8mHzd2l9DtCTK+1gyXePZHs/Mj4XFoqOmIjJ+9S6kd/my"
    "yJfW8wPyzVnUQflMh3zfg7/LGMdGXWOVafxWc0xh+kreR5J/Pq4xOiAHXb/kgaf/seRxxnyXHCvTNR5dItoCOD+r"
    "xVT5FsfKYo68npDsEsD7s8wJ0BbA/N9EaA/A/cd1Fba3jkHynDffe07X4tqv3hpf47FBP7a+G4zjLEcSC2DxpDC2"
    "fAPZ52hxe37Q90b429F4hh40f53VvjPf4YAc9sg11Hk7cxXrxhsFkTfECHR9AOO5jnmPz9BDfh8dLQTRtfQbZKPY"
    "yAExg8tPzX22q3f23jYiBv5F14PGDbIsND9z/T1qLjXfm9f+8d0Z70QHxA3yvIo4tta1ceT3gLiBlffou5MHec8Z"
    "x5Y+U41nqMXztq94Hwm9RQ788y3GLP53QNwAszQSiZH3n7O6fH8nOjaW/8Uzktm6s7dz7A2+fyHectC4Aa/ZI7YF"
    "4gZ55kZc907WfXk9o7vgAXEDneNHbAt9R4XZNsq1Qa58fpM85FvTdlzpK0LO/Dhr2fbOsNxRRskB71D7WvyBx5XG"
    "DRod2/I8f0eB3a7s2KNYu884i+tWufTxTsS5pnRNZxIaPRdxA3aDJXuss3xWq6EbjGtmDnEDpS0s6+SQcYN4L2Hv"
    "3R8ubpDnVLCZqzx7jVTZ3kzXlF3DsbMzlCNztneG5Q41VcQNWGYIsQ4QN8D802jLbW+Vb8ZkDft78C62wl2u3uz7"
    "SJbfqaeZxg2sXeO9MR/f3kvQ63L7G96HUecIy3c4yPvZPG+T+qkQN4inYE/lPXuGos79UJDf1MMMM56pckzFD3gG"
    "w0VBveug4icRTz/k+9tZLMHPYS7PiOnDReF9/kfw3cUb3dn4PtfqEO91jzK1qpnDqGZtlP9zwLs0nIKOjhw07z/6"
    "01nO2SG+AchrZfgcRnWRPJZpKcy9fZTcSmjMYZz7ZmSRxB0yWZjdTesEVJYL3d1QL8DyHdE22DkoG6nmATaKfoMw"
    "n4M/I07x3s1IHx9ZnLSegOci8tvambx/M5dVeC787QC9gohdngt/hyKPP26Owvv3ubw+nBCjmMtutBSyM1tnV1pp"
    "jvDjUY7mCfUI4/zQsIrkm4nZ+NVQ4HXjvL6PSpO+bT62UXYVKi6L3i7H287km4sZ5makCd9gRA6O5qDeudBZM1EW"
    "Ol84O/ksBRU/y3PM7Cryb7WO4wtn8h5PVrNcbj/qTN7lUfkw/lWWU7ypzqPe7CZ0Dt5X197YQ2F8drMV2DnM5Qzo"
    "qORJ3+/JrG2MHpwQ92DSzHzaU8Q+spqbq+rrojCOtTE/pjwUaAzkWw4MASGchG9Qciuf7IvkLfeMD8/94hR1FPkN"
    "yUlTvP+j7DTjgz67/SpUrvkJsRG9s6xs7BwybIffkKIs5t66i7kedg7Ze2UzFTknjZWMcnKdNF/UWXiL/1DIvo3b"
    "Qk/qFUO9hTr9fW6VXQW3k2jpVR39Kd4VGt31LAWlk7kXZE5eWX+BGWnCf3CxFP5VmRxBO0UdxigiYuYg36jH2KFY"
    "BanHmMmhtRTys3sc4zjpu0SsPkDe9eBNe4Ykeh8qzoHVVGdROdgX8F6R3RcqY9Ppg6jTYJEioVEQc5nLDLarUGd3"
    "fuIZChB7mcuPMquAug28LeINwZ1ZEIPJKSAOc9Lvio5Ofj+HOXxco/tnn8fIhQ8DMZm4s/n4lkKMAbJ94fPkIgUW"
    "m+GvtQitpu/w11Sjws6itR35vggWZuc13fy0Ybk1587yHeYkelGI9+72pS3LM76RxY7xwVyrO6yC2Unmy0tLS2I3"
    "3gvF6GqkMNJJlovvKbCzO6cQ+TCq10UEI9gHiONoCsJWH/HNHH5mJTvrYDnT/GYmTj2I4/hVKEzOUoj4JPpwA0/s"
    "iPVuEdlkOLGnEGtDIoVR9vl5sLwctS+4NJlO8nimmgPmU6M3iHmPhgKtFRnfNc0qaL3IeAWWQpYXlq3koYDf6Mwp"
    "gD6czE7meHm4650RnxxRwFWMvrlmbTS1tCfm74z54PUB3+7J0GbGh6iTTLN5nuI3hXVxgRzmhnlTh4z4kFBoUJ4v"
    "4Eioa4668kVT+SEx802D7Mb4IYEf78ovOxE4/5DINDM7QdtDInv6gKcw1sjOUQ7GCEX4kJh50CVzbj8klMVETIX7"
    "6OtiQjqj8g9t9D5kVkNmVEmSkLFayoNaU7N5/xUgtnMnPqOAi42B/Q+ZMa4+s/1cwCe7xgx4463qnN9IyOTP5n8v"
    "auR2fMhktaG50O1sSixIzh86UIuikSD2ugjPILjJvA1RMofqQ8bniM9UaKEv8CETH79+tz1vMjMvrk2wOA8R5Sk3"
    "hoyKE2n8FW+kHzIzwSJN6iYzHzHSkat1qcx95cnhGYuTt7dGXrGbzZwW53Dah4z6yue7relCSaxccs5QVH3/fzUb"
    "rcUjYTsy7NY1fwDfZOY/g6Oh0w+ZGS2Oi8LZTH6YgpVF261Jv1I8ZyjsoujzXuPUgGtmNxmVa6xrfZn6bfFiNgP9"
    "oN5s6APnW5LrDSnlyQ0FS+D8kFF5JGN74xY19ihYAkE06UmVD7+DslypdYFnwubBKbuopmox+B2W1+9+yMSPiI3C"
    "O9z6Db+goWMsVm+gJCj6xZxPMJvcL0akgOXFfciMEqFYYJvMhqENLFMxv5LBc2PzUJwjk3+7N8sXtGQgmMWew3iK"
    "a5TAaUQrr6MuRIu7euLiDcD2ITN6w+dhdXZq0kfKVIqL3pr069FRi31Mgi6qC/9mxh0wZGZx3NzZh6DXKJFLqN8p"
    "BD5yaj2Z6c+DYKjekRl9f48biihwWrTEyhozqPpDJmrxLNwReBO1+HcupHgHbVQPDWTUAxvscQ29w8WXR1QeowLp"
    "0ifS2vxsmF+cuY/8gJGFT9oeY5LFh0yGBfOsPMYbKIEaJZNxgUP8zJKILoBm8aFw4TcpLB8ysxkHCC87MlkJii5Y"
    "ADLZe/H8AkRZPEr8n4ObXXQty9TKZ0M/5Z1tBh/VuMlkuYRa6FHgZ/SLZ/QGT014qW02ZhcWpbQ4eqG5ST/f1JZa"
    "FQxkYlA4T5lVWgzVVNpxY1kLN5nsEwiXxRv7xbSuKsYmtbR+yKwL0+L8owxE4KuLy2UxTn6lv8koLcZrqk6N/ZD5"
    "fXyu2dmoj3K8gjpWqLr6TY7ph8zok8BT1m8dfqc8i4w3z+Z531gFZ29SMfqRhS3SjbGKT5v7eMyUS7m6Gq2ZgIEE"
    "qtbw0FyeTDpY4O9iekynfhXX8wkwN6ns9sdxL4FjrIMPqHMnzwf8b1LvELlrkXRWM6gcR3JBgjPI3BT+vkLRl8Y1"
    "IhQQeZXG/F5B1msS98t4xVS0MI8ky7ZMSL0t6tYSpBViqiII+eRIxTTKObyDzorlU85VlQCpUWLl9I16hZjgr9MZ"
    "VhoXnIFRCKkRBpKdhc5pXpMCM+UcKmWgMUKGko+VoapSirmItyOV5QqPsXtHar4wMiITsMD5L2qqi9hNKstAGl9Q"
    "3axmbDsjibxKCtWy+y7zZDae9Y63Bcy8AVIz5ZRTMPhKYolvMrjdrHJPBo1OskCGAEZ2T6UYrZtK/WQX2Hw7u9hi"
    "hloMwwbrxpJBZ1JaCSmWdzfSKy5BKIGLM1NkcFZQC6esA68UsbYdiuKy7ZwGmdc28mTyG7tbYPa5LK2mlFfvMJbM"
    "XpFHCjnqMyHBTNvHQIAjpWz765yZFWKRv87iWXvMhX6nDFavICb562yetY/wl3nwpKvc/Tkn0pEaafsLXmXaPuMY"
    "GVKjtP4crXekRtqeHRWBVzzRfwQnM4PcuW0f8wpJibI9DhHmNy9RvzcnRe9+kI81zV8B8NILcczR/XlATn86LM8N"
    "FeTm3jRRSEjckzS+qc7FsUsi4pz6iB2Qy8pdNCKprAaNe2YbK7/kiYJBXrwxvnHAK5DvERJHLn6aMd9YQ3IzXk/u"
    "QDlyvPB1tBMkubfVXQNys7dbbdCrJafRS5UWnqkxjZ++A47dYkcvDOSeYyQHT0+O/P98duebc2J864VHKdUTYVP1"
    "SiuNs76rX3bksnjr+2srrXl855w6cvrhoZwk90sgDpsfPYOQ9wpPXCrvcs6FFu9d5uSkZAs8fqnITWVilCVWmtev"
    "8Y6QzliR8dpfVdaU5f1ZkShKgfjt+3uDI6fuDjNeOiGnnpn5VVSw0LiuCicMrXGRsd1fGahC6zOz9ypSpKGsM7fn"
    "6aTyQt/izB2L5OJU4GHODK4bxk9KEu8dXVNEfK6s2fMheZhPKcxEbefLY6isLBN4XKmS8pLntv+Fz1fW0V3j/V6e"
    "ig+/8upLebNjpk66AvHi7Bozt3D6fOibw5OQzHfPyL2kJN/snjn7CPHkv/a6CtSX/v2BCrWms1E3bXqh7lTHbWYP"
    "B4g3j0gOEcgCz5i+BzQjLyH+PL59jjbk8KHT90dZ/Z1Hljl58BTqm5wjfaTB+6hvIsIPaZjtzC56b+jES6p/a0Yg"
    "jv3GkUlmm91p3h3Eluz2N15cQnZUo/W7DTuMe8+Bz0A222EzW4Hvsql4+Dwo7Wb8/7PTCOBVputwR1aM8PndG+9v"
    "fKu0XvcvdflNDe/7mUPMfZ4pMzyXcfi/c+bdEDPx+d8P839Zvjl0gRkBAA=="
)
_GRAPH_ATLAS_RECORDS = None


def _graph_atlas_records():
    """Return cached graph-atlas records parsed from the local upstream data."""
    global _GRAPH_ATLAS_RECORDS
    if _GRAPH_ATLAS_RECORDS is not None:
        return _GRAPH_ATLAS_RECORDS

    lines = gzip.decompress(base64.b64decode(_GRAPH_ATLAS_DATA_GZ)).decode().splitlines()
    records = []
    index = 0
    while index < len(lines):
        graph_line = lines[index]
        if not graph_line.startswith("GRAPH "):
            raise NetworkXError("invalid graph atlas data")
        graph_index = int(graph_line.split()[1])
        index += 1

        if index >= len(lines) or not lines[index].startswith("NODES "):
            raise NetworkXError("invalid graph atlas data")
        node_count = int(lines[index].split()[1])
        index += 1

        edges = []
        while index < len(lines) and not lines[index].startswith("GRAPH "):
            edge_line = lines[index].strip()
            if edge_line:
                u, v = edge_line.split()
                edges.append((int(u), int(v)))
            index += 1
        records.append((graph_index, node_count, tuple(edges)))

    if len(records) != _GRAPH_ATLAS_NUM_GRAPHS:
        raise NetworkXError("invalid graph atlas data")
    _GRAPH_ATLAS_RECORDS = tuple(records)
    return _GRAPH_ATLAS_RECORDS


def _graph_atlas_from_record(record):
    graph_index, node_count, edges = record
    graph = Graph()
    graph.name = f"G{graph_index}"
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from(edges)
    return graph


def graph_atlas(i):
    """Return graph i from the atlas."""
    if not 0 <= i < _GRAPH_ATLAS_NUM_GRAPHS:
        raise ValueError(f"index must be between 0 and {_GRAPH_ATLAS_NUM_GRAPHS}")
    return _graph_atlas_from_record(_graph_atlas_records()[i])


def graph_atlas_g():
    """Return list of all graphs in the atlas."""
    return [_graph_atlas_from_record(record) for record in _graph_atlas_records()]


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


def is_regular_expander(G, *, epsilon=0):
    """Check if G is a regular expander graph."""
    import numpy as np
    import scipy as sp

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if epsilon < 0:
        raise NetworkXError("epsilon must be non negative")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")
    if not is_regular(G):
        return False

    _, degree = next(iter(G.degree))
    adjacency = adjacency_matrix(G, dtype=float)
    eigenvalues = sp.sparse.linalg.eigsh(
        adjacency,
        which="LM",
        k=2,
        return_eigenvectors=False,
    )
    lambda2 = min(eigenvalues)
    return bool(abs(lambda2) < 2 * np.sqrt(degree - 1) + epsilon)


def maybe_regular_expander(n, d, seed=None):
    """Attempt to build a d-regular expander."""
    return maybe_regular_expander_graph(n, d, seed=seed)


def maybe_regular_expander_graph(n, d, *, create_using=None, max_tries=100, seed=None):
    """Utility for creating a random regular expander."""
    from networkx.utils.misc import create_random_state

    if n < 1:
        raise NetworkXError("n must be a positive integer")
    if not (d >= 2):
        raise NetworkXError("d must be greater than or equal to 2")
    if not (d % 2 == 0):
        raise NetworkXError("d must be even")
    if not (n - 1 >= d):
        raise NetworkXError(
            f"Need n-1>= d to have room for {d // 2} independent cycles with {n} nodes"
        )

    graph = empty_graph(n, create_using)
    if n < 2:
        return graph

    seed = create_random_state(seed)
    edges = set()

    for i in range(d // 2):
        iterations = max_tries
        while len(edges) != (i + 1) * n:
            iterations -= 1
            cycle = seed.permutation(n - 1).tolist()
            cycle.append(n - 1)
            new_edges = {
                (u, v)
                for u, v in itertools.pairwise(cycle + [cycle[0]])
                if (u, v) not in edges and (v, u) not in edges
            }
            if len(new_edges) == n:
                edges.update(new_edges)
            if iterations == 0:
                raise NetworkXError("Too many iterations in maybe_regular_expander_graph")

    graph.add_edges_from(edges)
    return graph


def random_regular_expander_graph(
    n,
    d,
    *,
    epsilon=0,
    create_using=None,
    max_tries=100,
    seed=None,
):
    """Return a random regular expander graph on n nodes with degree d."""
    from networkx.utils.misc import create_random_state

    seed = create_random_state(seed)
    graph = maybe_regular_expander_graph(
        n,
        d,
        create_using=create_using,
        max_tries=max_tries,
        seed=seed,
    )
    iterations = max_tries
    while not is_regular_expander(graph, epsilon=epsilon):
        iterations -= 1
        graph = maybe_regular_expander_graph(
            n,
            d,
            create_using=create_using,
            max_tries=max_tries,
            seed=seed,
        )
        if iterations == 0:
            raise NetworkXError("Too many iterations in random_regular_expander_graph")
    return graph


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
        mapping_keys = set(_map)
        mapping_values = set(_map.values())
        if mapping_keys & mapping_values:
            dependency_nodes = []
            dependency_seen = set()
            dependency_edges = {}
            indegree = {}

            def add_dependency_node(node):
                if node in dependency_seen:
                    return
                dependency_seen.add(node)
                dependency_nodes.append(node)
                dependency_edges[node] = []
                indegree[node] = indegree.get(node, 0)

            for old, new in _map.items():
                add_dependency_node(old)
                add_dependency_node(new)
                if old == new:
                    continue
                if new not in dependency_edges[old]:
                    dependency_edges[old].append(new)
                    indegree[new] = indegree.get(new, 0) + 1

            queue = deque(node for node in dependency_nodes if indegree[node] == 0)
            topo_order = []
            while queue:
                node = queue.popleft()
                topo_order.append(node)
                for neighbor in dependency_edges[node]:
                    indegree[neighbor] -= 1
                    if indegree[neighbor] == 0:
                        queue.append(neighbor)

            if len(topo_order) != len(dependency_nodes):
                raise NetworkXUnfeasible(
                    "The node label sets are overlapping and no ordering can "
                    "resolve the mapping. Use copy=True."
                )

            nodes = list(reversed(topo_order))
        else:
            nodes = [n for n in G if n in _map]

        multigraph = G.is_multigraph()
        directed = G.is_directed()

        for old in nodes:
            try:
                new = _map[old]
                G.add_node(new, **dict(G.nodes[old]))
            except KeyError:
                continue

            if new == old:
                continue

            if multigraph:
                new_edges = [
                    (new, new if old == target else target, key, dict(data))
                    for target, keyed_data in G[old].items()
                    for key, data in keyed_data.items()
                ]
                if directed:
                    new_edges += [
                        (new if old == source else source, new, key, dict(data))
                        for source, keyed_data in G.pred[old].items()
                        for key, data in keyed_data.items()
                    ]

                seen = set()
                for index, (source, target, key, data) in enumerate(new_edges):
                    if target in G[source] and key in G[source][target]:
                        new_key = key if isinstance(key, (int, float)) else 0
                        while new_key in G[source][target] or (target, new_key) in seen:
                            new_key += 1
                        new_edges[index] = (source, target, new_key, data)
                        seen.add((target, new_key))
            else:
                new_edges = [
                    (new, new if old == target else target, dict(data))
                    for target, data in G[old].items()
                ]
                if directed:
                    new_edges += [
                        (new if old == source else source, new, dict(data))
                        for source, data in G.pred[old].items()
                    ]

            G.remove_node(old)
            G.add_edges_from(new_edges)
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
        nodelist = G
    return {n: [nb for nb in G.neighbors(n) if nb in nodelist] for n in nodelist}


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


class _LiveMultiEdgeDataView(Mapping):
    def __init__(self, graph, u, v):
        self._graph = graph
        self._u = u
        self._v = v

    def _current(self):
        return self._graph[self._u][self._v]

    def __iter__(self):
        return iter(self._current())

    def __len__(self):
        return len(self._current())

    def __getitem__(self, key):
        return self._current()[key]


def _checked_create_using(create_using=None, *, directed=None, multigraph=None, default=Graph):
    """Validate and clear ``create_using`` using NetworkX's contract."""
    default_graph_type = _classic_default_graph_type(default)
    probe = create_using if create_using is not None else default_graph_type
    if isinstance(probe, type):
        probe = probe()

    if not all(hasattr(probe, attr) for attr in ("clear", "is_directed", "is_multigraph")):
        raise TypeError("create_using is not a valid NetworkX graph type or instance")

    if directed is not None:
        if directed and not probe.is_directed():
            raise NetworkXError("create_using must be directed")
        if not directed and probe.is_directed():
            raise NetworkXError("create_using must not be directed")

    if multigraph is not None:
        if multigraph and not probe.is_multigraph():
            raise NetworkXError("create_using must be a multi-graph")
        if not multigraph and probe.is_multigraph():
            raise NetworkXError("create_using must not be a multi-graph")

    return _empty_graph_from_create_using(create_using, default=default_graph_type)


def _copy_graph_into(source, target):
    """Populate ``target`` with the nodes, edges, and graph attrs from ``source``."""
    target.graph.update(dict(source.graph))
    for node, attrs in source.nodes(data=True):
        target.add_node(node, **dict(attrs))

    if source.is_multigraph():
        for u, v, key, attrs in source.edges(keys=True, data=True):
            target.add_edge(u, v, key=key, **dict(attrs))
    else:
        for u, v, attrs in source.edges(data=True):
            target.add_edge(u, v, **dict(attrs))

    return target


def _checked_directed_create_using(create_using=None, *, default=DiGraph):
    """Validate ``create_using`` for directed-growth generators."""
    default_graph_type = _classic_default_graph_type(default)
    probe = create_using if create_using is not None else default_graph_type
    if isinstance(probe, type):
        probe = probe()

    if not all(hasattr(probe, attr) for attr in ("clear", "is_directed", "is_multigraph")):
        raise TypeError("create_using is not a valid NetworkX graph type or instance")
    if not probe.is_directed():
        raise NetworkXError("create_using must indicate a Directed Graph")

    return _empty_graph_from_create_using(create_using, default=default_graph_type)


def _nodes_or_number_local(value):
    """Return ``(value, nodes)`` following NetworkX ``nodes_or_number`` rules."""
    try:
        nodes = list(range(value))
    except TypeError:
        nodes = tuple(value)
    else:
        if value < 0:
            raise NetworkXError(f"Negative number of nodes not valid: {value}")
    return value, nodes


def _tree_edges_local(n, r):
    """Yield rooted r-ary tree edges in NetworkX insertion order."""
    if n == 0:
        return

    nodes = iter(range(n))
    parents = [next(nodes)]
    while parents:
        source = parents.pop(0)
        for _ in range(r):
            try:
                target = next(nodes)
            except StopIteration:
                break
            parents.append(target)
            yield source, target


def _classic_default_graph_type(default):
    """Map a default graph constructor or instance to the Franken graph surface."""
    if default is None:
        return Graph
    if default in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        return default

    probe = default() if isinstance(default, type) else default
    if probe.is_multigraph():
        return MultiDiGraph if probe.is_directed() else MultiGraph
    return DiGraph if probe.is_directed() else Graph


def _classic_graph_from_create_using(create_using=None, default=Graph):
    """Create an empty graph for classic generator wrappers without NetworkX."""
    if create_using is None:
        return default()

    if isinstance(create_using, type):
        return create_using()

    if not hasattr(create_using, "clear"):
        raise TypeError("create_using is not a valid NetworkX graph type or instance")

    create_using.clear()
    return create_using


def _add_nodes_in_order(graph, nodes):
    """Add nodes one-by-one to preserve NetworkX insertion-order semantics."""
    for node in nodes:
        graph.add_node(node)


def _classic_named_graph_from_adjlist(
    adjacency, create_using=None, name=None, directed_error="Directed Graph not supported in create_using"
):
    """Build a named undirected graph from an adjacency dict with NetworkX parity."""
    graph = _classic_graph_from_create_using(create_using)
    if graph.is_directed():
        raise NetworkXError(directed_error)

    _add_nodes_in_order(graph, adjacency)
    if graph.is_multigraph():
        seen = {}
        for node, neighbors in adjacency.items():
            for neighbor in neighbors:
                if neighbor not in seen:
                    graph.add_edge(node, neighbor)
            seen[node] = 1
    else:
        graph.add_edges_from(
            (node, neighbor) for node, neighbors in adjacency.items() for neighbor in neighbors
        )

    if name is not None:
        graph.graph["name"] = name
    return graph


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
    _add_nodes_in_order(G, d)
    if G.is_multigraph() and not G.is_directed():
        seen = {}
        for node, neighbors in d.items():
            for nb in neighbors:
                if nb not in seen:
                    G.add_edge(node, nb)
            seen[node] = 1
    else:
        G.add_edges_from((node, nb) for node, neighbors in d.items() for nb in neighbors)
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
        nodes = [node for node, _degree in sorted(G.degree, key=lambda item: item[1])]
        nodes.reverse()
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


def from_pandas_edgelist(
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
    graph = _empty_graph_from_create_using(create_using)

    if edge_attr is None:
        if graph.is_multigraph() and edge_key is not None:
            for u, v, edge_key_value in zip(df[source], df[target], df[edge_key]):
                _add_json_multiedge(graph, u, v, edge_key_value, {})
        else:
            graph.add_edges_from(zip(df[source], df[target]))
        return graph

    reserved_columns = [source, target]
    if graph.is_multigraph() and edge_key is not None:
        reserved_columns.append(edge_key)

    if isinstance(edge_attr, bool) and edge_attr:
        attr_col_headings = [column for column in df.columns if column not in reserved_columns]
    elif isinstance(edge_attr, list | tuple):
        attr_col_headings = edge_attr
    else:
        attr_col_headings = [edge_attr]
    if len(attr_col_headings) == 0:
        raise NetworkXError(
            f"Invalid edge_attr argument: No columns found with name: {attr_col_headings}"
        )

    try:
        attribute_data = zip(*[df[column] for column in attr_col_headings])
    except (KeyError, TypeError) as err:
        msg = f"Invalid edge_attr argument: {edge_attr}"
        raise NetworkXError(msg) from err

    if graph.is_multigraph():
        if edge_key is not None:
            try:
                attribute_data = zip(attribute_data, df[edge_key])
            except (KeyError, TypeError) as err:
                msg = f"Invalid edge_key argument: {edge_key}"
                raise NetworkXError(msg) from err

        for source_node, target_node, attrs in zip(df[source], df[target], attribute_data):
            if edge_key is not None:
                attrs, edge_key_value = attrs
                _add_json_multiedge(
                    graph,
                    source_node,
                    target_node,
                    edge_key_value,
                    dict(zip(attr_col_headings, attrs)),
                )
            else:
                actual_key = graph.add_edge(source_node, target_node)
                graph[source_node][target_node][actual_key].update(zip(attr_col_headings, attrs))
    else:
        for source_node, target_node, attrs in zip(df[source], df[target], attribute_data):
            graph.add_edge(source_node, target_node)
            graph[source_node][target_node].update(zip(attr_col_headings, attrs))

    return graph


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


def from_numpy_array(
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
    kind_to_python_type = {
        "f": float,
        "i": int,
        "u": int,
        "b": bool,
        "c": complex,
        "S": str,
        "U": str,
        "V": "void",
    }
    graph = _empty_graph_from_create_using(create_using)
    if A.ndim != 2:
        raise NetworkXError(f"Input array must be 2D, not {A.ndim}")
    n, m = A.shape
    if n != m:
        raise NetworkXError(f"Adjacency matrix not square: nx,ny={A.shape}")
    dtype = A.dtype
    try:
        python_type = kind_to_python_type[dtype.kind]
    except Exception as err:
        raise TypeError(f"Unknown numpy data type: {dtype}") from err

    default_nodes = nodelist is None
    if default_nodes:
        nodelist = range(n)
    else:
        if len(nodelist) != n:
            raise ValueError("nodelist must have the same length as A.shape[0]")

    graph.add_nodes_from(nodelist)
    edges = ((int(u), int(v)) for u, v in zip(*A.nonzero()))
    if python_type == "void":
        fields = sorted((offset, field_dtype, name) for name, (field_dtype, offset) in dtype.fields.items())
        triples = (
            (
                u,
                v,
                {}
                if edge_attr in [False, None]
                else {
                    name: kind_to_python_type[field_dtype.kind](value)
                    for (_, field_dtype, name), value in zip(fields, A[u, v])
                },
            )
            for u, v in edges
        )
    elif python_type is int and graph.is_multigraph() and parallel_edges:
        chain = itertools.chain.from_iterable
        if edge_attr in [False, None]:
            triples = chain(((u, v, {}) for _ in range(A[u, v])) for (u, v) in edges)
        else:
            triples = chain(
                ((u, v, {edge_attr: 1}) for _ in range(A[u, v])) for (u, v) in edges
            )
    else:
        if edge_attr in [False, None]:
            triples = ((u, v, {}) for u, v in edges)
        else:
            triples = ((u, v, {edge_attr: python_type(A[u, v])}) for u, v in edges)

    if graph.is_multigraph() and not graph.is_directed():
        triples = ((u, v, attrs) for u, v, attrs in triples if u <= v)
    if not default_nodes:
        idx_to_node = dict(enumerate(nodelist))
        triples = ((idx_to_node[u], idx_to_node[v], attrs) for u, v, attrs in triples)

    graph.add_edges_from(triples)
    return graph


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


def from_scipy_sparse_array(
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
    kind_to_python_type = {
        "f": float,
        "i": int,
        "u": int,
        "b": bool,
        "c": complex,
    }
    graph = _empty_graph_from_create_using(create_using)
    n, m = A.shape
    if n != m:
        raise NetworkXError(f"Adjacency matrix not square: nx,ny={A.shape}")

    graph.add_nodes_from(range(n))
    coo = A.tocoo()
    python_type = kind_to_python_type.get(A.dtype.kind)
    triples = (
        (
            int(u),
            int(v),
            python_type(weight) if python_type is not None else weight,
        )
        for u, v, weight in zip(coo.row, coo.col, coo.data)
    )
    if A.dtype.kind in ("i", "u") and graph.is_multigraph() and parallel_edges:
        chain = itertools.chain.from_iterable
        triples = chain(((u, v, 1) for _ in range(int(weight))) for (u, v, weight) in triples)
    if graph.is_multigraph() and not graph.is_directed():
        triples = ((u, v, weight) for u, v, weight in triples if u <= v)

    graph.add_weighted_edges_from(triples, weight=edge_attribute)
    return graph


def from_dict_of_dicts(d, create_using=None, multigraph_input=False):
    """Return a graph from a dictionary of dictionaries."""
    graph = _empty_graph_from_create_using(create_using)
    graph.add_nodes_from(d)

    if multigraph_input:
        if graph.is_directed():
            if graph.is_multigraph():
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        for edge_key, edge_attrs in edge_map.items():
                            _add_json_multiedge(graph, u, v, edge_key, dict(edge_attrs))
            else:
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        for _, edge_attrs in edge_map.items():
                            graph.add_edge(u, v)
                            graph[u][v].update(edge_attrs)
        else:
            seen = set()
            if graph.is_multigraph():
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        if (u, v) in seen:
                            continue
                        for edge_key, edge_attrs in edge_map.items():
                            _add_json_multiedge(graph, u, v, edge_key, dict(edge_attrs))
                        seen.add((v, u))
            else:
                for u, nbrs in d.items():
                    for v, edge_map in nbrs.items():
                        if (u, v) in seen:
                            continue
                        for _, edge_attrs in edge_map.items():
                            graph.add_edge(u, v)
                            graph[u][v].update(edge_attrs)
                        seen.add((v, u))
        return graph

    if graph.is_multigraph():
        if graph.is_directed():
            for u, nbrs in d.items():
                for v, edge_attrs in nbrs.items():
                    _add_json_multiedge(graph, u, v, 0, dict(edge_attrs))
        else:
            seen = set()
            for u, nbrs in d.items():
                for v, edge_attrs in nbrs.items():
                    if (u, v) in seen:
                        continue
                    _add_json_multiedge(graph, u, v, 0, dict(edge_attrs))
                    seen.add((v, u))
    else:
        for u, nbrs in d.items():
            for v, edge_attrs in nbrs.items():
                graph.add_edge(u, v)
                graph[u][v].update(edge_attrs)

    return graph


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
                    if G.is_multigraph():
                        d[u][v] = _LiveMultiEdgeDataView(G, u, v)
                    else:
                        d[u][v] = data
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
    if name == ident:
        raise NetworkXError("name and ident must be different.")

    multigraph = data.get("multigraph")
    directed = data.get("directed")
    graph = _json_graph_from_flags(
        directed=bool(directed),
        multigraph=bool(multigraph),
    )
    graph.graph.update(dict(data.get("data")))

    for node_entry in data["elements"]["nodes"]:
        node_data = node_entry["data"].copy()
        node = node_entry["data"]["value"]

        if node_entry["data"].get(name):
            node_data[name] = node_entry["data"].get(name)
        if node_entry["data"].get(ident):
            node_data[ident] = node_entry["data"].get(ident)

        graph.add_node(node)
        graph.nodes[node].update(node_data)

    for edge_entry in data["elements"]["edges"]:
        edge_data = edge_entry["data"].copy()
        source = edge_entry["data"]["source"]
        target = edge_entry["data"]["target"]
        if multigraph:
            edge_key = edge_entry["data"].get("key", 0)
            _add_json_multiedge(graph, source, target, edge_key, edge_data)
        else:
            graph.add_edge(source, target)
            graph.edges[source, target].update(edge_data)
    return graph


def to_networkx_graph(data, create_using=None, multigraph_input=False):
    """Convert supported input data to a graph."""
    if hasattr(data, "adj"):
        try:
            result = from_dict_of_dicts(
                data.adj,
                create_using=create_using,
                multigraph_input=data.is_multigraph(),
            )
            result.graph.update(data.graph)
            for node, attrs in data.nodes(data=True):
                result.nodes[node].update(attrs)
            return result
        except Exception as err:
            raise NetworkXError("Input is not a correct NetworkX graph.") from err

    if isinstance(data, dict):
        try:
            return from_dict_of_dicts(
                data,
                create_using=create_using,
                multigraph_input=multigraph_input,
            )
        except Exception as err1:
            if isinstance(multigraph_input, bool) and multigraph_input:
                raise NetworkXError(
                    f"converting multigraph_input raised:\n{type(err1)}: {err1}"
                )
            try:
                return from_dict_of_lists(data, create_using=create_using)
            except Exception as err2:
                raise TypeError("Input is not known type.") from err2

    if isinstance(data, (list, tuple, Iterator)):
        try:
            return from_edgelist(data, create_using=create_using)
        except Exception:
            pass

    try:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            if data.shape[0] == data.shape[1]:
                try:
                    return from_pandas_adjacency(data, create_using=create_using)
                except Exception as err:
                    msg = "Input is not a correct Pandas DataFrame adjacency matrix."
                    raise NetworkXError(msg) from err
            else:
                try:
                    return from_pandas_edgelist(
                        data,
                        edge_attr=True,
                        create_using=create_using,
                    )
                except Exception as err:
                    msg = "Input is not a correct Pandas DataFrame edge-list."
                    raise NetworkXError(msg) from err
    except ImportError:
        pass

    try:
        import numpy as np

        if isinstance(data, np.ndarray):
            try:
                return from_numpy_array(data, create_using=create_using)
            except Exception as err:
                raise NetworkXError("Failed to interpret array as an adjacency matrix.") from err
    except ImportError:
        pass

    try:
        if hasattr(data, "format"):
            return from_scipy_sparse_array(data, create_using=create_using)
    except Exception as err:
        raise NetworkXError("Input is not a correct scipy sparse array type.") from err

    if isinstance(data, (Collection, Generator, Iterator)):
        try:
            return from_edgelist(data, create_using=create_using)
        except Exception as err:
            raise NetworkXError("Input is not a valid edge list") from err

    raise NetworkXError("Input is not a known data type for conversion.")


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
    from franken_networkx import _fnx

    if create_using is None:
        return _fnx.gnc_graph(n, seed=seed, create_using=None)

    graph = _checked_directed_create_using(create_using, default=DiGraph)
    if n == 0:
        return empty_graph(1, create_using=graph, default=DiGraph)

    return _copy_graph_into(_fnx.gnc_graph(n, seed=seed, create_using=None), graph)


def gnr_graph(n, p, create_using=None, seed=None):
    """Return a growing network with redirection (GNR) digraph."""
    from franken_networkx import _fnx

    if create_using is None:
        return _fnx.gnr_graph(n, p, seed=seed, create_using=None)

    graph = _checked_directed_create_using(create_using, default=DiGraph)
    if n == 0:
        return empty_graph(1, create_using=graph, default=DiGraph)

    return _copy_graph_into(_fnx.gnr_graph(n, p, seed=seed, create_using=None), graph)


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
    graph = _checked_create_using(create_using, directed=False, multigraph=False, default=Graph)
    if m < 1 or m >= n:
        raise NetworkXError(
            f"Extended Barabasi-Albert network needs m>=1 and m<n, m={m}, n={n}"
        )
    if p + q >= 1:
        raise NetworkXError(
            f"Extended Barabasi-Albert network needs p + q <= 1, p={p}, q={q}"
        )

    rng = _generator_random_state(seed)
    graph.add_nodes_from(range(m))
    attachment_preference = list(range(m))
    new_node = m

    def random_subset(population, count):
        targets = set()
        while len(targets) < count:
            targets.add(rng.choice(population))
        return targets

    while new_node < n:
        a_probability = rng.random()
        clique_degree = len(graph) - 1
        clique_size = (len(graph) * clique_degree) / 2

        if a_probability < p and graph.size() <= clique_size - m:
            eligible_nodes = [
                node for node, degree_value in graph.degree if degree_value < clique_degree
            ]
            for _ in range(m):
                src_node = rng.choice(eligible_nodes)
                prohibited_nodes = list(graph[src_node])
                prohibited_nodes.append(src_node)
                dest_node = rng.choice(
                    [node for node in attachment_preference if node not in prohibited_nodes]
                )
                graph.add_edge(src_node, dest_node)
                attachment_preference.append(src_node)
                attachment_preference.append(dest_node)

                if graph.degree[src_node] == clique_degree:
                    eligible_nodes.remove(src_node)
                if graph.degree[dest_node] == clique_degree and dest_node in eligible_nodes:
                    eligible_nodes.remove(dest_node)

        elif p <= a_probability < (p + q) and m <= graph.size() < clique_size:
            eligible_nodes = [
                node
                for node, degree_value in graph.degree
                if 0 < degree_value < clique_degree
            ]
            for _ in range(m):
                node = rng.choice(eligible_nodes)
                nbr_nodes = list(graph[node])
                src_node = rng.choice(nbr_nodes)
                nbr_nodes.append(node)
                dest_node = rng.choice(
                    [
                        candidate
                        for candidate in attachment_preference
                        if candidate not in nbr_nodes
                    ]
                )
                graph.remove_edge(node, src_node)
                graph.add_edge(node, dest_node)
                attachment_preference.remove(src_node)
                attachment_preference.append(dest_node)

                if graph.degree[src_node] == 0 and src_node in eligible_nodes:
                    eligible_nodes.remove(src_node)
                if dest_node in eligible_nodes:
                    if graph.degree[dest_node] == clique_degree:
                        eligible_nodes.remove(dest_node)
                elif graph.degree[dest_node] == 1:
                    eligible_nodes.append(dest_node)

        else:
            targets = random_subset(attachment_preference, m)
            graph.add_edges_from(zip([new_node] * m, targets))
            attachment_preference.extend(targets)
            attachment_preference.extend([new_node] * (m + 1))
            new_node += 1

    return graph


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
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    sequence = random_powerlaw_tree_sequence(n, gamma=gamma, seed=seed, tries=tries)
    return degree_sequence_tree(sequence, create_using=graph)


def random_powerlaw_tree_sequence(n, gamma=3, seed=None, tries=100):
    """Return a degree sequence suitable for a random power-law tree."""
    rng = _generator_random_state(seed)
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
    import bisect

    from franken_networkx import _fnx

    if kernel is None and create_using is None:
        return _fnx.gn_graph(n, seed=seed, create_using=None)

    graph = _checked_directed_create_using(create_using, default=DiGraph)
    if kernel is None and n != 0:
        return _copy_graph_into(_fnx.gn_graph(n, seed=seed, create_using=None), graph)

    if kernel is None:

        def kernel(x):
            return x

    rng = _generator_random_state(seed)
    graph = empty_graph(1, create_using=graph, default=DiGraph)
    if n == 1:
        return graph

    graph.add_edge(1, 0)
    degree_sequence = [1, 1]

    for source in range(2, n):
        cumulative = [0.0]
        total = 0.0
        for degree in degree_sequence:
            total += kernel(degree)
            cumulative.append(total)
        cumulative = [value / total for value in cumulative]
        target = bisect.bisect_left(cumulative, rng.random()) - 1
        graph.add_edge(source, target)
        degree_sequence.append(1)
        degree_sequence[target] += 1
    return graph


def LCF_graph(n, shift_list, repeats, create_using=None):
    """Return the cubic Hamiltonian graph defined by Lederberg-Coxeter-Fruchte."""
    if n <= 0:
        return empty_graph(0, create_using)

    graph = cycle_graph(n, create_using=create_using)
    if graph.is_directed():
        raise NetworkXError("Directed Graph not supported")
    graph.graph["name"] = "LCF_graph"
    nodes = sorted(graph)

    n_extra_edges = repeats * len(shift_list)
    if n_extra_edges < 1:
        return graph

    for i in range(n_extra_edges):
        shift = shift_list[i % len(shift_list)]
        v1 = nodes[i % n]
        v2 = nodes[(i + shift) % n]
        graph.add_edge(v1, v2)
    return graph


def _lfr_zipf_rv(alpha, xmin, rng):
    if xmin < 1:
        raise ValueError("xmin < 1")
    if alpha <= 1:
        raise ValueError("a <= 1.0")
    alpha_minus_one = alpha - 1.0
    base = 2**alpha_minus_one
    while True:
        u = 1.0 - rng.random()
        v = rng.random()
        value = int(xmin * u ** -(1.0 / alpha_minus_one))
        threshold = (1.0 + (1.0 / value)) ** alpha_minus_one
        if v * value * (threshold - 1.0) / (base - 1.0) <= threshold / base:
            return value


def _lfr_zipf_rv_below(gamma, xmin, threshold, rng):
    value = _lfr_zipf_rv(gamma, xmin, rng)
    while value > threshold:
        value = _lfr_zipf_rv(gamma, xmin, rng)
    return value


def _lfr_powerlaw_sequence(gamma, low, high, condition, length, max_iters, rng):
    for _ in range(max_iters):
        sequence = []
        while not length(sequence):
            sequence.append(_lfr_zipf_rv_below(gamma, low, high, rng))
        if condition(sequence):
            return sequence
    raise NetworkXError("Could not create power law sequence")


def _lfr_hurwitz_zeta(x, q, tolerance):
    total = 0
    previous = -float("inf")
    k = 0
    while abs(total - previous) > tolerance:
        previous = total
        total += 1 / ((k + q) ** x)
        k += 1
    return total


def _lfr_generate_min_degree(gamma, average_degree, max_degree, tolerance, max_iters):
    try:
        from scipy.special import zeta
    except ImportError:

        def zeta(x, q):
            return _lfr_hurwitz_zeta(x, q, tolerance)

    min_degree_top = max_degree
    min_degree_bottom = 1
    min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
    iterations = 0
    mid_average_degree = 0
    while abs(mid_average_degree - average_degree) > tolerance:
        if iterations > max_iters:
            raise NetworkXError("Could not match average_degree")
        mid_average_degree = 0
        for x in range(int(min_degree_mid), max_degree + 1):
            mid_average_degree += (x ** (-gamma + 1)) / zeta(gamma, min_degree_mid)
        if mid_average_degree > average_degree:
            min_degree_top = min_degree_mid
            min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
        else:
            min_degree_bottom = min_degree_mid
            min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
        iterations += 1
    return round(min_degree_mid)


def _lfr_generate_communities(degree_sequence, community_sizes, mu, max_iters, rng):
    result = [set() for _ in community_sizes]
    free = list(range(len(degree_sequence)))
    for _ in range(max_iters):
        node = free.pop()
        community_index = rng.choice(range(len(community_sizes)))
        internal_degree = round(degree_sequence[node] * (1 - mu))
        if internal_degree < community_sizes[community_index]:
            result[community_index].add(node)
        else:
            free.append(node)
        if len(result[community_index]) > community_sizes[community_index]:
            free.append(result[community_index].pop())
        if not free:
            return result
    raise NetworkXError("Could not assign communities; try increasing min_community")


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
    if not tau1 > 1:
        raise NetworkXError("tau1 must be greater than one")
    if not tau2 > 1:
        raise NetworkXError("tau2 must be greater than one")
    if not 0 <= mu <= 1:
        raise NetworkXError("mu must be in the interval [0, 1]")

    if max_degree is None:
        max_degree = n
    elif not 0 < max_degree <= n:
        raise NetworkXError("max_degree must be in the interval (0, n]")
    if not ((min_degree is None) ^ (average_degree is None)):
        raise NetworkXError(
            "Must assign exactly one of min_degree and average_degree",
        )

    rng = _generator_random_state(seed)
    if min_degree is None:
        min_degree = _lfr_generate_min_degree(
            tau1,
            average_degree,
            max_degree,
            tol,
            max_iters,
        )

    degree_sequence = _lfr_powerlaw_sequence(
        tau1,
        min_degree,
        max_degree,
        lambda sequence: sum(sequence) % 2 == 0,
        lambda sequence: len(sequence) >= n,
        max_iters,
        rng,
    )

    if min_community is None:
        min_community = min(degree_sequence)
    if max_community is None:
        max_community = max(degree_sequence)

    community_sizes = _lfr_powerlaw_sequence(
        tau2,
        min_community,
        max_community,
        lambda sequence: sum(sequence) == n,
        lambda sequence: sum(sequence) >= n,
        max_iters,
        rng,
    )
    communities = _lfr_generate_communities(
        degree_sequence,
        community_sizes,
        mu,
        max_iters * 10 * n,
        rng,
    )

    graph = Graph()
    graph.add_nodes_from(range(n))
    for community in communities:
        community_nodes = list(community)
        for node in community:
            while graph.degree[node] < round(degree_sequence[node] * (1 - mu)):
                graph.add_edge(node, rng.choice(community_nodes))
            while graph.degree[node] < degree_sequence[node]:
                target = rng.choice(range(n))
                if target not in community:
                    graph.add_edge(node, target)
            graph.nodes[node]["community"] = community
    return graph


def hexagonal_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a hexagonal lattice graph."""
    graph = empty_graph(0, create_using)
    if m == 0 or n == 0:
        return graph
    if periodic and (n % 2 == 1 or m < 2 or n < 2):
        raise NetworkXError(
            "periodic hexagonal lattice needs m > 1, n > 1 and even n"
        )

    height = 2 * m
    rows = range(height + 2)
    cols = range(n + 1)

    col_edges = (
        ((i, j), (i, j + 1))
        for i in cols
        for j in rows[: height + 1]
    )
    row_edges = (
        ((i, j), (i + 1, j))
        for i in cols[:n]
        for j in rows
        if i % 2 == j % 2
    )
    graph.add_edges_from(col_edges)
    graph.add_edges_from(row_edges)
    graph.remove_node((0, height + 1))
    graph.remove_node((n, (height + 1) * (n % 2)))

    if periodic:
        for i in cols[:n]:
            graph = contracted_nodes(graph, (i, 0), (i, height), copy=True)
        for i in cols[1:]:
            graph = contracted_nodes(graph, (i, 1), (i, height + 1), copy=True)
        for j in rows[1:height]:
            graph = contracted_nodes(graph, (0, j), (n, j), copy=True)
        graph.remove_node((n, height))

    if with_positions:
        sqrt3_over_2 = math.sqrt(3) / 2
        positions = {}
        for i in cols:
            for j in rows:
                if (i, j) not in graph:
                    continue
                x = 0.5 + i + i // 2 + (j % 2) * ((i % 2) - 0.5)
                if periodic:
                    y = sqrt3_over_2 * j + 0.01 * i * i
                else:
                    y = sqrt3_over_2 * j
                positions[(i, j)] = (x, y)
        set_node_attributes(graph, positions, "pos")
    return graph


def triangular_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a triangular lattice graph."""
    graph = empty_graph(0, create_using)
    if n == 0 or m == 0:
        return graph
    if periodic and (n < 5 or m < 3):
        raise NetworkXError(f"m > 2 and n > 4 required for periodic. m={m}, n={n}")

    width = (n + 1) // 2
    rows = range(m + 1)
    cols = range(width + 1)

    graph.add_edges_from(((i, j), (i + 1, j)) for j in rows for i in cols[:width])
    graph.add_edges_from(((i, j), (i, j + 1)) for j in rows[:m] for i in cols)
    graph.add_edges_from(
        ((i, j), (i + 1, j + 1))
        for j in rows[1:m:2]
        for i in cols[:width]
    )
    graph.add_edges_from(
        ((i + 1, j), (i, j + 1))
        for j in rows[:m:2]
        for i in cols[:width]
    )

    if periodic:
        for i in cols:
            graph = contracted_nodes(graph, (i, 0), (i, m), copy=True)
        for j in rows[:m]:
            graph = contracted_nodes(graph, (0, j), (width, j), copy=True)
    elif n % 2:
        graph.remove_nodes_from((width, j) for j in rows[1::2])

    if with_positions:
        sqrt3_over_2 = math.sqrt(3) / 2
        positions = {}
        for i in cols:
            for j in rows:
                if (i, j) not in graph:
                    continue
                x = 0.5 * (j % 2) + i
                if periodic:
                    y = sqrt3_over_2 * j + 0.01 * i * i
                else:
                    y = sqrt3_over_2 * j
                positions[(i, j)] = (x, y)
        set_node_attributes(graph, positions, "pos")
    return graph


def grid_graph(dim, periodic=False):
    """Return an n-dimensional grid graph.

    The dimension n is the length of `dim` and the size in each dimension
    is the value of the corresponding list element.
    """
    if not dim:
        return Graph()

    dimensions = list(dim)
    periodic_flags = (
        iter(periodic) if isinstance(periodic, Iterable) else itertools.repeat(periodic)
    )

    axes = []
    periods = []
    for axis in dimensions:
        periods.append(bool(next(periodic_flags)))
        if isinstance(axis, numbers.Integral):
            axes.append(list(range(axis)))
        else:
            axes.append(list(axis))

    graph = Graph()
    output_axes = list(reversed(axes))
    if not output_axes or any(len(axis) == 0 for axis in output_axes):
        return graph

    index_axes = [range(len(axis)) for axis in output_axes]

    def make_node(positions):
        values = [
            output_axes[index][position]
            for index, position in enumerate(positions)
        ]
        return values[0] if len(values) == 1 else tuple(values)

    for positions in itertools.product(*index_axes):
        graph.add_node(make_node(positions))

    for positions in itertools.product(*index_axes):
        left = make_node(positions)
        for output_index, axis in enumerate(output_axes):
            axis_pos = positions[output_index]
            right_positions = list(positions)
            if axis_pos + 1 < len(axis):
                right_positions[output_index] = axis_pos + 1
            elif periods[len(output_axes) - 1 - output_index]:
                if len(axis) == 1:
                    graph.add_edge(left, left)
                    continue
                if len(axis) == 2:
                    continue
                right_positions[output_index] = 0
            else:
                continue
            graph.add_edge(left, make_node(right_positions))

    return graph


def lattice_reference(G, niter=5, D=None, connectivity=True, seed=None):
    """Return a lattice-like rewiring of *G* preserving degree sequence."""
    import bisect
    import math

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if G.number_of_edges() < 2:
        raise NetworkXError("Graph has fewer that 2 edges")

    def cumulative_distribution(distribution):
        cdf = [0.0]
        cumulative = 0.0
        for element in distribution:
            cumulative += element
            cdf.append(cumulative)
        return [element / cumulative for element in cdf]

    def discrete_sequence(count, cdistribution, rng):
        return [
            bisect.bisect_left(cdistribution, rng.random()) - 1
            for _ in range(count)
        ]

    def matrix_value(matrix, row, col):
        try:
            return matrix[row, col]
        except (TypeError, KeyError):
            return matrix[row][col]

    def has_path(graph, source, target):
        if source == target:
            return True
        seen = {source}
        queue = [source]
        index = 0
        while index < len(queue):
            node = queue[index]
            index += 1
            for neighbor in graph[node]:
                if neighbor == target:
                    return True
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return False

    graph = Graph()
    graph.graph.update(dict(G.graph))
    graph.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
    graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in G.edges(data=True))
    rng = _generator_random_state(seed)
    keys, degrees = zip(*graph.degree)
    cdf = cumulative_distribution(degrees)

    node_count = len(graph)
    edge_count = graph.number_of_edges()
    if D is None:
        distance = [[0 for _ in range(node_count)] for _ in range(node_count)]
        lower = list(range(1, node_count))
        upper = list(range(node_count - 1, 0, -1))
        wrapped = [0] + [min(left, right) for left, right in zip(lower, upper)]
        for v in range(math.ceil(node_count / 2)):
            row = wrapped[v + 1 :] + wrapped[: v + 1]
            distance[node_count - v - 1] = row
            distance[v] = list(reversed(row))
    else:
        distance = D

    total_iterations = niter * edge_count
    max_attempts = int(node_count * edge_count / (node_count * (node_count - 1) / 2))

    for _ in range(total_iterations):
        attempts = 0
        while attempts < max_attempts:
            ai, ci = discrete_sequence(2, cdf, rng)
            if ai == ci:
                continue
            a = keys[ai]
            c = keys[ci]
            b = rng.choice(list(graph.neighbors(a)))
            d = rng.choice(list(graph.neighbors(c)))
            bi = keys.index(b)
            di = keys.index(d)

            if b in [a, c, d] or d in [a, b, c]:
                continue

            if d not in graph[a] and b not in graph[c]:
                if (
                    matrix_value(distance, ai, bi) + matrix_value(distance, ci, di)
                    >= matrix_value(distance, ai, ci) + matrix_value(distance, bi, di)
                ):
                    graph.add_edge(a, d)
                    graph.add_edge(c, b)
                    graph.remove_edge(a, b)
                    graph.remove_edge(c, d)

                    if connectivity and not has_path(graph, a, b):
                        graph.remove_edge(a, d)
                        graph.remove_edge(c, b)
                        graph.add_edge(a, b)
                        graph.add_edge(c, d)
                    else:
                        break
            attempts += 1

    return graph


def margulis_gabber_galil_graph(n, create_using=None):
    """Return a Margulis-Gabber-Galil expander graph."""
    graph = empty_graph(0, create_using, default=MultiGraph)
    if graph.is_directed() or not graph.is_multigraph():
        raise NetworkXError("`create_using` must be an undirected multigraph.")

    for x, y in itertools.product(range(n), repeat=2):
        for u, v in (
            ((x + 2 * y) % n, y),
            ((x + (2 * y + 1)) % n, y),
            (x, (y + 2 * x) % n),
            (x, (y + (2 * x + 1)) % n),
        ):
            graph.add_edge((x, y), (u, v))
    graph.graph["name"] = f"margulis_gabber_galil_graph({n})"
    return graph


def sudoku_graph(n=3):
    """Return the Sudoku constraint graph of order *n*.

    The n-Sudoku graph has n^4 vertices (cells of an n^2 × n^2 grid).
    Two cells are adjacent iff they share a row, column, or n×n box.
    """
    return _rust_sudoku_graph(n)


def fast_gnp_random_graph(n, p, seed=None, directed=False, create_using=None):
    """Return a fast G(n,p) random graph (Batagelj-Brandes O(n+m) algorithm)."""
    from franken_networkx._fnx import fast_gnp_random_graph as _rust_fast_gnp

    if create_using is None:
        return _rust_fast_gnp(
            n,
            p,
            seed=_native_random_seed(seed),
            directed=directed,
        )

    rng = _generator_random_state(seed)
    default = DiGraph if directed else Graph
    graph = _checked_create_using(
        create_using,
        directed=directed,
        multigraph=False,
        default=default,
    )
    if p <= 0 or p >= 1:
        return gnp_random_graph(
            n,
            p,
            seed=rng,
            directed=directed,
            create_using=graph,
        )

    graph = empty_graph(n, create_using=graph, default=default)
    lp = math.log(1.0 - p)

    if directed:
        v = 1
        w = -1
        while v < n:
            lr = math.log(1.0 - rng.random())
            w = w + 1 + int(lr / lp)
            while w >= v and v < n:
                w = w - v
                v += 1
            if v < n:
                graph.add_edge(w, v)

    v = 1
    w = -1
    while v < n:
        lr = math.log(1.0 - rng.random())
        w = w + 1 + int(lr / lp)
        while w >= v and v < n:
            w = w - v
            v += 1
        if v < n:
            graph.add_edge(v, w)
    return graph


def newman_watts_strogatz_graph(n, k, p, seed=None, create_using=None):
    """Return a Newman-Watts-Strogatz small-world graph."""
    graph = _rust_newman_watts_strogatz_graph(
        n, k, p, seed=_native_random_seed(seed)
    )
    if create_using is None:
        return graph
    return _copy_graph_into(
        graph,
        _checked_create_using(
            create_using,
            directed=False,
            multigraph=False,
            default=Graph,
        ),
    )


def connected_watts_strogatz_graph(n, k, p, tries=100, seed=None, create_using=None):
    """Return a connected Watts-Strogatz small-world graph."""
    graph = _rust_connected_watts_strogatz_graph(
        n,
        k,
        p,
        tries=tries,
        seed=_native_random_seed(seed),
    )
    if create_using is None:
        return graph
    return _copy_graph_into(
        graph,
        _checked_create_using(
            create_using,
            directed=False,
            multigraph=False,
            default=Graph,
        ),
    )


def random_regular_graph(d, n, seed=None, create_using=None):
    """Return a random d-regular graph."""
    if create_using is None:
        return _rust_random_regular_graph(d, n, seed=_native_random_seed(seed))

    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    if (n * d) % 2 != 0:
        raise NetworkXError("n * d must be even")
    if not 0 <= d < n:
        raise NetworkXError("the 0 <= d < n inequality must be satisfied")

    graph = empty_graph(n, create_using=graph)
    if d == 0:
        return graph

    def _suitable(edges, potential_edges):
        if not potential_edges:
            return True
        for s1 in potential_edges:
            for s2 in potential_edges:
                if s1 == s2:
                    break
                if s1 > s2:
                    s1, s2 = s2, s1
                if (s1, s2) not in edges:
                    return True
        return False

    def _try_creation():
        edges = set()
        stubs = list(range(n)) * d

        while stubs:
            potential_edges = defaultdict(lambda: 0)
            rng.shuffle(stubs)
            stubiter = iter(stubs)
            for s1, s2 in zip(stubiter, stubiter):
                if s1 > s2:
                    s1, s2 = s2, s1
                if s1 != s2 and (s1, s2) not in edges:
                    edges.add((s1, s2))
                else:
                    potential_edges[s1] += 1
                    potential_edges[s2] += 1

            if not _suitable(edges, potential_edges):
                return None

            return_stubs = []
            for node, potential in potential_edges.items():
                return_stubs.extend([node] * potential)
            stubs[:] = return_stubs

        return edges

    edges = _try_creation()
    while edges is None:
        edges = _try_creation()
    graph.add_edges_from(edges)
    return graph


def powerlaw_cluster_graph(n, m, p, seed=None, create_using=None):
    """Return a powerlaw-cluster graph."""
    graph = _rust_powerlaw_cluster_graph(n, m, p, seed=_native_random_seed(seed))
    if create_using is None:
        return graph
    return _copy_graph_into(
        graph,
        _checked_create_using(
            create_using,
            directed=False,
            multigraph=False,
            default=Graph,
        ),
    )


def directed_configuration_model(
    in_degree_sequence,
    out_degree_sequence,
    create_using=None,
    seed=None,
):
    """Return a directed configuration model graph."""
    if sum(in_degree_sequence) != sum(out_degree_sequence):
        raise NetworkXError("Invalid degree sequences: sequences must have equal sums")

    graph = _empty_graph_from_create_using(
        create_using,
        default=MultiDiGraph,
    )
    return _configuration_model_local(
        out_degree_sequence,
        graph,
        directed=True,
        in_degree_sequence=in_degree_sequence,
        seed=seed,
    )


def directed_joint_degree_graph(in_degrees, out_degrees, nkk, seed=None):
    """Return a directed graph matching a directed joint-degree distribution."""
    if not is_valid_directed_joint_degree(in_degrees, out_degrees, nkk):
        raise NetworkXError("Input is not realizable as a simple graph")

    graph = DiGraph()
    degree_nodes_in = {}
    degree_nodes_out = {}
    degree_nodes_in_unsat = {}
    degree_nodes_out_unsat = {}
    residual_out = {}
    residual_in = {}
    partition_out = {}
    partition_in = {}
    non_chords = {}

    for idx, in_degree in enumerate(in_degrees):
        idx = int(idx)
        if in_degree > 0:
            degree_nodes_in.setdefault(in_degree, [])
            degree_nodes_in_unsat.setdefault(in_degree, set())
            degree_nodes_in[in_degree].append(idx)
            degree_nodes_in_unsat[in_degree].add(idx)
            residual_in[idx] = in_degree
            partition_in[idx] = in_degree

    for idx, out_degree in enumerate(out_degrees):
        non_chords[(out_degree, in_degrees[idx])] = (
            non_chords.get((out_degree, in_degrees[idx]), 0) + 1
        )
        idx = int(idx)
        if out_degree > 0:
            degree_nodes_out.setdefault(out_degree, [])
            degree_nodes_out_unsat.setdefault(out_degree, set())
            degree_nodes_out[out_degree].append(idx)
            degree_nodes_out_unsat[out_degree].add(idx)
            residual_out[idx] = out_degree
            partition_out[idx] = out_degree
        graph.add_node(idx)

    count_in = {degree: len(nodes) for degree, nodes in degree_nodes_in.items()}
    count_out = {degree: len(nodes) for degree, nodes in degree_nodes_out.items()}
    rng = _generator_random_state(seed)

    for out_degree in nkk:
        for in_degree in nkk[out_degree]:
            edges_to_add = nkk[out_degree][in_degree]
            if edges_to_add <= 0:
                continue

            chords = set()
            out_count = count_out[out_degree]
            in_count = count_in[in_degree]
            sample = rng.sample(
                range(out_count * in_count),
                edges_to_add + non_chords.get((out_degree, in_degree), 0),
            )

            sample_index = 0
            while len(chords) < edges_to_add:
                source = degree_nodes_out[out_degree][sample[sample_index] % out_count]
                target = degree_nodes_in[in_degree][sample[sample_index] // out_count]
                sample_index += 1
                if source != target:
                    chords.add((source, target))

            out_unsat = degree_nodes_out_unsat[out_degree]
            in_unsat = degree_nodes_in_unsat[in_degree]

            while edges_to_add > 0:
                source, target = chords.pop()
                chords.add((source, target))

                if residual_out[source] == 0:
                    switched = _directed_neighbor_switch_local(
                        graph,
                        source,
                        out_unsat,
                        residual_out,
                        chords,
                        partition_in,
                        in_degree,
                    )
                    if switched is not None:
                        source = switched

                if residual_in[target] == 0:
                    switched = _directed_neighbor_switch_rev_local(
                        graph,
                        target,
                        in_unsat,
                        residual_in,
                        chords,
                        partition_out,
                        out_degree,
                    )
                    if switched is not None:
                        target = switched

                graph.add_edge(source, target)
                residual_out[source] -= 1
                residual_in[target] -= 1
                edges_to_add -= 1
                chords.discard((source, target))

                if residual_out[source] == 0:
                    out_unsat.discard(source)
                if residual_in[target] == 0:
                    in_unsat.discard(target)

    return graph


def joint_degree_graph(joint_degrees, seed=None):
    """Return an undirected graph matching a joint-degree distribution."""
    if not is_valid_joint_degree(joint_degrees):
        raise NetworkXError("Input joint degree dict not realizable as a simple graph")

    degree_count = {
        degree: sum(edges.values()) // degree
        for degree, edges in joint_degrees.items()
        if degree > 0
    }
    graph = empty_graph(sum(degree_count.values()))

    degree_nodes = {}
    residual = {}
    node_id = 0
    for degree, num_nodes in degree_count.items():
        degree_nodes[degree] = range(node_id, node_id + num_nodes)
        for node in degree_nodes[degree]:
            residual[node] = degree
        node_id += int(num_nodes)

    rng = _generator_random_state(seed)
    for degree_left in joint_degrees:
        for degree_right in joint_degrees[degree_left]:
            edges_to_add = joint_degrees[degree_left][degree_right]
            if edges_to_add <= 0 or degree_left < degree_right:
                continue

            left_count = degree_count[degree_left]
            right_count = degree_count[degree_right]
            left_nodes = degree_nodes[degree_left]
            right_nodes = degree_nodes[degree_right]
            left_unsat = {node for node in left_nodes if residual[node] > 0}

            if degree_left != degree_right:
                right_unsat = {node for node in right_nodes if residual[node] > 0}
            else:
                right_unsat = left_unsat
                edges_to_add = joint_degrees[degree_left][degree_right] // 2

            while edges_to_add > 0:
                source = left_nodes[rng.randrange(left_count)]
                target = right_nodes[rng.randrange(right_count)]

                if graph.has_edge(source, target) or source == target:
                    continue

                if residual[source] == 0:
                    _neighbor_switch_local(graph, source, left_unsat, residual)
                if residual[target] == 0:
                    if degree_left != degree_right:
                        _neighbor_switch_local(graph, target, right_unsat, residual)
                    else:
                        _neighbor_switch_local(
                            graph,
                            target,
                            right_unsat,
                            residual,
                            avoid_node_id=source,
                        )

                graph.add_edge(source, target)
                residual[source] -= 1
                residual[target] -= 1
                edges_to_add -= 1

                if residual[source] == 0:
                    left_unsat.discard(source)
                if residual[target] == 0:
                    right_unsat.discard(target)

    return graph


def expected_degree_graph(w, seed=None, selfloops=True):
    """Return a Chung-Lu expected-degree random graph."""
    n = len(w)
    graph = empty_graph(n)
    if n == 0 or max(w) == 0:
        return graph

    rng = _generator_random_state(seed)
    rho = 1 / sum(w)
    order = sorted(enumerate(w), key=lambda item: item[1], reverse=True)
    mapping = {canonical: node for canonical, (node, _) in enumerate(order)}
    sequence = [weight for _, weight in order]
    last = n if selfloops else n - 1
    for source in range(last):
        target = source if selfloops else source + 1
        factor = sequence[source] * rho
        probability = min(sequence[target] * factor, 1)
        while target < n and probability > 0:
            if probability != 1:
                target += math.floor(math.log(rng.random(), 1 - probability))
            if target < n:
                next_probability = min(sequence[target] * factor, 1)
                if rng.random() < next_probability / probability:
                    graph.add_edge(mapping[source], mapping[target])
                target += 1
                probability = next_probability
    return graph


def directed_havel_hakimi_graph(in_deg_sequence, out_deg_sequence, create_using=None):
    """Return a directed graph with prescribed in/out degree sequences."""
    try:
        in_deg_sequence = [int(degree) for degree in in_deg_sequence]
        out_deg_sequence = [int(degree) for degree in out_deg_sequence]
    except (TypeError, ValueError):
        raise NetworkXError("Invalid degree sequences. Sequence values must be positive.")

    sumin = 0
    sumout = 0
    nin = len(in_deg_sequence)
    nout = len(out_deg_sequence)
    maxn = max(nin, nout)
    graph = _empty_graph_from_create_using(create_using, default=DiGraph)
    graph.add_nodes_from(range(maxn))
    if maxn == 0:
        return graph

    maxin = 0
    stubheap = []
    zeroheap = []
    for node in range(maxn):
        out_degree = out_deg_sequence[node] if node < nout else 0
        in_degree = in_deg_sequence[node] if node < nin else 0
        if in_degree < 0 or out_degree < 0:
            raise NetworkXError(
                "Invalid degree sequences. Sequence values must be positive."
            )
        sumin += in_degree
        sumout += out_degree
        maxin = max(maxin, in_degree)
        if in_degree > 0:
            heappush(stubheap, (-out_degree, -in_degree, node))
        elif out_degree > 0:
            heappush(zeroheap, (-out_degree, node))
    if sumin != sumout:
        raise NetworkXError("Invalid degree sequences. Sequences must have equal sums.")

    modified = [(0, 0, 0)] * (maxin + 1)
    while stubheap:
        freeout, freein, target = heappop(stubheap)
        freein *= -1
        if freein > len(stubheap) + len(zeroheap):
            raise NetworkXError("Non-digraphical integer sequence")

        modified_len = 0
        for _ in range(freein):
            if zeroheap and (not stubheap or stubheap[0][0] > zeroheap[0][0]):
                stubout, source = heappop(zeroheap)
                stubin = 0
            else:
                stubout, stubin, source = heappop(stubheap)
            if stubout == 0:
                raise NetworkXError("Non-digraphical integer sequence")
            graph.add_edge(source, target)
            if stubout + 1 < 0 or stubin < 0:
                modified[modified_len] = (stubout + 1, stubin, source)
                modified_len += 1

        for i in range(modified_len):
            stub = modified[i]
            if stub[1] < 0:
                heappush(stubheap, stub)
            else:
                heappush(zeroheap, (stub[0], stub[2]))
        if freeout < 0:
            heappush(zeroheap, (freeout, target))

    return graph


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
    # Community extras
    # exported earlier to preserve stable __all__ ordering
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
    # exported earlier to preserve stable __all__ ordering
    # Lattice graphs
    # exported earlier to preserve stable __all__ ordering
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
