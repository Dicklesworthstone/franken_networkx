

def dispersion(
    G,
    u=None,
    v=None,
    normalized=True,
    alpha=1.0,
    b=0.0,
    c=0.0,
    *,
    backend=None,
    **backend_kwargs,
):
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
    _validate_backend_dispatch_keywords("dispersion", backend, backend_kwargs)
    if u is not None and v is not None:
        return _dispersion_pair(G, u, v, normalized, alpha, b, c)

    # br-r37-c1-disp-keyerr: same KeyError contract on the dict-form
    # path (``dispersion(G, u=99)``).  nx accesses ``G[u]`` which
    # raises KeyError; fnx's ``G.neighbors(u)`` raised NetworkXError.
    if u is not None and u not in G:
        raise KeyError(u)
    # br-r37-c1-o53cp: native bitset kernel for the full dict form. The
    # Backstrom-Kleinberg ``disp`` count is an order-invariant integer and the
    # predicate is symmetric in the common-neighbour pair, so the result is
    # byte-identical to the Python path. Gated to undirected simple loop-free
    # graphs with the normalized formula: the kernel uses an undirected
    # adjacency (directed dispersion needs successor-only neighbours), assumes
    # ``u`` is never its own neighbour, and returns floats (normalized=False
    # yields int ``disp`` values, kept on the Python path).
    if (
        u is None
        and v is None
        and normalized
        and not G.is_directed()
        and not G.is_multigraph()
        and number_of_selfloops(G) == 0
    ):
        try:
            return _fnx.dispersion_full_rust(
                _coerce_arg_to_fnx_graph(G), float(alpha), float(b), float(c)
            )
        except Exception:
            pass  # fall through to the Python path on any kernel issue
    # br-r37-c1-dispadj: the dict form recomputed ``set(G.neighbors(x))`` from
    # the String-keyed substrate for every (node, nbr) pair AND every common
    # neighbour ``s``/``t`` inside ``_dispersion_pair`` -- O(E * embeddedness^2)
    # neighbour materializations that left fnx ~3x SLOWER than networkx (which
    # walks its native dict adjacency). Precompute every adjacency set ONCE and
    # reuse it; the set logic is identical and ``disp`` is an order-invariant
    # integer count, so the float results are byte-for-byte unchanged.
    # br-r37-c1-brlzk: keep BOTH the insertion-ordered neighbour list and the
    # set. The ordered list is required to build ``common`` in nx's exact
    # iteration order: when a self-loop puts ``v`` (or ``u``) into ``common``
    # the dispersion predicate is asymmetric, so nx's ``combinations(ST, 2)``
    # order over ``G[v]`` decides the count. fnx's neighbour order matches nx,
    # so iterating the ordered list (not the set) reproduces it. The set is
    # kept for O(1) membership in the inner predicate.
    # br-r37-c1-dispego: the single-node ego form (``dispersion(G, u)`` — the
    # canonical Backstrom-Kleinberg "find the partner" usage) only ever touches
    # the adjacency of ``u`` and of u's neighbours: every ``common`` neighbour
    # s/t lies in N(u), and the predicate reads adj[v]/adj[s]/adj[t] for v,s,t in
    # N(u). Building the whole-graph adjacency snapshot to answer about one node
    # was an O(V+E) tax (~138x slower than nx, which walks ``G[x]`` lazily).
    # Restrict the snapshot to ``{u} ∪ N(u)``; the set logic and iteration order
    # are unchanged, so results are byte-for-byte identical.
    if u is not None:
        # br-r37-c1-dispego: native local-universe kernel for the ego form on
        # undirected/simple/loop-free graphs with the normalized formula (same
        # gate as the full-dict kernel). Falls through to the Python path on any
        # kernel issue (e.g. the gate not met or a directed/multi graph).
        if (
            normalized
            and not G.is_directed()
            and not G.is_multigraph()
            and number_of_selfloops(G) == 0
        ):
            try:
                _row = _fnx.dispersion_node_rust(
                    _coerce_arg_to_fnx_graph(G), u, float(alpha), float(b), float(c)
                )
                if _row is not None:
                    return _row
            except Exception:
                pass
        nbr_order = {u: list(G.neighbors(u))}
        for _nbr in nbr_order[u]:
            if _nbr not in nbr_order:
                nbr_order[_nbr] = list(G.neighbors(_nbr))
        adj = {n: set(lst) for n, lst in nbr_order.items()}
        nodes = [u]
    else:
        nbr_order = {n: list(G.neighbors(n)) for n in G}
        adj = {n: set(lst) for n, lst in nbr_order.items()}
        nodes = list(G.nodes())
    result = {}
    for node in nodes:
        result[node] = {}
        for nbr in nbr_order[node]:
            result[node][nbr] = _dispersion_pair_cached(
                nbr_order, adj, node, nbr, normalized, alpha, b, c
            )
    if u is not None:
        return result[u]
    return result


def _dispersion_pair_cached(nbr_order, adj, u, v, normalized, alpha, b, c):
    # Identical to ``_dispersion_pair`` but reads from precomputed adjacency
    # (``nbr_order`` insertion-ordered lists + ``adj`` membership sets) instead
    # of calling ``G.neighbors`` per pair. ``common`` is built by iterating the
    # ordered neighbour list of ``v`` so its set-iteration order matches nx's
    # ``ST`` (needed for self-loop parity, br-r37-c1-brlzk). Membership /
    # KeyError contracts are enforced by the caller (every node comes from G).
    u_nbrs = adj[u]
    common = {n for n in nbr_order[v] if n in u_nbrs}
    set_uv = {u, v}

    disp = 0
    common_list = list(common)
    for i in range(len(common_list)):
        for j in range(i + 1, len(common_list)):
            s, t = common_list[i], common_list[j]
            nbrs_s = u_nbrs & adj[s] - set_uv
            if t not in nbrs_s and nbrs_s.isdisjoint(adj[t]):
                disp += 1

    embeddedness = len(common)
    if normalized:
        val = (disp + b) ** alpha
        if embeddedness + c != 0:
            val = val / (embeddedness + c)
        return val
    return disp


def _dispersion_pair(G, u, v, normalized, alpha, b, c):
    # Match networkx's algorithm exactly (Backstrom & Kleinberg). Two
    # earlier fnx bugs: (a) the "no shared connection" check restricted
    # the shared neighbour to ``common``; nx only requires it be in u's
    # neighbourhood, and (b) the normalisation raised ``alpha`` on the
    # denominator rather than the numerator.
    # br-r37-c1-disp-keyerr: nx accesses ``G[u]`` / ``G[v]`` directly,
    # which raises ``KeyError`` when a node is missing.  fnx used
    # ``G.neighbors(...)`` which raises NetworkXError.  Pre-check
    # membership and raise KeyError to match nx's leaky-but-stable
    # contract (callers using ``except KeyError:`` to detect missing
    # node-pairs were broken otherwise).
    if u not in G:
        raise KeyError(u)
    if v not in G:
        raise KeyError(v)
    u_nbrs = set(G.neighbors(u))
    common = {n for n in G.neighbors(v) if n in u_nbrs}
    set_uv = {u, v}

    disp = 0
    common_list = list(common)
    for i in range(len(common_list)):
        for j in range(i + 1, len(common_list)):
            s, t = common_list[i], common_list[j]
            nbrs_s = u_nbrs & set(G.neighbors(s)) - set_uv
            if t not in nbrs_s and nbrs_s.isdisjoint(G.neighbors(t)):
                disp += 1

    embeddedness = len(common)
    if normalized:
        val = (disp + b) ** alpha
        if embeddedness + c != 0:
            val = val / (embeddedness + c)
        return val
    return disp


