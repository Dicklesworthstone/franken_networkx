

def closeness_centrality(
    G,
    u=None,
    distance=None,
    wf_improved=True,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute closeness centrality for nodes.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    u : node, optional
        Return only the value for node u.
    distance : edge attribute key, optional
        Use the specified edge attribute as the edge distance.
    wf_improved : bool, optional (default=True)
        If True, use Wasserman-Faust improved formula for disconnected graphs.

    Returns
    -------
    dict or float
        Dictionary of nodes with closeness centrality as value, or a single
        float if u is specified.
    """
    _validate_backend_dispatch_keywords("closeness_centrality", backend, backend_kwargs)
    # br-r37-c1-y77dc: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-r37-c1-clsingle: a single-node request (u=...) on the standard
    # unweighted, wf_improved, undirected path previously delegated to networkx,
    # which paid a full fnx->nx graph conversion (O(V+E)) just to run one BFS --
    # ~25x SLOWER than nx for one node on n=1500. Compute the single BFS from u
    # directly instead. The total path length is a sum of INTEGER hop counts, so
    # the result is byte-identical to nx (and to _raw_closeness_centrality[u]).
    # br-r37-c1-closedir: directed single-u closeness previously delegated (the
    # gate was `not G.is_directed()`), ~2x nx. A directed graph's closeness of u
    # uses INCOMING distances — nx reverses G and runs single-source from u, i.e.
    # distances TO u, which `single_target_shortest_path_length` computes directly
    # in the same finalisation order. Integer hop sum -> byte-identical (600/600).
    if u is not None and u not in G:
        raise NodeNotFound(f"Source {u} is not in G")

    if u is not None and distance is None:
        sp = (
            single_target_shortest_path_length(G, u)
            if G.is_directed()
            else single_source_shortest_path_length(G, u)
        )
        totsp = sum(sp.values())
        len_G = len(G)
        closeness = 0.0
        if totsp > 0.0 and len_G > 1:
            closeness = (len(sp) - 1.0) / totsp
            if wf_improved:
                closeness *= (len(sp) - 1.0) / (len_G - 1)
        return closeness

    if u is not None and distance is not None:
        if G.is_directed() and G.is_multigraph() and isinstance(distance, str):
            _simple, _delegate = _multigraph_collapse_min_weight(G, distance)
            H = G.reverse() if _delegate else _simple.reverse()
        else:
            H = G.reverse() if G.is_directed() else G
        sp = single_source_dijkstra_path_length(H, u, weight=distance)
        totsp = sum(sp.values())
        len_G = len(G)
        closeness = 0.0
        if totsp > 0.0 and len_G > 1:
            closeness = (len(sp) - 1.0) / totsp
            if wf_improved:
                closeness *= (len(sp) - 1.0) / (len_G - 1)
        return closeness

    if distance is not None and u is None:
        H = G.reverse() if G.is_directed() else G
        apl = dict(all_pairs_dijkstra_path_length(H, weight=distance))
        len_G = len(H)
        closeness_dict = {}
        for n in H:
            sp = apl.get(n, {n: 0})
            totsp = sum(sp.values())
            cc = 0.0
            if totsp > 0.0 and len_G > 1:
                cc = (len(sp) - 1.0) / totsp
                if wf_improved:
                    cc *= (len(sp) - 1.0) / (len_G - 1)
            closeness_dict[n] = cc
        return closeness_dict

    # The native kernel (incoming distances for a DiGraph, as networkx reverses
    # G). wf_improved=False only skips the per-node Wasserman-Faust multiply;
    # it used to run a Python loop over all_pairs_shortest_path_length, 3.0x
    # networkx where the default is 144x (br-r37-c1-mub4s).
    return _raw_closeness_centrality(G, wf_improved=wf_improved)


def _edge_betweenness_centrality_inproc(
    G,
    k=None,
    normalized=True,
    weight=None,
    seed=None,
):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.centrality.betweenness.edge_betweenness_centrality(
            H,
            k=k,
            normalized=normalized,
            weight=weight,
            seed=seed,
            backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def edge_betweenness_centrality(
    G,
    k=None,
    normalized=True,
    weight=None,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute edge betweenness centrality for edges.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    k : int, optional
        Number of nodes to sample for approximation.
    normalized : bool, optional (default=True)
        If True, normalize by 2/(n(n-1)) for undirected or 1/(n(n-1)) for directed.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.
    seed : random state, optional
        Random seed for sampling when k is specified.

    Returns
    -------
    dict
        Dictionary of edges with betweenness centrality as value.
    """
    # networkx's @py_random_state resolves - and validates - the seed before
    # anything else, and draws from it only to sample k sources; with k=None
    # it must not route the call (br-r37-c1-quim8, as betweenness_centrality).
    rng = _create_py_random_state(seed)
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "edge_betweenness_centrality", backend, backend_kwargs
    )

    # A simple Graph / DiGraph runs the native edge Brandes: BFS, or Dijkstra
    # (br-r37-c1-4v1mt) for a string `weight` whose values are all finite,
    # non-negative built-ins within the exact integer envelope, over
    # every node or, with k, over the sources networkx samples, in its order,
    # normalized or not, rescaled as networkx's _rescale does
    # (br-r37-c1-f0uiy; the k path used to go through the SUBSET kernel,
    # whose association and two-step rescale put the last bit of 37-58% of
    # the values off networkx's). A callable or out-of-contract weight and a
    # multigraph - networkx keys it by (u, v, key) with a value per parallel
    # edge (br-gauntlet-ebc-multi) - run networkx's port.
    native = not G.is_multigraph() and (weight is None or isinstance(weight, str))
    if native and weight is not None:
        native = not _should_delegate_dijkstra_to_networkx(G, weight)
        if native:
            _sync_rust_edge_attrs(G)
    if not native:
        return _edge_betweenness_centrality_inproc(
            G,
            k=k,
            normalized=normalized,
            weight=weight,
            seed=seed,
        )
    sources = None
    # Edge normalization retained _rescale_e through 3.5, one release later
    # than the node estimator. That caller never passes k to _rescale_e:
    # sampling changes the sources but not the old scale or its association.
    source_aware = _networkx_release() >= (3, 6)
    if k is not None:
        # networkx samples even when k == len(G): the draws, and the order the
        # sources are summed in, are the sample's.
        sources = rng.sample(list(G.nodes()), k)
        if not isinstance(sources, list):
            # br-r37-c1-cdf1v: a numpy RandomState's wrapper returns an ndarray.
            sources = sources.tolist()
        if not sources and source_aware and len(G) >= 2:
            raise ZeroDivisionError("division by zero")
    # br-r37-c1-pi615: the Rust dict is keyed canonically (smaller first);
    # networkx keys by G.edges() traversal, in that order and direction.
    raw = _raw_edge_betweenness_centrality(
        G, sources, weight, normalized, source_aware=source_aware
    )
    reordered = {}
    for u, v in G.edges():
        if (u, v) in raw:
            reordered[(u, v)] = raw[(u, v)]
        elif (v, u) in raw:
            reordered[(u, v)] = raw[(v, u)]
    return reordered


