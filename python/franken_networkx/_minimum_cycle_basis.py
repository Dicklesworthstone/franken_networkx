"""Exact de Pina cycle bases over an indexed double cover.

The public contract is specified in EXISTING_NETWORKX_STRUCTURE.md, section
25. Python arithmetic preserves exact numeric weights and reachable paths at
infinite distance. Native/SciPy acceleration is optional and restricted to
domains where it preserves arithmetic and observable basis ordering.
"""

from networkx.exception import NetworkXNoPath


class _MinimumCycleBasisLift:
    """Indexed adjacency consumed by the shared exact Python Dijkstra solvers."""

    __slots__ = ("_adj",)

    def __init__(self, adjacency):
        self._adj = adjacency

    def __contains__(self, node):
        return 0 <= node < len(self._adj)

    def is_directed(self):
        return False


def _minimum_cycle_basis_float_exact(edges, node_count):
    # Each lifted simple path has fewer than 2*n edges. The bidirectional
    # search also compares sums of two such paths. Keep all those integer
    # additions exact, not merely the individual edge conversions.
    limit = (1 << 53) // max(1, 4 * node_count)
    return all(
        type(cost) in (int, bool) and 0 <= cost <= limit
        for _, _, cost in edges
    )


def _minimum_cycle_basis_scipy_start(lifted, node_count):
    """Optionally accelerate exact integral distances with bounded-size batches."""
    try:
        import numpy as np
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import dijkstra
    except ImportError:
        return None

    rows, columns, weights = [], [], []
    for source, neighbors in enumerate(lifted._adj):
        for target, cost in neighbors.items():
            rows.append(source)
            columns.append(target)
            weights.append(cost)
    matrix = csr_matrix(
        (np.asarray(weights, dtype=float), (rows, columns)),
        shape=(2 * node_count, 2 * node_count),
    )
    best_start = best_distance = None
    # Only n distances from the n-by-2n result are needed. Batching bounds
    # temporary storage by O(n), rather than materializing the full matrix.
    for first in range(0, node_count, 64):
        sources = np.arange(first, min(first + 64, node_count))
        distances = dijkstra(matrix, directed=False, indices=sources)
        for offset, source in enumerate(sources):
            distance = distances[offset, source + node_count]
            if best_start is None or distance < best_distance:
                best_start, best_distance = int(source), distance
    return best_start


def _minimum_cycle_basis_orthogonal_cycle(nodes, edges, orth, float_exact):
    from franken_networkx import (
        _bidirectional_dijkstra_local,
        _dijkstra_multisource_inproc,
    )

    n = len(nodes)
    index = {node: position for position, node in enumerate(nodes)}
    adjacency = [{} for _ in range(2 * n)]
    for u, v, cost in edges:
        left, right = index[u], index[v]
        if (u, v) in orth or (v, u) in orth:
            pairs = ((left, right + n), (left + n, right))
        else:
            pairs = ((left, right), (left + n, right + n))
        for source, target in pairs:
            adjacency[source][target] = cost
            adjacency[target][source] = cost

    # Both sheets use integer IDs, so an input node such as (u, 1) cannot
    # accidentally become the lifted copy of another input node u.
    lifted = _MinimumCycleBasisLift(adjacency)

    def edge_weight(_u, _v, cost):
        return cost

    start = _minimum_cycle_basis_scipy_start(lifted, n) if float_exact else None
    if start is None:
        best_distance = None
        for source in range(n):
            target = source + n
            distances = _dijkstra_multisource_inproc(
                lifted, [source], edge_weight, target=target
            )
            if target not in distances:
                raise NetworkXNoPath(
                    f"Node {(nodes[source], 1)} not reachable from {nodes[source]}"
                )
            distance = distances[target]
            # Infinity is a reachable distance when finite floats overflow.
            if start is None or distance < best_distance:
                start, best_distance = source, distance

    _, lifted_path = _bidirectional_dijkstra_local(
        lifted, start, start + n, edge_weight
    )
    path = [nodes[node % n] for node in lifted_path]
    edgelist = list(zip(path, path[1:]))
    edgeset = set()
    for edge in edgelist:
        if edge in edgeset:
            edgeset.remove(edge)
        elif edge[::-1] in edgeset:
            edgeset.remove(edge[::-1])
        else:
            edgeset.add(edge)

    min_edgelist = []
    for edge in edgelist:
        if edge in edgeset:
            min_edgelist.append(edge)
            edgeset.remove(edge)
        elif edge[::-1] in edgeset:
            min_edgelist.append(edge[::-1])
            edgeset.remove(edge[::-1])
    return min_edgelist


def _minimum_cycle_basis_component(component_graph, weight):
    """Owned de Pina basis construction with NetworkX's chord/set order."""
    from franken_networkx import (
        Graph,
        _kruskal_spanning_edges_inproc,
        _raw_minimum_cycle_basis,
    )

    cb = []
    tree_edges = list(
        _kruskal_spanning_edges_inproc(component_graph, weight=None, data=False)
    )
    chords = component_graph.edges - tree_edges - {(v, u) for u, v in tree_edges}
    if not chords:
        return cb

    nodes = list(component_graph)
    # Read live dictionaries explicitly: filtered edge views need not support
    # projecting arbitrary attribute keys. NetworkX uses even a literal None
    # key here because its lifted paths always select internal "Gi_weight".
    if weight is False:
        edges = list(component_graph.edges)
    elif weight is True:
        edges = list(component_graph.edges(data=True))
    else:
        edges = [
            (u, v, data[weight] if weight in data else 1)
            for u, v, data in component_graph.edges(data=True)
        ]
    float_exact = _minimum_cycle_basis_float_exact(edges, len(nodes))
    if (
        len(chords) == 1
        and float_exact
        and _raw_minimum_cycle_basis is not None
        and all(type(node) in (int, str) for node in nodes)
        and all(None not in data for _, _, data in component_graph.edges(data=True))
    ):
        # The general raw kernel exposes a different Python chord-set order.
        # A unicyclic component has one chord, eliminating that ambiguity.
        # Build from the logical rows so views and escaped attributes remain
        # authoritative; only the selected exact weights enter native storage.
        native_graph = Graph()
        native_graph.add_nodes_from(nodes)
        native_graph.add_edges_from(
            (u, v, {"weight": cost}) for u, v, cost in edges
        )
        return _raw_minimum_cycle_basis(native_graph, weight="weight")

    set_orth = [{edge} for edge in chords]
    while set_orth:
        base = set_orth.pop()
        cycle_edges = _minimum_cycle_basis_orthogonal_cycle(
            nodes, edges, base, float_exact
        )
        cb.append([v for u, v in cycle_edges])

        set_orth = [
            (
                {e for e in orth if e not in base if e[::-1] not in base}
                | {e for e in base if e not in orth if e[::-1] not in orth}
            )
            if sum((e in orth or e[::-1] in orth) for e in cycle_edges) % 2
            else orth
            for orth in set_orth
        ]
    return cb


def minimum_cycle_basis(G, weight=None):
    """Compute an independent minimum basis for every connected component."""
    from franken_networkx import connected_components

    # The filtered component's iteration order selects tied cycles. Retain
    # that order and its live attributes instead of copying unrelated data.
    basis = []
    for component in connected_components(G):
        basis.extend(_minimum_cycle_basis_component(G.subgraph(component), weight))
    return basis