def closeness_vitality(
    G,
    node=None,
    weight=None,
    wiener_index=None,
    *,
    backend=None,
    **backend_kwargs,
):
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
    _validate_backend_dispatch_keywords("closeness_vitality", backend, backend_kwargs)
    # br-r37-c1-cvnative: the all-nodes unweighted undirected case previously
    # called ``G.subgraph(set(G) - {v}).copy()`` once per node — each copy is the
    # full-graph construction tax (~3.6ms on n=80), so the loop ran ~13x SLOWER
    # than networkx. Route the CONNECTED case to the native Rust kernel instead (a
    # single pass that computes every Wiener-index delta over integer adjacency).
    # The kernel emits values keyed by internal node id, so re-key in ``G``'s node
    # order to match nx's ``{v: ... for v in G}`` dict. Gate on the exact concrete
    # ``Graph`` type (the kernel reads the full Rust adjacency, which would bypass
    # SubgraphView filtering, and only handles undirected simple graphs) and on
    # connectivity: for a disconnected graph nx's per-node result depends on
    # whether removing the node reconnects it (``inf`` vs ``nan``), which the
    # native kernel does not reproduce, so that case keeps the exact Python path.
    if (
        node is None
        and weight is None
        and wiener_index is None
        and type(G) is Graph
        and G.number_of_nodes() >= 2
        and is_connected(G)
    ):
        raw = _rust_closeness_vitality(G)
        return {v: raw[v] for v in G}
    wi = (
        wiener_index
        if wiener_index is not None
        else globals()["wiener_index"](G, weight=weight)
    )
    if node is not None:
        after_graph = G.subgraph(set(G) - {node}).copy()
        after = globals()["wiener_index"](after_graph, weight=weight)
        return wi - after
    return {
        v: closeness_vitality(G, node=v, weight=weight, wiener_index=wi) for v in G
    }


def _tracemin_fiedler_pcg(L, X, normalized, tol):
    import numpy as np
    import scipy as sp
    from scipy.linalg.blas import dasum, daxpy, ddot
    from scipy.sparse._sparsetools import csr_matvec

    n = X.shape[0]
    if normalized:
        e = np.sqrt(L.diagonal())
        D_norm = sp.sparse.dia_array((1 / e, 0), shape=(n, n)).tocsr()
        L = D_norm @ L @ D_norm
        e *= 1.0 / np.linalg.norm(e, 2)

        def project(X_arr):
            X_arr = np.asarray(X_arr)
            for j in range(X_arr.shape[1]):
                X_arr[:, j] -= (X_arr[:, j] @ e) * e
    else:

        def project(X_arr):
            X_arr = np.asarray(X_arr)
            for j in range(X_arr.shape[1]):
                X_arr[:, j] -= X_arr[:, j].sum() / n

    L_csr = L if sp.sparse.isspmatrix_csr(L) or isinstance(L, sp.sparse.csr_array) else L.tocsr()
    indptr = L_csr.indptr
    indices = L_csr.indices
    data = L_csr.data.astype(float, copy=False)
    D = L.diagonal().astype(float)
    Ap = np.empty(n, dtype=float)

    def solve_pcg(B, tol_outer):
        B = np.asarray(B)
        X_sol = np.ndarray(B.shape, order="F")
        for j in range(B.shape[1]):
            b = B[:, j]
            tol_b = tol_outer * dasum(b)
            x = np.zeros(b.shape)
            r = b.copy()
            z = D * r
            rz = ddot(r, z)
            p = z.copy()
            while True:
                Ap.fill(0.0)
                csr_matvec(n, n, indptr, indices, data, p, Ap)
                alpha = rz / ddot(p, Ap)
                x = daxpy(p, x, a=alpha)
                r = daxpy(Ap, r, a=-alpha)
                if dasum(r) < tol_b:
                    X_sol[:, j] = x
                    break
                z = D * r
                beta = ddot(r, z)
                beta, rz = beta / rz, beta
                p = daxpy(p, z, a=beta)
        return X_sol

    Lnorm = abs(L).sum(axis=1).flatten().max()
    project(X)
    W = np.ndarray(X.shape, order="F")

    while True:
        X = np.linalg.qr(X)[0]
        W[:, :] = L @ X
        H = X.T @ W
        sigma, Y = sp.linalg.eigh(H, overwrite_a=True)
        X = X @ Y
        res = dasum(W @ Y[:, 0] - sigma[0] * X[:, 0]) / Lnorm
        if res < tol:
            break
        W[:, :] = solve_pcg(X, tol)
        X = (sp.linalg.inv(W.T @ X) @ W.T).T
        project(X)

    return sigma[0], np.asarray(X)[:, 0]


def _spectral_ordering_inproc(
    G,
    weight="weight",
    normalized=False,
    tol=1e-08,
    method="tracemin_pcg",
    seed=None,
):
    try:
        seed = _numpy_random_state(seed)
        if len(G) == 0:
            raise NetworkXError("graph is empty.")
        import numpy as np
        import networkx.linalg.algebraicconnectivity as ac

        G_prep = ac._preprocess_graph(G, weight)
        find_fiedler = ac._get_fiedler_func(method)
        order = []
        for component in connected_components(G_prep):
            size = len(component)
            if size > 2:
                L = laplacian_matrix(G_prep, component)
                if method in ("tracemin_pcg", "tracemin"):
                    X = np.asarray(seed.normal(size=(1, L.shape[0]))).T
                    sigma, fiedler = _tracemin_fiedler_pcg(L, X, normalized, tol)
                else:
                    x = None if method != "lobpcg" else ac._rcm_estimate(G_prep, component)
                    sigma, fiedler = find_fiedler(L, x, normalized, tol, seed)
                sort_info = zip(fiedler, range(size), component)
                order.extend(u for x, c, u in sorted(sort_info))
            else:
                order.extend(component)
        return order
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def spectral_ordering(
    G,
    weight="weight",
    normalized=False,
    tol=1e-08,
    method="tracemin_pcg",
    seed=None,
):
    """Return nodes ordered by the Fiedler vector (spectral bisection ordering).

    br-r37-c1-xiqgr: the local fiedler_vector + argsort path picked
    the eigenvector with whichever sign scipy's eigensolver returned,
    which differed from nx's choice on many graphs (giving e.g.
    [4,3,2,1,0] instead of nx's [0,1,2,3,4] on a path graph). The
    Fiedler vector is sign-ambiguous so both are mathematically
    valid, but drop-in code comparing the ordering to nx's reference
    broke. Delegate to nx so the chosen sign + tie-break match
    exactly.
    """
    return _spectral_ordering_inproc(
        G,
        weight=weight,
        normalized=normalized,
        tol=tol,
        method=method,
        seed=seed,
    )


def _bellman_ford_weight_function(G, weight):
    if callable(weight):
        return weight
    if G.is_multigraph():
        return lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    return lambda u, v, data: data.get(weight, 1)


