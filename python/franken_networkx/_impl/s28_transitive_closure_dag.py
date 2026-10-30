

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

    br-r37-c1-utmy6: the previous transitive_closure (Rust) shortcut
    produced a graph whose adj[node] iteration order drifted from nx
    (nx appends new transitive edges in its BFS-from-each-source
    discovery order, e.g. adj[a] = [b,c,e,d] when 'd' is reached
    last via the longer (a→c→d) chain). Delegate to nx so the
    output graph's adj iteration matches nx's contract.
    """
    if not G.is_directed():
        # br-r37-c1-1ewpw: nx's @not_implemented_for('undirected')
        # raises NetworkXNotImplemented; fnx silently ran. Surface the
        # standard message for drop-in parity.
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-tcddedeleg: run nx's exact algorithm IN-PROCESS on the fnx
    # graph for a plain DiGraph, instead of round-tripping through nx
    # (_networkx_graph_for_parity built a full nx copy AND _from_nx_graph
    # rebuilt the larger closure graph — ~59% of the time was these two
    # O(V+E) conversions). nx appends each adj[v]'s transitive edges in
    # CPython set-iteration order; we reproduce that natively by using real
    # Python sets with identical insertion order, so the output graph's
    # adj iteration is byte-identical (ordered edges == nx). Multigraph /
    # views / nx-private-storage graphs keep the proven delegation path.
    if type(G) is DiGraph:
        result = _transitive_closure_dag_inproc(G, topo_order)
        if result is not None:
            return result
    return _transitive_closure_dag_via_parity(G, topo_order)


def _transitive_closure_dag_inproc(G, topo_order):
    """In-process nx-exact transitive_closure_dag for a plain DiGraph.

    Mirrors networkx.algorithms.dag.transitive_closure_dag verbatim:
    ``TC = G.copy(); for v in reversed(topo_order): TC.add_edges_from(
    (v, u) for u in descendants_at_distance(TC, v, 2))``. The distance-2
    BFS is inlined with the raw Rust successor accessor (skipping the
    AtlasView per-access tax) but builds the SAME Python sets in the SAME
    insertion order, so CPython set-iteration order — and thus the appended
    transitive-edge order in every adj[v] — matches nx exactly. Returns
    ``None`` to signal the caller to fall back (raw accessor unavailable).
    """
    if topo_order is None:
        topo_order = list(topological_sort(G))
    TC = G.copy()
    # br-r37-c1-ey5n2: the successor snapshot comes from one native call. Read
    # row by row through the raw neighbors accessor, every row got a live row
    # mirror, and a graph with row mirrors turns the final add_edges_from away
    # from the native append batch - most of this function's time.
    adj = _fnx.to_dict_of_lists_undirected(TC)
    succ = _raw_neighbors_dispatch(TC) if adj is None else None
    if adj is None and succ is None:
        return None
    # br-cc-tcdsnap: the distance-2 BFS below previously called ``succ(TC, node)``
    # (a PyO3 successor lookup) per node on the MUTATING TC — O(closure-edges)
    # round-trips, ~0.67x vs nx (which walks native dicts). Snapshot TC's
    # successor adjacency ONCE into Python LISTS (insertion order — set order
    # would scramble nx's discovery order), run the BFS on those, and keep them
    # in sync as edges are discovered so a node's successors are fully closed
    # before its predecessors (processed later in reversed topo) read them. All
    # transitive edges are committed in ONE final ``add_edges_from`` instead of
    # per-v: identical per-v / set-order append, so the result graph's adj
    # iteration is byte-identical to nx.
    if adj is None:
        adj = {node: list(succ(TC, node)) for node in TC}
    new_edges = []
    for v in reversed(topo_order):
        # descendants_at_distance(TC, v, 2) == set(bfs_layers(TC, v)[2]).
        # bfs_layers builds each layer as a LIST in BFS discovery order
        # (next_layer.append), so the distance-2 layer's element order — and
        # hence the iteration order of set(layer) consumed by add_edges_from —
        # is deterministic and matches nx EXACTLY.
        current_layer = [v]
        visited = {v}
        descendants = []
        i = 0
        while current_layer:
            if i == 2:
                descendants = current_layer
                break
            next_layer = []
            for node in current_layer:
                for child in adj[node]:
                    if child not in visited:
                        visited.add(child)
                        next_layer.append(child)
            current_layer = next_layer
            i += 1
        dset = set(descendants)
        new_edges.extend((v, u) for u in dset)
        adj[v].extend(dset)
    TC.add_edges_from(new_edges)
    return TC


def _transitive_closure_dag_via_parity(G, topo_order):
    """In-process transitive_closure_dag for multigraphs, views, and subclasses."""
    G = _coerce_arg_to_fnx_graph(G)
    if topo_order is None:
        topo_order = list(topological_sort(G))
    else:
        topo_order = list(topo_order)
    TC = G.copy()
    for v in reversed(topo_order):
        TC.add_edges_from((v, u) for u in descendants_at_distance(TC, v, 2))
    return TC


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

    br-r37-c1-0l76i: nx populates the predecessor dict in
    edge-relaxation insertion order during traversal (so pred[v]
    appears in the dict at the moment a tentative shortest path is
    found, not when the distance is finalized). The native kernel
    records that relaxation-insertion stream independently from the
    finalized distance order, preserving nx's algorithm-discovery
    contract while avoiding the full fnx->nx conversion fallback.
    """
    # Private root rows remain authoritative through views; coercion can read
    # stale native edges or replace the row's discovery objects before routing.
    if _point_query_uses_private_rows(G):
        return _dijkstra_predecessor_and_distance_inproc(
            G, source, cutoff=cutoff, weight=weight,
        )
    G = _coerce_arg_to_fnx_graph(G)
    # br-cc-mgbfpath: a DIRECTED multigraph collapses to the simple min-weight
    # DiGraph byte-EXACTLY for BOTH the predecessor-list dict AND the distance
    # dict (order-sensitive), since the collapsed out-adjacency order == the
    # multigraph's -> identical relaxation-insertion stream (verified 210/210).
    # Replaces the full fnx->nx conversion the multigraph otherwise pays
    # (0.19x -> ~0.5x). cutoff!=None keeps delegating (unverified); UNDIRECTED MG
    # stays on delegation (collapse reorders per-node adjacency, 151/210 divergent).
    if (
        cutoff is None
        and G.is_directed()
        and G.is_multigraph()
        and isinstance(weight, str)
    ):
        _simple, _delegate = _multigraph_collapse_min_weight(G, weight)
        if _delegate:
            return _dijkstra_predecessor_and_distance_via_parity(
                G, source, cutoff=cutoff, weight=weight,
            )
        return dijkstra_predecessor_and_distance(
            _simple, source, cutoff=cutoff, weight=weight,
        )
    if (
        type(G) not in (Graph, DiGraph)
        or (cutoff is not None and not isinstance(cutoff, _numbers.Real))
        or _should_delegate_dijkstra_to_networkx(G, weight)
    ):
        return _dijkstra_predecessor_and_distance_via_parity(
            G, source, cutoff=cutoff, weight=weight,
        )
    if source not in G:
        raise NodeNotFound(f"Node {source} is not found in the graph")
    return _raw_dijkstra_predecessor_and_distance(
        G,
        source,
        weight=weight,
        cutoff=cutoff,
    )


