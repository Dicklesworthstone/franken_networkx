

def _minimum_cut_value_inproc(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(flowG)
    kwargs.setdefault("backend", "networkx")
    try:
        return _nx.algorithms.flow.maxflow.minimum_cut_value(
            H, _s, _t, capacity=capacity, flow_func=flow_func, **kwargs
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def minimum_cut(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    """Return the minimum cut value and node partition.

    br-mincutsig: parameter names match nx.minimum_cut exactly so that
    kwarg-style calls (``minimum_cut(g, _s=s, _t=t)``) work on both
    libraries. Previously fnx used ``G, source, sink`` which broke
    drop-in code written against upstream.

    ``**kwargs`` is accepted for networkx parity. nx only forwards
    extra kwargs to a user-supplied ``flow_func``; with ``flow_func is
    None`` passing any kwarg is a user error, so we raise with nx's
    message instead of ``TypeError: unexpected keyword argument``.
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    flowG = _coerce_arg_to_fnx_graph(flowG)
    _validate_flow_func_selector(flow_func)
    _reject_multigraph_flow(flowG)
    _check_flow_endpoints(flowG, _s, _t)
    if kwargs and flow_func is None:
        raise NetworkXError(
            "You have to explicitly set a flow_func if you need to pass "
            "parameters via kwargs."
        )
    needs_nx = bool(flow_func is not None or kwargs)
    if not needs_nx:
        # br-r37-c1-31tby: single fused capacity scan.
        needs_nx, all_int = _flow_caps_summary(flowG, capacity)
    if needs_nx:
        return _minimum_cut_inproc(
            flowG,
            _s,
            _t,
            capacity=capacity,
            flow_func=flow_func,
            **kwargs,
        )
    _sync_rust_edge_attrs(flowG, edge_only=True)
    value, partition = _minimum_cut_raw(flowG, _s, _t, capacity=capacity)
    return _coerce_flow_value(value, all_int), partition


def minimum_cut_value(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    """Return the minimum cut value between source and sink.

    br-mincutsig: see ``minimum_cut`` — parameter names follow nx. The
    trailing ``**kwargs`` mirrors nx's contract of forwarding to
    ``flow_func`` (and raising when none is supplied).
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    flowG = _coerce_arg_to_fnx_graph(flowG)
    _validate_flow_func_selector(flow_func)
    _reject_multigraph_flow(flowG)
    _check_flow_endpoints(flowG, _s, _t)
    if kwargs and flow_func is None:
        raise NetworkXError(
            "You have to explicitly set a flow_func if you need to pass "
            "parameters via kwargs."
        )
    needs_nx = bool(flow_func is not None or kwargs)
    if not needs_nx:
        # br-r37-c1-31tby: single fused capacity scan.
        needs_nx, all_int = _flow_caps_summary(flowG, capacity)
    if needs_nx:
        return _minimum_cut_value_inproc(
            flowG,
            _s,
            _t,
            capacity=capacity,
            flow_func=flow_func,
            **kwargs,
        )
    _sync_rust_edge_attrs(flowG, edge_only=True)
    return _coerce_flow_value(
        _minimum_cut_value_raw(flowG, _s, _t, capacity=capacity),
        all_int,
    )

# Algorithm functions — distance measures
from franken_networkx._fnx import (
    center as _raw_center,
    density,
    diameter as _raw_diameter,
    eccentricity as _raw_eccentricity,
    periphery as _raw_periphery,
    radius as _raw_radius,
)


# A successful unweighted undirected eccentricity sweep already computes every
# value needed by diameter/radius/center/periphery.  NetworkX's public API makes
# callers materialize those results separately, but repeating the all-sources
# traversal four more times is not observable behavior.  Keep one immutable
# snapshot on the graph, keyed by the native topology revisions.  Public dicts
# and lists are rebuilt on every call so mutating a returned value can never
# poison a later result.
_DISTANCE_MEASURES_CACHE_ATTR = "_fnx_unweighted_distance_measures_cache_v1"
_DISTANCE_MEASURES_CACHE_SENTINEL = object()


def _distance_measures_cache_key(G):
    try:
        return (G.nodes_seq, G.edges_seq)
    except AttributeError:
        return None


def _cached_distance_measures_snapshot(G):
    key = _distance_measures_cache_key(G)
    if key is None:
        return None
    try:
        snapshot = G.__dict__.get(_DISTANCE_MEASURES_CACHE_ATTR)
    except AttributeError:
        return None
    if (
        isinstance(snapshot, tuple)
        and len(snapshot) == 8
        and snapshot[0] is _DISTANCE_MEASURES_CACHE_SENTINEL
        and snapshot[1:3] == key
    ):
        return snapshot
    return None


def _store_distance_measures_snapshot(G, eccentricities, start_key):
    # The Rust sweep releases the GIL.  Do not retain its result if another
    # thread changed the topology while it was running.
    if start_key is None or _distance_measures_cache_key(G) != start_key:
        return None
    items = tuple(eccentricities.items())
    if not items:
        return None
    diameter_value = max(value for _, value in items)
    radius_value = min(value for _, value in items)
    snapshot = (
        _DISTANCE_MEASURES_CACHE_SENTINEL,
        start_key[0],
        start_key[1],
        items,
        diameter_value,
        radius_value,
        tuple(node for node, value in items if value == radius_value),
        tuple(node for node, value in items if value == diameter_value),
    )
    G.__dict__[_DISTANCE_MEASURES_CACHE_ATTR] = snapshot
    return snapshot


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


def _tree_center_unweighted(G):
    center_candidates_degree = dict(G.degree)
    leaves = {node for node, degree in center_candidates_degree.items() if degree == 1}

    while len(center_candidates_degree) > 2 and leaves:
        new_leaves = set()
        for leaf in leaves:
            del center_candidates_degree[leaf]
            for neighbor in G.neighbors(leaf):
                if neighbor not in center_candidates_degree:
                    continue
                center_candidates_degree[neighbor] -= 1
                degree = center_candidates_degree[neighbor]
                if degree == 1:
                    new_leaves.add(neighbor)
                elif degree == 0 and len(center_candidates_degree) != 1:
                    raise NotATree("input graph is not a tree")
        leaves = new_leaves

    n = len(center_candidates_degree)
    if (n == 2 and not leaves) or n not in {1, 2}:
        raise NotATree("input graph is not a tree")

    return list(center_candidates_degree)


def diameter(G, e=None, usebounds=False, weight=None):
    """Returns the diameter of the graph G.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    e : dict, optional
        Precomputed eccentricity dict {node: eccentricity}.
    usebounds : bool, optional (default=False)
        Use bounds to speed up eccentricity computation.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.

    Returns
    -------
    int or float
        Diameter of the graph.
    """
    # br-r37-c1-eg0jk: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if e is not None:
        return max(e.values())
    if len(G) == 0:
        raise ValueError("max() iterable argument is empty")
    if weight is not None or usebounds:
        return max(eccentricity(G, weight=weight).values())
    # br-r37-c1-tcyne: the Rust _raw_diameter calls gr.undirected()
    # before computing — collapses antiparallel directions (returns
    # 2 on directed cycle5 instead of nx's 4). Stay on _raw_diameter
    # for the fast undirected path; for directed inputs, reuse the
    # fnx.eccentricity native path (already directed-aware) and take
    # the max — matches nx exactly without the fnx_to_nx round-trip.
    if G.is_directed():
        ecc = eccentricity(G)
        return max(ecc.values())
    snapshot = _cached_distance_measures_snapshot(G)
    if snapshot is not None:
        return snapshot[4]
    return _raw_diameter(G)


def radius(G, e=None, usebounds=False, weight=None):
    """Returns the radius of the graph G.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    e : dict, optional
        Precomputed eccentricity dict {node: eccentricity}.
    usebounds : bool, optional (default=False)
        Use bounds to speed up eccentricity computation.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.

    Returns
    -------
    int or float
        Radius of the graph.
    """
    # br-r37-c1-eg0jk: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if e is not None:
        return min(e.values())
    if len(G) == 0:
        raise ValueError("min() iterable argument is empty")
    if weight is not None or usebounds:
        return min(eccentricity(G, weight=weight).values())
    # br-r37-c1-tcyne: same directed-collapse defect as _raw_diameter —
    # _raw_radius runs on gr.undirected(). Use fnx.eccentricity for the
    # directed path (correct, no fnx_to_nx round-trip).
    if G.is_directed():
        ecc = eccentricity(G)
        return min(ecc.values())
    snapshot = _cached_distance_measures_snapshot(G)
    if snapshot is not None:
        return snapshot[5]
    return _raw_radius(G)


def center(G, e=None, usebounds=False, weight=None):
    """Returns the center of the graph G.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    e : dict, optional
        Precomputed eccentricity dict {node: eccentricity}.
    usebounds : bool, optional (default=False)
        Use bounds to speed up eccentricity computation.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.

    Returns
    -------
    list
        List of nodes in the center.
    """
    # br-r37-c1-eg0jk: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if e is not None:
        radius_w = min(e.values())
        return [v for v in e if e[v] == radius_w]
    if len(G) == 0:
        if weight is None and not G.is_directed():
            raise NetworkXPointlessConcept("G has no nodes.")
        raise ValueError("min() iterable argument is empty")
    if weight is not None or usebounds:
        ecc = eccentricity(G, weight=weight)
        if not ecc:
            return []
        radius_w = min(ecc.values())
        return [n for n in G.nodes() if ecc[n] == radius_w]
    # br-r37-c1-6qcaw: nx iterates the eccentricity dict (node-
    # insertion order) and filters by min eccentricity. The Rust
    # _raw_center returned nodes in a different order. Filter
    # explicitly so nodes appear in G.nodes() insertion order.
    #
    # br-r37-c1-bnzab: directed-graph case used to delegate to nx for
    # safety; fnx.eccentricity now handles directed inputs natively
    # (verified on cycle3 and 5-cycle+chord against nx 3.6.1) so we
    # can drop the delegate and stay on the native path.
    if not G.is_directed():
        snapshot = _cached_distance_measures_snapshot(G)
        if snapshot is not None:
            return list(snapshot[6])
        if is_tree(G):
            return _tree_center_unweighted(G)
    ecc = eccentricity(G)
    if not ecc:
        return []
    radius = min(ecc.values())
    return [n for n in G.nodes() if ecc[n] == radius]


def periphery(G, e=None, usebounds=False, weight=None):
    """Returns the periphery of the graph G.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    e : dict, optional
        Precomputed eccentricity dict {node: eccentricity}.
    usebounds : bool, optional (default=False)
        Use bounds to speed up eccentricity computation.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.

    Returns
    -------
    list
        List of nodes in the periphery.
    """
    # br-r37-c1-eg0jk: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if e is not None:
        diameter_w = max(e.values())
        return [v for v in e if e[v] == diameter_w]
    if len(G) == 0:
        raise ValueError("max() iterable argument is empty")
    if weight is not None or usebounds:
        ecc = eccentricity(G, weight=weight)
        if not ecc:
            return []
        diameter_w = max(ecc.values())
        return [n for n in G.nodes() if ecc[n] == diameter_w]
    # br-r37-c1-6qcaw: nx iterates the eccentricity dict (node-
    # insertion order) and filters by max eccentricity. The Rust
    # _raw_periphery returned nodes in a different order. Filter
    # explicitly so nodes appear in G.nodes() insertion order.
    #
    # br-r37-c1-bnzab: directed-graph case used to delegate to nx for
    # safety; fnx.eccentricity now handles directed inputs natively
    # so we can drop the delegate and stay on the native path.
    if not G.is_directed():
        snapshot = _cached_distance_measures_snapshot(G)
        if snapshot is not None:
            return list(snapshot[7])
    ecc = eccentricity(G)
    if not ecc:
        return []
    diameter = max(ecc.values())
    return [n for n in G.nodes() if ecc[n] == diameter]


def eccentricity(G, v=None, sp=None, weight=None):
    """Returns the eccentricity of nodes in G."""
    # br-r37-c1-eg0jk: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if len(G) == 0 and _networkx_release() >= (3, 7):
        # This check precedes nbunch/sp validation in the actual 3.7 oracle.
        raise NetworkXPointlessConcept("Cannot compute eccentricity of a null graph.")
    # br-r37-c1-ct24s: a v given on the null graph is still checked, as
    # nx's nbunch_iter checks it.
    if len(G) == 0 and v is None:
        return {}

    if v is None:
        nodes = list(G)
        single_node = False
    else:
        single_node = False
        try:
            if v in G:
                nodes = [v]
                single_node = True
            else:
                nodes = _global_nbunch_nodes(G, v)
        except TypeError:
            nodes = _global_nbunch_nodes(G, v)

    # br-eccdir: ``_raw_eccentricity`` collapses directed graphs to
    # undirected — it walks ``gr.undirected()`` so a directed C_n is
    # treated as undirected C_n and every node ends up with
    # eccentricity ⌊n/2⌋ instead of NX's correct n-1. The companion
    # functions diameter/radius/center/periphery already delegate the
    # directed case to NX; mirror that here so the family stays
    # internally consistent and matches NX.
    if sp is None and weight is None and not G.is_directed():
        snapshot = _cached_distance_measures_snapshot(G)
        if snapshot is not None:
            # Normalize v before checking the topology key: consuming a bunch
            # can mutate G, and its validation/order remain observable.
            if not nodes:
                return {}
            cached = dict(snapshot[3])
            if v is None:
                return cached
            if single_node:
                return cached[v]
            return {node: cached[node] for node in nodes}
        if v is None:
            # Cold subsets still compute only the requested sources.
            start_key = _distance_measures_cache_key(G)
            result = _raw_eccentricity(G)
            _store_distance_measures_snapshot(G, result, start_key)
            return result

    order = G.order()
    eccentricities = {}
    # br-r37-c1-eccallpairs (cc): for the all-nodes case compute every distance in ONE
    # all-pairs call (all_pairs_dijkstra / all_pairs_shortest_path_length both WIN ~2.7x)
    # instead of V separate shortest_path_length calls, each re-paying the per-source
    # setup — that loop made weighted eccentricity 0.84x. max() is order-invariant so the
    # result is identical; the reachability check matches nx's per-source one.
    #
    # The pairs are consumed ONE SOURCE AT A TIME, in node order (the order both
    # all-pairs generators yield and nx's loop visits), with the check applied as each
    # arrives: draining them first let a later source's error win - a negative cycle
    # unreachable from the first node raised ValueError('Contradictory paths') where nx
    # raises "not strongly connected" at that first node.
    if v is None and sp is None:
        if weight is not None:
            all_lengths = all_pairs_dijkstra_path_length(G, weight=weight)
        else:
            all_lengths = all_pairs_shortest_path_length(G)
        for node, lengths in all_lengths:
            if len(lengths) != order:
                if G.is_directed():
                    raise NetworkXError(
                        "Found infinite path length because the digraph is not strongly connected"
                    )
                raise NetworkXError(
                    "Found infinite path length because the graph is not connected"
                )
            eccentricities[node] = max(lengths.values())
        return eccentricities
    for node in nodes:
        if sp is None:
            lengths = shortest_path_length(G, source=node, weight=weight)
            reachable = len(lengths)
        else:
            try:
                lengths = sp[node]
                reachable = len(lengths)
            except TypeError as err:
                raise NetworkXError('Format of "sp" is invalid.') from err

        if reachable != order:
            if G.is_directed():
                raise NetworkXError(
                    "Found infinite path length because the digraph is not strongly connected"
                )
            raise NetworkXError(
                "Found infinite path length because the graph is not connected"
            )

        eccentricities[node] = max(lengths.values())

    if single_node:
        return eccentricities[v]
    return eccentricities


# Algorithm functions — tree, forest, bipartite, coloring, core
from franken_networkx._fnx import (
    bipartite_sets as _bipartite_sets,
    core_number as _raw_core_number,
    greedy_color as _raw_greedy_color,
    greedy_color_directed_rust as _raw_greedy_color_directed,
    is_bipartite as _raw_is_bipartite,
    is_regular as _raw_is_regular,
    is_forest as _raw_is_forest,
    is_tree as _raw_is_tree,
    number_of_spanning_trees as _raw_number_of_spanning_trees,
    minimum_spanning_edges as _raw_minimum_spanning_edges,
    prim_spanning_edges as _raw_prim_spanning_edges,
    multigraph_minimum_spanning_tree as _raw_multigraph_minimum_spanning_tree,
    minimum_spanning_tree as _raw_minimum_spanning_tree,
    partition_spanning_tree as _raw_partition_spanning_tree,
    random_spanning_tree as _raw_random_spanning_tree,
)

# br-r37-c1-l5es6: native onion_layers kernel now matches nx exactly; route the
# wrapper to it instead of delegating (avoids the _fnx_to_nx conversion cost).
try:
    from franken_networkx._fnx import onion_layers_rust as _raw_onion_layers
except ImportError:  # pragma: no cover — defensive for partial builds
    _raw_onion_layers = None


def is_bipartite(G):
    """Return True if graph ``G`` is bipartite.

    br-r37-c1-pf5vu: thin wrapper around the Rust ``_raw_is_bipartite``
    so we can coerce nx-typed inputs at the boundary (the bare PyO3
    import would reject nx graphs with a TypeError).
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_bipartite(G)


def number_of_spanning_trees(G, *, root=None, weight=None):
    """Return the number of spanning trees in G (Kirchhoff/Tutte).

    Thin wrapper over the Rust binding so the introspectable signature
    matches nx's ``(G, *, root=None, weight=None)`` (br-r37-c1-cirha).
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        return _multigraph_number_of_spanning_trees(G, root, weight)
    # br-r37-c1-33ctq: nx answers the literal 0 when no spanning tree exists
    # (disconnected; weakly disconnected once root is valid) - the kernel's
    # determinant would be the float 0.0.
    if len(G):
        if not G.is_directed():
            if not is_connected(G):
                return 0
        elif root is not None and root in G and not is_weakly_connected(G):
            return 0
    if isinstance(weight, str):
        # br-r37-c1-4tmgq: weights written after construction live only in the
        # Python edge dicts until synced into the Rust store the kernel reads.
        _sync_rust_edge_attrs(G, edge_only=True)
    return _raw_number_of_spanning_trees(G, root=root, weight=weight)


def _multigraph_number_of_spanning_trees(G, root, weight):
    """networkx's Kirchhoff/Tutte count for multigraphs.

    nro4w.7: the native kernel counts each adjacent pair once, so parallel
    edges vanished (MultiGraph 3.0 where networkx counts 8). networkx's
    Laplacian sums parallel edges (their weights, or 1 each); this is its
    code over fnx's matrix builders, which sum the same way.
    """
    import numpy as np

    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph G must contain at least one node.")
    if not G.is_directed():
        if not is_connected(G):
            return 0
        G_laplacian = laplacian_matrix(G, weight=weight).toarray()
        return float(np.linalg.det(G_laplacian[1:, 1:]))
    if root is None:
        raise NetworkXError("Input `root` must be provided when G is directed")
    if root not in G:
        raise NetworkXError("The node root is not in the graph G.")
    if not is_weakly_connected(G):
        return 0
    nodelist = [root] + [n for n in G if n != root]
    A = adjacency_matrix(G, nodelist=nodelist, weight=weight)
    D = np.diag(A.sum(axis=0))
    G_laplacian = D - A
    return float(np.linalg.det(G_laplacian[1:, 1:]))


def _prim_spanning_edges_native(G, weight, minimum, ignore_nan):
    """br-r37-c1-primidx: run the byte-exact native Prim kernel.

    nx's ``prim_mst_edges`` starts each component at ``set(G).pop()`` — a
    CPython set iteration order that the Rust kernel cannot reproduce — so the
    full pop sequence is computed here (over the fnx graph's own nodes, which
    hash identically to the equivalent nx graph) and passed as node indices.
    Returns a list of ``(u, v)`` node pairs, or ``None`` when a NaN weight is hit
    with ``ignore_nan=False`` (so the caller delegates to nx for the exact error).
    """
    node_to_index = {node: i for i, node in enumerate(G)}
    remaining = set(G)
    start_order = []
    while remaining:
        start_order.append(node_to_index[remaining.pop()])
    return _raw_prim_spanning_edges(G, weight, minimum, start_order, ignore_nan)


def _boruvka_spanning_edges_inproc(G, weight, minimum, ignore_nan):
    """br-r37-c1-jl0xr: in-process Borůvka MST, byte-exact with nx.

    Delegating boruvka to nx was 1.40x slower than nx — but cProfile showed
    the cost is NOT the ``_fnx_to_nx`` conversion (~20%). nx's own
    ``boruvka_mst_edges`` calls ``nx.edge_boundary`` once per component per
    pass (~70k times at n=1500), and because franken_networkx is registered
    as an nx backend, every one of those calls pays the full
    ``@nx._dispatchable`` backend-dispatch wrapper plus an ``EdgeDataView``
    construction. That dispatch/view machinery is the hot path.

    This reimplements nx's algorithm directly over a plain adjacency snapshot
    (one cheap native ``fnx_to_nx_adjacency`` crossing), with the edge
    boundary inlined as a tight loop — no nx graph build, no per-call
    dispatch, no views. It reuses the *real* ``networkx.utils.UnionFind`` over
    the fnx node objects so the component grouping (``to_sets``), set
    iteration order, and union tie-breaks are bit-identical to nx; the
    best-edge selection uses nx's exact strict-``<`` first-wins rule over the
    same iteration order (node-set order x adjacency-insertion order).

    Returns the ordered list of ``(u, v)`` tree edges, or ``None`` to request
    delegation to nx (native helper unavailable, or a NaN / non-numeric
    weight where nx's exact error message must be preserved).
    """
    from math import isnan

    from networkx.utils import UnionFind

    from franken_networkx.backend import _native_fnx_to_nx_adjacency

    if _native_fnx_to_nx_adjacency is None or type(G) is not Graph:
        return None
    bulk = _native_fnx_to_nx_adjacency(G)
    if bulk is None:
        return None

    display_nodes = list(G)
    # Map the native helper's canonical (interned) node keys back to the
    # original Python node objects (br-r37-c1-fnx2nx-lazykey): the lazy
    # display-key path can make e.g. canonical "0" diverge from the int 0.
    canon_to_obj = {canon: obj for (canon, _nbrs), obj in zip(bulk, display_nodes)}
    sign = 1 if minimum else -1
    # Signed-weight adjacency keyed by node object, in adj-insertion order.
    adj = {}
    for (_canon, nbrs), obj in zip(bulk, display_nodes):
        row = []
        for nbr_canon, attrs in nbrs:
            w = attrs.get(weight, 1)
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                return None  # non-numeric weight: let nx raise / handle
            w = w * sign
            if isnan(w):
                if ignore_nan:
                    continue
                return None  # NaN with ignore_nan=False: nx's exact ValueError
            row.append((canon_to_obj[nbr_canon], w))
        adj[obj] = row

    forest = UnionFind(G)

    def _best_edge(component):
        # Mirrors nx.edge_boundary order: nset1 = {n for n in component};
        # for n in nset1: for nbr in adj[n]: keep nbr not in nset1.
        cset = {n for n in component}
        best = None
        best_w = float("inf")
        for n in cset:
            for nbr, w in adj[n]:
                if nbr in cset:
                    continue
                if w < best_w:
                    best_w = w
                    best = (n, nbr)
        return best

    out = []
    while True:
        best_edges = []
        for component in forest.to_sets():
            be = _best_edge(component)
            if be is not None:
                best_edges.append(be)
        if not best_edges:
            break
        for u, v in best_edges:
            if forest[u] != forest[v]:
                out.append((u, v))
                forest.union(u, v)
    return out


def _kruskal_spanning_edges_inproc(
    G, minimum=True, weight="weight", keys=True, data=True, ignore_nan=False, partition=None
):
    from math import isnan
    from operator import itemgetter
    from networkx.utils import UnionFind

    subtrees = UnionFind()
    if G.is_multigraph():
        edges = G.edges(keys=True, data=True)
    else:
        edges = G.edges(data=True)

    included_edges = []
    open_edges = []
    for e in edges:
        d = e[-1]
        wt = d.get(weight, 1)
        if isinstance(wt, float) and isnan(wt):
            if ignore_nan:
                continue
            raise ValueError(f"NaN found as an edge weight. Edge {e}")

        edge = (wt,) + e
        if partition is not None:
            part_val = d.get(partition)
            if getattr(part_val, "name", None) == "INCLUDED" or part_val == 1:
                included_edges.append(edge)
                continue
            elif getattr(part_val, "name", None) == "EXCLUDED" or part_val == 2:
                continue
        open_edges.append(edge)

    if minimum:
        sorted_open_edges = sorted(open_edges, key=itemgetter(0))
    else:
        sorted_open_edges = sorted(open_edges, key=itemgetter(0), reverse=True)

    included_edges.extend(sorted_open_edges)
    sorted_edges = included_edges

    edges_needed = len(G) - 1
    edges_added = 0

    if G.is_multigraph():
        for wt, u, v, k, d in sorted_edges:
            if subtrees[u] != subtrees[v]:
                if keys:
                    if data:
                        yield u, v, k, d
                    else:
                        yield u, v, k
                else:
                    if data:
                        yield u, v, d
                    else:
                        yield u, v
                subtrees.union(u, v)
                edges_added += 1
                if edges_added == edges_needed:
                    return
    else:
        for wt, u, v, d in sorted_edges:
            if subtrees[u] != subtrees[v]:
                if data:
                    yield u, v, d
                else:
                    yield u, v
                subtrees.union(u, v)
                edges_added += 1
                if edges_added == edges_needed:
                    return


def _prim_spanning_edges_inproc(
    G, minimum=True, weight="weight", keys=True, data=True, ignore_nan=False
):
    from heapq import heappop, heappush
    from itertools import count
    from math import isnan

    is_multigraph = G.is_multigraph()
    nodes = set(G)
    c = count()
    sign = 1 if minimum else -1

    while nodes:
        u = nodes.pop()
        frontier = []
        visited = {u}
        if is_multigraph:
            for v, keydict in G.adj[u].items():
                for k, d in keydict.items():
                    wt = d.get(weight, 1) * sign
                    if isinstance(wt, float) and isnan(wt):
                        if ignore_nan:
                            continue
                        msg = f"NaN found as an edge weight. Edge {(u, v, k, d)}"
                        raise ValueError(msg)
                    heappush(frontier, (wt, next(c), u, v, k, d))
        else:
            for v, d in G.adj[u].items():
                wt = d.get(weight, 1) * sign
                if isinstance(wt, float) and isnan(wt):
                    if ignore_nan:
                        continue
                    msg = f"NaN found as an edge weight. Edge {(u, v, d)}"
                    raise ValueError(msg)
                heappush(frontier, (wt, next(c), u, v, d))
        while nodes and frontier:
            if is_multigraph:
                W, _, u, v, k, d = heappop(frontier)
            else:
                W, _, u, v, d = heappop(frontier)
            if v in visited or v not in nodes:
                continue
            if is_multigraph and keys:
                if data:
                    yield u, v, k, d
                else:
                    yield u, v, k
            else:
                if data:
                    yield u, v, d
                else:
                    yield u, v
            visited.add(v)
            nodes.discard(v)
            if is_multigraph:
                for w, keydict in G.adj[v].items():
                    if w in visited:
                        continue
                    for k2, d2 in keydict.items():
                        new_weight = d2.get(weight, 1) * sign
                        if isinstance(new_weight, float) and isnan(new_weight):
                            if ignore_nan:
                                continue
                            msg = f"NaN found as an edge weight. Edge {(v, w, k2, d2)}"
                            raise ValueError(msg)
                        heappush(frontier, (new_weight, next(c), v, w, k2, d2))
            else:
                for w, d2 in G.adj[v].items():
                    if w in visited:
                        continue
                    new_weight = d2.get(weight, 1) * sign
                    if isinstance(new_weight, float) and isnan(new_weight):
                        if ignore_nan:
                            continue
                        msg = f"NaN found as an edge weight. Edge {(v, w, d2)}"
                        raise ValueError(msg)
                    heappush(frontier, (new_weight, next(c), v, w, d2))


def _boruvka_inproc_full(G, minimum=True, weight="weight", data=True, ignore_nan=False):
    from networkx.utils import UnionFind
    from math import isnan

    forest = UnionFind(G)

    def best_edge(component):
        sign = 1 if minimum else -1
        minwt = float("inf")
        boundary = None
        # br-r37-c1-w0902: networkx's nx.edge_boundary walks the component in
        # the order of the set it builds from it, not the graph's node order -
        # walking the graph broke weight ties differently (a Graph subclass,
        # which takes this path, got another spanning tree).
        cset = {n for n in component if n in G}
        for n in cset:
            for nbr, d in G[n].items():
                if nbr not in cset:
                    wt = d.get(weight, 1) * sign
                    if isinstance(wt, float) and isnan(wt):
                        if ignore_nan:
                            continue
                        msg = f"NaN found as an edge weight. Edge {(n, nbr, d)}"
                        raise ValueError(msg)
                    if wt < minwt:
                        minwt = wt
                        boundary = (n, nbr, d)
        return boundary

    best_edges = (best_edge(component) for component in forest.to_sets())
    best_edges = [edge for edge in best_edges if edge is not None]
    while best_edges:
        best_edges = (best_edge(component) for component in forest.to_sets())
        best_edges = [edge for edge in best_edges if edge is not None]
        for u, v, d in best_edges:
            if forest[u] != forest[v]:
                if data:
                    yield u, v, d
                else:
                    yield u, v
                forest.union(u, v)


# networkx's ALGORITHMS table keys (algorithms/tree/mst.py).
_SPANNING_EDGE_ALGORITHMS = frozenset({"boruvka", "borůvka", "kruskal", "prim"})


def _check_spanning_edge_algorithm(algorithm):
    """nro4w.7: networkx looks ``algorithm`` up when the edges function is
    called; fnx's edges functions are generators, so their own check fired
    only on the first ``next()``. Set membership keeps nx's TypeError for an
    unhashable value."""
    if algorithm not in _SPANNING_EDGE_ALGORITHMS:
        raise ValueError(f"{algorithm} is not a valid choice for an algorithm.")


def minimum_spanning_edges(G, algorithm="kruskal", weight="weight", keys=True, data=True, ignore_nan=False):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-spanalgos: nx supports ``kruskal`` / ``prim`` / ``boruvka`` for
    the ``algorithm`` kwarg. The Rust binding only implemented
    ``kruskal`` and raised ``ValueError`` on the other two — a real
    contract gap when users explicitly request a non-default
    algorithm. Delegate the non-kruskal cases to nx.

    br-r37-c1-mse-gen: this is a generator function (``yield from``)
    so ``isinstance(result, types.GeneratorType)`` matches nx's
    contract.  The Rust kruskal fast path returns a ``list_iterator``
    (eagerly materialised); the delegate paths return a true
    generator.  Wrapping both in ``yield from`` normalises the
    return type for callers that introspect generator-ness (e.g.
    Cython interop, ``inspect.isgenerator``).
    """
    # br-r37-c1-gr1ct: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    _check_spanning_edge_algorithm(algorithm)

    def _gen():
        # br-r37-c1-mstcsr: the native kruskal kernel now reproduces nx's exact
        # MST — edge set, yield order AND (u, v) orientation — via node-index
        # edge orientation + a weight-only stable sort (the old kernel
        # canonicalised endpoints by string, flipping orientation and breaking
        # ties differently, which is why weighted graphs used to delegate to nx).
        # Route the weighted *simple-graph* case here too: delegating paid a full
        # fnx->nx conversion + nx kruskal (~4-5x slower). Multigraphs (parallel-
        # edge keys), prim/boruvka and callable weights still delegate to nx.
        # br-r37-c1-6eaq6: the native kernels read a weight that is not a
        # number - or an int wider than i64, which the store holds only as a
        # stand-in - as the default 1; networkx raises TypeError on the first
        # and computes exactly on the second, as the in-process paths below do.
        native_weights = (
            isinstance(weight, str)
            and not G.is_multigraph()
            and algorithm in ("kruskal", "prim")
        )
        if native_weights:
            _sync_rust_edge_attrs(G, edge_only=True)
            native_weights = not _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        if algorithm == "kruskal" and native_weights:
            # The kernel selects on the native store and emits each edge's data
            # from its mirror, or from the store when the edge has none
            # (br-r37-c1-mselazypostcheck's re-run on an all-empty result only
            # covered the case where NO edge had been materialised).
            yield from _raw_minimum_spanning_edges(G, algorithm=algorithm, weight=weight, keys=keys, data=data, ignore_nan=ignore_nan)
            return
        # br-r37-c1-primidx: native byte-exact Prim. nx's set(G).pop() start
        # order is computed here (CPython set order is un-reproducible in Rust),
        # the kernel does the heap traversal over neighbors_indices. Returns None
        # on a NaN weight with ignore_nan=False so we fall through to nx's exact
        # ValueError.
        if algorithm == "prim" and native_weights:
            _edges = _prim_spanning_edges_native(G, weight, True, ignore_nan)
            if _edges is not None:
                if data:
                    for _u, _v in _edges:
                        yield (_u, _v, G[_u][_v])
                else:
                    yield from _edges
                return
        # br-r37-c1-jl0xr: in-process Borůvka avoiding the fnx->nx conversion
        # AND nx's per-component edge_boundary backend-dispatch tax. Returns
        # None to fall through to nx for NaN/non-numeric weights.
        if (
            algorithm == "boruvka"
            and isinstance(weight, str)
            and not G.is_multigraph()
        ):
            _edges = _boruvka_spanning_edges_inproc(G, weight, True, ignore_nan)
            if _edges is not None:
                if data:
                    for _u, _v in _edges:
                        yield (_u, _v, G[_u][_v])
                else:
                    yield from _edges
                return
        if algorithm == "kruskal":
            yield from _kruskal_spanning_edges_inproc(
                G,
                minimum=True,
                weight=weight,
                keys=keys,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        if algorithm == "prim":
            yield from _prim_spanning_edges_inproc(
                G,
                minimum=True,
                weight=weight,
                keys=keys,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        if algorithm in ("boruvka", "borůvka"):
            if G.is_multigraph():
                raise NetworkXNotImplemented("not implemented for multigraph type")
            yield from _boruvka_inproc_full(
                G,
                minimum=True,
                weight=weight,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        raise ValueError(f"{algorithm} is not a valid choice for an algorithm.")

    return _gen()


def maximum_spanning_edges(G, algorithm="kruskal", weight="weight", keys=True, data=True, ignore_nan=False):
    """br-isokw: ``G`` matches nx.

    br-spanalgos: see minimum_spanning_edges — delegate non-kruskal
    algorithms to nx.

    br-r37-c1-mse-gen: generator function (``yield from``) so the
    Rust fast path's ``list_iterator`` is normalised to a true
    generator matching nx's contract.
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx is @not_implemented_for('directed') — eager raise.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    _check_spanning_edge_algorithm(algorithm)
    from franken_networkx._fnx import maximum_spanning_edges as _raw_mse

    def _gen():
        # br-mstcallable / br-mstweightwrong: see minimum_spanning_edges.
        # br-r37-c1-msemaxweighted (cc): maximum kruskal used to gate the native
        # kernel on ``not _mst_has_weight_edge_attr`` (unweighted only) -> WEIGHTED
        # graphs fell through to _call_networkx_for_parity (full fnx->nx round-trip,
        # 0.29x). minimum_spanning_edges already routes the weighted simple-graph
        # case through the native kernel via _sync_rust_edge_attrs + a lazy-mirror
        # post-check; mirror that exactly for maximum (same _raw_mse kernel, just
        # maximum sort). Multigraph / prim / boruvka / callable-weight still fall
        # through below. -> 0.29x -> native (matches minimum's ~2.5x).
        # br-r37-c1-6eaq6: weights the native kernels cannot read take the
        # in-process paths (see minimum_spanning_edges).
        native_weights = (
            isinstance(weight, str)
            and not G.is_multigraph()
            and algorithm in ("kruskal", "prim")
        )
        if native_weights:
            _sync_rust_edge_attrs(G, edge_only=True)
            native_weights = not _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        if algorithm == "kruskal" and native_weights:
            # Edge data comes from the mirror or, without one, the store (see
            # minimum_spanning_edges).
            yield from _raw_mse(G, algorithm=algorithm, weight=weight, keys=keys, data=data, ignore_nan=ignore_nan)
            return
        # br-r37-c1-primidx: native byte-exact Prim (maximum -> minimum=False).
        if algorithm == "prim" and native_weights:
            _edges = _prim_spanning_edges_native(G, weight, False, ignore_nan)
            if _edges is not None:
                if data:
                    for _u, _v in _edges:
                        yield (_u, _v, G[_u][_v])
                else:
                    yield from _edges
                return
        # br-r37-c1-jl0xr: in-process Borůvka (maximum -> minimum=False).
        if (
            algorithm == "boruvka"
            and isinstance(weight, str)
            and not G.is_multigraph()
        ):
            _edges = _boruvka_spanning_edges_inproc(G, weight, False, ignore_nan)
            if _edges is not None:
                if data:
                    for _u, _v in _edges:
                        yield (_u, _v, G[_u][_v])
                else:
                    yield from _edges
                return
        if algorithm == "kruskal":
            yield from _kruskal_spanning_edges_inproc(
                G,
                minimum=False,
                weight=weight,
                keys=keys,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        if algorithm == "prim":
            yield from _prim_spanning_edges_inproc(
                G,
                minimum=False,
                weight=weight,
                keys=keys,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        if algorithm in ("boruvka", "borůvka"):
            if G.is_multigraph():
                raise NetworkXNotImplemented("not implemented for multigraph type")
            yield from _boruvka_inproc_full(
                G,
                minimum=False,
                weight=weight,
                data=data,
                ignore_nan=ignore_nan,
            )
            return
        raise ValueError(f"{algorithm} is not a valid choice for an algorithm.")

    return _gen()


def _branching_partition_graph_for_networkx(G, partition):
    """Convert fnx EdgePartition attributes before NetworkX delegation."""
    graph = _networkx_graph_for_parity(G)
    if partition is None:
        return graph

    import networkx as nx

    graph = graph.copy()
    for _, _, attrs in graph.edges(data=True):
        value = attrs.get(partition)
        if isinstance(value, EdgePartition):
            attrs[partition] = nx.EdgePartition(value.value)
    return graph


def _branching_structural_nx(G, nx_name, attr, default):
    """Structural-only nx delegation for the branching family.

    br-r37-c1-p80x1.14. Lives in a private helper so the public wrappers keep no direct
    ``_nx.*`` reference, matching ``_greedy_color_structural_nx`` and
    ``_max_weight_matching_structural_nx``. Nodes in order, edges in order, carrying only
    the caller's ``attr`` - which is all networkx's own output retains when
    ``preserve_attrs`` is false. Mirrors the input's directedness, since a branching on a
    DiGraph is a different problem from one on a Graph.
    """
    _H = _nx.DiGraph() if G.is_directed() else _nx.Graph()
    _H.add_nodes_from(G)
    # Copy `attr` ONLY where the edge actually carries it, and let networkx apply its own
    # `default` to the rest. Materialising `d.get(attr, default)` here is WRONG and was
    # caught by the parameter sweep: on a graph with no weight attribute and default=-1,
    # writing -1 onto every edge made networkx select a full branching where the
    _H.add_edges_from(
        (u, v, {attr: d[attr]} if attr in d else {}) for u, v, d in G.edges(data=True)
    )
    fn = getattr(_nx.algorithms.tree.branchings, nx_name)
    try:
        return fn(_H, attr=attr, default=default, backend="networkx")
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def _maximum_branching_inproc(G, attr="weight", default=1, preserve_attrs=False, partition=None):
    nx_g = _branching_partition_graph_for_networkx(G, partition)
    try:
        return _nx.algorithms.tree.branchings.maximum_branching(
            nx_g, attr=attr, default=default, preserve_attrs=preserve_attrs, partition=partition, backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def _random_spanning_tree_inproc(G, weight=None, *, multiplicative=True, seed=None):
    nx_g = _networkx_graph_for_parity(G)
    try:
        return _nx.algorithms.tree.mst.random_spanning_tree(
            nx_g, weight=weight, multiplicative=multiplicative, seed=seed, backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def minimum_branching(G, attr="weight", default=1, preserve_attrs=False, partition=None):
    """br-isokw: ``G`` matches nx; default aligned to int 1 (was 1.0).

    br-r37-c1-ugod2: nx accepts undirected graphs (returns an empty
    Graph since branchings are tree-shaped; an undirected graph has
    no branching with positive sum). Delegate the undirected case so
    drop-in code works.

    br-r37-c1-s8x7z: the Rust kernel matches only ``GraphRef::Directed``
    (simple DiGraph) and rejects MultiDiGraph with a custom error
    message. nx accepts MultiDiGraph. Delegate multigraph input to nx
    so drop-in callers using MultiDiGraph keep working.
    """
    G = _coerce_arg_to_fnx_graph(G)

    def negate(w):
        return -w

    # networkx negates every weight in place, runs maximum_branching and
    # negates back (see _branching_round_trip): exact for numbers, but an
    # edge without ``attr`` ends up carrying ``default``.
    return _branching_round_trip(G, attr, default, preserve_attrs, partition, negate, negate)


_EDMONDS_CANDIDATE_ATTR = "edmonds' secret candidate attribute"


def _maximum_branching_native(G, attr, default, preserve_attrs, partition):
    """networkx's ``maximum_branching`` through the native plan (sfq4w.4).

    The kernel repeats networkx's Edmonds step for step over integer edge
    keys and returns the history of networkx's final ``set`` of keys; replaying
    it here gives networkx's result edge ORDER, which comes from that set.
    Returns None, for networkx's own code to run, where the plan would not be
    exact: a weight that is not an int or float, an int too large for f64
    arithmetic to stay exact through the contractions, or an attribute name
    equal to networkx's private candidate attribute.
    """
    if attr == _EDMONDS_CANDIDATE_ATTR or partition == _EDMONDS_CANDIDATE_ATTR:
        return None
    if preserve_attrs or partition is not None:
        rows = list(G.edges(data=True))
        if preserve_attrs and any(_EDMONDS_CANDIDATE_ATTR in d for _, _, d in rows):
            return None
        weights = [d.get(attr, default) for _, _, d in rows]
    else:
        rows = list(G.edges(data=attr, default=default))
        weights = [w for _, _, w in rows]
    # Each contraction can move a weight by twice the largest one.
    bound = 2**53 // (2 * len(rows) + 2)
    ids = {}
    sources, targets, floats = [], [], []
    for (u, v, _), w in zip(rows, weights):
        kind = type(w)
        if kind is float:
            floats.append(w)
        elif (kind is int or kind is bool) and -bound <= w <= bound:
            floats.append(float(w))
        else:
            return None
        sources.append(ids.setdefault(u, len(ids)))
        targets.append(ids.setdefault(v, len(ids)))
    parts = None
    if partition is not None:
        parts = []
        for _, _, d in rows:
            value = d.get(partition)
            if value == EdgePartition.EXCLUDED:
                parts.append(2)
            elif value == EdgePartition.INCLUDED:
                parts.append(1)
            else:
                parts.append(0)
    initial, steps = _raw_networkx_maximum_branching_plan(sources, targets, floats, parts)
    # networkx takes set() of a DICT (its edge index): CPython sizes the table
    # for a dict in one step but grows it while inserting from a list, and the
    # table size decides where small int keys collide, hence the order.
    kept = set(dict.fromkeys(initial))
    for circuit, removed in steps:
        kept.update(circuit)
        kept.remove(removed)
    H = G.__class__()
    H.add_nodes_from(G)
    for key in kept:
        u, v, data = rows[key]
        dd = {attr: weights[key]}
        if preserve_attrs:
            # networkx's G^0 edge data, then its result data without the
            # weight's second copy or the candidate marker.
            d = {attr: weights[key]}
            if data.get(partition) is not None:
                d[partition] = data.get(partition)
            for k, value in data.items():
                if k != attr:
                    d[k] = value
            for k, value in d.items():
                if k not in (attr, _EDMONDS_CANDIDATE_ATTR):
                    dd[k] = value
        H.add_edge(u, v, **dd)
    return H


def maximum_branching(G, attr="weight", default=1, preserve_attrs=False, partition=None):
    """br-isokw: ``G`` matches nx; default aligned to int 1.

    br-r37-c1-ugod2: nx accepts undirected graphs (returns the
    maximum-weight spanning result). Delegate to nx for undirected
    so drop-in code works.

    br-r37-c1-s8x7z: also delegate MultiDiGraph; the Rust kernel
    rejects MultiDiGraph but nx accepts it.

    br-r37-c1-kb9hm: the old native Edmonds kernel did not preserve
    NetworkX's incoming-edge iteration order through tie-rich cycle
    contractions. sfq4w.4: ``_maximum_branching_native`` runs a
    step-for-step port instead (edge order included); the networkx
    delegation below remains for weights that port does not cover.
    """
    G = _coerce_arg_to_fnx_graph(G)
    H = _maximum_branching_native(G, attr, default, preserve_attrs, partition)
    if H is not None:
        return H
    from franken_networkx.readwrite import _from_nx_graph

    # br-r37-c1-p80x1.14: the delegation above stays - br-r37-c1-kb9hm rejected the native
    # Edmonds kernel because it does not reproduce nx's incoming-edge iteration order
    # through tie-rich cycle contractions - but the CONVERSION does not have to be
    # faithful. networkx's output carries only the `attr` weight here (verified on both
    # classes); node and graph attributes are dropped. Measured at n=400:
    # DiGraph 432.1M Ir/call against nx's 378.7M (0.876x), Graph 215.3M against 164.8M
    # (0.766x) - every call was paying an attribute copy the result discards.
    #
    # Same scope clauses as minimum_branching, each checked rather than assumed:
    # preserve_attrs=True DOES retain extra edge attributes; a multigraph would lose its
    # parallel edges to a simple copy; partition routes through a different input; and
    # `attr` is carried rather than hardcoded.
    if (
        partition is None
        and not G.is_multigraph()
        and not preserve_attrs
    ):
        return _from_nx_graph(
            _branching_structural_nx(G, "maximum_branching", attr, default)
        )
    nx_result = _maximum_branching_inproc(
        G, attr=attr, default=default,
        preserve_attrs=preserve_attrs, partition=partition,
    )
    return _from_nx_graph(nx_result)


def _branching_round_trip(G, attr, default, preserve_attrs, partition, forward, backward):
    """networkx's minimum / minimal / spanning-arborescence wrappers, as written.

    nro4w.7: networkx rewrites every edge weight of G in place, runs
    maximum_branching on that, then rewrites G's weights and the result's
    back. The round trip is not exact in floating point (0.1 comes back as
    0.09999999999999964 from minimal_branching's C - (C - w)), it turns int
    weights into floats when the transform does, and it writes ``attr`` onto
    edges that lacked it; networkx declares these functions mutates_input for
    that reason. fnx used to return the exact original weights and leave G
    alone, so its results and inputs differed from networkx's after the call
    (under the test backend: test_edge_augmentation::test_weight_key). The
    selection itself runs on the transformed weights, as in networkx, so
    near-ties after rounding break the same way. fnx's maximum_branching
    equals networkx's exactly (0 of 200 random weighted digraphs differ).
    """
    for _, _, d in G.edges(data=True):
        d[attr] = forward(d.get(attr, default))
    B = maximum_branching(G, attr, default, preserve_attrs, partition)
    for _, _, d in G.edges(data=True):
        d[attr] = backward(d.get(attr, default))
    for _, _, d in B.edges(data=True):
        d[attr] = backward(d.get(attr, default))
    return B


def _minimal_branching_round_trip(G, attr, default, preserve_attrs, partition):
    max_weight = -float("inf")
    min_weight = float("inf")
    for _, _, w in G.edges(data=attr, default=default):
        if w > max_weight:
            max_weight = w
        if w < min_weight:
            min_weight = w

    def transform(w):
        # networkx's expression, in its evaluation order: the float result
        # depends on it.
        return max_weight + 1 + (max_weight - min_weight) - w

    return _branching_round_trip(G, attr, default, preserve_attrs, partition, transform, transform)


def minimum_spanning_arborescence(G, attr="weight", default=1, preserve_attrs=False, partition=None):
    """networkx's minimum_spanning_arborescence: minimal_branching's in-place
    weight round trip, then the arborescence check (see _branching_round_trip).

    Undirected input goes through the whole round trip before is_arborescence
    raises NetworkXNotImplemented, exactly as in networkx, so G's weights are
    rewritten even then. No arborescence raises the base NetworkXException.
    """
    G = _coerce_arg_to_fnx_graph(G)
    B = _minimal_branching_round_trip(G, attr, default, preserve_attrs, partition)
    if not is_arborescence(B):
        raise NetworkXException("No minimum spanning arborescence in G.")
    return B


def _minimal_branching_backend_impl(G, /, *, attr="weight", default=1, preserve_attrs=False, partition=None):
    """br-r37-c1-0epvo: backend-only implementation of ``minimal_branching``.

    nx exposes ``minimal_branching`` only under ``nx.algorithms.tree`` (no
    top-level alias) — the namespace-parity lock in
    ``test_branching_weight_minimal_branching_only_at_branchings_namespace``
    enforces that fnx mirrors that. So this implementation is private
    (underscore-prefixed) and registered into the backend dispatch table
    via ``franken_networkx.backend._SUPPORTED_ALGORITHMS`` *only*; it is
    not exposed at ``fnx.minimal_branching``.

    Once registered, ``nx.algorithms.tree.minimal_branching(fnx_graph)``
    routes through this implementation (after the ``__networkx_backend__``
    class attribute tags fnx graphs as belonging to the franken_networkx
    backend). It is networkx's in-place weight round trip over fnx's
    maximum_branching (see _branching_round_trip); the former delegation
    to networkx ran on a converted copy, so the caller's graph never saw
    networkx's weight rewrite.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _minimal_branching_round_trip(G, attr, default, preserve_attrs, partition)


def maximum_spanning_arborescence(G, attr="weight", default=1, preserve_attrs=False, partition=None):
    """networkx's maximum_spanning_arborescence: its own in-place weight shift
    and back (see _branching_round_trip), then the arborescence check, which
    is also where undirected input raises NetworkXNotImplemented.
    """
    G = _coerce_arg_to_fnx_graph(G)
    min_weight = float("inf")
    max_weight = -float("inf")
    for _, _, w in G.edges(data=attr, default=default):
        if w < min_weight:
            min_weight = w
        if w > max_weight:
            max_weight = w

    def forward(w):
        return w - min_weight + 1 - (min_weight - max_weight)

    def backward(w):
        return w + min_weight - 1 + (min_weight - max_weight)

    B = _branching_round_trip(G, attr, default, preserve_attrs, partition, forward, backward)
    if not is_arborescence(B):
        raise NetworkXException("No maximum spanning arborescence in G.")
    return B


def random_spanning_tree(G, weight=None, *, multiplicative=True, seed=None):
    """br-isokw: ``G`` matches nx.

    Matches nx exactly: the returned tree carries only the structure
    chosen by the random spanning tree algorithm (no graph/node/edge
    attribute carryover from G). Strict nx parity is enforced by
    test_spanning_tree_conformance.py — see commit 122ab6a2.
    """
    G = _coerce_arg_to_fnx_graph(G)
    rng = _create_py_random_state(seed) if _create_py_random_state is not None else _random.Random(seed)

    def find_node(merged_nodes, node):
        if node not in merged_nodes:
            return node
        rep = find_node(merged_nodes, merged_nodes[node])
        merged_nodes[node] = rep
        return rep

    def prepare_graph():
        result = MultiGraph(incoming_graph_data=G)
        edges_to_remove = set(result.edges()).difference(V)
        result.remove_edges_from(edges_to_remove)
        merged_nodes = {}
        for u, v in U:
            u_rep = find_node(merged_nodes, u)
            v_rep = find_node(merged_nodes, v)
            if u_rep == v_rep:
                continue
            contracted_nodes(result, u_rep, v_rep, self_loops=False, copy=False)
            merged_nodes[v_rep] = u_rep
        return merged_nodes, result

    def spanning_tree_total_weight(H, w_key):
        if multiplicative:
            return number_of_spanning_trees(H, weight=w_key)
        if H.number_of_edges() == 1:
            return H.edges(data=w_key).__iter__().__next__()[2]
        total = 0
        for u, v, w in H.edges(data=w_key):
            total += w * number_of_spanning_trees(
                contracted_edge(H, edge=(u, v), self_loops=False),
                weight=None,
            )
        return total

    if G.number_of_nodes() < 2:
        return empty_graph(G.nodes)

    U = set()
    st_cached_value = 0
    V = set(G.edges())
    shuffled_edges = list(G.edges())
    rng.shuffle(shuffled_edges)

    for u, v in shuffled_edges:
        e_weight = G[u][v][weight] if weight is not None else 1
        node_map, prepared_G = prepare_graph()
        G_total_tree_weight = spanning_tree_total_weight(prepared_G, weight)
        rep_edge = (find_node(node_map, u), find_node(node_map, v))
        if rep_edge in prepared_G.edges:
            prepared_G_e = contracted_edge(
                prepared_G, edge=rep_edge, self_loops=False
            )
            G_e_total_tree_weight = spanning_tree_total_weight(prepared_G_e, weight)
            if multiplicative:
                threshold = e_weight * G_e_total_tree_weight / G_total_tree_weight
            else:
                numerator = (st_cached_value + e_weight) * number_of_spanning_trees(
                    prepared_G_e
                ) + G_e_total_tree_weight
                denominator = (
                    st_cached_value * number_of_spanning_trees(prepared_G)
                    + G_total_tree_weight
                )
                threshold = numerator / denominator
        else:
            threshold = 0.0
        z = rng.uniform(0.0, 1.0)
        if z > threshold:
            V.remove((u, v))
        else:
            st_cached_value += e_weight
            U.add((u, v))
        if len(U) == G.number_of_nodes() - 1:
            spanning_tree = Graph()
            spanning_tree.add_edges_from(U)
            return spanning_tree
    raise Exception(f"Something went wrong! Only {len(U)} edges in the spanning tree!")


def partition_spanning_tree(G, minimum=True, weight="weight", partition="partition", ignore_nan=False):
    """br-isokw: ``G`` matches nx.

    br-r37-c1-3jn5a-followup: the Rust kernel rejects directed and
    multigraph input, but nx accepts all four graph classes (the
    Kruskal/Prim variants generalize trivially across them). Delegate
    those cases to nx so drop-in callers keep working.
    """
    # br-r37-c1-gr1ct: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed() or G.is_multigraph():
        edges = _kruskal_spanning_edges_inproc(
            G,
            minimum=minimum,
            weight=weight,
            keys=True,
            data=True,
            ignore_nan=ignore_nan,
            partition=partition,
        )
        T = _concrete_class_for(G)()
        T.graph.update(G.graph)
        T.add_nodes_from(G.nodes.items())
        T.add_edges_from(edges)
        return T
    # br-r37-c1-4tmgq: both ``weight`` and ``partition`` are read from the Rust
    # store by the native kernel; flush post-construction writes first.
    _sync_rust_edge_attrs(G, edge_only=True)
    return _raw_partition_spanning_tree(G, minimum=minimum, weight=weight, partition=partition, ignore_nan=ignore_nan)

# Algorithm functions — Euler
from franken_networkx._fnx import (
    eulerian_circuit as _raw_eulerian_circuit,
    eulerian_path as _raw_eulerian_path,
    has_eulerian_path as _raw_has_eulerian_path,
    is_eulerian as _raw_is_eulerian,
    is_semieulerian as _raw_is_semieulerian,
)


def is_semieulerian(G):
    """Return True iff the graph has an Eulerian path but not a circuit.

    br-r37-c1-lg07d: the Rust kernel ``_raw_is_semieulerian`` has
    ``require_undirected`` and rejects directed input. nx supports
    ``is_semieulerian`` on digraphs (a digraph has an Eulerian path iff
    at most one node has out-in=1, at most one has in-out=1, and all
    others have equal in/out, with the underlying graph connected).
    Compose from the directed-aware ``has_eulerian_path`` and
    ``is_eulerian`` wrappers so the directed semantics are preserved.
    """
    return has_eulerian_path(G) and not is_eulerian(G)