def _bellman_ford_adjacency_entries(G):
    if G.is_multigraph():
        for u in G:
            for v, keyed_data in G.adj[u].items():
                yield u, v, keyed_data
        return
    for u in G:
        for v, data in G.adj[u].items():
            yield u, v, data


def bellman_ford_predecessor_and_distance(
    G, source, target=None, weight="weight", heuristic=False
):
    """Return predecessors and distances from Bellman-Ford.

    Parameters
    ----------
    G : Graph or DiGraph
    source : node
    target : node, optional
    weight : str or callable, optional
    heuristic : bool, optional

    Returns
    -------
    (pred, dist) : tuple of dicts
        pred maps each node to its predecessor list.
        dist maps each node to its distance from source.

    br-r37-c1-bfslow: the pure-Python relaxation loop below is the
    textbook O(N·E) algorithm and on a 200-node 1k-edge graph ran in
    ~96ms — 128× slower than ``nx.bellman_ford_predecessor_and_distance``,
    which uses an SLF-queue optimization in its inner loop.  Delegate
    to nx unconditionally; the conversion cost (~6ms post the
    backend.py topo / attr-cache fix in br-r37-c1-d4h4l) is far less
    than the ~90ms saved.
    """
    del target, heuristic

    if source not in G:
        raise NodeNotFound(f"Node {source} is not found in the graph")

    # br-bfport: port nx's SPFA Bellman-Ford in-process for simple Graph/DiGraph
    # (the previous code delegated to nx, paying the full fnx->nx conversion —
    # 6.85x slower than nx on small/mid graphs). nx's own naive loop was 128x
    # slower; the SPFA variant (a queue that only re-relaxes nodes whose distance
    # improved, skipping a node while any predecessor is still queued) is what
    # makes nx fast. We reproduce it byte-for-byte (pred is a dict of predecessor
    # LISTS, ties append) on a one-time native to_dict_of_dicts snapshot, so the
    # result is identical to nx with no conversion. MultiGraph / callable weight
    # keep the nx delegation.
    if type(G) in (Graph, DiGraph) and not callable(weight):
        return _bellman_ford_pred_dist_inprocess(G, source, weight)

    return _bellman_ford_predecessor_and_distance_inproc(
        G, source, weight=weight
    )


def _bellman_ford_predecessor_and_distance_inproc(G, source, target=None, weight="weight", heuristic=False):
    if source not in G:
        raise NodeNotFound(f"Node {source} is not found in the graph")
    weight_fn = _weight_function(G, weight)
    if G.is_multigraph():
        if any(
            weight_fn(u, v, {k: d}) < 0
            for u, v, k, d in selfloop_edges(G, keys=True, data=True)
        ):
            raise NetworkXUnbounded("Negative cycle detected.")
    else:
        if any(weight_fn(u, v, d) < 0 for u, v, d in selfloop_edges(G, data=True)):
            raise NetworkXUnbounded("Negative cycle detected.")

    dist = {source: 0}
    pred = {source: []}

    if len(G) == 1:
        return pred, dist

    dist = _bellman_ford_inproc(
        G, [source], weight_fn, pred=pred, dist=dist, target=target, heuristic=heuristic
    )
    return (pred, dist)


def _bellman_ford_pred_dist_inprocess(G, source, weight):
    """networkx ``bellman_ford_predecessor_and_distance`` (SPFA variant,
    heuristic=False — the public default) on a native adjacency snapshot. Byte-
    identical (pred dict of lists, dist) to nx, no fnx->nx conversion."""
    from collections import deque as _deque

    g_succ = {
        u: {v: attrs.get(weight, 1) for v, attrs in row.items()}
        for u, row in to_dict_of_dicts(G).items()
    }
    # Negative self-loop is a negative cycle (matches nx).
    for u, nbrs in g_succ.items():
        if u in nbrs and nbrs[u] < 0:
            raise NetworkXUnbounded("Negative cycle detected.")

    dist = {source: 0}
    pred = {source: []}
    if len(g_succ) == 1:
        return pred, dist

    inf = float("inf")
    n = len(g_succ)
    count = {}
    q = _deque([source])
    in_q = {source}
    while q:
        u = q.popleft()
        in_q.remove(u)
        # Skip relaxing u while any of its predecessors is still queued.
        if all(pred_u not in in_q for pred_u in pred[u]):
            dist_u = dist[u]
            for v, w in g_succ[u].items():
                dist_v = dist_u + w
                if dist_v < dist.get(v, inf):
                    if v not in in_q:
                        q.append(v)
                        in_q.add(v)
                        count_v = count.get(v, 0) + 1
                        if count_v == n:
                            raise NetworkXUnbounded("Negative cycle detected.")
                        count[v] = count_v
                    dist[v] = dist_v
                    pred[v] = [u]
                elif dist.get(v) is not None and dist_v == dist.get(v):
                    pred[v].append(u)
    return pred, dist


# ---------------------------------------------------------------------------
# Communicability and subgraph centrality (matrix exponential)
# ---------------------------------------------------------------------------


def communicability(G, *, backend=None, **backend_kwargs):
    """Return communicability between all pairs of nodes.

    Based on the matrix exponential of the adjacency matrix.

    Returns
    -------
    dict of dicts
        ``result[u][v]`` is the communicability between u and v.
    """
    _validate_backend_dispatch_keywords(
        "communicability",
        backend,
        backend_kwargs,
    )
    import numpy as np

    # br-r37-c1-tqimg: nx is @not_implemented_for('multigraph').
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

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