def _dijkstra_predecessor_and_distance_via_parity(G, source, cutoff=None, weight="weight"):
    return _dijkstra_predecessor_and_distance_inproc(
        G, source, cutoff=cutoff, weight=weight,
    )


def multi_source_dijkstra(G, sources, target=None, cutoff=None, weight="weight"):
    """Return shortest path lengths and paths from any source in *sources*."""
    if not sources:
        raise ValueError("sources must not be empty")
    if _point_query_uses_private_rows(G):
        return _multi_source_dijkstra_inproc(
            G, sources, target=target, cutoff=cutoff, weight=weight,
        )
    # br-r37-c1-gr1ct: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-m0cj7: a simple graph runs networkx's search natively - cutoff
    # and target inside the search, distances typed and paths built as
    # networkx's are, weights checked on the rows it reads after a write. It
    # used to run an UNBOUNDED whole-graph search and filter, re-type and
    # re-sort the result in Python (87 us beside a 32k ring for cutoff=2), and
    # sent every float-weighted graph to networkx.
    if (
        type(G) in (Graph, DiGraph, MultiGraph)
        and isinstance(weight, str)
        and (
            cutoff is None
            or type(cutoff) is float
            or (type(cutoff) is int and -(2**53) <= cutoff <= 2**53)
        )
    ):
        route = _dijkstra_weight_route(G, weight)
        if route != "networkx" and not _binding_self_syncs_gate(G, weight):
            for s in sources:
                if s not in G:
                    raise NodeNotFound(f"Node {s} not found in graph")
            if target in sources:
                return (0, [target])
            try:
                dists, paths = _raw_multi_source_dijkstra(
                    G,
                    sources,
                    weight=weight,
                    cutoff=cutoff,
                    target=target,
                    check_rows=route == "rows",
                )
            except _WeightRowsUnverified:
                dists = None
            if dists is None:
                return _rerun_with_weight_scan(
                    multi_source_dijkstra, G, sources, target=target, cutoff=cutoff, weight=weight
                )
            if target is None:
                return dists, paths
            if target not in dists:
                raise NetworkXNoPath(f"No path to {target}.")
            # networkx walks the predecessors back from the target object it
            # was given.
            path = paths[target]
            path[-1] = target
            return dists[target], path
    # br-r37-c1-msd-projfix (cc): multigraphs and the rest keep the raw binding
    # on the BORROWED ORIGINAL graph (nx's finalize order) with the Python
    # cutoff filter and int-typing below; float/mixed, callable, negative and
    # sync-gated weights delegate.
    if (
        callable(weight)
        or _should_delegate_dijkstra_to_networkx(G, weight)
        or (
            _mst_has_weight_edge_attr(G, weight)
            and not _sp_edge_weights_all_int(G, weight)
        )
        or _binding_self_syncs_gate(G, weight)
    ):
        return _multi_source_dijkstra_inproc(
            G,
            sources,
            target=target,
            cutoff=cutoff,
            weight=weight,
        )
    # br-r37-c1-k4pod: pre-check membership for nx's exact wording
    # ('Node X not found in graph') — Rust binding emits a quoted-repr
    # variant that breaks message-matching code.
    for s in sources:
        if s not in G:
            raise NodeNotFound(f"Node {s} not found in graph")
    dists, paths = _raw_multi_source_dijkstra(G, sources, weight=weight)
    # br-r37-c1-msd-cutnan: nx Dijkstra's cutoff check is
    # ``if d > cutoff: continue`` so ``cutoff=NaN`` and
    # ``cutoff=+inf`` both behave as unbounded (comparison
    # always False → never skips).  fnx's inverse predicate
    # ``distance <= cutoff`` is ALSO always False for NaN →
    # filters out everything (sister of the single-source fix
    # br-r37-c1-djk-cutnan).  Short-circuit before the filter.
    if cutoff is not None:
        if not (isinstance(cutoff, float) and (_math.isnan(cutoff) or cutoff == _math.inf)):
            # nx always retains the source nodes even when
            # ``cutoff < 0`` (sources have d=0 and the filter
            # ``d <= cutoff`` would drop them; nx's loop adds
            # them before applying the cutoff via the priority
            # queue's pop order).
            source_set = set(sources)
            dists = {
                node: distance for node, distance in dists.items()
                if distance <= cutoff or node in source_set
            }
            paths = {node: path for node, path in paths.items() if node in dists}
    # br-r37-c1-msd-intfloat: nx preserves int distances when
    # every edge weight is int (path graph default = unit
    # weight).  fnx's Rust binding casts to f64.  Mirror nx's
    # int/float parity (sister of br-ssintfloat for single-
    # source).
    if _sp_edge_weights_all_int(G, weight):
        dists = _sp_coerce_dist_to_int(dists)
    else:
        # br-r37-c1-srczero: per-path int-type propagation (see helper).
        dists = _sp_propagate_int_types(G, weight, dists, paths)
    # br-r37-c1-msd-order: nx's Dijkstra emits nodes in pop
    # order from the priority queue → ascending distance.  fnx's
    # Rust binding returns a dict in adjacency-walk order.
    # Reorder by distance to match nx's iteration contract
    # (dict order is observable in py3.7+).  Sister of the
    # br-r37-c1-62jy2 single-source reorder.
    order = _reorder_by_distance(dists)
    dists = {k: dists[k] for k in order}
    paths = {k: paths[k] for k in order if k in paths}
    if target is not None:
        if target not in dists:
            raise NetworkXNoPath(f"No path to {target}.")
        return dists[target], paths[target]
    return dists, paths