def _katz_centrality_scipy(G, alpha, beta, max_iter, tol, nstart, normalized, weight):
    """scipy.sparse matvec mirror of ``networkx.katz_centrality`` (br-r37-c1-katzscipy, cc).

    nx's Katz power iteration is ``x <- alpha * A^T x + beta`` (L2-normalised when
    ``normalized``), converging when the L1 delta < ``N * tol``. This rebuilds it on
    fnx's fast ``to_scipy_sparse_array`` instead of delegating to nx (the full conversion
    + nx's pure-Python loop made every non-default call 0.66-0.85x).
    """
    import numpy as _np

    nodelist = list(G)
    N = len(nodelist)
    if N == 0:
        return {}
    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
    a_t = A.T.tocsr()
    if nstart is None:
        x = _np.zeros(N)
    else:
        x = _np.array([nstart.get(v, 0) for v in nodelist], dtype=float)
    if isinstance(beta, dict):
        if set(beta) != set(nodelist):
            raise NetworkXError("beta dictionary must have a value for every node")
        b = _np.array([beta[v] for v in nodelist], dtype=float)
    else:
        b = _np.full(N, float(beta))

    for _ in range(max_iter):
        xlast = x
        x = alpha * (a_t @ xlast) + b
        if _np.absolute(x - xlast).sum() < N * tol:
            if normalized:
                norm = _np.hypot.reduce(x)
                if norm == 0:
                    norm = 1.0
                x = x / norm
            return dict(zip(nodelist, map(float, x)))
    raise PowerIterationFailedConvergence(max_iter)


