

def current_flow_closeness_centrality(
    G,
    weight=None,
    dtype=float,
    solver="lu",
    *,
    backend=None,
    **backend_kwargs,
):
    """Closeness centrality based on effective resistance (information centrality)."""
    _validate_backend_dispatch_keywords(
        "current_flow_closeness_centrality", backend, backend_kwargs
    )

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    solvername = {
        "full": _FullInverseLaplacian,
        "lu": _SuperLUInverseLaplacian,
        "cg": _CGInverseLaplacian,
    }

    if not is_connected(G):
        raise NetworkXError("Graph not connected.")

    import numpy as np
    node_count = G.number_of_nodes()
    ordering = list(_reverse_cuthill_mckee_ordering(G))
    if (
        solver == "lu"
        and weight is None
        and dtype is float
        and type(G) is Graph
        and hasattr(_fnx, "current_flow_closeness_centrality_rust")
    ):
        # br-r37-c1-8n5ni: emit in G's node order, not RCM order — see the
        # comment on the return of the general path below.
        raw = _fnx.current_flow_closeness_centrality_rust(G, ordering)
        return {node: raw[node] for node in G}

    relabeled = relabel_nodes(G, dict(zip(ordering, range(node_count))))

    laplacian = laplacian_matrix(
        relabeled,
        nodelist=range(node_count),
        weight=weight,
    ).asformat("csc")
    laplacian = laplacian.astype(dtype)
    inverse = solvername[solver](laplacian, width=1, dtype=dtype)

    # br-r37-c1-icperf: previously a per-pair O(N²) Python inner loop
    # over relabeled × relabeled, calling ``row.item(node)`` and
    # ``row.item(other)`` ~40,000 times for n=200 (~400ms of the
    # 468ms total).  The inner loop is mathematically equivalent to:
    #   centrality[node] += n * row[node] - 2 * row.sum()
    #   centrality       += row[node]    (broadcast to all entries)
    # — a fully vectorized form that drops the 40k Python iterations
    # to two numpy ops per outer iteration (~9ms total).
    n = node_count
    centrality_arr = np.zeros(n, dtype=float)
    for node in range(n):
        row = inverse.get_row(node)
        diag = float(row[node])
        centrality_arr[node] += n * diag - 2.0 * float(row.sum())
        centrality_arr += diag

    # br-r37-c1-cfctype: nx returns Python ``float`` dict values; ``centrality_arr``
    # is a numpy array so ``1.0 / centrality_arr[i]`` is ``np.float64``, which
    # diverges on ``type(v) is float`` and on repr (``np.float64(...)``).
    # current_flow_betweenness already coerces — match it here.
    #
    # br-r37-c1-8n5ni: iterate G, not ``range(n)``. ``centrality_arr`` is indexed
    # by RCM RANK, so ``{ordering[i]: ... for i in range(n)}`` emitted keys in RCM
    # order — nx emits them in G's node order. nx gets there by keying its
    # accumulator off the relabeled graph (``dict.fromkeys(H)``), whose node order
    # is ``[mapping[v] for v in G]``, so ``ordering[node]`` maps each key straight
    # back to G's order. Values are untouched; only the key sequence moves.
    rank = {node: index for index, node in enumerate(ordering)}
    return {node: float(1.0 / centrality_arr[rank[node]]) for node in G}