def multi_source_dijkstra_path(G, sources, cutoff=None, weight="weight"):
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
    _, paths = multi_source_dijkstra(G, sources, cutoff=cutoff, weight=weight)
    return paths


def multi_source_dijkstra_path_length(G, sources, cutoff=None, weight="weight"):
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
    if not sources:
        raise ValueError("sources must not be empty")
    if _point_query_uses_private_rows(G):
        for source in sources:
            if source not in G:
                raise NodeNotFound(f"Node {source} not found in graph")
        return _dijkstra_multisource_inproc(
            G, sources, _weight_function(G, weight), cutoff=cutoff,
        )
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-msd-projfix (cc): the native length-only binding runs on the
    # BORROWED ORIGINAL graph (after syncing the mirror), so its settle order is
    # networkx's heap-pop order even on dense tie-heavy graphs.
    # br-r37-c1-m0cj7: it now types distances as networkx does (per path) and
    # applies cutoff inside the search, so float / mixed weights and a cutoff
    # stay native too; after a write it checks the rows it read.
    if (
        isinstance(weight, str)
        and type(G) in (Graph, DiGraph, MultiGraph)
        and (
            cutoff is None
            or type(cutoff) is float
            or (type(cutoff) is int and -(2**53) <= cutoff <= 2**53)
        )
    ):
        route = _dijkstra_weight_route(G, weight)
        if route != "networkx" and not _binding_self_syncs_gate(G, weight):
            for s in sources:
                if s not in G:
                    raise NodeNotFound(f"Node {s} not found in graph")
            try:
                return _fnx.multi_source_dijkstra_path_length(
                    G, sources, weight=weight, cutoff=cutoff, check_rows=route == "rows"
                )
            except _WeightRowsUnverified:
                pass
            return _rerun_with_weight_scan(
                multi_source_dijkstra_path_length, G, sources, cutoff=cutoff, weight=weight
            )
    dists, _ = multi_source_dijkstra(G, sources, cutoff=cutoff, weight=weight)
    return dists


def _build_paths_from_predecessors(sources, target, pred):
    """Compute all simple paths to target, given predecessors, terminating at sources."""
    if target not in pred:
        raise NetworkXNoPath(f"Target {target} cannot be reached from given sources")

    seen = {target}
    stack = [[target, 0]]
    top = 0
    while top >= 0:
        node, i = stack[top]
        if node in sources:
            yield [p for p, n in reversed(stack[: top + 1])]
        if len(pred[node]) > i:
            stack[top][1] = i + 1
            next_node = pred[node][i]
            if next_node in seen:
                continue
            seen.add(next_node)
            top += 1
            if top == len(stack):
                stack.append([next_node, 0])
            else:
                stack[top][:] = [next_node, 0]
        else:
            seen.discard(node)
            top -= 1


def single_source_all_shortest_paths(G, source, weight=None, method="dijkstra"):
    """Yield all shortest paths from source to every reachable target.

    Parameters
    ----------
    G : Graph
    source : node
    weight : str or callable or None, optional
    method : str, optional

    Yields
    ------
    (target, paths)
        ``paths`` is the list of all shortest paths from source to target.
    """
    method = "unweighted" if weight is None else method
    if method == "unweighted":
        pred = predecessor(G, source)
    elif method == "dijkstra":
        pred, _ = dijkstra_predecessor_and_distance(G, source, weight=weight)
    elif method == "bellman-ford":
        pred, _ = bellman_ford_predecessor_and_distance(G, source, weight=weight)
    else:
        raise ValueError(f"method not supported: {method}")

    for n in pred:
        yield n, list(_build_paths_from_predecessors({source}, n, pred))


def all_pairs_all_shortest_paths(G, weight=None, method="dijkstra"):
    """Yield all shortest paths between all pairs.

    Parameters
    ----------
    G : Graph
    weight : str or callable or None, optional
    method : str, optional

    Yields
    ------
    (source, paths_dict)
        Where paths_dict maps target -> list of shortest paths.
    """
    # Each result necessarily contains all paths for its source, but later
    # sources must remain uncomputed until requested. This also keeps their
    # searches sensitive to mutations between yields, as in NetworkX.
    for source in G:
        yield (
            source,
            dict(single_source_all_shortest_paths(G, source, weight=weight, method=method)),
        )


def reconstruct_path(source, target, predecessors):
    """Reconstruct a path from *source* to *target*.

    Matches networkx's public signature
    ``reconstruct_path(source, target, predecessors)`` where
    ``predecessors`` is the nested
    ``floyd_warshall_predecessor_and_distance`` dict
    (``predecessors[src][tgt] -> predecessor``).
    """
    # br-r37-c1-recon-keyerr: nx raises KeyError(node) when the
    # source / target is not present in the predecessor dict.  fnx
    # previously fell through to a dijkstra-style fallback that
    # walked through dict-typed inner predecessor maps, raising
    # ``TypeError: unhashable type: 'dict'`` on bad-source or
    # silently returning ``[]`` on bad-target.

    if source == target:
        return []
    table = predecessors[source]
    current = table[target]
    path = [target, current]
    while current != source:
        current = table[current]
        path.append(current)
    path.reverse()
    return path