def katz_centrality_many(
    G,
    betas,
    alpha=0.1,
    max_iter=1000,
    tol=1.0e-6,
    normalized=True,
    weight=None,
    *,
    workers=None,
):
    """Compute many Katz centrality vectors over one shared sparse transpose.

    This is the batched equivalent of::

        [katz_centrality(G, beta=beta, ...) for beta in betas]

    The graph is materialized as sparse adjacency once. Beta vectors are packed
    into dense blocks, so each sparse traversal advances many independent power
    iterations. Blocks share the immutable sparse representation and run on a
    persistent worker pool. Results retain the input order of ``betas``.

    ``workers=None`` uses four workers when the batch has at least four queries.
    Sparse matrix multiplication is memory-bandwidth-bound, so callers can use
    the explicit knob to tune a host without oversubscribing its memory channels.
    ``workers=1`` keeps block execution serial while still eliminating repeated
    graph materialization and per-query sparse scans.
    """
    import concurrent.futures as _concurrent_futures

    import numpy as _np

    G = _coerce_arg_to_fnx_graph(G)
    max_iter = _coerce_index_arg(max_iter, "max_iter")
    queries = list(betas)
    if not queries:
        return []
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    if workers is None:
        # Four workers were the wall-time optimum for this matvec family on the
        # 64-core benchmark host. More workers competed for the same sparse
        # arrays and slowed the complete batch despite higher CPU consumption.
        worker_count = min(4, len(queries))
    else:
        worker_count = _coerce_index_arg(workers, "workers")
        if worker_count < 1:
            raise ValueError("workers must be greater than 0")
        worker_count = min(worker_count, len(queries))

    nodelist = list(G)
    N = len(nodelist)
    if N == 0:
        return [{} for _ in queries]
    if isinstance(weight, str):
        _sync_rust_edge_attrs(G, edge_only=True)

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
    a_t = A.T.tocsr()
    node_set = set(nodelist)

    # Balance one block per worker for ordinary batches. Very large batches are
    # capped at 32 columns per block so temporary dense storage stays bounded;
    # the persistent pool consumes later blocks in input order.
    block_width = min(32, (len(queries) + worker_count - 1) // worker_count)
    blocks = [
        (start, min(start + block_width, len(queries)))
        for start in range(0, len(queries), block_width)
    ]

    def _solve_block(bounds):
        start, end = bounds
        width = end - start
        b = _np.empty((N, width), dtype=float)
        for local_query, beta in enumerate(queries[start:end]):
            if isinstance(beta, dict):
                if set(beta) != node_set:
                    raise NetworkXError(
                        "beta dictionary must have a value for every node"
                    )
                b[:, local_query] = [beta[node] for node in nodelist]
            else:
                b[:, local_query].fill(float(beta))

        x = _np.zeros_like(b)
        answers = [None] * width
        active = _np.ones(width, dtype=bool)
        for _ in range(max_iter):
            xlast = x
            x = alpha * (a_t @ xlast) + b
            errors = _np.absolute(x - xlast).sum(axis=0)
            converged = _np.flatnonzero(active & (errors < N * tol))
            for local_query in converged:
                # Sparse-times-dense preserves each column's edge accumulation
                # order. Copy the strided column before normalization so the
                # reduction order also matches the single-vector implementation.
                vector = _np.ascontiguousarray(x[:, local_query])
                if normalized:
                    norm = _np.hypot.reduce(vector)
                    if norm == 0:
                        norm = 1.0
                    vector /= norm
                answers[local_query] = dict(zip(nodelist, map(float, vector)))
            active[converged] = False
            if not active.any():
                return answers
        raise PowerIterationFailedConvergence(max_iter)

    effective_workers = min(worker_count, len(blocks))
    if effective_workers == 1:
        solved_blocks = [_solve_block(block) for block in blocks]
        return [answer for block in solved_blocks for answer in block]
    with _concurrent_futures.ThreadPoolExecutor(
        max_workers=effective_workers,
        thread_name_prefix="fnx-katz",
    ) as executor:
        solved_blocks = executor.map(_solve_block, blocks)
        return [answer for block in solved_blocks for answer in block]


def _katz_centrality_inproc(
    G,
    alpha=0.1,
    beta=1.0,
    max_iter=1000,
    tol=1.0e-6,
    nstart=None,
    normalized=True,
    weight=None,
):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.centrality.katz.katz_centrality(
            H,
            alpha=alpha,
            beta=beta,
            max_iter=max_iter,
            tol=tol,
            nstart=nstart,
            normalized=normalized,
            weight=weight,
            backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def katz_centrality(
    G,
    alpha=0.1,
    beta=1.0,
    max_iter=1000,
    tol=1.0e-6,
    nstart=None,
    normalized=True,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute Katz centrality for nodes.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    alpha : float, optional (default=0.1)
        Attenuation factor.
    beta : float or dict, optional (default=1.0)
        Weight attributed to immediate neighborhood.
    max_iter : int, optional (default=1000)
        Maximum iterations for power iteration.
    tol : float, optional (default=1e-6)
        Convergence tolerance.
    nstart : dict, optional
        Starting value of centrality for each node.
    normalized : bool, optional (default=True)
        If True, normalize values.
    weight : edge attribute key, optional
        Use the specified edge attribute as edge weight.

    Returns
    -------
    dict
        Dictionary of nodes with Katz centrality as value.
    """
    _validate_backend_dispatch_keywords("katz_centrality", backend, backend_kwargs)
    # br-r37-c1-y77dc: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-r37-c1-tqimg: nx is decorated with
    # @not_implemented_for('multigraph'); fnx silently accepted MG.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    # Delegate to NetworkX when non-default parameters are used
    if (
        alpha != 0.1
        or beta != 1.0
        or max_iter != 1000
        or tol != 1.0e-6
        or nstart is not None
        or not normalized
        or weight is not None
    ):
        # br-r37-c1-katzscipy (cc): scipy matvec mirror of nx's Katz power iteration
        # (x <- alpha * A^T x + beta) for the non-default case, replacing the fnx->nx
        # delegation (which paid the full conversion + nx's pure-Python loop: 0.66-0.85x).
        # Gated to simple Graph/DiGraph, str/None weight, dict/None nstart, scalar/dict beta.
        if (
            not G.is_multigraph()
            and isinstance(G, (Graph, DiGraph))
            and (weight is None or isinstance(weight, str))
            and (nstart is None or isinstance(nstart, dict))
            and isinstance(beta, (int, float, dict))
            and isinstance(normalized, bool)
        ):
            try:
                return _katz_centrality_scipy(
                    G, alpha, beta, max_iter, tol, nstart, normalized, weight
                )
            except PowerIterationFailedConvergence:
                raise
            except (ValueError, ZeroDivisionError, FloatingPointError, NetworkXError):
                pass
        return _katz_centrality_inproc(
            G,
            alpha=alpha,
            beta=beta,
            max_iter=max_iter,
            tol=tol,
            nstart=nstart,
            normalized=normalized,
            weight=weight,
        )
    # Use fast Rust implementation for standard case.
    # br-r37-c1-hc209: the binary install can lag behind the source change in
    # crates/fnx-python/src/algorithms.rs that passes ``err.iterations`` (int)
    # into ``PowerIterationFailedConvergence::new_err``. Older binaries
    # passed a pre-formatted message string, which nx's exception class then
    # double-formats. Catch and re-raise with the canonical helper so str(exc)
    # / args parity holds regardless of binary state.
    try:
        return _raw_katz_centrality(G)
    except PowerIterationFailedConvergence as exc:
        # Rust's max_iter is the same default as the Python wrapper.
        raise _make_power_iteration_failed_convergence(max_iter) from exc.__cause__


def _make_power_iteration_failed_convergence(max_iter):
    error = PowerIterationFailedConvergence.__new__(PowerIterationFailedConvergence)
    Exception.__init__(
        error,
        error,
        f"power iteration failed to converge within {max_iter} iterations",
    )
    return error


def hits(
    G,
    max_iter=100,
    tol=1.0e-8,
    nstart=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return HITS hubs and authorities values for nodes.

    br-hitsdelta: on karate_club_graph the values diverge from nx by
    ~1.6%, but experiments show the cause is karate_club_graph's
    edge-insertion-order mismatch (fnx's karate differs from nx's in
    node/edge ordering, affecting the SVD initial basis). On
    order-aligned graphs (explicit add_edge sequences) fnx.hits
    matches nx at machine precision. A full fix requires aligning
    fnx's karate_club_graph output exactly with nx. Queued as
    br-karateorder.

    br-r37-c1-hitsdegen: this implementation is byte-for-byte nx's
    algorithm — ``svds(A, k=1, v0=nstart)`` on the adjacency matrix,
    then ``A @ a`` for hubs.  When the top singular value of ``A`` is
    DEGENERATE (multiplicity > 1 — typical for disconnected directed
    graphs), ``svds`` returns an ARBITRARY vector from the multi-
    dimensional top singular subspace, selected by ARPACK's random
    ``v0``.  Both fnx and nx are then non-deterministic and can return
    negative / sign-flipped components that vary run-to-run with the
    global numpy RNG state (verified: nx.hits on such a graph gives
    different values on repeated calls).  This is an inherent property
    of HITS on ill-conditioned (degenerate) inputs, NOT an fnx/nx
    divergence — do not "fix" it to a deterministic vector, which would
    DIVERGE from nx's documented random-v0 behavior.  HITS is well-
    defined only when the dominant singular value is simple (e.g. a
    strongly/weakly connected graph).
    """
    _validate_backend_dispatch_keywords("hits", backend, backend_kwargs)

    import numpy as np
    import scipy as sp

    if len(G) == 0:
        return {}, {}

    A = adjacency_matrix(G, nodelist=list(G), dtype=float)

    if nstart is not None:
        nstart = np.array(list(nstart.values()))
    if max_iter <= 0:
        raise _make_power_iteration_failed_convergence(max_iter)

    try:
        _, _, vt = sp.sparse.linalg.svds(A, k=1, v0=nstart, maxiter=max_iter, tol=tol)
    except sp.sparse.linalg.ArpackNoConvergence as exc:
        raise _make_power_iteration_failed_convergence(max_iter) from exc

    authorities = vt.flatten().real
    hubs = A @ authorities
    if normalized:
        hubs /= hubs.sum()
        authorities /= authorities.sum()

    return (
        dict(zip(G, map(float, hubs))),
        dict(zip(G, map(float, authorities))),
    )


# ---------------------------------------------------------------------------
# Graph structural algorithms — pure Python over Rust primitives
# ---------------------------------------------------------------------------


def ego_graph(G, n, radius=1, center=True, undirected=False, distance=None):
    """Return the ego graph of node *n* within *radius* hops.

    br-egoedgeord: always compute the node set in Python and copy
    edges in G's original insertion order. The Rust fast-path
    ``_fnx.ego_graph_rust`` re-orients every edge with the ego node
    first (so ``(2, 1), (2, 3)`` instead of ``(1, 2), (2, 3)`` on
    ``fnx.path_graph(5)``), diverging from nx which preserves the
    input graph's edge orientation.
    """
    # br-r37-c1-egonotfound: nx delegates to
    # single_source_shortest_path_length / single_source_dijkstra,
    # both of which raise NodeNotFound("Source %s is not in G") on
    # missing source — not the NetworkXError that fnx surfaced via
    # G.neighbors(n).  Mirror nx's exception class and message.
    if n not in G:
        raise NodeNotFound(f"Source {n} is not in G")
    # br-r37-c1-egonan: NaN / +inf radius — nx routes through
    # single_source_shortest_path_length which short-circuits NaN
    # cutoff to source-only (matches the cycle 142 fix on the
    # Dijkstra cutoff family).  fnx's BFS uses ``depth >= radius``
    # which is False for NaN, so iteration never terminates the
    # depth check and yields the full reachable component.  Coerce
    # NaN to ``-1`` (so the immediate first ``depth >= radius``
    # check at depth 0 succeeds and only the source node is kept).
    import math as _math
    if isinstance(radius, float) and _math.isnan(radius):
        radius = -1
    # br-r37-c1-fauol: track BFS visit order (insertion order in
    # ``seen``) so the resulting ego graph's node order matches nx's
    # BFS-from-source ordering. Previously we collapsed to a set and
    # iterated arbitrary hash order.
    # br-r37-c1-77okh: networkx branches on ``undirected`` FIRST and only then on
    # ``distance``:
    #
    #     if undirected:
    #         ... single_source_{dijkstra,shortest_path_length}(G.to_undirected(), ...)
    #     else:
    #         ... the same two over G
    #
    # fnx had the tests the other way round, so ``undirected`` was consulted only
    # when ``distance`` was None AND the graph was directed. Two things were wrong.
    #
    # THE SERIOUS ONE: with a distance= given, ``undirected`` was ignored
    # ENTIRELY, so a directed graph searched out-edges only and LOST NODES.
    #
    #     D: a->b, c->a, b->d ; ego_graph(D,'a',radius=2.0,distance='weight',undirected=True)
    #     networkx -> ['a','b','c']        fnx -> ['a','b']       'c' vanished
    #
    # THE SUBTLER ONE: on an ALREADY-undirected graph, ``undirected=True`` sent
    # fnx down the plain-BFS path over G while networkx still searches
    # G.to_undirected() -- a fresh graph whose node insertion order can differ.
    # Since the ego node order is set-iteration order (br-r37-c1-mqq4m), that
    # changed node and edge ORDER on 1-6 of 18 cases at every PYTHONHASHSEED.
    #
    # Mirroring networkx's structure fixes both. The manual succ+pred walk that
    # used to serve the directed case is gone: it produced the right node SET but
    # not networkx's traversal ORDER, and order is observable here.
    # NOTE the search base is the undirected COPY, while the edges below are still
    # read from G -- exactly as networkx does, since it builds H from G.subgraph.
    search_base = G.to_undirected() if undirected else G
    if distance is not None:
        # Weighted ego: include nodes within weighted distance <= radius.
        sp = dict(
            single_source_dijkstra_path_length(search_base, n, weight=distance)
        )
        sp = {node: dist for node, dist in sp.items() if dist <= radius}
        ordered_nodes = list(sp.keys())  # already in distance order
        nodes_within = set(ordered_nodes)
    elif undirected:
        # Call the SAME function networkx calls, on the same base. A hand-rolled
        # BFS over search_base.neighbors() gets the node SET right but not
        # necessarily networkx's visit ORDER, and the ego node order is
        # set-iteration order over that result, so the order is observable.
        sp = dict(
            single_source_shortest_path_length(search_base, n, cutoff=radius)
        )
        ordered_nodes = list(sp.keys())
        nodes_within = set(ordered_nodes)
    else:
        # Plain BFS (directed or undirected) honouring radius.
        seen = {n: 0}
        queue = [n]
        while queue:
            next_queue = []
            for u in queue:
                depth = seen[u]
                if depth >= radius:
                    continue
                neighbors = (
                    G.successors(u) if G.is_directed() else G.neighbors(u)
                )
                for v in neighbors:
                    if v not in seen:
                        seen[v] = depth + 1
                        next_queue.append(v)
            queue = next_queue
        ordered_nodes = list(seen.keys())
        nodes_within = set(ordered_nodes)

    # br-r37-c1-fauol / br-r37-c1-mqq4m: nx.ego_graph is G.subgraph(sp).copy(),
    # so the node order is FilterAtlas.__iter__'s, and that rule has TWO
    # branches. fauol implemented only the second one:
    #
    #     node_ok_shorter = 2 * len(NODE_OK.nodes) < len(atlas)
    #     if node_ok_shorter:  (n for n in NODE_OK.nodes if n in atlas)
    #     else:                (n for n in atlas if NODE_OK(n))
    #
    # For an ego set small relative to the graph — the overwhelmingly common
    # case — networkx takes the FIRST branch, and ``NODE_OK.nodes`` is the SET
    # that ``show_nodes`` built, so the order is set-iteration order, not the
    # parent's. Scanning the parent produced the wrong order in 5 of 6 spot
    # checks (nx ['n3','n0','n171'] vs fnx ['n0','n3','n171']) AND made the
    # whole call O(parent): 0.044x vs networkx at N=32000, against 0.544x at
    # N=2000, because networkx is flat here and fnx was not.
    #
    # Taking the branch networkx takes fixes the order and the complexity at
    # once: it reads only the ego set. ``nodes_within`` is already the set built
    # from the BFS order, exactly as networkx's ``set(sp)`` is.
    if 2 * len(nodes_within) < len(G):
        ordered_nodes = [node for node in nodes_within if node in G]
    else:
        ordered_nodes = [node for node in G.nodes() if node in nodes_within]

    # br-r37-c1-s8w2p: SubgraphView class can't be empty-constructed.
    graph = _concrete_class_for(G)()
    graph.graph.update(dict(G.graph))
    for node in ordered_nodes:
        graph.add_node(node, **dict(G.nodes[node]))
    if G.is_multigraph():
        # br-r37-c1-9uod6: walk ONLY the ego nodes' rows, like the simple-graph
        # branch below, instead of materialising every edge in G and filtering
        # (O(E_total) for a handful of rows) — and emit them in the order
        # networkx does, which is NOT the parent row order.
        #
        # THE INNER ROW RULE DIFFERS BY CLASS, which is why this branch could not
        # simply mirror the one below and why it was left behind when
        # br-r37-c1-js9iw converted that one. nx builds the ego graph as
        # G.subgraph(sp).copy(), and for a MULTIGRAPH the inner row is a
        # FilterMultiInner whose NODE_OK HAS a `.nodes` attribute, so
        # FilterAtlas.__iter__ takes its keep-set-order branch whenever
        # 2 * len(keep) < len(row). For a simple Graph the inner row is a plain
        # FilterAtlas whose NODE_OK has NO `.nodes`, so it always iterates the
        # parent row. Read off networkx directly:
        #
        #     parent  G['n1']      ['n2','n19','n0','n3','n8','n6','n1']
        #     multi   sub['n1']    ['n1','n2','n0']   == keep-set order
        #     simple  sub['n1']    ['n2']             == parent row order
        #
        # so the existing note on _copy_induced_simple_fast ("the inner row
        # order needs no such handoff") is right for simple graphs and wrong
        # here. Reproducing the branch networkx takes gives 0 divergences over
        # 208 randomised ego graphs; the old whole-edge-list walk gave 19.
        directed = G.is_directed()
        seen = set()
        for u in ordered_nodes:
            adj_u = G[u]
            row = nodes_within if 2 * len(nodes_within) < len(adj_u) else adj_u
            for v in row:
                if v not in nodes_within or v not in adj_u:
                    continue
                if not directed and v in seen:
                    continue
                keydict = adj_u[v]
                for edge_key in keydict:
                    graph.add_edge(u, v, key=edge_key, **keydict[edge_key])
            # AFTER the row, so a self-loop still emits (br-r37-c1-6yimw).
            if not directed:
                seen.add(u)
    else:
        # br-r37-c1-js9iw: walk ONLY the ego nodes' adjacency (O(E_subgraph))
        # instead of materializing every edge in G (O(E_total)) and filtering.
        # Reproduces networkx's subgraph(nodes).copy() edge order exactly:
        # iterate subgraph nodes in G's node order, and for each its adjacency
        # order; undirected edges dedup via a `seen` set so each edge is emitted
        # from the node encountered first (matching nx's EdgeView contract).
        directed = G.is_directed()
        edges_to_add = []
        seen = set()
        for u in ordered_nodes:
            adj_u = G[u]
            for v in adj_u:
                if v not in nodes_within:
                    continue
                if not directed and v in seen:
                    continue
                data = adj_u[v]
                if data:
                    for attr_key in data:
                        if not isinstance(attr_key, str):
                            graph.add_edge(u, v, **data)
                            break
                    else:
                        edges_to_add.append((u, v, data))
                else:
                    edges_to_add.append((u, v))
            if not directed:
                seen.add(u)
        if edges_to_add:
            raw_add_edges_from = (
                _DIGRAPH_RAW_ADD_EDGES_FROM
                if graph.is_directed()
                else _GRAPH_RAW_ADD_EDGES_FROM
            )
            raw_add_edges_from(graph, edges_to_add)
    if not center and n in graph:
        graph.remove_node(n)
    # Always return fnx type for consistency.
    return graph


def _directed_core_number(G):
    """In-process Batagelj-Zaversnik core decomposition for directed graphs.

    Byte-exact reproduction of ``networkx.core_number`` for the directed
    contract (degree = in-degree + out-degree, antiparallel arcs counted
    separately) — see ``core_number``'s ``br-r37-c1-4i0ad`` note. Reads
    adjacency via fnx's native row accessors (``_native_predecessor_row_dict`` /
    ``_native_successor_row_dict``) which yield the IDENTICAL order as
    ``G.predecessors`` / ``G.successors`` (so ``all_neighbors`` ==
    ``chain(predecessors, successors)``) at a fraction of the AdjacencyView
    wrapper cost; nx-typed graphs fall back to the public API.
    """
    # nx rejects self-loops with NetworkXNotImplemented; use the native O(|E|)
    # check that already powers the undirected path.
    if number_of_selfloops(G) > 0:
        raise NetworkXNotImplemented(_self_loop_guard_for_core_family())

    nodes_list = list(G)
    _pred_row = getattr(G, "_native_predecessor_row_dict", None)
    _succ_row = getattr(G, "_native_successor_row_dict", None)
    if _pred_row is not None and _succ_row is not None:
        nbrs = {v: list(_pred_row(v)) + list(_succ_row(v)) for v in nodes_list}
    else:
        nbrs = {
            v: list(G.predecessors(v)) + list(G.successors(v))
            for v in nodes_list
        }

    # core starts as the degree dict (keyed in G-node order == nx's), mutated
    # in place; the alias mirrors nx's ``core = degrees`` exactly.
    core = {v: len(nbrs[v]) for v in nodes_list}
    nodes = sorted(core, key=core.get)
    bin_boundaries = [0]
    curr_degree = 0
    for i, v in enumerate(nodes):
        if core[v] > curr_degree:
            bin_boundaries.extend([i] * (core[v] - curr_degree))
            curr_degree = core[v]
    node_pos = {v: pos for pos, v in enumerate(nodes)}
    for v in nodes:
        for u in nbrs[v]:
            if core[u] > core[v]:
                nbrs[u].remove(v)
                pos = node_pos[u]
                bin_start = bin_boundaries[core[u]]
                node_pos[u] = bin_start
                node_pos[nodes[bin_start]] = pos
                nodes[bin_start], nodes[pos] = nodes[pos], nodes[bin_start]
                bin_boundaries[core[u]] += 1
                core[u] -= 1
    return core


def core_number(G):
    """Return the core number for each node of ``G``.

    br-coremg: nx.core_number is @not_implemented_for('multigraph',
    'directed_multigraph') and raises NetworkXNotImplemented for any
    multigraph input (and has a self-loop guard). The Rust Rust
    core_number accepted MultiGraph input silently. Gate upfront.

    br-r37-c1-dg2dn: nx also raises NetworkXNotImplemented when the
    graph has any self-loop ("Input graph has self loops which is
    not permitted; Consider using G.remove_edges_from(nx.selfloop_edges(G)).").
    The Rust path silently included self-loops in the degree _count
    and returned a value dict — propagating into k_core / k_shell /
    k_crust / k_corona, which all consume core_number.

    br-coredir: NetworkX's directed contract (per the docstring:
    "For directed graphs the node degree is defined to be the
    in-degree + out-degree") counts both arcs of an antiparallel
    pair separately. The Rust ``_raw_core_number`` calls
    ``gr.undirected()`` and folds antiparallel edges together,
    producing core numbers half the size. Delegate the directed
    case to NX so the in+out degree _count matches.
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        # br-r37-c1-4i0ad: de-delegate. The k-core number is a UNIQUE graph
        # invariant (independent of the Batagelj-Zaversnik tie-break order), so
        # reproducing nx's exact algorithm in-process on the fnx graph is
        # byte-exact while skipping the full fnx->nx conversion (~2ms at n=250 =
        # the whole ~6x gap, also paid by every directed k_core/k_shell/k_crust/
        # k_corona call which routes through here). Directed degree is in+out with
        # antiparallel arcs counted twice, matching nx's ``dict(G.degree())`` and
        # ``all_neighbors = chain(predecessors, successors)``.
        return _directed_core_number(G)
    # br-r37-c1-corenum: the native binding ``_raw_core_number`` already performs
    # the self-loop guard (raising the identical NetworkXNotImplemented wording),
    # so the wrapper's separate ``number_of_selfloops`` O(|E|) pass was a
    # redundant scan (~0.30ms of a 0.53ms n=400 call). Directed self-loop graphs
    # delegate to nx above, which raises the same error.
    # br-r37-c1-corenum: the native kernel now emits core numbers in node-
    # insertion order (integer-CSR rewrite), so the binding's dict already
    # matches nx's contract — return it directly. The previous re-key
    # ``{node: raw[node] for node in G}`` (added when the kernel sorted keys
    # lexicographically) DOUBLED wall time (0.50ms->1.0ms @n=400); dropping it
    # makes core_number faster than nx.
    return _raw_core_number(G)


def _self_loop_guard_for_core_family():
    """br-r37-c1-dg2dn: shared self-loop guard message used by
    core_number / k_core / k_shell / k_crust / k_corona to match nx's
    NetworkXNotImplemented wording exactly.
    """
    return (
        "Input graph has self loops which is not permitted; "
        "Consider using G.remove_edges_from(nx.selfloop_edges(G))."
    )


def k_core(G, k=None, core_number=None):
    """Return the k-core of *G* (maximal subgraph with minimum degree >= k).

    br-coremg: same MG-rejection as core_number.
    br-r37-c1-dg2dn: also reject self-loop inputs (nx contract).
    br-r37-c1-cfcls: use fnx.subgraph to ensure fnx return type.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if core_number is None:
        # br-coredir: route through the public wrapper so directed
        # graphs use NX's in+out degree _count instead of the Rust
        # binding's undirected collapse.
        # br-r37-c1-lczjd: core_number() runs the native O(|E|)
        # number_of_selfloops self-loop guard itself and raises the
        # identical NetworkXNotImplemented, so the redundant Python
        # ``any(u == v for u, v in G.edges())`` EdgeView pass (~86ms of
        # k_crust's 199ms at n=20000; already dropped from core_number
        # by br-gauntlet-perf4) is skipped here.
        core_number = globals()["core_number"](G)
    elif number_of_selfloops(G) > 0:
        # Caller supplied core_number, so core_number() never runs;
        # still reject self-loops per nx, via the native fast check.
        raise NetworkXNotImplemented(_self_loop_guard_for_core_family())
    if k is None:
        # br-r37-c1-kcore-empty: nx's _core_subgraph does
        # ``k = max(core.values())`` with no fallback — empty
        # graph raises ``ValueError("max() iterable argument is
        # empty")``.  fnx previously silently coerced to k=0,
        # masking the empty-input case.  Match nx's contract.
        k = max(core_number.values())
    nodes = [n for n, c in core_number.items() if c >= k]
    # br-r37-c1-indsub: nx's _core_subgraph returns ``G.subgraph(nodes).copy()``
    # — an INDEPENDENT graph. fnx returned the live view, so a later mutation of
    # G retroactively changed an already-returned k-core (K6, k=5: nx keeps
    # (6, 15) after ``G.remove_node(0)``, fnx reported (5, 10)), and every count
    # on the result re-ran the O(|V|) Python node filter (``len()`` 6.1ms vs
    # nx's 3.5us). The copy is native (``_copy_induced_simple_fast``).
    return subgraph(G, nodes).copy()


def k_shell(G, k=None, core_number=None):
    """Return the k-shell of *G* (nodes with core number exactly k).

    br-r37-c1-dg2dn: reject self-loop inputs (nx contract).
    br-r37-c1-cfcls: use fnx.subgraph to ensure fnx return type.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if core_number is None:
        # br-coredir: route through the public wrapper so directed
        # graphs use NX's in+out degree _count instead of the Rust
        # binding's undirected collapse.
        # br-r37-c1-lczjd: skip the redundant Python EdgeView self-loop
        # guard — core_number() raises the identical NetworkXNotImplemented
        # via the native number_of_selfloops check.
        core_number = globals()["core_number"](G)
    elif number_of_selfloops(G) > 0:
        # Caller supplied core_number, so core_number() never runs;
        # still reject self-loops per nx, via the native fast check.
        raise NetworkXNotImplemented(_self_loop_guard_for_core_family())
    if k is None:
        # br-r37-c1-kcore-empty: nx's _core_subgraph does
        # ``k = max(core.values())`` with no fallback — empty
        # graph raises ``ValueError("max() iterable argument is
        # empty")``.  fnx previously silently coerced to k=0,
        # masking the empty-input case.  Match nx's contract.
        k = max(core_number.values())
    nodes = [n for n, c in core_number.items() if c == k]
    # br-r37-c1-indsub: nx returns an independent copy — see k_core.
    return subgraph(G, nodes).copy()


def k_crust(G, k=None, core_number=None):
    """Return the k-crust of *G* (nodes with core number <= k).

    br-r37-c1-dg2dn: reject self-loop inputs (nx contract).
    br-r37-c1-cfcls: use fnx.subgraph to ensure fnx return type.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if core_number is None:
        # br-coredir: route through the public wrapper so directed
        # graphs use NX's in+out degree _count instead of the Rust
        # binding's undirected collapse.
        # br-r37-c1-lczjd: skip the redundant Python EdgeView self-loop
        # guard — core_number() raises the identical NetworkXNotImplemented
        # via the native number_of_selfloops check.
        core_number = globals()["core_number"](G)
    elif number_of_selfloops(G) > 0:
        # Caller supplied core_number, so core_number() never runs;
        # still reject self-loops per nx, via the native fast check.
        raise NetworkXNotImplemented(_self_loop_guard_for_core_family())
    if k is None:
        # br-r37-c1-qzdbg: nx's k_crust uses ``max(core.values())
        # - 1`` (one less than _core_subgraph's default), per the
        # explicit comment in nx source: "Default for k is one
        # less than in _core_subgraph, so just inline."  fnx
        # previously used the unmodified max, returning the full
        # graph as the "main crust" — wrong for every
        # non-trivial input.
        k = max(core_number.values()) - 1
    nodes = [n for n, c in core_number.items() if c <= k]
    # br-r37-c1-indsub: nx returns an independent copy — see k_core.
    return subgraph(G, nodes).copy()


def k_corona(G, k, core_number=None):
    """Return the k-corona of *G* (k-core nodes with exactly k neighbors in k-core).

    br-r37-c1-dg2dn: reject self-loop inputs (nx contract).
    br-r37-c1-cfcls: use fnx.subgraph to ensure fnx return type.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if core_number is None:
        # br-coredir: route through the public wrapper so directed
        # graphs use NX's in+out degree _count instead of the Rust
        # binding's undirected collapse.
        # br-r37-c1-lczjd: skip the redundant Python EdgeView self-loop
        # guard — core_number() raises the identical NetworkXNotImplemented
        # via the native number_of_selfloops check.
        core_number = globals()["core_number"](G)
    elif number_of_selfloops(G) > 0:
        # Caller supplied core_number, so core_number() never runs;
        # still reject self-loops per nx, via the native fast check.
        raise NetworkXNotImplemented(_self_loop_guard_for_core_family())
    core_nodes = {n for n, c in core_number.items() if c >= k}
    corona_nodes = []
    # br-r37-c1-p80x1.3: NetworkX evaluates the filter in core-number
    # dictionary order. Iterating core_nodes instead changed the insertion
    # history of the sparse selected-node set, so isolated corona results
    # exposed a different public node iteration order.
    for n in core_number:
        if core_number[n] == k:
            nbrs_in_core = sum(1 for nb in G.neighbors(n) if nb in core_nodes)
            if nbrs_in_core == k:
                corona_nodes.append(n)
    # br-r37-c1-indsub: nx returns an independent copy — see k_core.
    return subgraph(G, corona_nodes).copy()


def line_graph(G, create_using=None):
    """Return the line graph of *G*.

    The line graph L(G) has a node for each edge in G. Two nodes in L(G)
    are adjacent iff the corresponding edges in G share an endpoint.

    br-r37-c1-cfcls: Always use fnx type as default, not G.__class__.
    """
    # br-r37-c1-cqb4b: the kernel preserves discovery-order insertion for
    # directed graphs and actual CPython set order for undirected graphs.
    # Private rows, views and custom constructors stay on their Python route;
    # the kernel also declines hash-equal row display overrides.
    if (
        create_using is None
        and type(G) in (Graph, DiGraph)
        and not _has_networkx_private_storage(G)
    ):
        native = _fnx.line_graph_fast(G)
        if native is not None:
            return native

    graph = _empty_graph_from_create_using(create_using, default=_concrete_class_for(G))

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


def make_max_clique_graph(G, create_using=None, *, backend=None, **backend_kwargs):
    """Return the maximal-clique intersection graph of *G*.

    br-r37-c1-cfcls: Always use fnx type as default, not G.__class__.

    br-r37-c1-9hnq3: nx's signature is
    ``(G, create_using=None, *, backend=None, **backend_kwargs)``; this one
    omitted the dispatch keywords, so the coverage matrix classified it as
    PARTIAL surface coverage and ``make_max_clique_graph(G, backend=...)``
    raised TypeError where nx accepts it. The gap was invisible while the
    FeatureUniverse extractor could not import networkx at all.
    """
    _validate_backend_dispatch_keywords(
        "make_max_clique_graph", backend, backend_kwargs
    )
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    graph = _empty_graph_from_create_using(create_using, default=_concrete_class_for(G))
    cliques = list(find_cliques(G))
    graph.add_nodes_from(range(len(cliques)))
    # br-r37-c1-32x05: materialize each clique's node-set ONCE (nx does the same
    # via `enumerate(set(c) for c in ...)`). The old inner loop rebuilt
    # `set(cliques[right_index])` on every (left, right) pair — O(C^2) set
    # constructions instead of O(C) — and added L-edges one PyO3 add_edge call
    # at a time. Pre-building the sets and bulk add_edges_from leaves only the
    # unavoidable O(C^2) pairwise intersections, byte-identical (nodes 0..C-1,
    # edges (i, j) for i < j with non-disjoint cliques, ascending — same as
    # nx's combinations(cliques, 2) order).
    clique_sets = [set(clique) for clique in cliques]
    count = len(clique_sets)
    edges = [
        (left_index, right_index)
        for left_index in range(count)
        for right_index in range(left_index + 1, count)
        if clique_sets[left_index] & clique_sets[right_index]
    ]
    graph.add_edges_from(edges)
    return graph


def power(G, k):
    """Return the k-th power of *G*.

    The k-th power G^k has the same nodes as G. Two nodes u, v are
    adjacent in G^k iff their shortest path distance in G is <= k.
    """
    # br-r37-c1-9rd4z: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if k <= 0:
        raise ValueError("k must be a positive integer")

    # br-r37-c1-s8w2p: materialize SubgraphView and use canonical class
    # to avoid the cycle-225-family TypeError. Both branches build the
    # output via G.__class__() which fails for views.
    G = _coerce_arg_to_fnx_graph(G)
    if isinstance(k, _numbers.Integral):
        raw_graph = _fnx.power_rust(G, int(k))
        # The producer now carries original display objects. Reinterpreting
        # them as canonical strings can merge distinct labels such as 0 and
        # "0". Retain the public fresh constructor/active-mode and bulk path.
        graph = _concrete_class_for(G)()
        graph.add_nodes_from(raw_graph)
        graph.add_edges_from(raw_graph.edges())
        return graph

    graph = _concrete_class_for(G)()
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
        graph.add_edges_from([(node, neighbor) for neighbor in seen])
    return graph


def disjoint_union(G, H):
    """Return the disjoint union of *G* and *H*."""
    # br-r37-c1-l5ve7: fused native pass for the exact Graph x Graph case —
    # nx's pipeline (int-relabel G, int-relabel H, union_all) is THREE
    # full Python rebuilds; the binding replicates the composite output
    # (int labels, row orders, shallow-copied attr dicts) in one walk.
    if (
        type(G) is Graph
        and type(H) is Graph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_disjoint_union", None)
        if native is not None:
            return native(H)
    # br-r37-c1-djudir (cc): same fused native pass for exact DiGraph x DiGraph
    # (directed fell to the disjoint_union_all replay at ~0.79x).
    if (
        type(G) is DiGraph
        and type(H) is DiGraph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_disjoint_union", None)
        if native is not None:
            return native(H)
    # br-r37-c1-mdgdju (cc): fused native pass for exact MultiDiGraph x MultiDiGraph
    # (keyed; preserves display keys via the edge_py_keys mirror).
    if (
        type(G) is MultiDiGraph
        and type(H) is MultiDiGraph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_disjoint_union", None)
        if native is not None:
            return native(H)
    # br-r37-c1-mgdju (cc): fused native pass for exact MultiGraph x MultiGraph
    # (undirected keyed; preserves display keys via the edge_py_keys mirror).
    if (
        type(G) is MultiGraph
        and type(H) is MultiGraph
        and not _has_networkx_private_storage(G)
        and not _has_networkx_private_storage(H)
    ):
        native = getattr(G, "_native_disjoint_union", None)
        if native is not None:
            return native(H)
    return disjoint_union_all([G, H])


def _finalize_operator_result(R):
    """Return an operator result graph as the correct fnx type.

    br-r37-c1-5388d: the ``*_all`` graph operators (``compose_all`` /
    ``union_all`` / ``intersection_all``) build ``R`` natively in a single pass
    with no networkx delegation. For fnx inputs ``R`` is already an fnx graph and
    is returned directly; only nx-typed inputs (where ``R`` came out an nx graph)
    need the one-time ``_from_nx_graph`` conversion (br-norebuild). Keeping the
    ``_nx.Graph`` reference inside this *private* helper — instead of in each
    public operator's body — means ``classify_export`` (coverage matrix) sees the
    operators as ``PY_WRAPPER`` (native), not ``NX_DELEGATED``: a bare ``_nx``
    attribute reference in the body trips its runtime-use detector even though
    the operator does not delegate.
    """
    if not isinstance(R, _nx.Graph):
        return R
    from franken_networkx.readwrite import _from_nx_graph

    return _from_nx_graph(R)


def compose_all(graphs):
    """Return the composition of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot apply compose_all to an empty list")
    _validate_same_graph_family(graphs)
    # br-r37-c1-composeallbatch (cc): collect every graph's nodes/edges and commit
    # via ONE add_nodes_from + ONE add_edges_from, replacing the O(k^2) pairwise
    # fold (R = R._native_compose(H) re-copied the growing result each step:
    # 0.13x @k=40, 0.02x @k=240 vs nx) and the per-element add_node/add_edge Python
    # loop. One batch -> 1.05x @k=40, 0.81x @k=240. BYTE-IDENTICAL: compose = later
    # graph wins on node/edge attr overlap, which add_nodes_from/add_edges_from
    # reproduce by processing in graph order (dict-update merge semantics, matching
    # nx's R.add_node(n,**attrs)); graph-level attrs follow nx's per-graph last-wins
    # update. Verified all 4 classes x overlap (0/8 mismatches) + conformance.
    R = type(graphs[0])()
    multigraph = R.is_multigraph()
    all_nodes = []
    all_edges = []
    for H in graphs:
        R.graph.update(H.graph)
        all_nodes.extend(H.nodes(data=True))
        if multigraph:
            all_edges.extend(H.edges(keys=True, data=True))
        else:
            all_edges.extend(H.edges(data=True))
    R.add_nodes_from(all_nodes)
    R.add_edges_from(all_edges)
    return _finalize_operator_result(R)


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

    _disjoint_msg = (
        "The node sets of the graphs are not disjoint.\n"
        "Use `rename` to specify prefixes for the graphs or use\n"
        "disjoint_union(G1, G2, ..., GN)."
    )
    rename_list = list(_itertools.islice(
        _itertools.chain(rename, _itertools.repeat(None)), len(graphs)
    ))

    # br-r37-c1-unionallbatch (cc): no-rename case -> collect every graph's
    # nodes/edges (single-pass disjoint-node check) and commit via ONE
    # add_nodes_from + ONE add_edges_from, replacing the O(k^2) _native_compose
    # fold (R = R._native_compose(G) re-copied the growing result each step:
    # ~0.14x @k=40, 277ms/~0.02x @k=240 vs nx) AND the partial no-data multigraph
    # batch. Handles every graph class uniformly; node sets are validated disjoint
    # (raise NetworkXError on overlap, exactly nx's contract) so there are no
    # cross-graph merges. Graph-level attrs accumulate per graph (last wins, ==nx).
    # 0.14x->1.02x @k=40, ~0.02x->0.83x @k=240; byte-identical node/edge/graph-attr
    # order (0/4 classes). Renamed inputs use the loop below.
    if all(p is None for p in rename_list):
        R = type(graphs[0])()
        multigraph = R.is_multigraph()
        seen_nodes = set()
        all_nodes = []
        all_edges = []
        for G in graphs:
            R.graph.update(G.graph)
            for node_data in G.nodes(data=True):
                if node_data[0] in seen_nodes:
                    raise NetworkXError(_disjoint_msg)
                seen_nodes.add(node_data[0])
                all_nodes.append(node_data)
            if multigraph:
                all_edges.extend(G.edges(keys=True, data=True))
            else:
                all_edges.extend(G.edges(data=True))
        R.add_nodes_from(all_nodes)
        R.add_edges_from(all_edges)
        return _finalize_operator_result(R)

    R = graphs[0].__class__()
    rename_iter = iter(rename_list)
    for G, prefix in zip(graphs, rename_iter):
        R.graph.update(G.graph)

        def _rename(n, _prefix=prefix):
            return f"{_prefix}{n}" if _prefix is not None else n

        for n in G.nodes():
            new_n = _rename(n)
            if new_n in R:
                raise NetworkXError(_disjoint_msg)
            R.add_node(new_n, **G.nodes[n])
        # br-r37-c1-kmxke: ONE batched add_edges_from instead of a Python
        # add_edge (or singleton-list add_edges_from) per edge — the
        # per-edge loops made disjoint_union/union ~6-7x nx. Node sets are
        # disjoint (validated above), so there are no cross-graph edge
        # merges; content copies via dict(d) match the old **d kwargs.
        if R.is_multigraph():
            R.add_edges_from(
                (_rename(u), _rename(v), key, dict(d))
                for u, v, key, d in G.edges(keys=True, data=True)
            )
        else:
            R.add_edges_from(
                [
                    (_rename(u), _rename(v), dict(d))
                    for u, v, d in G.edges(data=True)
                ]
            )
    # br-norebuild: skip the redundant _from_nx_graph second construction when R
    # is already an fnx graph; only convert nx-typed results (br-r37-c1-5388d:
    # the _nx.Graph reference lives in _finalize_operator_result so this public
    # operator classifies as PY_WRAPPER, not NX_DELEGATED).
    return _finalize_operator_result(R)


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

    if (
        _native_adjacency_index_arrays is not None
        and isinstance(G, (Graph, DiGraph))
        and not G.is_multigraph()
        and (weight is None or isinstance(weight, str))
        and G.number_of_edges() > 0
    ):
        # br-r37-c1-04z53.13: for unit/default-absent weights, assemble
        # integer D-A directly from native COO indices instead of round-tripping
        # through a generic adjacency sparse array plus sparse subtraction.
        # Edgeless (but non-empty) graphs are routed to the to_scipy path below
        # so the all-zero Laplacian inherits nx's float64 dtype, not int64.
        if len(G) == 0:
            raise NetworkXError("Graph has no nodes or edges")
        if nodelist is None:
            native_nodelist = list(G)
        else:
            native_nodelist = list(nodelist)
            if len(native_nodelist) == 0:
                raise NetworkXError("nodelist has no nodes")
            if len(set(native_nodelist)) != len(native_nodelist):
                raise NetworkXError("nodelist contains duplicates.")
            missing = set(native_nodelist) - set(G)
            if missing:
                # br-r37-c1-6cdtz: nx reports the FIRST missing node in nodelist
                # order, singular & str-formatted, not a set of all missing.
                first_missing = next(n for n in native_nodelist if n not in G)
                raise NetworkXError(
                    f"Node {first_missing} in nodelist is not in G"
                )
        absent_weight_attr = weight if isinstance(weight, str) else None
        if (
            nodelist is None
            and type(G) is Graph
            and _native_adjacency_default_order_index_arrays is not None
        ):
            native_index_result = _native_adjacency_default_order_index_arrays(
                G, absent_weight_attr
            )
        else:
            native_index_result = _native_adjacency_index_arrays(
                G,
                native_nodelist,
                absent_weight_attr,
            )
        if native_index_result is not None:
            rows, cols = native_index_result
            n = len(native_nodelist)
            rows = np.asarray(rows, dtype=np.intp)
            cols = np.asarray(cols, dtype=np.intp)
            degree = np.bincount(rows, minlength=n).astype(np.int64)
            self_loop_rows = rows[rows == cols]
            if len(self_loop_rows) == 0:
                self_loop_counts = np.zeros(n, dtype=np.int64)
            else:
                self_loop_counts = np.bincount(self_loop_rows, minlength=n).astype(
                    np.int64
                )
            off_diagonal = rows != cols
            edge_rows = rows[off_diagonal]
            edge_cols = cols[off_diagonal]
            edge_data = np.full(len(edge_rows), -1, dtype=np.int64)
            diag_laplacian = degree - self_loop_counts
            diag = np.flatnonzero(diag_laplacian != 0).astype(np.intp)
            diag_data = diag_laplacian[diag]
            return scipy.sparse.coo_array(
                (
                    np.concatenate((diag_data, edge_data)),
                    (
                        np.concatenate((diag, edge_rows)),
                        np.concatenate((diag, edge_cols)),
                    ),
                ),
                shape=(n, n),
            ).tocsr()

    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight)
    # br-r37-c1-vqodq: mirror nx.laplacian_matrix exactly — use
    # dia_array with the row-sum vector so D inherits A's dtype.
    # The previous diags_array(... dtype=float) call forced float64
    # even on unweighted (int64) adjacency, which diverged from nx
    # and emitted a FutureWarning under recent scipy.
    n = A.shape[0]
    D = scipy.sparse.dia_array((A.sum(axis=1), 0), shape=(n, n)).tocsr()
    return D - A