def betweenness_centrality_subset(
    G,
    sources,
    targets,
    normalized=False,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Betweenness centrality restricted to source/target subsets."""
    _validate_backend_dispatch_keywords(
        "betweenness_centrality_subset",
        backend,
        backend_kwargs,
    )

    # br-r37-c1-tm1tq: nx hashes each source/target into a dict /
    # tuple-iter — raises ``TypeError: unhashable type`` on the
    # first unhashable element.  fnx's Rust binding silently
    # ignored unhashable members.  Materialize and hash-validate
    # both lists to match nx's contract.
    sources = list(sources)
    targets = list(targets)
    for s in sources:
        _HASH_PROBE.get(s)
    for t in targets:
        _HASH_PROBE.get(t)
    # br-r37-c1-bcs-bad-src: nx's SSSP raises KeyError when called
    # with a source not in G (it tries to index ``predecessors[s]``
    # before the source is initialized).  fnx's Rust binding
    # silently treated unknown sources as no-op contributions and
    # returned an all-zero dict, masking the contract.  Targets are
    # not validated by nx (absence just yields zeros for those
    # paths) — match that asymmetry.
    for s in sources:
        if s not in G:
            raise KeyError(s)

    if weight is None and not G.is_multigraph():
        scores = _betweenness_centrality_subset_rust(
            G, sources, targets, normalized
        )
        return {node: scores.get(node, 0.0) for node in G}
    # br-r37-c1-664w5: weighted subset betweenness ran a pure-Python per-source
    # Dijkstra + accumulation loop (~3.2x SLOWER than nx). Route to the native
    # weighted subset Brandes kernel (Dijkstra SSSP, byte-exact) for the
    # common simple-graph string-weight case with finite/non-negative/numeric
    # weights; callable/non-string weight, multigraph, or bad weights fall
    # through to the parity path.
    if isinstance(weight, str) and not G.is_multigraph():
        _sync_rust_edge_attrs(G)
        if not (
            _has_negative_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_positive_infinity_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        ):
            scores = _betweenness_centrality_subset_weighted_rust(
                G, sources, targets, weight, normalized
            )
            return {node: scores.get(node, 0.0) for node in G}
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
    G,
    sources,
    targets,
    normalized=False,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Edge betweenness restricted to source/target subsets."""
    _validate_backend_dispatch_keywords(
        "edge_betweenness_centrality_subset",
        backend,
        backend_kwargs,
    )

    # br-r37-c1-39gx2: nx hashes each source/target into a dict —
    # raises TypeError on the first unhashable element.  Without
    # this check fnx silently ignores unhashable members.  Mirror
    # the fix already in betweenness_centrality_subset (br-r37-c1-tm1tq).
    sources = list(sources)
    targets = list(targets)
    for s in sources:
        _HASH_PROBE.get(s)
    for t in targets:
        _HASH_PROBE.get(t)
    # br-r37-c1-bcs-bad-src: nx's SSSP raises KeyError on sources
    # not in G; mirror the betweenness_centrality_subset fix.
    for s in sources:
        if s not in G:
            raise KeyError(s)

    if weight is None and not G.is_multigraph():
        rust_scores = _edge_betweenness_centrality_subset_rust(
            G, sources, targets, normalized
        )
        betweenness = dict.fromkeys(G.edges(), 0.0)
        is_directed = G.is_directed()
        for (u, v), score in rust_scores.items():
            if (u, v) in betweenness:
                betweenness[(u, v)] = score
            elif not is_directed and (v, u) in betweenness:
                betweenness[(v, u)] = score
        return betweenness
    # br-r37-c1-gqgds: weighted subset edge betweenness ran a pure-Python
    # per-source Dijkstra + accumulation loop (~3x SLOWER than nx). Route to the
    # native weighted subset edge-Brandes kernel (Dijkstra SSSP, byte-exact) for
    # the simple-graph string-weight case with finite/non-negative/numeric
    # weights; callable/non-string weight, multigraph, or bad weights fall
    # through to the parity path.
    if isinstance(weight, str) and not G.is_multigraph():
        _sync_rust_edge_attrs(G)
        if not (
            _has_negative_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_positive_infinity_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        ):
            rust_scores = _edge_betweenness_centrality_subset_weighted_rust(
                G, sources, targets, weight, normalized
            )
            betweenness = dict.fromkeys(G.edges(), 0.0)
            is_directed = G.is_directed()
            for (u, v), score in rust_scores.items():
                if (u, v) in betweenness:
                    betweenness[(u, v)] = score
                elif not is_directed and (v, u) in betweenness:
                    betweenness[(v, u)] = score
            return betweenness
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


def edge_load_centrality(G, cutoff=False, *, backend=None, **backend_kwargs):
    """Load centrality for edges."""
    _validate_backend_dispatch_keywords("edge_load_centrality", backend, backend_kwargs)

    if cutoff is False:
        cutoff = None

    # br-elccsr: integer-CSR BFS fast path. The per-source pure-Python BFS
    # (_edge_load_from_source_local -> _single_source_shortest_path_basic_local)
    # plus an O(E) (node, node)-keyed `between` dict rebuilt once per source
    # made this ~3-10x slower than nx (up to 1.25s under load). Relabel nodes to
    # dense indices once, snapshot a local integer adjacency list, and run all N
    # BFS + the edge-load accumulation on integer-keyed dicts. Neighbor order is
    # preserved from G[node] and edge order from G.edges(), so the float result
    # is BIT-identical to the prior implementation (and matches nx).
    nodes = list(G)
    n = len(nodes)
    index = {node: i for i, node in enumerate(nodes)}
    adj = [[index[nbr] for nbr in G[node]] for node in nodes]
    edge_pairs = [(index[u], index[v]) for u, v in G.edges()]

    aggregate = {}
    for a, b in edge_pairs:
        aggregate[(a, b)] = 0.0
        aggregate[(b, a)] = 0.0

    for s in range(n):
        stack = []
        pred = [[] for _ in range(n)]
        dist = [-1] * n
        dist[s] = 0
        queue = _deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            dv = dist[v]
            if cutoff is not None and dv >= cutoff:
                continue
            for w in adj[v]:
                if dist[w] < 0:
                    queue.append(w)
                    dist[w] = dv + 1
                if dist[w] == dv + 1:
                    pred[w].append(v)
        between = {}
        for a, b in edge_pairs:
            between[(a, b)] = 1.0
            between[(b, a)] = 1.0
        ordered = list(stack)
        while ordered:
            node = ordered.pop()
            for p in pred[node]:
                if pred[p]:
                    num_paths = len(pred[p])
                    for parent in pred[p]:
                        between[(p, parent)] += between[(node, p)] / num_paths
                        between[(parent, p)] += between[(p, node)] / num_paths
        for edge, value in between.items():
            aggregate[edge] += value

    return {(nodes[a], nodes[b]): value for (a, b), value in aggregate.items()}


def laplacian_centrality(
    G,
    normalized=True,
    nodelist=None,
    weight="weight",
    walk_type=None,
    alpha=0.95,
    *,
    backend=None,
    **backend_kwargs,
):
    """Laplacian centrality: drop in Laplacian energy when node is removed."""
    _validate_backend_dispatch_keywords("laplacian_centrality", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-lapcentnative / br-r37-c1-dirlapnative: laplacian_centrality is a
    # laplacian matrix (undirected: D - A; directed: the Chung directed Laplacian)
    # + a deterministic numpy energy loop — no extra eigenvalues. Both matrices
    # are now native (laplacian_matrix / directed_laplacian_matrix), so compute
    # in-process with the same numpy, dropping the per-call fnx->nx conversion.
    import numpy as _np

    if len(G) == 0:
        raise NetworkXPointlessConcept("null graph has no centrality defined")
    if G.size(weight=weight) == 0:
        if normalized:
            raise ZeroDivisionError("graph with no edges has zero full energy")
        return {n: 0 for n in G}

    if nodelist is not None:
        nodeset = set(G.nbunch_iter(nodelist))
        if len(nodeset) != len(nodelist):
            raise NetworkXError("nodelist has duplicate nodes or nodes not in G")
        nodes = nodelist + [n for n in G if n not in nodeset]
    else:
        nodelist = nodes = list(G)

    if G.is_directed():
        lap_matrix = directed_laplacian_matrix(G, nodes, weight, walk_type, alpha)
    else:
        lap_matrix = laplacian_matrix(G, nodes, weight).toarray()
    full_energy = _np.sum(lap_matrix**2)

    # br-r37-c1-lapcent-vec (cc): nx's per-node "delete row/col i, re-sum the
    # Laplacian energy" loop materialises an (n-1)x(n-1) submatrix every iteration
    # = O(n^3) (102ms at n=400, both fnx and nx). The energy drop has a closed
    # form. Removing node i (delete row+col i, then subtract |L[:,i]| from the
    # surviving diagonal) gives, after the column terms cancel:
    #     new_energy[i] = full_energy - rowsq[i] + 2*diag[i]^2 - 2*(diag @ |L|)[i]
    #     lapl_cent[i]  = rowsq[i] - 2*diag[i]^2 + 2*(diag @ |L|)[i]
    # where rowsq = sum over columns of L^2 and (diag @ |L|)[i] = sum_a diag[a]
    # |L[a,i]|. Vectorised over all nodes in O(n^2): byte-EXACT on unweighted
    # (integer L) and 1e-16 on weighted/directed. 0.659x -> 16x (n=120) / 124x
    # (n=400) vs nx, the speedup growing as O(n). lapl_cent[i] uses ROW i of L
    # (sum over the deleted column index b) — correct for the asymmetric directed
    # Laplacian too (verified against nx on directed/weighted/complete/path/gnp).
    # br-r37-c1-p1uop: the i-th term of that sum is diag[i]*|diag[i]|, not
    # diag[i]^2 - the same for a non-negative degree, but a node whose weighted
    # degree is negative (negative weights) came out wrong (-0.018 where
    # networkx's loop gives 0.0).
    diag = _np.diagonal(lap_matrix).astype(float)
    row_sq = _np.sum(lap_matrix**2, axis=1)
    weighted_diag_col = diag @ _np.abs(lap_matrix)
    cents = row_sq - 2.0 * diag * _np.abs(diag) + 2.0 * weighted_diag_col
    if normalized:
        cents = cents / full_energy

    # ``nodes`` orders nodelist first, so positions 0..len(nodelist)-1 are exactly
    # the reported nodes (matches nx's ``enumerate(nodelist)`` indexing).
    laplace_centralities_dict = {
        node: float(cents[i]) for i, node in enumerate(nodelist)
    }

    return laplace_centralities_dict


def percolation_centrality(
    G,
    attribute="percolation",
    states=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Percolation centrality based on percolation states."""
    _validate_backend_dispatch_keywords(
        "percolation_centrality", backend, backend_kwargs
    )

    percolation = dict.fromkeys(G, 0.0)
    if states is None:
        states = {
            node: G.nodes[node].get(attribute, 1)
            for node in G
        }

    state_sum = sum(states.values())

    # br-r37-c1-percw: weighted percolation centrality previously ran a
    # pure-Python per-source Dijkstra + accumulation loop (~1.8s n=400, 3.2x
    # SLOWER than nx). Route to the native weighted percolation kernel (Dijkstra
    # SSSP, parallel, byte-exact) — the same Brandes recurrence as the native
    # weighted betweenness, with each w!=s weighted by
    # states[s]/(state_sum - states[w]) and a final 1/(n-2) scale. Pass the
    # per-node states aligned to G's node-iteration order. Mirror the
    # dijkstra/astar weight contract; callable/non-string weight, multigraph,
    # negative/+inf/non-numeric weight, n<=2, or non-float states fall through
    # to the parity path / nx.
    if (
        weight is not None
        and isinstance(weight, str)
        and len(G) > 2
        and not G.is_multigraph()
    ):
        _sync_rust_edge_attrs(G)
        if not (
            _has_negative_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_positive_infinity_edge_weight_for_dijkstra(G, weight, _skip_sync=True)
            or _has_nonnumeric_edge_weight(G, weight, _skip_sync=True)
        ):
            try:
                states_list = [float(states[node]) for node in G]
            except (TypeError, ValueError, KeyError):
                states_list = None
            if states_list is not None:
                return _raw_percolation_centrality_weighted(G, weight, states_list)

    # br-perccsr: integer-CSR BFS fast-path for the unweighted case. The
    # per-source pure-Python Brandes BFS (_single_source_shortest_path_basic_
    # local) walks string-keyed dicts over fnx adjacency once per node — the
    # "BFS-from-every-source string tax", ~3x slower than nx. Relabel nodes to
    # dense indices once and run all N BFS on flat integer arrays + a local
    # adjacency list. Brandes accumulation is order-independent and neighbor
    # order is preserved from G[node], so the result is BIT-identical to the
    # dict version (and to nx). 173ms -> 30ms (faster than nx). Tiny graphs
    # (<=2 nodes) keep the original path so the 1/(n-2) edge behavior is
    # untouched.
    if weight is None and len(G) > 2:
        # br-r37-c1-percunit (cc): the unweighted percolation Brandes loop below
        # runs SERIALLY in Python over all N sources (2.18s at n=1500). The native
        # weighted percolation kernel (parallel Dijkstra SSSP) defaults a missing
        # edge-weight attribute to 1.0 — unit weights, whose shortest-path counts
        # are identical to BFS — so routing through it with a sentinel (absent)
        # weight name is BYTE-IDENTICAL (verified undirected/directed/disconnected/
        # non-uniform-states, 0..7e-18 vs nx) and parallel-native: 123ms -> 3.5ms
        # (n=400), ~35x. Multigraph keeps the Python loop (the native kernel guards
        # !multigraph, matching the weighted path above).
        if not G.is_multigraph():
            try:
                states_list = [float(states[node]) for node in G]
            except (TypeError, ValueError, KeyError):
                states_list = None
            if states_list is not None:
                return _raw_percolation_centrality_weighted(
                    G, "\x00__fnx_unit_weight_sentinel__", states_list
                )
        nodes = list(G)
        n = len(nodes)
        index = {node: i for i, node in enumerate(nodes)}
        st = [states[node] for node in nodes]
        adj = [[index[nbr] for nbr in G[node]] for node in nodes]
        perc = [0.0] * n
        for s in range(n):
            stack = []
            pred = [[] for _ in range(n)]
            sigma = [0.0] * n
            dist = [-1] * n
            sigma[s] = 1.0
            dist[s] = 0
            queue = _deque([s])
            while queue:
                v = queue.popleft()
                stack.append(v)
                dv = dist[v]
                sv = sigma[v]
                for w in adj[v]:
                    if dist[w] < 0:
                        queue.append(w)
                        dist[w] = dv + 1
                    if dist[w] == dv + 1:
                        sigma[w] += sv
                        pred[w].append(v)
            delta = [0.0] * n
            while stack:
                v = stack.pop()
                coeff = (1 + delta[v]) / sigma[v]
                for parent in pred[v]:
                    delta[parent] += sigma[parent] * coeff
                if v != s:
                    perc[v] += delta[v] * (st[s] / (state_sum - st[v]))
        scale = 1 / (n - 2)
        return {nodes[i]: perc[i] * scale for i in range(n)}

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


def information_centrality(
    G,
    weight=None,
    dtype=float,
    solver="lu",
    *,
    backend=None,
    **backend_kwargs,
):
    """Information centrality (same as current-flow closeness)."""
    _validate_backend_dispatch_keywords(
        "current_flow_closeness_centrality", backend, backend_kwargs
    )

    return current_flow_closeness_centrality(
        G,
        weight=weight,
        dtype=dtype,
        solver=solver,
    )


def _second_order_fundamental_columns(transition, ones):
    """Return the n x n matrix whose column ``j`` is ``(I - Q_j)^{-1} ones``,
    where ``Q_j`` is ``transition`` with column ``j`` zeroed.

    Computed in O(n^3) via one shared LU factorization of the anchor
    ``A = I - Q_0`` plus a rank-2 Sherman-Morrison-Woodbury correction per
    column, instead of ``n`` independent O(n^3) dense solves (O(n^4)).  Returns
    ``None`` if the fast path is numerically unusable, so the caller can fall
    back to the exact per-column solves.
    """
    import numpy as np

    n = transition.shape[0]
    try:
        # anchor A = I - Q_0 = I - transition + transition[:, 0] e_0^T
        A = np.eye(n) - transition
        A[:, 0] += transition[:, 0]
        # Factor A once and solve both right-hand sides (the all-ones vector and
        # every column of `transition`) in a single LAPACK call.
        rhs_all = np.empty((n, n + 1))
        rhs_all[:, 0] = ones
        rhs_all[:, 1:] = transition
        sol = np.linalg.solve(A, rhs_all)
        a = sol[:, 0]                        # A^{-1} ones
        bp = sol[:, 1:]                      # column k = A^{-1} transition[:, k]
        matrix = np.empty((n, n))
        matrix[:, 0] = a                    # I - Q_0 == A, so column 0 is a
        if n > 1:
            # Per column j>=1: x_j = a - (A^{-1}U)(I_2 + V^T A^{-1} U)^{-1}(V^T a)
            # with U = [transition[:,j], -transition[:,0]], V = [e_j, e_0]. The
            # 2x2 system has a closed form, so the whole correction vectorizes
            # over j (no Python loop, no per-column solve) -- O(n^2).
            d = np.diag(bp)
            s00 = 1.0 + d[1:]               # 1 + bp[j, j]
            s01 = -bp[1:, 0]               # -bp[j, 0]
            s10 = bp[0, 1:]               # bp[0, j]
            s11 = 1.0 - bp[0, 0]           # 1 - bp[0, 0]  (scalar)
            det = s00 * s11 - s01 * s10
            c0 = (s11 * a[1:] - s01 * a[0]) / det
            c1 = (s00 * a[0] - s10 * a[1:]) / det
            matrix[:, 1:] = a[:, None] - (
                bp[:, 1:] * c0[None, :] - bp[:, 0][:, None] * c1[None, :]
            )
        if not np.all(np.isfinite(matrix)):
            return None
        return matrix
    except Exception:
        return None


def second_order_centrality(G, weight="weight", *, backend=None, **backend_kwargs):
    """Second-order centrality based on random walk standard deviation."""
    _validate_backend_dispatch_keywords("second_order_centrality", backend, backend_kwargs)

    # br-r37-c1-u7ry8: the Rust fast path silently returned a value
    # dict on empty / disconnected graphs (zeros, NaNs, or {}). nx
    # raises NetworkXException with specific wording — mirror that
    # contract before any Rust dispatch so drop-in code that does
    # ``pytest.raises(NetworkXException, match='Non connected graph')``
    # triggers the same way under fnx. Single-isolated-node case is
    # the documented exception (returns {n: 0.0} on both libraries).
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    n_nodes = len(G)
    if n_nodes == 0:
        raise NetworkXException("Empty graph.")
    if n_nodes > 1 and not is_connected(G):
        raise NetworkXException("Non connected graph.")

    if (
        weight == "weight"
        and not _graph_has_edge_attribute(G, "weight")
    ):
        raw = _fnx.second_order_centrality_rust(G)
        # br-r37-c1-f6epo: the Rust binding returns the dict in
        # arbitrary internal order; nx iterates in node-insertion
        # order. Reorder so ``for node, score in result.items():``
        # matches nx's contract.
        return {node: raw[node] for node in G if node in raw}  # br-gauntlet-perf4: `for node in G` (fast native Graph.__iter__) not `G.nodes()` (NodeView iterator is ~350x slower; identical order)

    import numpy as np

    nodelist = list(G.nodes())
    n = len(nodelist)

    if n == 1:
        return {nodelist[0]: 0.0}
    if any(data.get(weight, 0) < 0 for _, _, data in G.edges(data=True)):
        # br-r37-c1-soc-exc: nx raises the base NetworkXException class
        # here (atypical — most fnx errors are NetworkXError subclasses),
        # so callers using ``except NetworkXException as e`` to discriminate
        # this specific failure don't catch fnx's NetworkXError. Match nx.
        raise NetworkXException("Graph has negative edge weights.")

    # br-r37-c1-socindeg: build the Metropolis-Hastings transition matrix DIRECTLY in
    # numpy from G's edge data, instead of via `DiGraph(G)` + the native in_degree /
    # to_numpy_array. A batch-built graph leaves G's edge-attr mirror lazy, and the
    # directed copy's native 'weight'-keyed (default-attr) fast paths then read unit
    # DEFAULTS -> wrong d_max -> wrong balancing self-loops -> centrality off by ~17 vs nx
    # (only when second_order is the FIRST op on the fresh graph; any prior weighted read
    # masked it, and a non-default weight key like 'cost' dodged the stale fast path).
    # `G.edges(data=True)` returns the correct live weights, so reconstruct nx's exact
    # algorithm over it: directed adjacency by the 'weight' (default) key — what
    # nx.to_numpy_array(directed) reads — with each undirected edge in both orientations;
    # in-degree by `weight`; balancing self-loops (d_max - in_deg) added to the diagonal.
    index = {node: i for i, node in enumerate(nodelist)}
    adjacency = np.zeros((n, n))
    in_weighted = np.zeros(n)
    edge_rows = G.edges(data=True)
    if G.is_multigraph():
        # br-r37-c1-vwh94: nx's DiGraph(G) keeps ONE edge per pair whose dict is
        # every parallel edge's data merged in key order (the last 'weight' wins),
        # not the sum of the parallel edges. G.edges yields a pair's keys together.
        merged = {}
        for _u, _v, _data in edge_rows:
            merged.setdefault((_u, _v), {}).update(_data)
        edge_rows = [(_u, _v, _data) for (_u, _v), _data in merged.items()]
    for _u, _v, _data in edge_rows:
        iu, iv = index[_u], index[_v]
        edge_w = _data.get("weight", 1)
        in_w = _data.get(weight, 1)
        adjacency[iu, iv] += edge_w
        in_weighted[iv] += in_w
        if iu != iv:  # undirected -> the reverse orientation, except for self-loops
            adjacency[iv, iu] += edge_w
            in_weighted[iu] += in_w
    max_in_degree = in_weighted.max()
    for i in range(n):
        if in_weighted[i] < max_in_degree:
            # nx's G.add_edge(i, i, weight=d_max - deg) REPLACES an existing
            # selfloop's 'weight' rather than adding to it (br-r37-c1-vwh94).
            adjacency[i, i] = max_in_degree - in_weighted[i]
    transition = adjacency / adjacency.sum(axis=1)[:, np.newaxis]

    # br-socwoodbury: the previous code solved (I - Q_idx) x = 1 for every
    # column idx -- n dense O(n^3) solves => O(n^4) overall (catastrophic on a
    # weighted graph: n=300 ran tens of seconds). Each system differs from the
    # common anchor A = I - Q_0 by a rank-2 update,
    #     I - Q_j = A + p_j e_j^T - p_0 e_0^T        (p_k = transition[:, k]),
    # so a single shared LU of A plus a Sherman-Morrison-Woodbury correction
    # yields every column in O(n) extra work -- O(n^3) total. A = I - Q_0 is the
    # absorbing fundamental matrix for sink node 0 and is non-singular on a
    # connected chain. The per-column vectors are reproduced to ~1e-11 (proved
    # against the exact loop and against networkx); the centrality formula below
    # is byte-unchanged, so results match to floating-point rounding. Any
    # numerical anomaly (a non-finite entry) transparently falls back to the
    # exact per-column n-solves.
    ones = np.ones(n)
    matrix = _second_order_fundamental_columns(transition, ones)
    if matrix is None:
        identity = np.identity(n)
        matrix = np.empty([n, n])
        for idx in range(n):
            restricted = transition.copy()
            restricted[:, idx] = 0
            matrix[:, idx] = np.linalg.solve(identity - restricted, ones)

    return dict(
        zip(
            nodelist,
            (
                float(np.sqrt(2 * np.sum(matrix[:, idx]) - n * (n + 1)))
                for idx in range(n)
            ),
        )
    )


def subgraph_centrality_exp(
    G,
    *,
    normalized=False,
    backend=None,
    **backend_kwargs,
):
    """Subgraph centrality via explicit scipy.linalg.expm."""
    _validate_backend_dispatch_keywords(
        "subgraph_centrality_exp",
        backend,
        backend_kwargs,
    )

    centrality = subgraph_centrality(G)
    if normalized:
        values = map(float, centrality.values())
        values.max()
    return centrality


def communicability_betweenness_centrality(G, *, backend=None, **backend_kwargs):
    """Betweenness centrality based on communicability.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    _validate_backend_dispatch_keywords(
        "communicability_betweenness_centrality", backend, backend_kwargs
    )

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-cbcexpm: the native communicability_betweenness_centrality_rust kernel
    # (own LU/Pade expm) is ~2.5x SLOWER than nx's per-node scipy.linalg.expm approach
    # (n=150: native 693ms vs nx 275ms; n=300: 10.8s vs 4.0s) AND diverged ~1e-12, which is
    # why it needed a separate disconnected-nan delegation. Run nx's EXACT algorithm
    # in-process on the fnx graph (fnx's fast to_numpy_array + scipy expm): BYTE-identical
    # to nx (0.0e+00, incl the disconnected nan contract that falls straight out of the
    # expA division) and 2.5x faster than the kernel. (The n per-node expm are independent,
    # but scipy expm does not release the GIL enough for thread parallelism to help here.)
    import numpy as np
    import scipy as sp

    nodelist = list(G)
    n = len(nodelist)
    if n == 0:
        return {}
    A = to_numpy_array(G, nodelist)
    A[np.nonzero(A)] = 1
    expA = sp.linalg.expm(A)
    mapping = dict(zip(nodelist, range(n)))
    cbc = {}
    for v in G:  # node-insertion order matches nx's contract
        i = mapping[v]
        row = A[i, :].copy()
        col = A[:, i].copy()
        A[i, :] = 0
        A[:, i] = 0
        B = (expA - sp.linalg.expm(A)) / expA
        B[i, :] = 0
        B[:, i] = 0
        B -= np.diag(np.diag(B))
        cbc[v] = float(B.sum())
        A[i, :] = row
        A[:, i] = col
    order = len(cbc)
    if order > 2:
        scale = 1.0 / ((order - 1.0) ** 2 - (order - 1.0))
        cbc = {node: value * scale for node, value in cbc.items()}
    return cbc


def trophic_levels(G, weight="weight"):
    """Compute trophic levels in a directed graph (food web).

    br-trophdir: nx.trophic_levels / trophic_differences /
    trophic_incoherence_parameter are @not_implemented_for('undirected');
    fnx silently computed garbage (all-nodes at ~4.8e16) on Graph input.
    Reject undirected input with nx's exact exception type + message so
    the contract matches upstream.

    Default ``weight='weight'`` matches nx (br-r37-c1-rygbm). Earlier
    fnx default ``weight=None`` silently dropped edge weights.

    br-r37-c1-jk4ym: nx raises NetworkXError("no basal nodes") on
    an empty DiGraph; fnx returns {} for that edge case (no levels
    to compute). This is the project-wide convention for vacuous
    inputs.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if G.number_of_nodes() == 0:
        return {}
    return _trophic_levels_compute(G, weight)


def _trophic_levels_compute(G, weight):
    """br-r37-c1-trophnative: nx's Levine trophic-level method, computed
    in-process from the NATIVE adjacency matrix + numpy, replacing the
    per-call fnx->nx conversion. Byte-exact: the native ``adjacency_matrix``
    matches nx's, and the remaining `(I - p)^-1 . 1` solve is identical numpy.
    Strict (no empty-graph shortcut): empty / no-basal / unreachable raise nx's
    exact messages — so trophic_differences/incoherence keep nx's error contract
    on degenerate inputs.
    """
    import numpy as _np

    in_deg = list(G.in_degree())
    basal_nodes = [nid for nid, deg in in_deg if deg == 0]
    if not basal_nodes:
        raise NetworkXError(
            "This graph has no basal nodes (nodes with no incoming edges)."
            "Trophic levels are not defined without at least one basal node."
        )
    reachable_nodes = set()
    for layer in bfs_layers(G, basal_nodes):
        reachable_nodes.update(layer)
    if len(reachable_nodes) != G.number_of_nodes():
        raise NetworkXError(
            "Trophic levels are only defined for graphs where every node has a path "
            "from a basal node (basal nodes are nodes with no incoming edges)."
        )

    a = adjacency_matrix(G, weight=weight).T.toarray()
    rowsum = _np.sum(a, axis=1)
    p = a[rowsum != 0][:, rowsum != 0]
    p = p / rowsum[rowsum != 0][:, _np.newaxis]
    nn = p.shape[0]
    i = _np.eye(nn)
    try:
        n = _np.linalg.inv(i - p)
    except _np.linalg.LinAlgError as err:
        raise NetworkXError(
            "Trophic levels are only defined for graphs where every "
            "node has a path from a basal node (basal nodes are nodes "
            "with no incoming edges)."
        ) from err
    y = n.sum(axis=1) + 1

    levels = {}
    for nid, deg in in_deg:
        if deg == 0:
            levels[nid] = 1
    nonzero_nodes = [nid for nid, deg in in_deg if deg != 0]
    for idx, nid in enumerate(nonzero_nodes):
        levels[nid] = y.item(idx)
    return levels


def trophic_differences(G, weight="weight"):
    """Compute trophic differences across edges.

    br-trophdir: see trophic_levels; reject undirected input.
    Default ``weight='weight'`` matches nx (br-r37-c1-rygbm).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-trophnative: nx computes levels then diffs[(u,v)] = s_v - s_u over
    # G.edges; do the same natively (strict levels match nx's degenerate-input
    # errors). MultiDiGraph: G.edges yields (u, v) per parallel edge and the
    # dict last-write-wins, identical to nx (the value is the same for parallels).
    levels = _trophic_levels_compute(G, weight)
    diffs = {}
    # Iterate the edge VIEW (not edges()) exactly like nx: on a MultiDiGraph this
    # yields 3-tuples and raises ValueError("too many values to unpack"), matching
    # nx's own (multigraph-unsupported) behavior; on a DiGraph it yields (u, v).
    for u, v in G.edges:
        diffs[(u, v)] = levels[v] - levels[u]
    return diffs


def trophic_incoherence_parameter(G, weight="weight", cannibalism=False):
    """Compute the trophic incoherence parameter (std of trophic differences).

    br-trophdir: see trophic_levels; reject undirected input.
    Default ``weight='weight'`` matches nx (br-r37-c1-rygbm).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    import numpy as _np

    # br-r37-c1-trophnative: nx removes self-loops (unless cannibalism), then
    # returns float(np.std(trophic_differences.values())). Mirror exactly.
    if cannibalism:
        diffs = trophic_differences(G, weight=weight)
    else:
        self_loops = list(selfloop_edges(G))
        if self_loops:
            G_2 = G.copy()
            G_2.remove_edges_from(self_loops)
        else:
            G_2 = G
        diffs = trophic_differences(G_2, weight=weight)
    return float(_np.std(list(diffs.values())))


def group_betweenness_centrality(
    G,
    C,
    normalized=True,
    weight=None,
    endpoints=False,
    *,
    backend=None,
    **backend_kwargs,
):
    """Betweenness centrality for a group of nodes C."""
    _validate_backend_dispatch_keywords(
        "group_betweenness_centrality", backend, backend_kwargs
    )

    list_of_groups = True
    if any(element in G for element in C):
        C = [C]
        list_of_groups = False
    group_nodes = {node for group in C for node in group}
    missing_nodes = group_nodes - set(G.nodes())
    if missing_nodes:
        raise NodeNotFound(f"The node(s) {missing_nodes} are in C but not in G.")

    if (
        not G.is_directed()
        and weight is None
        and not endpoints
        and all(len(set(group)) <= 2 for group in C)
    ):
        scores = []
        for group in C:
            group_size = len(set(group))
            remaining = len(G) - group_size
            if normalized and remaining < 2:
                raise ZeroDivisionError("division by zero")
            value = _fnx.group_betweenness_centrality_rust(G, list(group))
            if normalized:
                scores.append(value)
            else:
                scores.append(value * remaining * (remaining - 1) / 2)
        return scores if list_of_groups else scores[0]

    group_betweenness = []
    path_betweenness, sigma, distances = _group_preprocessing_local(
        G,
        group_nodes,
        weight,
    )

    for group in C:
        group = set(group)
        group_score = 0.0
        sigma_matrix = _deepcopy(sigma)
        path_matrix = _deepcopy(path_betweenness)
        next_sigma_matrix = _deepcopy(sigma_matrix)
        next_path_matrix = _deepcopy(path_matrix)
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
                                / sigma[node][right]
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


def group_closeness_centrality(G, S, weight=None, *, backend=None, **backend_kwargs):
    """Closeness centrality for a group of nodes S."""
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "group_closeness_centrality", backend, backend_kwargs
    )
    for s in S:
        if s not in G:
            raise NodeNotFound(f"Node {s} not found in graph")
    if not (set(G) - set(S)):
        return 0
    if not G.is_directed() and weight is None:
        return _fnx.group_closeness_centrality_rust(G, list(S))

    if G.is_directed():
        G = G.reverse()
    closeness = 0.0
    V_S = set(G) - set(S)
    shortest_path_lengths = multi_source_dijkstra_path_length(G, set(S), weight=weight)
    for v in V_S:
        closeness += shortest_path_lengths.get(v, 0)
    try:
        return len(V_S) / closeness
    except ZeroDivisionError:
        return 0


# ---------------------------------------------------------------------------
# Traversal Extras (br-do1)
# ---------------------------------------------------------------------------


def bfs_beam_edges(G, source, value, width=None):
    """BFS with beam search.

    At each visited node, only the top-``width`` neighbours (ordered by
    ``value`` descending) are enqueued for further exploration. Matches
    networkx's implementation — the old fnx version filtered the whole
    frontier instead, which let far more edges slip through and
    diverged from nx by an order of magnitude on karate (32 vs 7).
    """
    if width is None:
        width = len(G)

    def successors(v):
        return iter(
            sorted(G.neighbors(v), key=value, reverse=True)[:width]
        )

    yield from generic_bfs_edges(G, source, successors)


def bfs_labeled_edges(G, sources):
    """BFS yielding NetworkX-style ``(u, v, label)`` triples.

    Signature matches networkx: ``sources`` is required and may be a single
    node or an iterable of nodes.

    br-r37-c1-bfslabnative: ported nx's exact generator in-process (BFS over the
    native adjacency, which iterates in nx's `G._adj` order) instead of paying a
    full fnx->nx conversion per call. Labels: 'tree' (first discovery), 'forward'
    (u shallower than already-seen v), 'level' (same layer), 'reverse' (directed,
    u deeper). Byte-exact triple order verified vs nx.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if sources in G:
        sources = [sources]
    directed = G.is_directed()
    visited = set()
    # nx trick: undirected uses visited.add (so 'level' edges fire once on first
    # occurrence); directed uses visited.discard (a no-op keeping visited empty).
    visit = visited.discard if directed else visited.add
    depth = {s: 0 for s in sources}
    queue = _deque(depth.items())
    while queue:
        u, du = queue.popleft()
        for v in G[u]:
            if v not in depth:
                depth[v] = dv = du + 1
                queue.append((v, dv))
                yield u, v, "tree"
            else:
                dv = depth[v]
                if du == dv:
                    if v not in visited:
                        yield u, v, "level"
                elif du < dv:
                    yield u, v, "forward"
                elif directed:
                    yield u, v, "reverse"
        visit(u)


def dfs_labeled_edges(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """DFS yielding NetworkX-style traversal event triples.

    br-r37-c1-bfslabnative: ported nx's exact stack-based generator in-process
    (DFS over native `G.neighbors`, a stateful iterator resumed via the stack, in
    nx's order) instead of a full fnx->nx conversion per call. Byte-exact triple
    order verified vs nx.

    br-r37-c1-qnj0n: rows come from ``G.neighbors`` when the walk reaches a
    node, as in nx. The whole-graph ``to_dict_of_lists(G)`` snapshot this
    replaced cost O(V+E) before the first event of a walk that might touch
    four nodes (156 ms against nx's 7 us for a depth-3 walk beside a 64k-node
    component), and a snapshot row cannot see a mutation the way nx's live row
    does. A source missing from G still reaches G.neighbors and raises nx's
    NetworkXError after the start's "forward" event (br-r37-c1-750hp).
    """
    if not _point_query_uses_private_rows(G):
        G = _coerce_arg_to_fnx_graph(G)
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


def generic_bfs_edges(G, source, neighbors=None, depth_limit=None):
    """BFS with customizable neighbor function.

    br-r37-c1-lnqss: the Rust _fnx.generic_bfs_edges_rust default
    path yielded edges with adj iteration in a different order than
    nx (e.g. for adj[a]=[b,c], fnx returned (a,c),(a,b),... while
    nx yields (a,b),(a,c),...). Route through the Python path
    always, defaulting neighbors=G.neighbors when None.

    br-r37-c1-mub4s: networkx's loop line for line. ``neighbors(child)`` is
    called when the child is DISCOVERED - before its edge is yielded, and for
    children on the last level ``depth_limit`` allows - and the walk stops as
    soon as every node is seen. The level-queue this replaced called it when
    the child was expanded, so a callable with effects (a counter, a sort that
    records, a lazy row) saw different calls, and a row was consumed lazily
    there only by accident.
    """
    if neighbors is None:
        neighbors = G.neighbors
    if depth_limit is None:
        depth_limit = len(G)
    seen = {source}
    n = len(G)
    depth = 0
    next_parents_children = [(source, neighbors(source))]
    while next_parents_children and depth < depth_limit:
        this_parents_children = next_parents_children
        next_parents_children = []
        for parent, children in this_parents_children:
            for child in children:
                if child not in seen:
                    seen.add(child)
                    next_parents_children.append((child, neighbors(child)))
                    yield parent, child
            if len(seen) == n:
                return
        depth += 1


# ---------------------------------------------------------------------------
# Utility Extras A (br-tnl)
# ---------------------------------------------------------------------------


def _lp_community_of(G, node, community):
    """br-shcomm: lift nx's NetworkXAlgorithmError when a node lacks
    the community attribute, matching the link-prediction contract.
    """
    attrs = G.nodes[node]
    try:
        return attrs[community]
    except (KeyError, TypeError) as err:
        raise NetworkXAlgorithmError(
            f"No community information available for Node {node}"
        ) from err


def cn_soundarajan_hopcroft(G, ebunch=None, community="community"):
    """Common Neighbor link prediction with community information.

    br-shcomm: nx raises NetworkXAlgorithmError when any node in ebunch
    lacks the community attribute. fnx previously treated missing
    community as None and silently computed a plain common-neighbor
    _count without the bonus — a correctness trap for callers that
    assumed nx contract. Now raises the same error.

    br-r37-c1-fa5tf: nx is @not_implemented_for('directed',
    'multigraph'). Pre-fix fnx fell through to the per-node
    community-attr check and raised NetworkXAlgorithmError instead
    of NetworkXNotImplemented. Raise the type error eagerly (on
    function call, matching nx's argmap behavior) so iteration
    never reaches the community check on multi/directed inputs.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        # br-r37-c1-shlazy: lazily memoize neighbour sets so a small ebunch only
        # touches its endpoints instead of snapshotting the whole adjacency. The
        # old whole-graph snapshot was the entire cost for a small ebunch
        # (~340x slower than nx on a 10-pair ebunch over n=2000); the default
        # all-non-edges path still computes each neighbour set once. Score is an
        # integer count, so the result is byte-identical.
        nbr_set_cache = {}
        comm_cache = {}

        def nbr_set(x):
            r = nbr_set_cache.get(x)
            if r is None:
                r = set(G.neighbors(x))
                nbr_set_cache[x] = r
            return r

        def comm(x):
            # memoize the per-node community lookup (a PyO3 node-attr access);
            # default ebunch revisits the same w across many pairs. A missing
            # community still raises NetworkXAlgorithmError (never cached).
            if x in comm_cache:
                return comm_cache[x]
            c = _lp_community_of(G, x, community)
            comm_cache[x] = c
            return c

        eb = non_edges(G) if ebunch is None else ebunch
        for u, v in eb:
            u_comm = comm(u)
            v_comm = comm(v)
            nv = nbr_set(v)
            same = u_comm == v_comm
            score = 0
            for w in nbr_set(u):
                if w in nv and w != u and w != v:
                    score += 1
                    if same and comm(w) == u_comm:
                        score += 1
            yield (u, v, score)

    return _gen()


def ra_index_soundarajan_hopcroft(G, ebunch=None, community="community"):
    """Resource Allocation link prediction with community information.

    br-shcomm: see cn_soundarajan_hopcroft — same missing-community
    contract. Also, nx's formula is simply sum(1/deg(w)) for common
    neighbors w whose community == Cu, when Cu==Cv; else 0. fnx's
    previous formula added a per-w bonus term that was never part of
    the nx definition, producing systematically larger scores.

    br-r37-c1-fa5tf: same multigraph/directed eager-raise pattern as
    cn_soundarajan_hopcroft. See that function for details.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    def _gen():
        # br-r37-c1-shlazy: lazily memoize neighbour lists/sets/degrees so a
        # small ebunch only touches its endpoints (the old whole-graph snapshot
        # was ~500x slower than nx on a 10-pair ebunch over n=2000). Common
        # neighbours are iterated in G.neighbors(u) order and summed with the
        # builtin sum (nx's exact common_neighbors order + compensated sum), so
        # the score is now BYTE-identical to nx (the old set-order naive fold
        # drifted by ULPs on ~28% of cases).
        nbr_order_cache = {}
        nbr_set_cache = {}
        deg_cache = {}
        comm_cache = {}

        def nbr_order(x):
            r = nbr_order_cache.get(x)
            if r is None:
                r = list(G.neighbors(x))
                nbr_order_cache[x] = r
            return r

        def nbr_set(x):
            r = nbr_set_cache.get(x)
            if r is None:
                r = set(nbr_order(x))
                nbr_set_cache[x] = r
            return r

        def deg(x):
            r = deg_cache.get(x)
            if r is None:
                r = G.degree(x)
                deg_cache[x] = r
            return r

        def comm(x):
            # memoize the per-node community lookup (PyO3 node-attr access);
            # a missing community still raises NetworkXAlgorithmError.
            if x in comm_cache:
                return comm_cache[x]
            c = _lp_community_of(G, x, community)
            comm_cache[x] = c
            return c

        eb = non_edges(G) if ebunch is None else ebunch
        for u, v in eb:
            u_comm = comm(u)
            v_comm = comm(v)
            if u_comm != v_comm:
                # br-shratype: nx returns int 0 here (no division on early
                # return); match exactly so type-sensitive callers don't
                # diverge.
                yield (u, v, 0)
                continue
            nv = nbr_set(v)
            score = sum(
                1 / deg(w)
                for w in nbr_order(u)
                if w in nv and w != u and w != v and comm(w) == u_comm
            )
            yield (u, v, score)

    return _gen()


def node_attribute_xy(G, attribute, nodes=None):
    """Yield (x, y) pairs of attribute values for edges.

    ``nodes`` restricts the source side: when given, only edges whose
    source is in ``nodes`` are emitted. Matches networkx's public
    signature ``node_attribute_xy(G, attribute, nodes=None)``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    node_filter = None if nodes is None else set(nodes)
    # br-r37-c1-bjrgc: pre-materialize the node-attribute dict ONCE.
    # br-r37-c1-br82u: bypass G.adjacency() AtlasView for non-multigraph
    # via _raw_neighbors_dispatch.
    # br-r37-c1-bxvof: factor the per-node attr-resolution policy into
    # a single closure so the fast/slow/multigraph branches share one
    # source of truth (was duplicated at 5 callsites).
    try:
        node_attrs = dict(G.nodes(data=True))
    except (TypeError, AttributeError):
        node_attrs = None
    if node_attrs is not None:
        def _attr_for(node):
            return node_attrs.get(node, {}).get(attribute)
    else:
        nodes_view = G.nodes
        nodes_view_supports_getitem = hasattr(nodes_view, "__getitem__")
        def _attr_for(node):
            if not nodes_view_supports_getitem:
                return None
            attrs = nodes_view[node]
            return attrs.get(attribute) if isinstance(attrs, dict) else None
    _raw_nbrs = _raw_neighbors_dispatch(G) if not G.is_multigraph() else None
    if _raw_nbrs is not None:
        # Fast non-multigraph path: iterate G's nodes + raw neighbors.
        for u in G:
            if node_filter is not None and u not in node_filter:
                continue
            x = _attr_for(u)
            for v in _raw_nbrs(G, u):
                yield (x, _attr_for(v))
        return
    # Slow path: multigraph (needs AtlasView's keys structure for
    # parallel-edge counting) OR private-storage graph.
    for u, nbrsdict in G.adjacency():
        if node_filter is not None and u not in node_filter:
            continue
        x = _attr_for(u)
        if G.is_multigraph():
            for v, keys in nbrsdict.items():
                y = _attr_for(v)
                for _ in keys:
                    yield (x, y)
        else:
            for v in nbrsdict:
                yield (x, _attr_for(v))


def node_degree_xy(G, x="out", y="in", weight=None, nodes=None):
    """Yield (degree_x, degree_y) for each edge.

    br-r37-c1-6yimw: nx iterates ``xdeg(set(nodes))`` which yields
    nodes in hash-set order (since the implementation calls
    ``set(G)`` and iterates that). The previous fnx loop walked
    ``present_nodes`` (G.nodes()-insertion order), drifting tuple
    iteration order from nx. Replicate nx's exact algorithm.
    """
    node_set = set(G) if nodes is None else set(nodes)
    if G.is_directed():
        direction = {"out": G.out_degree, "in": G.in_degree}
        xdeg = direction[x]
        ydeg = direction[y]
    else:
        xdeg = ydeg = G.degree

    # br-r37-c1-wqhqr: nx recomputes each neighbor's y-degree via a FRESH
    # DegreeView per source node (``ydeg(neighbors)``) — O(E) degree
    # recomputations, each a per-node round-trip. Precompute the full
    # y-degree map ONCE (single bulk pass) and replace the inner view with
    # a dict lookup. ``dy[v]`` is identical to ``ydeg(v)`` for every node,
    # so this is byte-exact in both VALUE and ITERATION ORDER: the outer
    # ``xdeg(node_set)`` (source order + degu) and per-node ``G.edges(u)``
    # (neighbor order, multigraph parallel-edge multiplicity, self-loops)
    # are unchanged.
    dy = dict(ydeg(weight=weight))

    # Whole-graph fast path: nx's per-node ``G.edges(u)`` builds a fresh
    # EdgeView per source node (O(V) PyO3 view allocations on the fnx
    # substrate). For the default (nodes=None), non-multigraph case, snapshot
    # the entire adjacency with ONE native ``_native_adjacency_keys`` call
    # (verified to yield neighbours in exact ``G.edges(u)`` order, self-loops
    # included) and iterate it as a pure-Python dict — identical emission
    # order to nx (source order via ``set(G)``; neighbour order via the
    # snapshot). Multigraph (no native keys snapshot) and the ``nodes``
    # subset case keep the per-node path above.
    nak = getattr(G, "_native_adjacency_keys", None)
    if nodes is None and nak is not None and type(G) in (Graph, DiGraph):
        # undirected: xdeg is ydeg, so reuse dy (one degree pass instead of two)
        dx = dy if not G.is_directed() else dict(xdeg(weight=weight))
        adj = dict(nak())
        for u in node_set:
            degu = dx[u]
            for nbr in adj[u]:
                yield degu, dy[nbr]
        return

    for u, degu in xdeg(node_set, weight=weight):
        # use G.edges to treat multigraphs correctly (each
        # parallel edge yields a separate tuple).
        for _, nbr in G.edges(u):
            if nbr in node_set:
                yield degu, dy[nbr]


def number_of_walks(G, walk_length, *, backend=None, **backend_kwargs):
    """Count walks of given length via adjacency matrix power."""
    import numpy as np

    _validate_backend_dispatch_keywords("number_of_walks", backend, backend_kwargs)
    if len(G) == 0:
        raise NetworkXError("Graph has no nodes or edges")
    if walk_length < 0:
        raise ValueError(f"`walk_length` cannot be negative: {walk_length}")
    if not isinstance(walk_length, _numbers.Integral):
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