def generate_random_paths(
    G,
    sample_size,
    path_length=5,
    index_map=None,
    weight="weight",
    seed=None,
    *,
    source=None,
):
    """Generate random paths by weighted random walks.

    Parameters
    ----------
    G : Graph
    sample_size : int
        Number of paths to generate.
    path_length : int, optional
        Maximum length of each path. Default 5.
    weight : str or None, optional
        Edge attribute used as the transition weight. Default
        ``"weight"`` to match networkx (br-r37-c1-rygbm follow-up:
        the previous fnx default of ``None`` silently dropped edge
        weights and produced a uniform random walk where nx produces
        a weighted one). Pass ``weight=None`` for the legacy uniform
        behaviour.
    seed : int or None, optional
    source : node or None, optional (keyword-only)
        Fixed starting node for every sampled walk. When ``None``
        (default), each walk starts from a uniformly random node.

    Yields
    ------
    list
        Each yield is a random walk path.
    """
    # NetworkX uses the numpy random-state decorator and samples from a
    # transition-probability matrix.  The Panther helper below implements that
    # contract exactly and also populates ``index_map`` with the same path ids.
    yield from _panther_generate_random_paths(
        G,
        sample_size,
        path_length=path_length,
        index_map=index_map,
        weight=weight,
        seed=seed,
        source=source,
    )


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
        ``result[u][v]`` is the shortest path from u to v.

    br-r37-c1-9l73c: the local
    ``dict(all_pairs_bellman_ford_path(...))`` short-circuit
    produced inner-dict keys in BF-tree-discovery order, which
    differed from nx's johnson algorithm-specific Dijkstra-from-
    node iteration order (e.g. inner[a] keys ['a','b','d','c'] vs
    nx ['a','b','c','d']). br-r37-c1-gb8sj routes only the
    non-negative simple-graph subset to the native all-pairs
    Dijkstra path kernel, whose finalize order matches nx's
    Johnson Dijkstra order. Negative/callable/non-string/multi-
    graph/view/non-fnx cases remain delegated to nx Johnson.
    br-r37-c1-f61lr extends the native route only to exact DiGraph rows whose
    finite numeric weights include a negative edge and whose synced Rust attrs
    are all integer-typed, preserving the proof surface for tie/order parity.
    """
    if type(G) in (Graph, DiGraph) and isinstance(weight, str):
        fast_result = None
        if _native_check_dijkstra_weights_fast is not None and not G.is_multigraph():
            try:
                fast_result = _native_check_dijkstra_weights_fast(G, weight)
            except Exception:
                fast_result = None
        if fast_result is not None:
            has_negative, has_nonfinite, has_nonnumeric = fast_result
            if not (has_negative or has_nonfinite or has_nonnumeric):
                return dict(all_pairs_dijkstra_path(G, weight=weight))
            if (
                type(G) is DiGraph
                and has_negative
                and not has_nonfinite
                and not has_nonnumeric
            ):
                _sync_rust_edge_attrs(G)
                if _sp_edge_weights_all_int(G, weight):
                    return _raw_johnson_path_directed(G, weight=weight)
        elif not _should_delegate_dijkstra_to_networkx(G, weight):
            return dict(all_pairs_dijkstra_path(G, weight=weight))
    return _johnson_inproc(G, weight=weight)


def _johnson_inproc(G, weight="weight"):
    """In-process Johnson algorithm matching NetworkX."""
    dist = {v: 0 for v in G}
    pred = {v: [] for v in G}
    weight_fn = _weight_function(G, weight)

    dist_bellman = _bellman_ford_inproc(G, list(G), weight_fn, pred=pred, dist=dist)

    def new_weight(u, v, d):
        return weight_fn(u, v, d) + dist_bellman[u] - dist_bellman[v]

    def dist_path(v):
        paths = {v: [v]}
        _dijkstra_multisource_inproc(G, [v], new_weight, paths=paths)
        return paths

    return {v: dist_path(v) for v in G}


# ---------------------------------------------------------------------------
# Spectral & Matrix (numpy/scipy) — br-ulw
# ---------------------------------------------------------------------------


def bethe_hessian_matrix(G, r=None, nodelist=None):
    """Return the Bethe Hessian matrix: H(r) = (r^2-1)*I - r*A + D.

    br-bethedef: nx's default regularizer is
    ``r = sum(d_i^2)/sum(d_i) - 1`` (Le & Levina 2015). fnx used
    ``max(sqrt(mean(degree)), 1.0)`` which produced a different matrix
    whenever the default was requested — on path(5) fnx's r was
    ~1.265 (giving diag entry 2.6) vs nx's r=0.75 (giving diag 1.5625).
    Match nx's formula exactly.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph') — reject MG/DiGraph inputs.
    """
    import numpy as np
    import scipy.sparse

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # nx's bethe_hessian_matrix mixes weighted and unweighted quantities:
    # A and D come from the weighted adjacency (weight='weight'), but the
    # default regularizer r is computed from unweighted node degrees via
    # nx.degree(G). Match that mix exactly.
    default_nodelist = nodelist is None
    if default_nodelist:
        nodelist = list(G.nodes())
    # br-r37-c1-betheadj: pin dtype=float and, for the default node order, pass
    # nodelist=None so to_scipy_sparse_array takes its NATIVE weighted COO fast
    # path (the str-weight + dtype=None default falls back to per-edge G[u][v]
    # Python reads — ~2x of bethe's runtime). The matrix is byte-identical:
    # default order == G.nodes() order, and the H formula's ``r * A`` is float
    # regardless of A's dtype. ~2x faster.
    A = to_scipy_sparse_array(
        G,
        nodelist=None if default_nodelist else nodelist,
        dtype=float,
        format="csr",
    )
    n = A.shape[0]
    d = np.asarray(A.sum(axis=1)).flatten()
    # Use sparse *arrays* throughout (not legacy matrices) so the final
    # product preserves nx's csr_array return type.
    D = scipy.sparse.diags_array(d, dtype=float)
    if r is None:
        # br-r37-c1-smetricdegcache: dict(G.degree()) once instead of
        # per-node G.degree(v) PyO3 calls.
        deg_dict = dict(G.degree())
        unweighted_degs = [deg_dict[v] for v in nodelist]
        deg_sum = sum(unweighted_degs)
        # nx computes r = sum(d^2)/sum(d) - 1 with NO zero guard, so an
        # all-zero-degree graph (e.g. a single isolated node) raises
        # ZeroDivisionError. Match that contract exactly — do not fall back
        # to r=1.0, which silently returned a Laplacian where nx raises.
        r = sum(x * x for x in unweighted_degs) / deg_sum - 1
    I = scipy.sparse.eye_array(n)
    return ((r**2 - 1) * I - r * A + D).tocsr()


def bethe_hessian_spectrum(G, r=None):
    """Return sorted eigenvalues of the Bethe Hessian matrix."""
    import numpy as np

    H = bethe_hessian_matrix(G, r=r)
    return np.sort(np.linalg.eigvalsh(H.toarray()))


def google_matrix(
    G,
    alpha=0.85,
    personalization=None,
    nodelist=None,
    weight="weight",
    dangling=None,
):
    """Return the Google PageRank matrix: alpha*S + (1-alpha)*v*e^T.

    br-matsig: adds the ``dangling`` parameter nx exposes (weights used
    to redistribute mass from dangling nodes instead of the uniform
    teleport). Previously fnx rejected ``dangling=`` with a TypeError.
    """
    import numpy as np

    # br-r37-c1 (cc, verify phase): the google_matrix_rust native routing was a
    # MEASURED 3x REGRESSION (0.34x vs nx, gnp(500,.05): fnx 15.6ms vs nx 5.5ms).
    # The kernel returns a Python list-of-lists; the np.asarray conversion of n^2
    # floats dwarfs nx's pure-numpy path. The numpy path below (0.80x) is much
    # better. Reverted. (The dangling-redistribution bug fix below is retained.)
    if nodelist is None:
        nodelist = list(G.nodes())
    n = len(nodelist)
    if n == 0:
        # br-r37-c1-ct24s: nx returns to_numpy_array's 0 x 0 (np.array([[]]) is 1 x 0).
        return np.zeros((0, 0))
    A = to_numpy_array(G, nodelist=nodelist, weight=weight)
    row_sums = A.sum(axis=1)

    if personalization is None:
        v = np.ones(n) / n
    else:
        v = np.array([personalization.get(node, 0) for node in nodelist], dtype=float)
        s = v.sum()
        v = v / s if s > 0 else np.ones(n) / n

    # br-r37-c1-gmdangling: nx redistributes a dangling node's mass using the
    # dangling vector if given, otherwise the PERSONALIZATION vector v (NOT a
    # uniform 1/n). Previously fnx used 1/n for dangling rows, diverging from nx
    # whenever a dangling node coexisted with a non-uniform personalization.
    if dangling is None:
        dangling_weights = v
    else:
        dangling_weights = np.array(
            [dangling.get(node, 0) for node in nodelist], dtype=float
        )
        total = dangling_weights.sum()
        dangling_weights = dangling_weights / total if total > 0 else v

    # br-gmvec: vectorize the per-row Python normalization loop (was a
    # ``for i in range(n)`` over the dense n x n matrix — 0.38-0.81x vs nx,
    # whose google_matrix is fully numpy). Divide every row by its sum (using
    # 1.0 for dangling rows to avoid div-by-zero; those rows are all-zero so the
    # quotient stays zero), then overwrite the dangling rows with the RAW
    # dangling vector — byte-identical to the loop above (which used the raw,
    # un-renormalized ``dangling_weights`` for dangling rows, unlike nx's
    # re-divide). Verified np.array_equal over 30 configs incl. personalization +
    # dangling on sparse directed graphs. 1.06-1.22x vs nx.
    dangling_idx = np.where(row_sums == 0)[0]
    safe_sums = row_sums.copy()
    safe_sums[dangling_idx] = 1.0
    S = A / safe_sums[:, np.newaxis]
    if dangling_idx.size:
        S[dangling_idx] = dangling_weights
    return alpha * S + (1 - alpha) * v[np.newaxis, :]


def normalized_laplacian_spectrum(G, weight="weight"):
    """Return sorted eigenvalues of the normalized Laplacian."""
    import numpy as np

    edgeless_values = _edgeless_normalized_laplacian_spectrum_sorted_value_safe(
        G, weight
    )
    if edgeless_values is not None:
        return edgeless_values

    complete_values = _complete_normalized_laplacian_spectrum_sorted_value_safe(
        G, weight
    )
    if complete_values is not None:
        return complete_values

    star_values = _star_normalized_laplacian_spectrum_sorted_value_safe(G, weight)
    if star_values is not None:
        return star_values

    path_values = _path_normalized_laplacian_spectrum_sorted_value_safe(G, weight)
    if path_values is not None:
        return path_values

    cycle_values = _cycle_normalized_laplacian_spectrum_sorted_value_safe(G, weight)
    if cycle_values is not None:
        return cycle_values

    complete_bipartite_values = (
        _complete_bipartite_normalized_laplacian_spectrum_sorted_value_safe(G, weight)
    )
    if complete_bipartite_values is not None:
        return complete_bipartite_values

    NL = normalized_laplacian_matrix(G, weight=weight)
    # A negative or non-finite weight puts nan in the matrix; networkx's
    # scipy.linalg.eigvalsh rejects it with ValueError (br-r37-c1-63v34).
    return np.sort(np.linalg.eigvalsh(np.asarray_chkfinite(NL.toarray())))


def _edgeless_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0 or G.number_of_edges() != 0:
        return None

    import numpy as np

    return np.zeros(n, dtype=np.float64)


def _complete_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n == 0:
        return None
    native = getattr(G, "_native_is_complete_unweighted_graph", None)
    if native is not None:
        if not native(weight):
            return None
    else:
        if G.number_of_edges() != n * (n - 1) // 2:
            return None
        for _, degree in G.degree():
            if degree != n - 1:
                return None
        if isinstance(weight, str):
            for _, _, attrs in G.edges(data=True):
                if weight in attrs:
                    return None

    import numpy as np

    values = np.empty(n, dtype=np.float64)
    values[0] = 0.0
    if n > 1:
        values[1:] = float(n) / float(n - 1)
    return values


def _star_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n <= 2 or G.number_of_edges() != n - 1:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    center_count = 0
    leaf_count = 0
    for _, degree in G.degree():
        if degree == n - 1:
            center_count += 1
        elif degree == 1:
            leaf_count += 1
        else:
            return None
    if center_count != 1 or leaf_count != n - 1:
        return None

    import numpy as np

    values = np.ones(n, dtype=np.float64)
    values[0] = 0.0
    values[-1] = 2.0
    return values


def _path_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n <= 2 or G.number_of_edges() != n - 1:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    leaves = []
    for node, degree in G.degree():
        if degree == 1:
            leaves.append(node)
        elif degree != 2:
            return None
    if len(leaves) != 2:
        return None

    seen = {leaves[0]}
    stack = [leaves[0]]
    while stack:
        node = stack.pop()
        for neighbor in G.neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    if len(seen) != n:
        return None

    import numpy as np

    k = np.arange(n, dtype=np.float64)
    values = 1.0 - np.cos(np.pi * k / float(n - 1))
    values[0] = -0.0
    return values


def _cycle_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    if n < 3 or G.number_of_edges() != n:
        return None
    if isinstance(weight, str):
        for _, _, attrs in G.edges(data=True):
            if weight in attrs:
                return None

    start = None
    for node, degree in G.degree():
        if degree != 2:
            return None
        if start is None:
            start = node
    if start is None:
        return None

    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbor in G.neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    if len(seen) != n:
        return None

    import numpy as np

    k = np.arange(n, dtype=np.float64)
    return np.sort(1.0 - np.cos(2.0 * np.pi * k / float(n)))


def _complete_bipartite_normalized_laplacian_spectrum_sorted_value_safe(G, weight):
    if type(G) is not Graph or not (weight is None or isinstance(weight, str)):
        return None
    n = len(G)
    certificate_parts = _complete_bipartite_shape_certificate_parts(G, weight)
    if certificate_parts is None:
        native = getattr(G, "_native_complete_bipartite_unweighted_parts", None)
        if native is not None:
            if native(weight) is None:
                return None
        else:
            edge_count = G.number_of_edges()
            if n < 2 or edge_count == 0:
                return None
            if isinstance(weight, str):
                for _, _, attrs in G.edges(data=True):
                    if weight in attrs:
                        return None

            degrees = list(G.degree())
            start = degrees[0][0]
            colors = {start: 0}
            stack = [start]
            while stack:
                node = stack.pop()
                next_color = 1 - colors[node]
                for neighbor in G.neighbors(node):
                    color = colors.get(neighbor)
                    if color is None:
                        colors[neighbor] = next_color
                        stack.append(neighbor)
                    elif color != next_color:
                        return None
            if len(colors) != n:
                return None

            left_size = 0
            for color in colors.values():
                if color == 0:
                    left_size += 1
            right_size = n - left_size
            if left_size == 0 or right_size == 0 or edge_count != left_size * right_size:
                return None

            for node, degree in degrees:
                expected = right_size if colors[node] == 0 else left_size
                if degree != expected:
                    return None

    import numpy as np

    values = np.ones(n, dtype=np.float64)
    values[0] = 0.0
    values[-1] = 2.0
    return values


def _complete_bipartite_shape_certificate_parts(G, weight):
    certificate = vars(G).get("_fnx_complete_bipartite_shape")
    if certificate is None:
        return None
    try:
        nodes_seq, edges_seq, left_size, right_size = certificate
    except (TypeError, ValueError):
        return None
    native = getattr(G, "_native_complete_bipartite_certificate_parts", None)
    if native is None:
        return None
    parts = native(weight, nodes_seq, edges_seq, left_size, right_size)
    # br-r37-c1-starcertattr (cc): same synced-weighted bug as the star cert -- the
    # native certificate uses edges_dirty, which a sync clears while the weights stay
    # in the store, so a synced weighted complete-bipartite graph was wrongly
    # certified unweighted (2nd normalized_laplacian_spectrum call returned the
    # unweighted spectrum). For weight=str only an attr-FREE graph is genuinely
    # unweighted; if any attr exists, drop the certification -> caller takes the
    # weighted route. (O(1) native graph_has_any_attrs; attr-free graphs keep the
    # closed-form fast path.)
    if parts is not None and isinstance(weight, str):
        try:
            if _fnx.graph_has_any_attrs(G) is not False:
                return None
        except Exception:
            return None
    return parts


def _directed_laplacian_not_implemented_guard(G):
    # nx decorators report multigraph before undirected for MultiGraph inputs.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")


def _directed_transition_matrix(G, nodelist, weight, walk_type, alpha):
    """nx's `_transition_matrix`, in-process over fnx's NATIVE
    to_scipy_sparse_array / is_strongly_connected / is_aperiodic. The only
    eigensolve is in the callers (the Perron vector); this builds P exactly as nx
    does, so the downstream `eigs(P.T)` matches."""
    import numpy as _np
    import scipy as _sp

    if walk_type is None:
        if is_strongly_connected(G):
            walk_type = "random" if is_aperiodic(G) else "lazy"
        else:
            walk_type = "pagerank"

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
    n, m = A.shape
    if walk_type in ("random", "lazy"):
        DI = _sp.sparse.dia_array((1.0 / A.sum(axis=1), 0), shape=(n, n)).tocsr()
        if walk_type == "random":
            P = DI @ A
        else:
            ident = _sp.sparse.eye_array(n, format="csr")
            P = (ident + DI @ A) / 2.0
    elif walk_type == "pagerank":
        if not (0 < alpha < 1):
            raise NetworkXError("alpha must be between 0 and 1")
        A = A.toarray()
        A[A.sum(axis=1) == 0, :] = 1 / n
        A = A / A.sum(axis=1)[_np.newaxis, :].T
        P = alpha * A + (1 - alpha) / n
    else:
        raise NetworkXError("walk_type must be random, lazy, or pagerank")
    return P


def directed_laplacian_matrix(
    G, nodelist=None, weight="weight", walk_type=None, alpha=0.95
):
    """Return the directed Laplacian matrix of G.

    br-r37-c1-dirlapnative: computed in-process from nx's exact Chung directed
    Laplacian (native transition matrix + the single Perron-vector `eigs(P.T)`),
    dropping the per-call fnx->nx conversion. The Perron vector is normalized by
    `v / v.sum()` (sign-/scale-unique), so the result is deterministic and
    byte-matches nx in its defined domain (verified 0/480 over walk_type=None /
    pagerank / strong+random/lazy; the only divergent combo — forced random/lazy
    on a non-strongly-connected graph — is mathematically undefined and
    NON-deterministic in nx itself). The old delegation note (brittle to
    reproduce) is superseded.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _directed_laplacian_not_implemented_guard(G)
    import numpy as _np
    import scipy as _sp

    P = _directed_transition_matrix(G, nodelist, weight, walk_type, alpha)
    n, m = P.shape
    evals, evecs = _sp.sparse.linalg.eigs(P.T, k=1)
    v = evecs.flatten().real
    p = v / v.sum()
    sqrtp = _np.sqrt(_np.abs(p))
    Q = (
        _sp.sparse.dia_array((sqrtp, 0), shape=(n, n)).tocsr()
        @ P
        @ _sp.sparse.dia_array((1.0 / sqrtp, 0), shape=(n, n)).tocsr()
    )
    ident = _np.identity(len(G))
    return ident - (Q + Q.T) / 2.0