def subgraph_centrality(G, *, normalized=False, backend=None, **backend_kwargs):
    """Return the subgraph centrality for each node.

    The subgraph centrality is the diagonal of the matrix exponential
    of the adjacency matrix.

    Returns
    -------
    dict
        ``{node: centrality}``
    """
    _validate_backend_dispatch_keywords(
        "subgraph_centrality",
        backend,
        backend_kwargs,
    )

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-sceigh: the native subgraph_centrality_expdiag_rust kernel (matrix-exp
    # diagonal) is a PESSIMIZATION vs the dense LAPACK eigendecomposition below — the
    # gap GROWS with n (native 1.3/12/91/290ms vs eigh 0.8/2.8/17/43ms at n=100/200/400/
    # 600), so it ran 0.69x @100 and 0.19x @300 vs nx. nx's exact path (eigh + sum
    # exp(lambda)*v^2) is BYTE-identical to nx (0.00e+00) AND faster (eigh-path 1.0-1.08x).
    # Drop the native route; the dense path below handles every case.

    import numpy as np

    nodelist = list(G.nodes())
    A = to_numpy_array(G, nodelist=nodelist, weight=None)
    A[np.nonzero(A)] = 1
    # br-r37-c1-sceigh-scipy (cc): scipy.linalg.eigh (MRRR 'evr' driver, optimized
    # BLAS) is ~27x faster than np.linalg.eigh (which uses the slow 'evd' driver /
    # numpy's reference LAPACK here: 2.5ms vs 69ms at n=150). Result is identical —
    # eigenvalues match and the combine `sum(exp(lambda) * v^2)` is invariant to
    # eigenvector sign and eigenvalue ordering. 0.25x vs nx -> faster than nx.
    import scipy.linalg as _sla
    eigenvalues, eigenvectors = _sla.eigh(A)
    squared_eigenvectors = np.array(eigenvectors) ** 2
    if normalized:
        exp_eigenvalues = np.exp(eigenvalues - eigenvalues.max())
    else:
        exp_eigenvalues = np.exp(eigenvalues)
    centralities = squared_eigenvectors @ exp_eigenvalues
    return {nodelist[i]: float(centralities[i]) for i in range(len(nodelist))}


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
        ``result[d1][d2]`` is the _count of edges between nodes of
        degree d1 and degree d2.
    """
    # br-r37-c1-mixfast: vectorize the common undirected / unweighted /
    # full-graph count. node_degree_xy walks G.edges(u) per node AND
    # re-looks-up each neighbour's degree through the DegreeView (~4.8x nx).
    # Here count degree pairs over the native edge list once against a native
    # degree dict. The resulting counts are IDENTICAL (an undirected non-loop
    # edge contributes (du,dv) and (dv,du); a self-loop contributes (du,du)
    # once — exactly nx's per-node G.edges(u) enumeration). Directed /
    # weighted / multigraph / nodes-subset keep the generator path (in/out
    # semantics, parallel-edge tuples, weights, node filtering).
    if (
        weight is None
        and nodes is None
        and not G.is_directed()
        and not G.is_multigraph()
        and type(G) is Graph
    ):
        deg = dict(G.degree())
        result = {}
        for u, v in G.edges():
            du = deg[u]
            dv = deg[v]
            inner = result.setdefault(du, {})
            inner[dv] = inner.get(dv, 0) + 1
            if u != v:
                inner2 = result.setdefault(dv, {})
                inner2[du] = inner2.get(du, 0) + 1
        if normalized:
            total = sum(sum(inner.values()) for inner in result.values())
            if total:
                for inner in result.values():
                    for key in inner:
                        inner[key] /= total
        return result
    return mixing_dict(
        node_degree_xy(G, x=x, y=y, weight=weight, nodes=nodes),
        normalized=normalized,
    )


def degree_mixing_matrix(
    G,
    x="out",
    y="in",
    weight=None,
    nodes=None,
    normalized=True,
    mapping=None,
):
    """Return the degree mixing matrix of *G*.

    Returns
    -------
    numpy.ndarray
        2D array where entry (i,j) counts edges between nodes of
        degree i and degree j.
    """
    import numpy as np

    mixing = degree_mixing_dict(
        G,
        x=x,
        y=y,
        weight=weight,
        nodes=nodes,
        normalized=False,
    )
    if mapping is None:
        # br-mixmap: nx builds the default mapping from the set union of
        # outer keys + all inner keys, mirroring networkx.utils.misc.
        # _dict_to_numpy_array2. fnx's old ``list(mixing)`` used insertion
        # order of the outer dict alone, which (a) skipped inner-only
        # degrees like deg=1 that only appear as a neighbor degree and
        # (b) put the rows/cols in a different order than nx, so
        # M[i,j]-by-position didn't match between libraries.
        s = set(mixing.keys())
        for _, inner in mixing.items():
            s.update(inner.keys())
        mapping = dict(zip(s, range(len(s))))

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

    # br-assortfast: numeric assortativity is the Pearson correlation of the
    # attribute values across edges -- invariant to edge order. For the common
    # case (undirected simple graph, no self-loops, nodes=None) get the edge
    # endpoint index arrays natively (adjacency_default_order_index_arrays, which
    # yields both directions of each undirected edge) and compute Pearson's r in a
    # single vectorized pass -- ~2.5x FASTER than the slow node_attribute_xy
    # iterator + attribute_mixing_matrix. Any non-applicable case falls through.
    if (
        nodes is None
        and not G.is_directed()
        and not G.is_multigraph()
        and G.number_of_edges() > 0
        and number_of_selfloops(G) == 0
    ):
        try:
            ix = _fnx.adjacency_default_order_index_arrays(G)
            if ix is not None:
                node_list = list(G.nodes())
                vals = np.asarray([G.nodes[n][attribute] for n in node_list], dtype=float)
                row, col = ix
                x = vals[np.asarray(row)]
                y = vals[np.asarray(col)]
                xm = x - x.mean()
                ym = y - y.mean()
                return float((xm * ym).sum() / np.sqrt((xm * xm).sum() * (ym * ym).sum()))
        except Exception:
            pass  # fall back to the exact mixing-matrix path below

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
    import numpy as np

    # br-assortfast: the categorical coefficient ((trace - sum(M@M)) / (1 - ...))
    # is invariant to the category->index mapping, so for the common case (
    # undirected simple graph, no self-loops, nodes=None) build the normalized
    # mixing directly from the native edge endpoint index arrays (~2.2x faster
    # than the slow node_attribute_xy / attribute_mixing_matrix path).
    if (
        nodes is None
        and not G.is_directed()
        and not G.is_multigraph()
        and G.number_of_edges() > 0
        and number_of_selfloops(G) == 0
    ):
        try:
            ix = _fnx.adjacency_default_order_index_arrays(G)
            if ix is not None:
                node_list = list(G.nodes())
                cats = [G.nodes[n][attribute] for n in node_list]
                uniq = {c: i for i, c in enumerate(dict.fromkeys(cats))}
                cidx = np.asarray([uniq[c] for c in cats])
                row, col = ix
                M = np.zeros((len(uniq), len(uniq)))
                np.add.at(M, (cidx[np.asarray(row)], cidx[np.asarray(col)]), 1.0)
                total = M.sum()
                if total > 0:
                    M = M / total
                squared_sum = (M @ M).sum()
                return float((M.trace() - squared_sum) / (1 - squared_sum))
        except Exception:
            pass  # fall back to the exact path below

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
    # br-r37-c1-aun4c: replicate installed nx VERBATIM — node and edge
    # order come from CPython SET iteration (set(G.nodes) / set(G.edges)
    # with both orientations added for undirected graphs, then in-place
    # &=), NOT from graphs[0] insertion order. The old G0-order walk
    # silently diverged on both node and edge order. Pure-Python set ops
    # over the same values reproduce nx's iteration exactly (the jv0h5
    # kneser principle); error checks fire in nx's exact sequence.
    R = None
    for i, G in enumerate(graphs):
        G_nodes_set = set(G.nodes)
        G_edges_set = set(G.edges)
        if not G.is_directed():
            if G.is_multigraph():
                G_edges_set.update((v, u, k) for u, v, k in list(G_edges_set))
            else:
                G_edges_set.update((v, u) for u, v in list(G_edges_set))
        if i == 0:
            R = G.__class__()
            node_intersection = G_nodes_set
            edge_intersection = G_edges_set
        elif G.is_directed() != R.is_directed():
            raise NetworkXError("All graphs must be directed or undirected.")
        elif G.is_multigraph() != R.is_multigraph():
            raise NetworkXError("All graphs must be graphs or multigraphs.")
        else:
            node_intersection &= G_nodes_set
            edge_intersection &= G_edges_set

    if R is None:
        raise ValueError("cannot apply intersection_all to an empty list")

    R.add_nodes_from(node_intersection)
    # br-r37-c1-urle5b: nx intersects multigraph edges by (u, v) WITHOUT keys
    # (``set(G.edges)`` yields 2-tuples), so the result edges are plain 2-tuples
    # with auto-keys — feed a LIST (not the set) so the native plain-edge batch
    # (_try_add_edges_from_batch) fires on the fresh result. ``list(...)``
    # preserves the exact CPython set-iteration order ``add_edges_from(set)``
    # would consume, leaving the inserted-edge order unchanged.
    R.add_edges_from(list(edge_intersection))
    # br-norebuild: skip the redundant _from_nx_graph second construction when R
    # is already an fnx graph; only convert nx-typed results (br-r37-c1-5388d:
    # the _nx.Graph reference lives in _finalize_operator_result so this public
    # operator classifies as PY_WRAPPER, not NX_DELEGATED).
    return _finalize_operator_result(R)


def disjoint_union_all(graphs):
    """Return the disjoint union of all graphs in the iterable."""
    graphs = list(graphs)
    if not graphs:
        # br-r37-c1-djuall-msg: nx delegates the empty-list check to
        # ``union_all`` and lets that error message bubble up — so
        # the user-visible string says "union_all" rather than
        # "disjoint_union_all".  Match the exact text so caller-side
        # string checks align (the function-name nuance is a known
        # nx leak, not a fnx improvement worth diverging on).
        raise ValueError("cannot apply union_all to an empty list")

    _validate_same_graph_family(graphs)

    # br-r37-c1-djudirect (cc): build the disjoint union directly with shifted integer
    # labels instead of relabel-each-graph (convert_node_labels_to_integers — a full
    # copy that materializes every graph's node/edge attrs) followed by union_all.
    # convert_node_labels_to_integers maps node[i] -> i + first_label in node-iteration
    # order, and union_all merges graph attrs last-wins; doing both inline (one
    # add_nodes_from + add_edges_from per graph onto the growing result) is byte-
    # identical to nx AND skips the intermediate relabeled copies. 0.71x -> 1.06x.
    result = _concrete_class_for(graphs[0])()
    first_label = 0
    for graph in graphs:
        result.graph.update(graph.graph)
        index = {node: i + first_label for i, node in enumerate(graph.nodes())}
        result.add_nodes_from(
            (index[node], dict(data)) for node, data in graph.nodes(data=True)
        )
        if graph.is_multigraph():
            result.add_edges_from(
                (index[u], index[v], key, dict(data))
                for u, v, key, data in graph.edges(keys=True, data=True)
            )
        else:
            result.add_edges_from(
                (index[u], index[v], dict(data))
                for u, v, data in graph.edges(data=True)
            )
        first_label += len(graph)
    return result


def rescale_layout(pos, scale=1):
    """Rescale layout positions to fit within [-scale, scale].

    Parameters
    ----------
    pos : numpy array or dict
        Positions as numpy array (each row is a position) or dict.
    scale : float, optional

    Returns
    -------
    numpy array or dict
        Rescaled positions (same type as input).
    """
    import numpy as np
    from franken_networkx.drawing.layout import rescale_layout as _rescale_array

    # Match NetworkX's public surface for any non-dict array-like input.
    if isinstance(pos, np.ndarray) or not isinstance(pos, dict):
        return _rescale_array(pos, scale=scale)

    # Handle dict input
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
    """Modify *G* so that mutation raises an error. Returns *G*.

    br-r37-c1-cfcls: Convert nx input to fnx for consistent return type.
    """
    if not isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-frzsetattr: write the method shadows straight into the instance
    # dict, and let only the LAST assignment go through the normal path.
    #
    # Every setattr on an fnx graph runs the class's custom __setattr__, which
    # ends in self._fnx_register_gc_dict(vars(self)). vars(self) is the SAME dict
    # object each time, so freezing re-registered one dict TWELVE times per call -
    # and freeze() measured 0.0768-0.0820x against networkx, which just rebinds
    # the names. The cost was per-assignment bookkeeping, not the assignments.
    #
    # None of these names is in _MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES or
    # _DIRECTED_CACHED_PUBLIC_NAMES, so the custom path
    # would do nothing for them except the plain write and that redundant
    # registration. `G.frozen = True` is deliberately left on the normal path, so
    # the instance dict is still registered exactly once per freeze.
    instance_dict = vars(G)
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
            instance_dict[name] = _frozen
    G.frozen = True
    return G


def is_frozen(G):
    """Return True if *G* is frozen."""
    return getattr(G, "frozen", False)


def _frozen(*args, **kwargs):
    raise NetworkXError("Frozen graph can't be modified")


# ---------------------------------------------------------------------------
# Info — removed from NetworkX in 3.0; resolved via __getattr__ to mirror nx's
# AttributeError. (br-r37-c1-m8ktl)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _Generator aliases
# ---------------------------------------------------------------------------


def _kernel_seed(seed):
    """What a native MT19937 generator kernel draws from for ``seed``.

    br-r37-c1-ols3t: networkx resolves ``seed`` with create_py_random_state
    and draws from the result. The kernels reproduce ``random.Random``
    exactly, so:

    - an int below 2**64 in absolute value is seeded in the kernel as
      ``random.seed(int)`` seeds, from ``abs(int)`` (a bool is 0 / 1);
    - an exact ``random.Random`` - the global ``random._inst`` for None, the
      instance a caller passes, ``random.Random(seed)`` for a bigger int - is
      handed to the binding, which runs the kernel on its ``getstate()`` and
      ``setstate()``s the advanced state back, as networkx advances it;
    - a numpy-backed generator, or a ``random.Random`` subclass with draws
      of its own, has no MT19937 state to hand over: ``None``, and the
      caller runs networkx's Python body on ``_generator_random_state(seed)``.

    An invalid seed raises networkx's ValueError here - callers resolve the
    seed first, before their argument checks, as networkx's decorator does.
    The previous bridge drew ONE u64 from a random.Random (and from the global
    state for None), so a kernel drew another graph than networkx and left
    the caller's generator elsewhere (br-r37-c1-rustseed, ms5et, 3a1sy).
    """
    import random as _random

    if isinstance(seed, int) and abs(seed) < 1 << 64:
        return abs(seed)
    # the two common streamed seeds, without _generator_random_state's setup
    if seed is None:
        return _random._inst
    if type(seed) is _random.Random:
        return seed
    rng = _generator_random_state(seed)
    return rng if type(rng) is _random.Random else None


def _validate_backend_dispatch_keywords(function_name, backend, backend_kwargs):
    # br-r37-c1-rc0923-epic-honest-measurement-vbneu.1: this library IS the
    # installed "franken_networkx" backend, so its own name must run here just
    # like "networkx" does; rejecting it made portable code such as
    # ``pagerank(G, backend="franken_networkx")`` raise "'franken_networkx'
    # backend is not installed" under fnx while networkx accepted it.
    if backend is not None and backend not in ("networkx", "franken_networkx"):
        from networkx.utils.backends import backends as _installed_backends

        if backend in _installed_backends:
            raise NotImplementedError(
                f"franken_networkx.{function_name} runs its own implementation and "
                f"cannot dispatch to the {backend!r} backend; call "
                f"networkx.{function_name}(..., backend={backend!r}) instead"
            )
        raise ImportError(f"'{backend}' backend is not installed")
    if backend_kwargs:
        unexpected = next(iter(backend_kwargs))
        raise TypeError(f"{function_name}() got an unexpected keyword argument '{unexpected}'")


def binomial_graph(
    n, p, seed=None, directed=False, *, create_using=None, backend=None, **backend_kwargs
):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    _validate_backend_dispatch_keywords("binomial_graph", backend, backend_kwargs)
    return gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=create_using,
    )


def gnp_random_graph(n, p, seed=None, directed=False, *, create_using=None, backend=None, **backend_kwargs):
    """Return a G(n,p) random graph."""
    _validate_backend_dispatch_keywords("gnp_random_graph", backend, backend_kwargs)
    # br-r37-c1-ols3t: nx's py_random_state, resolved first; the kernels
    # draw from an int seed or stream a random.Random's state (None is the
    # global random._inst), and a numpy-backed seed takes the body below.
    kernel_seed = _kernel_seed(seed)
    # br-gnpvalid: match nx's NetworkXError for negative n before the
    # Rust binding surfaces OverflowError (Rust takes usize so negative
    # n crashes with a Python type-conversion error).
    if n < 0:
        raise NetworkXError(f"Negative number of nodes not valid: {n}")
    # br-r37-c1-lsdek: nx silently accepts ``p`` outside [0, 1] —
    # ``p >= 1`` produces the complete graph, ``p <= 0`` produces
    # the empty graph (the Python fallback below handles both
    # cases).  fnx's Rust ``_rust_gnp_random_graph`` validates p
    # strictly and raises ``ValueError("FailClosed { ... p=... is
    # outside [0.0, 1.0] }")`` (Rust internals leak too).  Route
    # out-of-range p through the Python path for parity.
    # 0 < p < 1 only: networkx returns the empty / complete graph for p <= 0 /
    # p >= 1 without a draw (the body below), and a streamed generator must be
    # left where networkx leaves it.
    if not directed and create_using is None and 0.0 < p < 1.0 and kernel_seed is not None:
        return _rust_gnp_random_graph(n, p, seed=kernel_seed)
    # br-r37-c1-gnpdinative: native directed G(n,p). The previous directed path
    # ran a pure-Python O(V^2) `permutations` loop with a per-edge PyO3
    # `add_edge` (~2.5-3.5x slower than nx). The native `gnp_random_digraph`
    # reproduces nx's exact draw sequence (PythonRandom over permutations
    # order, same as the proven undirected native path), so the edge set is
    # byte-identical. Restrict to strict 0<p<1 (p<=0 -> empty, p>=1 -> complete
    # handled below without consuming the RNG, matching nx).
    if directed and create_using is None and 0.0 < p < 1.0 and kernel_seed is not None:
        return _rust_gnp_random_digraph(n, p, seed=kernel_seed)

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

    # br-gnp-batch: the accept loop never reads the graph after
    # empty_graph pre-populates the nodes, so accepted edges can be
    # accumulated in the exact generated order and committed through a
    # single add_edges_from (same lever as fast_gnp_random_graph's
    # create_using path). RNG draw sequence, edge order and node order
    # are unchanged, so the result is byte-identical to the per-edge
    # add_edge loop while paying one PyO3 crossing instead of O(m).
    edge_pairs = _itertools.permutations(range(n), 2) if directed else _combinations(range(n), 2)
    edges = []
    for u, v in edge_pairs:
        if rng.random() < p:
            edges.append((u, v))
    graph.add_edges_from(edges)
    return graph


def erdos_renyi_graph(n, p, seed=None, directed=False, *, create_using=None, backend=None, **backend_kwargs):
    """Return a G(n,p) random graph (alias for ``gnp_random_graph``)."""
    return gnp_random_graph(
        n,
        p,
        seed=seed,
        directed=directed,
        create_using=create_using,
        backend=backend,
        **backend_kwargs,
    )


def _seeded_watts_strogatz_rust_args(n, k, p, kernel_seed, create_using):
    # br-r37-c1-ols3t: kernel_seed is _kernel_seed(seed) - an int or a
    # random.Random whose state the kernel streams; None for a numpy seed.
    if (
        create_using is None
        and kernel_seed is not None
        and isinstance(n, _numbers.Integral)
        and not isinstance(n, bool)
        and isinstance(k, _numbers.Integral)
        and not isinstance(k, bool)
    ):
        try:
            n_int = int(n)
            k_int = int(k)
            p_float = float(p)
        except (TypeError, ValueError):
            return None
        if n_int >= 0 and 2 <= k_int < n_int and 0.0 <= p_float <= 1.0:
            return n_int, k_int, p_float, kernel_seed
    return None


def watts_strogatz_graph(n, k, p, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Return a Watts-Strogatz small-world graph."""
    _validate_backend_dispatch_keywords("watts_strogatz_graph", backend, backend_kwargs)
    # br-r37-c1-ols3t: nx's py_random_state, resolved before the k checks.
    kernel_seed = _kernel_seed(seed)
    rust_args = _seeded_watts_strogatz_rust_args(n, k, p, kernel_seed, create_using)
    if rust_args is not None:
        return _rust_watts_strogatz_graph(*rust_args)

    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    if k > n:
        raise NetworkXError("k>n, choose smaller k or larger n")
    if k == n:
        return complete_graph(n, create_using=graph)

    graph = empty_graph(n, create_using=graph, default=Graph)
    nodes = list(range(n))
    for j in range(1, k // 2 + 1):
        targets = nodes[j:] + nodes[:j]
        graph.add_edges_from(zip(nodes, targets))

    rng = _generator_random_state(seed)
    for j in range(1, k // 2 + 1):
        targets = nodes[j:] + nodes[:j]
        for u, v in zip(nodes, targets):
            if rng.random() < p:
                w = rng.choice(nodes)
                while w == u or graph.has_edge(u, w):
                    w = rng.choice(nodes)
                    if graph.degree(u) >= n - 1:
                        break
                else:
                    graph.remove_edge(u, v)
                    graph.add_edge(u, w)
    return graph


def barabasi_albert_graph(
    n,
    m,
    seed=None,
    initial_graph=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Return a Barabasi-Albert preferential attachment graph."""
    _validate_backend_dispatch_keywords("barabasi_albert_graph", backend, backend_kwargs)
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    if m < 1 or m >= n:
        raise NetworkXError(
            f"Barabási–Albert network must have m >= 1 and m < n, m = {m}, n = {n}"
        )

    # cc-bastarbatch: for the default star seed (initial_graph is None) on a plain
    # Graph, don't pre-populate the star and then bulk-extend — that leaves the
    # graph with the star's m edges, so the final add_edges_from pays the
    # O(bunch) touches-existing pre-scan (frozenset per BA edge vs the star set)
    # even though NO BA edge can touch the star (every source is a fresh node
    # > m). Instead prepend the star edges to the batch and commit everything to
    # the still-EMPTY graph: the pre-scan short-circuits on edge_count == 0 and
    # the whole set uses the fresh-batch fast path. repeated_nodes is seeded
    # directly from the star's known degree sequence (center 0 has degree m; each
    # leaf 1..m degree 1) in star_graph node order, byte-identical to reading
    # ``graph.degree``. Node/edge insertion order (star first, then sources in
    # increasing order) is unchanged.
    star_seed_fastpath = initial_graph is None and type(graph) is Graph
    if star_seed_fastpath:
        new_edges = [(0, leaf) for leaf in range(1, m + 1)]
        repeated_nodes = [0] * m + list(range(1, m + 1))
    else:
        if initial_graph is None:
            graph = star_graph(m, create_using=graph)
        else:
            if len(initial_graph) < m or len(initial_graph) > n:
                raise NetworkXError(
                    f"Barabási–Albert initial graph needs between m={m} and n={n} nodes"
                )
            graph = _copy_graph_into(initial_graph, graph)
        repeated_nodes = [
            node for node, degree_value in graph.degree for _ in range(degree_value)
        ]
        new_edges = []

    rng = _generator_random_state(seed)
    source = len(graph) if not star_seed_fastpath else m + 1
    # br-r37-c1-bagen: the BA loop never READS the graph — the degree state lives
    # entirely in ``repeated_nodes`` — so accumulate every edge and add them in a
    # SINGLE add_edges_from at the end. The previous per-step add_edges_from paid
    # ~(n - m) native binding round-trips (the dominant cost). Edge + node
    # insertion order is preserved (sources processed in increasing order), so the
    # result is identical to networkx's incremental build.
    while source < n:
        targets = _random_generator_subset(repeated_nodes, m, rng)
        new_edges.extend((source, target) for target in targets)
        repeated_nodes.extend(targets)
        repeated_nodes.extend([source] * m)
        source += 1
    graph.add_edges_from(new_edges)
    return graph


def balanced_tree(r, h, create_using=None):
    """Return the perfectly balanced r-ary tree of height h.

    br-r37-c1-bt-neg-r: nx routes balanced_tree through
    full_rary_tree using n = (1 - r**(h+1)) // (1 - r) (or h+1 for
    r==1).  Negative r yields varied n (positive when h+1 is even
    — geometric sum is positive — negative when h+1 is odd, since
    the alternating series flips sign).  fnx previously short-
    circuited all r<0 to empty_graph(0), masking nx's NetworkXError
    on negative n and producing 0-node graphs where nx returns 1+
    isolated nodes.  Match nx's formula exactly and let
    full_rary_tree handle the n<0 contract (br-r37-c1-frt-neg).
    """
    if (
        create_using is None
        and isinstance(r, int)
        and isinstance(h, int)
        and r >= 0
        and h >= 0
    ):
        n = h + 1 if r == 1 else (1 - r ** (h + 1)) // (1 - r)
        if type(r) is int and type(h) is int:
            return _rust_full_rary_tree_native(r, n)
        return _rust_balanced_tree(r, h)
    if r == 1:
        n = h + 1
    else:
        n = (1 - r ** (h + 1)) // (1 - r)
    return full_rary_tree(r, n, create_using=create_using)


def full_rary_tree(r, n, create_using=None):
    """Return a full r-ary tree with n nodes.

    br-r37-c1-frt-neg: nx accepts negative ``r`` (returns ``n``
    isolated nodes — no children = no edges) and raises
    ``NetworkXError`` on negative ``n``. The Rust binding declared
    both as unsigned int and raised OverflowError uniformly.
    Match nx's domain-specific contracts:
      * n < 0 → NetworkXError("Negative number of nodes not valid: {n}")
      * r < 0 → empty_graph(n) (n isolated nodes)
    """
    if isinstance(n, int) and n < 0:
        raise NetworkXError(f"Negative number of nodes not valid: {n}")
    if isinstance(r, int) and r < 0:
        return empty_graph(n, create_using)
    if create_using is None:
        if type(r) is int and type(n) is int and r >= 0 and n >= 0:
            return _rust_full_rary_tree_native(r, n)
        return _rust_full_rary_tree(r, n)

    G = empty_graph(n, create_using)
    G.add_edges_from(_tree_edges_local(n, r))
    return G


def binomial_tree(n, create_using=None):
    """Return the binomial tree of order n.

    br-btneg: nx.binomial_tree(-1) returns a 1-node graph (the seed of
    the iterative doubling). fnx's Rust binding raised OverflowError
    on negative n. Short-circuit to match nx.

    br-binomlabels: the Rust path produced a tree that is isomorphic to
    nx's but with different node labels (edges like (1,3) where nx
    yields (2,3)). nx's recursive clone-and-shift produces a specific
    canonical labelling; downstream code that depends on fnx matching
    nx edge-by-edge broke. Always take the Python path so the labels
    match exactly.
    """
    if n < 0:
        return empty_graph(1, create_using=create_using)

    G = empty_graph(1, create_using)

    N = 1
    # br-r37-c1-btbypass (cc): every shifted-copy edge (u+N, v+N) references ONLY the
    # fresh nodes N..2N-1 (endpoints are always >= N), so it can NEVER collide with an
    # existing edge (all among nodes < N). add_edges_from's O(E) "touches an existing
    # plain edge" pre-scan (a THIRD of the build per cProfile) is therefore pure waste
    # here — call the native batch directly and fall back only if it bails (non-int
    # nodes / multigraph, where _try_add_edges_from_batch returns False and adds
    # nothing, so the fallback is byte-identical). 1.3-1.45x self, byte-exact across
    # all create_using types.
    _batch = getattr(G, "_try_add_edges_from_batch", None)
    for _ in range(n):
        # br-r37-c1-btorder: mirror networkx exactly — let the batch introduce the
        # shifted-copy nodes in edge-encounter order rather than pre-adding
        # range(N, 2*N) in sorted order. nx's node order is NOT sorted (e.g. node 12
        # before 11 at n=4) because the shifted edge list follows G.edges() order;
        # every node N..2N-1 appears in some edge so none are lost.
        edges = [(u + N, v + N) for u, v in G.edges()]
        if _batch is None or not _batch(edges):
            G.add_edges_from(edges)
        G.add_edge(0, N)
        N *= 2
    return G


def complete_bipartite_graph(n1, n2, create_using=None):
    """Return the complete bipartite graph K_(n1,n2).

    br-bipartiteattr: the Rust fast path omitted the per-node
    ``bipartite`` attribute and the ``G.graph['name']`` label that nx
    sets. Downstream consumers (anything in ``networkx.algorithms.
    bipartite`` that reads ``node['bipartite']``) silently got wrong
    partitions. Always take the Python path so these parity-critical
    attributes are set.
    """
    n1_value, top = _nodes_or_number_local(n1)
    n2_value, bottom = _nodes_or_number_local(n2)

    G = empty_graph(0, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    if isinstance(n1_value, _numbers.Integral) and isinstance(n2_value, _numbers.Integral):
        bottom = [n1_value + i for i in bottom]

    for node in top:
        G.add_node(node, bipartite=0)
    for node in bottom:
        G.add_node(node, bipartite=1)
    if len(G) != len(top) + len(bottom):
        raise NetworkXError("Inputs n1 and n2 must contain distinct nodes")
    G.add_edges_from((u, v) for u in top for v in bottom)
    G.graph["name"] = f"complete_bipartite_graph({len(top)}, {len(bottom)})"
    if type(G) is Graph:
        vars(G)["_fnx_complete_bipartite_shape"] = (
            G.nodes_seq,
            G.edges_seq,
            len(top),
            len(bottom),
        )
    return G


def grid_2d_graph(m, n, periodic=False, create_using=None):
    """Return the two-dimensional grid graph."""
    # Native one-call kernel for the default plain undirected, integer-sized,
    # non-periodic surface. Other surfaces stay on the Python parity path.
    if (
        create_using is None
        and type(m) is int
        and type(n) is int
        and m >= 0
        and n >= 0
        and not isinstance(periodic, tuple)
        and not periodic
        and _fnx is not None
        and hasattr(_fnx, "grid_2d_graph_simple")
    ):
        return _fnx.grid_2d_graph_simple(m, n)

    m_value, rows = _nodes_or_number_local(m)
    n_value, cols = _nodes_or_number_local(n)

    # The Rust native fast path (br-grid2d) emits node labels as strings like
    # "0,0" instead of (0, 0) tuples. Stay on the Python fallback so node
    # labels match NetworkX's documented contract.

    G = empty_graph(0, create_using)
    for i in rows:
        for j in cols:
            G.add_node((i, j))
    G.add_edges_from(((i, j), (pi, j)) for pi, i in _itertools.pairwise(rows) for j in cols)
    G.add_edges_from(((i, j), (i, pj)) for i in rows for pj, j in _itertools.pairwise(cols))

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


def hypercube_graph(n):
    """Return the n-dimensional hypercube graph Q_n.

    Matches NetworkX's contract: nodes are tuples of n bits (0 or 1); two
    nodes are adjacent when their tuples differ in exactly one coordinate.
    The Rust fast path (br-hypcub) emits integer node labels 0..2^n-1 which
    breaks drop-in parity for callers indexing by the tuple representation.
    """
    dim = [2] * int(n)
    return grid_graph(dim=dim, periodic=True) if n > 1 else grid_graph(dim=dim)


def kneser_graph(n, k):
    """Return the Kneser graph K(n, k).

    Matches NetworkX: nodes are sorted tuples of k-element subsets of
    range(n); two nodes are adjacent when the subsets are disjoint. The Rust
    fast path (br-kneser) emits string node labels like "0,1" which breaks
    drop-in parity.

    br-knesvalid: nx rejects n<=0 and k<=0 or k>=n with specific messages;
    fnx silently accepted n=0 (returning a 1-node graph with "()" label)
    or k=0 (returning degenerate graphs with empty-tuple nodes). Add
    nx-compatible validation so invalid inputs fail fast.
    """
    from itertools import combinations as _combinations

    if n <= 0:
        raise NetworkXError("n should be greater than zero")
    if k <= 0 or k > n:
        raise NetworkXError("k should be greater than zero and smaller than n")

    # br-r37-c1-z2eaa: native kernel for shapes where nx's set-iteration
    # order is PROVABLY ascending. ``universe - set(s)`` iterates ascending
    # iff every member value lands in its exact CPython set slot, i.e.
    # max value (n-1) < the set's final table capacity. Capacity follows
    # CPython's growth rule (resize when fill*5 >= (cap-1)*3, to the
    # smallest power of two > used*4). When both the universe (n adds) and
    # every complement (n-k adds) satisfy it, the Rust kernel's
    # lexicographic combinations over the sorted complement reproduce nx
    # byte-for-byte; otherwise fall through to the pure-Python build whose
    # set order matches nx by construction. 2k > n has no edges, so set
    # order is irrelevant and the kernel is always safe there.
    def _cpython_set_capacity_after(m_adds):
        cap, used = 8, 0
        for _ in range(m_adds):
            used += 1
            if used * 5 >= (cap - 1) * 3:
                target = used * 4 if used <= 50000 else used * 2
                newcap = 8
                while newcap <= target:
                    newcap <<= 1
                cap = newcap
        return cap

    _set_order_safe = (2 * k > n) or (
        (n - 1) < _cpython_set_capacity_after(n)
        and (n - 1) < _cpython_set_capacity_after(n - k)
    )
    if (
        _set_order_safe
        and type(n) is int
        and type(k) is int
        and hasattr(_fnx, "kneser_graph_native")
    ):
        return _fnx.kneser_graph_native(n, k)

    # br-r37-c1-jv0h5: replicate nx's construction VERBATIM — node order is
    # edge-DISCOVERY order (s in combinations order, t drawn from
    # combinations over the CPython set difference universe - set(s)),
    # except 2k > n where nodes are pre-added (the graph may have isolated
    # nodes / no edges). The old all-nodes-first + pairwise-disjoint loop
    # produced the same node/edge SETS but a different insertion ORDER.
    # Pure-Python here, so the CPython set-iteration dependence matches nx
    # exactly.
    G = empty_graph(0)
    subsets = list(_combinations(range(n), k))
    if 2 * k > n:
        G.add_nodes_from(subsets)
    universe = set(range(n))
    G.add_edges_from(
        (s, t) for s in subsets for t in _combinations(universe - set(s), k)
    )
    return G


def turan_graph(n, r):
    """Return the Turán graph T(n, r).

    Matches NetworkX's partition ordering: `r - (n % r)` partitions of size
    `n // r` followed by `n % r` partitions of size `n // r + 1`. The Rust
    fast path (br-turan5) uses a different partition-node assignment so
    specific edge tuples diverge from upstream (e.g.,
    `turan_graph(5, 2).has_edge(0, 2)` is True on nx, False on fnx).
    """
    if not 1 <= r <= n:
        raise NetworkXError("Must satisfy 1 <= r <= n")
    partitions = [n // r] * (r - (n % r)) + [n // r + 1] * (n % r)
    return complete_multipartite_graph(*partitions)


def barbell_graph(m1, m2, create_using=None):
    """Return the barbell graph.

    br-r37-c1-iw2hz: drop the Rust fast path — it drifted adj order
    on bar-vs-bell joining nodes (e.g. fnx adj[3] = [2,4] vs
    nx [4,2]). Python construction below matches nx.
    """
    if m1 < 2:
        raise NetworkXError("Invalid graph description, m1 should be >=2")
    if m2 < 0:
        raise NetworkXError("Invalid graph description, m2 should be >=0")

    G = complete_graph(m1, create_using)
    if G.is_directed():
        raise NetworkXError("Directed Graph not supported")

    G.add_nodes_from(range(m1, m1 + m2 - 1))
    if m2 > 1:
        G.add_edges_from(_itertools.pairwise(range(m1, m1 + m2)))

    # br-r37-c1-btbypass (cc): the second bell K_{m1} spans ONLY the fresh nodes
    # m1+m2 .. 2m1+m2-1 (every endpoint >= m1+m2), so none of its O(m1^2) edges can
    # touch an existing edge (the first bell + bar live in 0 .. m1+m2-1). Skip
    # add_edges_from's touches-existing pre-scan — which builds an existing-edge set
    # + membership-tests every second-bell edge, ~doubling the work on the already-
    # populated graph — by calling the native batch directly. 0.79-0.93x -> 1.43x.
    _second_bell = [
        (u, v)
        for u in range(m1 + m2, 2 * m1 + m2)
        for v in range(u + 1, 2 * m1 + m2)
    ]
    _batch = getattr(G, "_try_add_edges_from_batch", None)
    if _batch is None or not _batch(_second_bell):
        G.add_edges_from(_second_bell)
    G.add_edge(m1 - 1, m1)
    if m2 > 0:
        G.add_edge(m1 + m2 - 1, m1 + m2)
    return G