def directed_combinatorial_laplacian_matrix(
    G, nodelist=None, weight="weight", walk_type=None, alpha=0.95
):
    """Return the directed combinatorial Laplacian: ``Phi - (Phi P + P^T Phi)/2``.

    br-r37-c1-dirlapnative: in-process via the same native transition matrix +
    Perron vector as ``directed_laplacian_matrix`` (byte-matches nx in its defined
    domain), dropping the per-call fnx->nx conversion.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _directed_laplacian_not_implemented_guard(G)
    import scipy as _sp

    P = _directed_transition_matrix(G, nodelist, weight, walk_type, alpha)
    n, m = P.shape
    evals, evecs = _sp.sparse.linalg.eigs(P.T, k=1)
    v = evecs.flatten().real
    p = v / v.sum()
    Phi = _sp.sparse.dia_array((p, 0), shape=(n, n)).toarray()
    return Phi - (Phi @ P + P.T @ Phi) / 2.0


def attr_matrix(
    G,
    edge_attr=None,
    node_attr=None,
    normalized=False,
    rc_order=None,
    dtype=None,
    order=None,
):
    """Construct a matrix from edge attributes.

    When *node_attr* is given, nodes are grouped by attribute value and the
    matrix has size ``len(unique_attr_values)`` with entries summed over
    nodes sharing the same attribute.  *rc_order* then specifies the
    ordering of attribute values, not nodes.

    br-r37-c1-attrmtx: nx requires the named ``edge_attr`` / ``node_attr``
    to be present on every edge / node and raises ``KeyError`` when
    missing.  fnx previously used ``.get(attr, default)`` which silently
    swallowed missing attrs and returned a default-1 / node-as-label
    matrix — masking caller bugs.  Mirror nx's exact subscript pattern
    (``data[edge_attr]`` / ``G.nodes[u][node_attr]``) and support
    callable values too.
    """
    import numpy as np

    # br-r37-c1-attrmtxcoo: vectorised fast path for the common case
    # (node_attr=None, simple Graph/DiGraph, edge_attr None or "weight"). The
    # general path below builds per-edge attr dicts via to_edgelist_simple (~8ms
    # @1500 edges) and scatters with scalar ``M[i,j] += value`` (~8ms more) —
    # ~2x slower than nx. Instead read native f64 COO arrays in the rc/node
    # ordering (adjacency_nodelist_typed_arrays remaps endpoints) and scatter
    # vectorised with np.add.at. attr_matrix's M is float64 (np.zeros default)
    # unless dtype is pinned, so no int/float inference is needed; the undirected
    # COO is already symmetric. ~3.3x self-speedup, beats nx.
    if (
        node_attr is None
        and not callable(edge_attr)
        and (edge_attr is None or edge_attr == "weight")
        and not G.is_multigraph()
        and type(G) in (Graph, DiGraph)
        and _native_adjacency_nodelist_typed_arrays is not None
        # br-r37-c1-64xcg: the native scatter drops an edge whose endpoint is
        # not in rc_order; networkx raises KeyError, so such a call takes the
        # loop below, which raises it.
        and (rc_order is None or not any(G.degree(x) for x in set(G).difference(rc_order)))
    ):
        _ordering = list(rc_order) if rc_order is not None else list({n for n in G})
        _N = len(_ordering)
        # edge_attr=None => unit weights regardless of any "weight" attr: probe a
        # sentinel attr no edge carries so every value defaults to 1.0.
        _wattr = "weight" if edge_attr == "weight" else "\x00__fnx_attr_matrix_unit__"
        _sync_rust_edge_attrs(G, edge_only=True)
        _res = _native_adjacency_nodelist_typed_arrays(G, _ordering, _wattr, 1.0)
        if _res is not None:
            _rows, _cols, _data, _ = _res
            M = np.zeros((_N, _N), dtype=dtype, order=order)
            np.add.at(
                M,
                (
                    np.asarray(_rows, dtype=np.intp),
                    np.asarray(_cols, dtype=np.intp),
                ),
                np.asarray(_data, dtype=M.dtype),
            )
            if normalized:
                # br-r37-c1-6zlfk: nx's in-place division - a row with no
                # edges is 0/0, NaN (the old code divided it by 1).
                M /= M.sum(axis=1).reshape((M.shape[0], 1))
            if rc_order is None:
                return M, _ordering
            return M

    # br-r37-c1-attrmtx: build edge / node value resolvers matching nx.
    # ``None`` -> default semantics; ``callable`` -> user-supplied;
    # ``str`` -> direct subscript that raises KeyError on missing.
    # nx special-cases ``edge_attr == "weight"`` with a default of 1
    # (so unweighted graphs still work when the canonical "weight"
    # name is asked for); other named attrs MUST exist on every edge.
    if edge_attr is None:
        if G.is_multigraph():
            def edge_value(u, v):
                return len(G[u][v])
        else:
            def edge_value(u, v):
                return 1
    elif callable(edge_attr):
        edge_value = edge_attr
    elif edge_attr == "weight":
        if G.is_multigraph():
            def edge_value(u, v):
                return sum(d.get("weight", 1) for d in G[u][v].values())
        else:
            def edge_value(u, v):
                return G[u][v].get("weight", 1)
    else:
        if G.is_multigraph():
            def edge_value(u, v):
                return sum(d[edge_attr] for d in G[u][v].values())
        else:
            def edge_value(u, v):
                return G[u][v][edge_attr]

    if node_attr is None:
        def node_value(u):
            return u
    elif callable(node_attr):
        node_value = node_attr
    else:
        def node_value(u):
            return G.nodes[u][node_attr]

    if rc_order is None:
        ordering = list({node_value(n) for n in G.nodes()})
    else:
        ordering = list(rc_order)
    N = len(ordering)
    undirected = not G.is_directed()
    index = dict(zip(ordering, range(N)))
    M = np.zeros((N, N), dtype=dtype, order=order)

    # br-r37-c1-amdsnap: G.adjacency() is ~12× slower than G._adj.items()
    # because of AdjacencyView wrapping.  Same yield shape.
    if node_attr is None and type(G) in (Graph, DiGraph):
        edgelist = _fnx.to_edgelist_simple(G)
        if edgelist is not None:
            for u, v, attrs in edgelist:
                # br-r37-c1-64xcg: an endpoint missing from rc_order raises
                # networkx's KeyError (it was skipped).
                i, j = index[u], index[v]
                if edge_attr is None:
                    value = 1
                elif callable(edge_attr):
                    value = edge_attr(u, v)
                elif edge_attr == "weight":
                    value = attrs.get("weight", 1)
                else:
                    value = attrs[edge_attr]
                M[i, j] += value
                if undirected:
                    M[j, i] = M[i, j]
            if normalized:
                # br-r37-c1-6zlfk: nx's in-place division (a 0 row is NaN).
                M /= M.sum(axis=1).reshape((M.shape[0], 1))

            if rc_order is None:
                return M, ordering
            return M

    seen = set()
    # br-r37-c1-nodekeys: per-node native O(deg) rows (G[u]) instead of
    # G._adj.items() — the AdjacencyView's .items() re-materialises the whole
    # adjacency per node on a MultiGraph (O(N*(N+E)) -> TIMEOUT). Node order
    # (== G._adj order) is preserved; the matrix is endpoint-order-invariant.
    for u in G:
        nbrdict = G[u]
        for v in nbrdict:
            # br-r37-c1-64xcg: a missing node attribute, or a value missing
            # from rc_order, raises networkx's KeyError (the pair was skipped).
            i, j = index[node_value(u)], index[node_value(v)]
            if v not in seen:
                M[i, j] += edge_value(u, v)
                if undirected:
                    M[j, i] = M[i, j]
        if undirected:
            seen.add(u)

    if normalized:
        # br-r37-c1-6zlfk: nx's in-place division (a 0 row is NaN).
        M /= M.sum(axis=1).reshape((M.shape[0], 1))

    if rc_order is None:
        return M, ordering
    return M


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
    # br-costint: nx preserves int when all factors are int, so no float() cast.
    #
    # br-r37-c1-txgb4: iterate the GRAPH's edges, exactly as nx does
    # (``sum(flowDict[u][v] * d.get(weight, 0) for u, v, d in G.edges(data=True))``).
    # The previous implementation walked flowDict instead, which diverged from nx
    # two ways — the second a SILENT WRONG VALUE:
    #
    #   * an edge of G absent from flowDict scored 0; nx raises KeyError(u), so a
    #     partial flow dict was accepted and quietly under-counted;
    #   * on a MultiDiGraph with PARALLEL edges and an unkeyed flowDict, nx yields
    #     each parallel edge from edges(data=True) and sums 2*3 + 2*5 = 16. fnx
    #     read ``G.get_edge_data(u, v)`` — a ``{key: attrs}`` mapping for a
    #     multigraph — found no ``weight`` inside it, and returned 0.
    #
    # The keyed-flow-dict form (``flowDict[u][v][key]``) is a DELIBERATE fnx
    # extension: nx raises TypeError on it, but fnx's own network_simplex emits
    # that shape for multigraphs and test_flow_conformance_matrix locks it. It is
    # kept, and now scores each parallel edge against ITS OWN key instead of
    # collapsing them.
    if G.is_multigraph():
        total = 0
        for u, v, key, data in G.edges(keys=True, data=True):
            flow = flowDict[u][v]
            total = total + (flow[key] if isinstance(flow, dict) else flow) * data.get(
                weight, 0
            )
        return total
    return sum(flowDict[u][v] * d.get(weight, 0) for u, v, d in G.edges(data=True))


def _mcf_inputs_all_integral(G, demand, capacity, weight, _fastg=None):
    """br-mcfint: nx.min_cost_flow and nx.network_simplex preserve int
    flow values when every demand, capacity, and weight on the graph
    is an integer. fnx's Python implementation widens via ``float(...)``
    casts, so the flow dict comes back with float values. Detect the
    all-int-input case so callers can coerce the flow dict back to
    int for exact nx parity.
    """
    import numbers as _numbers

    def _is_int(x):
        # br-r37-c1-8foqi: fast path for plain Python ints (``type is int``
        # excludes bool, the common case) before the slow numbers.Integral ABC
        # check (which dominated min_cost_flow setup — 78k ABC instancechecks).
        return type(x) is int or (
            isinstance(x, _numbers.Integral) and not isinstance(x, bool)
        )

    # br-r37-c1-8foqi: read node/edge attrs from the pre-extracted _FastG shim
    # when available (one native bulk read shared with the solver) instead of
    # re-walking G.nodes[node] / G.edges(data=True) per element.
    if _fastg is not None:
        node_attr_iter = _fastg._nattr.values()
        edge_iter = ((e[-1]) for e in _fastg._edges)
    else:
        node_attr_iter = (
            G.nodes[node] if hasattr(G.nodes, "__getitem__") else {}
            for node in G.nodes()
        )
        edge_iter = (e[-1] for e in G.edges(data=True))
    for attrs in node_attr_iter:
        if isinstance(attrs, dict) and not _is_int(attrs.get(demand, 0)):
            return False
    for attrs in edge_iter:
        if not isinstance(attrs, dict):
            continue
        if not _is_int(attrs.get(capacity, 1)) or not _is_int(attrs.get(weight, 0)):
            return False
    return True


def _coerce_flow_dict_to_int(flow_dict):
    """Coerce a dict-of-dicts flow to int values (used when _mcf_inputs_all_integral)."""
    out = {}
    for u, inner in flow_dict.items():
        out[u] = {v: (int(f) if isinstance(f, float) and f.is_integer() else f)
                  for v, f in inner.items()}
    return out
