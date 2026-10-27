

def node_connectivity(G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs):
    """Return the node connectivity of the graph.

    Parameters
    ----------
    G : graph
        An undirected or directed graph.
    s : node, optional
        Source node.
    t : node, optional
        Target node.
    flow_func : function, optional
        A function for computing the maximum flow between a pair of nodes.

    Returns
    -------
    int
        The node connectivity of G.
    """
    _validate_backend_dispatch_keywords("node_connectivity", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    if (s is None) ^ (t is None):
        raise NetworkXError("Both source and target must be specified.")
    if s is not None and s not in G:
        raise NetworkXError(f"node {s} not in graph")
    if t is not None and t not in G:
        raise NetworkXError(f"node {t} not in graph")
    # br-r37-c1-ct24s: after s / t, as in nx (its is_connected raises this).
    if len(G) == 0:
        raise NetworkXPointlessConcept(
            "Connectivity is undefined for the null graph."
        )
    if flow_func is not None:
        return _node_connectivity_inproc(
            G,
            s=s,
            t=t,
            flow_func=flow_func,
        )

    # Local node connectivity
    if s is not None and t is not None:
        H = _build_auxiliary_node_connectivity_fast(G)
        mapping = H.graph["mapping"]
        val, _ = _minimum_cut_raw(H, f"{mapping[s]}B", f"{mapping[t]}A", capacity="capacity")
        return int(val)

    # Global node connectivity
    if G.is_directed():
        if not is_weakly_connected(G):
            return 0
        # br-r37-c1-npdzs (restored, br-r37-c1-rc0923-epic-evidence-authority-hhj5p.2):
        # networkx 3.6.1 OVER-reports global connectivity on some strongly
        # connected digraphs because it only tests flows leaving the
        # min-degree node. The project deliberately locked the correct value
        # (test_directed_node_connectivity_divergence.py); b2ae44f7f replaced
        # the native global kernel with an nx replica and silently reverted
        # that decision. Simple digraphs without self-loops use the native
        # kernel again; multigraphs / self-loops keep nx's degree convention.
        if not G.is_multigraph() and number_of_selfloops(G) == 0:
            return _raw_node_connectivity(G)
        iter_func = _itertools.permutations

        def neighbors(v):
            return _itertools.chain(G.predecessors(v), G.successors(v))
    else:
        if not is_connected(G):
            return 0
        iter_func = _itertools.combinations
        neighbors = G.neighbors

    H = _build_auxiliary_node_connectivity_fast(G)
    mapping = H.graph["mapping"]
    v, K = min(G.degree(), key=_operator.itemgetter(1))
    for w in set(G) - set(neighbors(v)) - {v}:
        val, _ = _minimum_cut_raw(H, f"{mapping[v]}B", f"{mapping[w]}A", capacity="capacity")
        K = min(K, int(val))
    for x, y in iter_func(neighbors(v), 2):
        if y in G[x]:
            continue
        val, _ = _minimum_cut_raw(H, f"{mapping[x]}B", f"{mapping[y]}A", capacity="capacity")
        K = min(K, int(val))
    return K


def _edge_connectivity_inproc(G, s=None, t=None, flow_func=None, cutoff=None):
    from franken_networkx.backend import _fnx_to_nx
    H = _fnx_to_nx(G)
    try:
        return _nx.algorithms.connectivity.connectivity.edge_connectivity(
            H, s=s, t=t, flow_func=flow_func, cutoff=cutoff, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def edge_connectivity(G, s=None, t=None, flow_func=None, cutoff=None, *, backend=None, **backend_kwargs):
    """Return the edge connectivity of the graph.

    Parameters
    ----------
    G : graph
        An undirected or directed graph.
    s : node, optional
        Source node.
    t : node, optional
        Target node.
    flow_func : function, optional
        A function for computing the maximum flow between a pair of nodes.
    cutoff : int, optional
        If specified, stop computing when connectivity is found to be at least cutoff.

    Returns
    -------
    int
        The edge connectivity of G.
    """
    _validate_backend_dispatch_keywords("edge_connectivity", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    if (s is None) ^ (t is None):
        raise NetworkXError("Both source and target must be specified.")
    if s is not None and s not in G:
        raise NetworkXError(f"node {s} not in graph")
    if t is not None and t not in G:
        raise NetworkXError(f"node {t} not in graph")
    # br-r37-c1-ct24s: after s / t, as in nx (its is_connected raises this).
    if len(G) == 0:
        raise NetworkXPointlessConcept(
            "Connectivity is undefined for the null graph."
        )
    if flow_func is not None or cutoff is not None:
        return _edge_connectivity_inproc(
            G,
            s=s,
            t=t,
            flow_func=flow_func,
            cutoff=cutoff,
        )

    # Local edge connectivity
    if s is not None and t is not None:
        if s == t:
            raise NetworkXError("source and sink are the same node")
        H = _build_auxiliary_edge_connectivity_fast(G)
        val, _ = _minimum_cut_raw(H, s, t, capacity="capacity")
        val = int(val)
        if cutoff is not None:
            return min(val, cutoff)
        return val

    # Global edge connectivity
    H = _build_auxiliary_edge_connectivity_fast(G)
    if G.is_directed():
        if not is_weakly_connected(G):
            return 0
        if len(G) == 1:
            raise NetworkXError("source and sink are the same node")

        L = min(d for n, d in G.degree())
        nodes = list(G)
        n = len(nodes)
        if cutoff is not None:
            L = min(cutoff, L)

        for i in range(n):
            nxt = nodes[i + 1] if i + 1 < n else nodes[0]
            val, _ = _minimum_cut_raw(H, nodes[i], nxt, capacity="capacity")
            L = min(L, int(val))
        return L
    else:
        if not is_connected(G):
            return 0
        L = min(d for n, d in G.degree())
        if cutoff is not None:
            L = min(cutoff, L)

        for node in G:
            D = set(dominating_set(G, start_with=node))
            v = D.pop()
            if D:
                break
        else:
            return L

        for w in D:
            val, _ = _minimum_cut_raw(H, v, w, capacity="capacity")
            L = min(L, int(val))
        return L








# Algorithm functions — centrality
from franken_networkx._fnx import (
    average_neighbor_degree as _raw_average_neighbor_degree,
    betweenness_centrality as _raw_betweenness_centrality,
    betweenness_centrality_sampled_rust as _betweenness_centrality_sampled_rust,
    betweenness_centrality_subset_rust as _betweenness_centrality_subset_rust,
    betweenness_centrality_subset_weighted_rust as _betweenness_centrality_subset_weighted_rust,
    closeness_centrality as _raw_closeness_centrality,
    closeness_vitality as _rust_closeness_vitality,
    degree_assortativity_coefficient as _raw_degree_assortativity_coefficient,
    degree_assortativity_coefficient_directed as _raw_degree_assortativity_coefficient_directed,
    degree_centrality as _raw_degree_centrality,
    edge_betweenness_centrality as _raw_edge_betweenness_centrality,
    edge_betweenness_centrality_subset_rust as _edge_betweenness_centrality_subset_rust,
    edge_betweenness_centrality_subset_weighted_rust as _edge_betweenness_centrality_subset_weighted_rust,
    eigenvector_centrality as _raw_eigenvector_centrality,
    harmonic_centrality as _raw_harmonic_centrality,
    hits,
    katz_centrality as _raw_katz_centrality,
    load_centrality as _raw_load_centrality,
    load_centrality_weighted as _raw_load_centrality_weighted,
    percolation_centrality_weighted as _raw_percolation_centrality_weighted,
    pagerank as _raw_pagerank,
    voterank as _raw_voterank,
)


def _multigraph_degree_assortativity_coefficient(G, weight):
    """Byte-exact in-process degree assortativity for multigraphs.

    br-r37-c1-6pdq6: the multigraph case used to convert fnx->nx (the
    AtlasView per-edge / ``_align_rows`` conversion path is pathologically slow
    for multigraphs — ~540ms / 239x vs nx for a 200-node MultiGraph, with the nx
    algorithm itself only ~2ms). degree_assortativity is an order-invariant
    scalar, so reproduce nx's exact pipeline directly on the fnx graph: build the
    degree-pair iterator with nx's ``node_degree_xy`` semantics from fast BULK
    reads (``dict(G.degree())`` + ``list(G.edges())`` — both native, vs the
    per-node ``G.edges(u)`` round-trips that made even the in-process version
    slow), then feed nx's own ``mixing_dict`` / ``dict_to_numpy_array`` /
    ``_numeric_ac`` (graph-agnostic numpy) so the float result is byte-identical.
    Only the default (x="out", y="in", nodes=None) contract is routed here.
    """
    import numpy as _np

    if G.is_directed():
        outdeg = dict(G.out_degree(weight=weight))
        indeg = dict(G.in_degree(weight=weight))
        degrees = set.union(set(indeg.values()), set(outdeg.values()))

        def _xy():
            # nx node_degree_xy (x="out", y="in"): one (out_src, in_tgt) pair
            # per directed edge.
            for u, v in G.edges():
                yield outdeg[u], indeg[v]
    else:
        deg = dict(G.degree(weight=weight))
        degrees = set(deg.values())

        def _xy():
            # nx node_degree_xy (undirected): each edge contributes BOTH
            # (deg_u, deg_v) and (deg_v, deg_u); self-loops only once.
            for u, v in G.edges():
                du = deg[u]
                dv = deg[v]
                yield du, dv
                if u != v:
                    yield dv, du

    mapping = {d: i for i, d in enumerate(degrees)}
    k = len(mapping)
    if k == 0:
        return float("nan")
    matrix = _np.zeros((k, k), dtype=float)
    for u_deg, v_deg in _xy():
        matrix[mapping[u_deg], mapping[v_deg]] += 1.0
    total = matrix.sum()
    if total == 0.0:
        return float("nan")
    matrix = matrix / total
    if matrix.sum() != 1.0:
        matrix = matrix / matrix.sum()
    x_arr = _np.array(list(mapping.keys()))
    y_arr = x_arr
    idx = list(mapping.values())
    a = matrix.sum(axis=0)
    b = matrix.sum(axis=1)
    vara = (a[idx] * x_arr**2).sum() - ((a[idx] * x_arr).sum()) ** 2
    varb = (b[idx] * y_arr**2).sum() - ((b[idx] * y_arr).sum()) ** 2
    xy = _np.outer(x_arr, y_arr)
    ab = _np.outer(a[idx], b[idx])
    with _np.errstate(divide="ignore", invalid="ignore"):
        return float((xy * (matrix - ab)).sum() / _np.sqrt(vara * varb))


def _degree_assortativity_inproc(G, x="out", y="in", weight=None, nodes=None):
    import numpy as _np

    if nodes is None:
        nodes = G.nodes
    if G.is_directed():
        indeg = (
            {d for _, d in G.in_degree(nodes, weight=weight)}
            if "in" in (x, y)
            else set()
        )
        outdeg = (
            {d for _, d in G.out_degree(nodes, weight=weight)}
            if "out" in (x, y)
            else set()
        )
        degrees = set.union(indeg, outdeg)
    else:
        degrees = {d for _, d in G.degree(nodes, weight=weight)}
    mapping = {d: i for i, d in enumerate(degrees)}
    matrix = degree_mixing_matrix(
        G, x=x, y=y, nodes=nodes, weight=weight, mapping=mapping
    )
    if matrix.size == 0:
        return float("nan")
    if matrix.sum() != 1.0:
        total = matrix.sum()
        if total == 0.0:
            return float("nan")
        matrix = matrix / total
    x_arr = _np.array(list(mapping.keys()))
    y_arr = x_arr
    idx = list(mapping.values())
    a = matrix.sum(axis=0)
    b = matrix.sum(axis=1)
    vara = (a[idx] * x_arr**2).sum() - ((a[idx] * x_arr).sum()) ** 2
    varb = (b[idx] * y_arr**2).sum() - ((b[idx] * y_arr).sum()) ** 2
    xy = _np.outer(x_arr, y_arr)
    ab = _np.outer(a[idx], b[idx])
    with _np.errstate(divide="ignore", invalid="ignore"):
        return float((xy * (matrix - ab)).sum() / _np.sqrt(vara * varb))


def degree_assortativity_coefficient(
    G, x="out", y="in", weight=None, nodes=None, *, backend=None, **backend_kwargs
):
    """Compute degree assortativity of graph.

    br-assortkw: accepts nx's full parameter surface (``x``, ``y``,
    ``weight``, ``nodes``).
    br-r37-c1-vbjbk: route the default ``(x="out", y="in", nodes=None)``
    contract through ``_multigraph_degree_assortativity_coefficient`` so the
    mixing-matrix evaluation is bit-for-bit identical (``==``) to NetworkX's
    ``numeric_assortativity_coefficient`` pipeline with zero NetworkX frames.
    """
    _validate_backend_dispatch_keywords(
        "degree_assortativity_coefficient", backend, backend_kwargs
    )
    G = _coerce_arg_to_fnx_graph(G)
    if (
        x == "out"
        and y == "in"
        and nodes is None
        and (not G.is_multigraph() or weight is None)
    ):
        if G.number_of_edges() == 0:
            return float("nan")
        return _multigraph_degree_assortativity_coefficient(G, weight)
    return _degree_assortativity_inproc(
        G,
        x=x,
        y=y,
        weight=weight,
        nodes=nodes,
    )


def average_neighbor_degree(
    G,
    source="out",
    target="out",
    nodes=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Returns the average degree of the neighborhood of each node."""
    _validate_backend_dispatch_keywords("average_neighbor_degree", backend, backend_kwargs)

    # br-r37-c1-c7xg2: materialize SubgraphView before crossing into
    # Rust so the filter is honored. Pass-through for plain fnx graphs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-mgavgnbd: the Rust fast path ignored parallel multi-edges, so
    # sum(t_deg[nbr] for nbr in adj[n]) was computed against an
    # adj-view that collapsed parallel edges but the degree was also
    # collapsed, yielding wrong ratios on MultiGraph. nx's Python
    # reference iterates unique neighbors via G.adj[n] but uses the
    # multi-counting degree (G.degree) — fnx's Python fallback below
    # already follows that contract, so just skip the Rust shortcut
    # for multigraphs.
    if (
        not G.is_directed()
        and not G.is_multigraph()
        and source == "out"
        and target == "out"
        and nodes is None
        and weight is None
    ):
        # br-r37-c1-anbrdeg: the native kernel now emits scores in node-insertion
        # order (integer-CSR rewrite), so the binding's dict already matches nx's
        # contract — return it directly. The previous re-key
        # ``{node: raw[node] for node in G}`` was a redundant rebuild.
        return _raw_average_neighbor_degree(G)

    if G.is_directed():
        if source == "in":
            source_degree = G.in_degree
        elif source == "out":
            source_degree = G.out_degree
        elif source == "in+out":
            source_degree = G.degree
        else:
            raise NetworkXError(
                f"source argument {source} must be 'in', 'out' or 'in+out'"
            )

        if target == "in":
            target_degree = G.in_degree
        elif target == "out":
            target_degree = G.out_degree
        elif target == "in+out":
            target_degree = G.degree
        else:
            raise NetworkXError(
                f"target argument {target} must be 'in', 'out' or 'in+out'"
            )
    else:
        if source != "out" or target != "out":
            raise NetworkXError(
                "source and target arguments are only supported for directed graphs"
            )
        source_degree = target_degree = G.degree

    if (
        nodes is None
        and not G.is_multigraph()
        and (weight is None or isinstance(weight, str))
    ):
        res = _raw_average_neighbor_degree(G, source, target, weight)
        if res is not None:
            return res

    target_degrees = dict(target_degree())

    pred_neighbors = succ_neighbors = {n: {} for n in G}
    if G.is_directed():
        if "in" in source:
            pred_neighbors = G.pred
        if "out" in source:
            succ_neighbors = G.succ
    else:
        succ_neighbors = G.adj

    avg = {}
    for node, degree in source_degree(nodes, weight=weight):
        if degree == 0:
            avg[node] = 0.0
            continue

        if weight is None:
            avg[node] = (
                sum(target_degrees[neighbor] for neighbor in succ_neighbors[node])
                + sum(target_degrees[neighbor] for neighbor in pred_neighbors[node])
            ) / degree
        else:
            avg[node] = (
                sum(
                    edge_data.get(weight, 1) * target_degrees[neighbor]
                    for neighbor, edge_data in succ_neighbors[node].items()
                )
                + sum(
                    edge_data.get(weight, 1) * target_degrees[neighbor]
                    for neighbor, edge_data in pred_neighbors[node].items()
                )
            ) / degree
    return avg


def _eigenvector_centrality_scipy(G, max_iter, tol, nstart, weight):
    """scipy.sparse matvec mirror of ``networkx.eigenvector_centrality`` for the
    weight / nstart cases (br-r37-c1-eigscipy, cc).

    nx's power iteration is ``x <- (I + A^T) x`` (each node accumulates its own
    value plus its in-neighbours'), L2-normalised, converging when the L1 delta
    drops below ``N * tol``. This rebuilds that matvec on fnx's fast
    ``to_scipy_sparse_array`` instead of delegating (which paid the full fnx->nx
    conversion). Verified byte-close to nx (<1e-6).
    """
    import numpy as _np

    nodelist = list(G)
    N = len(nodelist)
    A = to_scipy_sparse_array(G, nodelist=nodelist, weight=weight, dtype=float)
    a_t = A.T.tocsr()
    if nstart is None:
        x = _np.ones(N)
    else:
        x = _np.array([nstart.get(v, 0) for v in nodelist], dtype=float)
    nstart_sum = x.sum()
    if nstart_sum == 0:
        raise NetworkXError("initial vector cannot have all zero values")
    x = x / nstart_sum

    for _ in range(max_iter):
        xlast = x
        x = xlast + a_t @ xlast
        norm = _np.hypot.reduce(x) or 1
        x = x / norm
        if _np.absolute(x - xlast).sum() < N * tol:
            return dict(zip(nodelist, map(float, x)))
    raise PowerIterationFailedConvergence(max_iter)


def _eigenvector_centrality_inproc(G, max_iter=100, tol=1e-6, nstart=None, weight=None):
    import math

    if len(G) == 0:
        raise NetworkXPointlessConcept("cannot compute centrality for the null graph")
    if nstart is None:
        nstart = {v: 1 for v in G}
    if all(v == 0 for v in nstart.values()):
        raise NetworkXError("initial vector cannot have all zero values")
    nstart_sum = sum(nstart.values())
    x = {k: v / nstart_sum for k, v in nstart.items()}
    nnodes = G.number_of_nodes()
    is_multi = G.is_multigraph()
    for _ in range(max_iter):
        xlast = x
        x = xlast.copy()
        if is_multi:
            for n in x:
                for nbr, keydict in G[n].items():
                    for key, datadict in keydict.items():
                        w = datadict.get(weight, 1) if weight else 1
                        x[nbr] += xlast[n] * w
        else:
            for n in x:
                for nbr in G[n]:
                    w = G[n][nbr].get(weight, 1) if weight else 1
                    x[nbr] += xlast[n] * w
        norm = math.hypot(*x.values()) or 1
        x = {k: v / norm for k, v in x.items()}
        if sum(abs(x[n] - xlast[n]) for n in x) < nnodes * tol:
            return x
    raise PowerIterationFailedConvergence(max_iter)


def eigenvector_centrality(
    G,
    max_iter=100,
    tol=1e-06,
    nstart=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute eigenvector centrality for nodes.

    Parameters
    ----------
    G : graph
        A graph.
    max_iter : int, optional
        Maximum iterations. Default is 100.
    tol : float, optional
        Convergence tolerance. Default is 1e-6.
    nstart : dict, optional
        Starting values for iteration.
    weight : str, optional
        Edge attribute to use as weight. Default is None.

    Returns
    -------
    dict
        Dictionary of nodes with eigenvector centrality as value.
    """
    _validate_backend_dispatch_keywords("eigenvector_centrality", backend, backend_kwargs)

    # br-r37-c1-pyo3prefix: see ``pagerank`` for the rationale.  The
    # br-r37-c1-y77dc: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # Rust binding declares ``max_iter`` as unsigned int and prefixes
    # the TypeError with ``argument 'max_iter':``; nx raises the bare
    # ``'float' object cannot be interpreted as an integer`` from
    # ``range(max_iter)``.  Pre-validate to strip the PyO3 prefix.
    max_iter = _coerce_index_arg(max_iter, "max_iter")

    # br-r37-c1-tqimg: nx is decorated with @not_implemented_for('multigraph');
    # fnx silently accepted MultiGraph and raised
    # PowerIterationFailedConvergence on MultiDiGraph. Match nx's contract.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    # br-r37-c1-zvfcu: nx raises NetworkXPointlessConcept on the empty
    # graph; the Rust fast path silently returned {}. Drop-in code that
    # does ``pytest.raises(NetworkXPointlessConcept)`` failed under fnx.
    if len(G) == 0:
        raise NetworkXPointlessConcept(
            "cannot compute centrality for the null graph"
        )

    # br-r37-c1-eigvec-maxiter: nx raises
    # PowerIterationFailedConvergence on max_iter <= 0 (the loop
    # exits immediately without converging). The Rust binding
    # declared max_iter as unsigned int and raised OverflowError on
    # negatives. Match nx's domain-specific failure mode by
    # delegating to the converging path with max_iter clamped to 0,
    # which produces the same PowerIterationFailedConvergence.
    if isinstance(max_iter, int) and max_iter <= 0:
        raise PowerIterationFailedConvergence(max(max_iter, 0))

    # br-eignstart: the Rust _raw_eigenvector_centrality raised
    # ``TypeError('franken_networkx currently only supports
    # nstart=None and weight=None...')`` when either kwarg was
    # supplied. nx accepts both — weight for weighted adjacency and
    # nstart for custom power-iteration start vector. Delegate to
    # nx whenever either non-default is supplied; keep the Rust
    # fast path for the common default case.
    if nstart is not None or weight is not None:
        # br-r37-c1-eigscipy (cc): scipy matvec mirror of nx's power iteration for the
        # weight / nstart cases — delegating paid the full fnx->nx conversion (weighted
        # 0.86x, nstart 0.67x). Gated to simple Graph/DiGraph with str weight + dict
        # nstart; other inputs (callable weight etc.) keep delegating for exact parity.
        if (
            not G.is_multigraph()
            and isinstance(G, (Graph, DiGraph))
            and (weight is None or isinstance(weight, str))
            and (nstart is None or isinstance(nstart, dict))
        ):
            try:
                return _eigenvector_centrality_scipy(G, max_iter, tol, nstart, weight)
            except PowerIterationFailedConvergence:
                raise
            except (ImportError, ValueError, ZeroDivisionError, FloatingPointError):
                # NumPy/SciPy accelerate this path but are not required by
                # the eigenvector power-iteration API.
                pass
        return _eigenvector_centrality_inproc(
            G,
            max_iter=max_iter,
            tol=tol,
            nstart=nstart,
            weight=weight,
        )
    return _raw_eigenvector_centrality(
        G,
        max_iter=max_iter,
        tol=tol,
        nstart=nstart,
        weight=weight,
    )


def harmonic_centrality(
    G,
    nbunch=None,
    distance=None,
    sources=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute harmonic centrality for nodes.

    Parameters
    ----------
    G : graph
        A graph.
    nbunch : container, optional
        Nodes for which to compute centrality. Default is all nodes.
    distance : str, optional
        Edge attribute to use as distance. Default is None.
    sources : container, optional
        Source nodes for computing centrality.

    Returns
    -------
    dict
        Dictionary of nodes with harmonic centrality as value.
    """
    _validate_backend_dispatch_keywords("harmonic_centrality", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)

    # br-r37-c1-19lrl: harmonic_centrality(G, nbunch=[few]) previously delegated
    # to networkx, paying a full fnx->nx O(V+E) conversion just to run one BFS per
    # nbunch node -- ~26x SLOWER than nx (73.9ms vs 2.8ms on n=1500, nbunch=5).
    # For the standard unweighted, undirected case (distance/sources unset) nx's
    # algorithm reduces to: for each v in nbunch,
    #   harmonic(v) = sum over reachable u (d!=0) of 1/d(v, u),
    # accumulated (running ``+=``) in single_source_shortest_path_length BFS order.
    # fnx's native single-source BFS emits distances in nx's exact dict order, so
    # the running float sum is BYTE-IDENTICAL to nx (not merely tolerance). The
    # result dict is keyed by ``set(G.nbunch_iter(nbunch))`` exactly as nx does.
    if (
        nbunch is not None
        and distance is None
        and sources is None
        and not G.is_directed()
        and not _has_networkx_private_storage(G)
    ):
        centrality = {u: 0 for u in set(G.nbunch_iter(nbunch))}
        for v in centrality:
            cc = 0
            for u, d_uv in single_source_shortest_path_length(G, v).items():
                if d_uv != 0:
                    cc += 1 / d_uv
            centrality[v] = cc
        return centrality

    # br-r37-c1-harmdir: directed harmonic(G, nbunch=[few]) previously delegated,
    # paying a full fnx->nx O(V+E) conversion just to run a few reverse BFS — ~7x
    # SLOWER than nx (14.3ms vs 2.1ms on n=1500, nbunch=3). For a directed graph
    # harmonic(v) sums 1/d(u, v) over u that REACH v, i.e. distances TO v. nx
    # computes exactly this via its transpose optimisation (when nbunch < |V| it
    # swaps nbunch/sources and reverses the graph), so the float sum accumulates in
    # reverse-BFS-from-v order. fnx's single_target_shortest_path_length emits the
    # distance-to-v in that same order, so the running sum is BYTE-IDENTICAL to nx
    # (verified 492/492). Only when the transpose fires (len(nbunch) < |V|).
    if (
        nbunch is not None
        and distance is None
        and sources is None
        and G.is_directed()
        and not _has_networkx_private_storage(G)
    ):
        nb = set(G.nbunch_iter(nbunch))
        if len(nb) < G.number_of_nodes():
            centrality = {u: 0 for u in nb}
            for v in centrality:
                cc = 0
                for u, d_uv in single_target_shortest_path_length(G, v).items():
                    if d_uv != 0:
                        cc += 1 / d_uv
                centrality[v] = cc
            return centrality

    # Source-only queries share this route: capture targets before consuming
    # lazy sources, then decide transpose and native eligibility on live state.
    if (
        nbunch is not None or distance is not None or sources is not None
        or _has_networkx_private_storage(G)
    ):
        nb = set(G.nbunch_iter(nbunch) if nbunch is not None else G.nodes)
        sources_set = set(G.nbunch_iter(sources) if sources is not None else G.nodes)
        centrality = {u: 0 for u in nb}
        if (
            distance is None
            and len(nb) >= len(sources_set)
            and type(G) in _CONCRETE_FNX_GRAPH_TYPES
            and not _has_networkx_private_storage(G)
            and (type(G) in (Graph, DiGraph) or nbunch is None)
        ):
            # br-r37-c1-mub4s: the native reducer replays this source set in
            # order, without emitting a Python distance dict per forward BFS.
            # Do not use it for transpose: that accumulates in BFS order instead.
            # Both-bunch multigraph calls retain direct native BFS: the reducer
            # projects the whole graph first, a measured regression for subsets.
            if not sources_set:
                return centrality
            for source in sources_set:
                if source not in G:
                    # Lazy sources can remove an already-admitted root. The
                    # reducer ignores unknown roots; the public BFS must raise.
                    single_source_shortest_path_length(G, source)
            raw = _raw_harmonic_centrality(G, sources=sources_set)
            for u in centrality:
                # Retain caller key objects and removed targets' integer zeros.
                score = raw.get(u, 0.0)
                if score != 0.0:
                    centrality[u] = score
            return centrality
        transposed = False
        g_work = G
        if len(nb) < len(sources_set):
            transposed = True
            nb, sources_set = sources_set, nb
            if g_work.is_directed():
                g_work = reverse(g_work, copy=False)
        for v in sources_set:
            # Reach the helper before the generic router materializes the
            # reverse view. Its guarded predecessor BFS keeps discovery order.
            if distance is None:
                dist = single_source_shortest_path_length(g_work, v)
            else:
                dist = shortest_path_length(g_work, source=v, weight=distance)
            for u, d_uv in dist.items():
                if d_uv != 0 and u in nb:
                    centrality[v if transposed else u] += 1 / d_uv
        return centrality
    raw = _raw_harmonic_centrality(G)
    # br-r37-c1-rsom6: nx initializes ``{u: 0 for u in set(G.nbunch_iter())}``,
    # so output dict iteration order is set(G.nodes) order — for small int
    # nodes this is sorted-like (CPython hash(int) == int), for str/etc it's
    # hash-randomized. The Rust path emits in insertion order. Re-key
    # through ``set(G.nodes)`` so drop-in code that does e.g.
    # ``next(iter(harmonic_centrality(G)))`` matches nx exactly.
    # NetworkX initializes every target with integer ``0`` and only promotes
    # it to float when at least one nonzero-distance source contributes.
    # Preserve that observable value type for isolates and directed sources
    # with no predecessors.
    return {u: (0 if raw[u] == 0.0 else raw[u]) for u in set(G.nodes)}


def degree_centrality(G, *, backend=None, **backend_kwargs):
    """Compute degree centrality for nodes.

    For MultiGraph inputs (br-zzcm9), _count parallel edges in the degree
    numerator — nx's contract is ``{v: G.degree(v) / (n - 1)}`` where
    ``G.degree(v)`` counts parallels, but the Rust native projects to a
    simple graph first, which under-reports degree for parallel-edged
    nodes.
    """
    _validate_backend_dispatch_keywords("degree_centrality", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-pu5q7: nx special-cases ``len(G) <= 1`` and returns
    # ``{n: 1 for n in G}`` (int 1, not 1.0 or NaN) before any
    # ``1 / (n - 1)`` would divide by zero. Mirror that for both the
    # multigraph branch (was returning NaN on singletons) and the
    # simple-graph branch (Rust path returns float 1.0 — type drift).
    if G.number_of_nodes() <= 1:
        return {v: 1 for v in G}
    if G.is_multigraph():
        n = G.number_of_nodes()
        s = 1.0 / (n - 1)
        return {v: d * s for v, d in G.degree()}
    return _raw_degree_centrality(G)


def _single_source_betweenness_dijkstra(G, source, weight):
    """Count weighted shortest paths without coercing Python edge arithmetic.

    Full Brandes retains equal-distance predecessors even after settlement.
    This matters for zero-weight edges, including self-loops. Unlike general
    Dijkstra, a weight of ``None`` is an arithmetic error, not a hidden edge.
    """
    weight_fn = _centrality_weight_function(G, weight)
    stack = []
    predecessors = {node: [] for node in G}
    sigma = dict.fromkeys(G, 0.0)
    sigma[source] = 1.0
    distances = {}
    seen = {source: 0}
    counter = _count()
    queue = [(0, next(counter), source, source)]
    while queue:
        distance, _, parent, node = _heappop(queue)
        if node in distances:
            continue
        sigma[node] += sigma[parent]
        stack.append(node)
        distances[node] = distance
        for neighbor, edge_data in G[node].items():
            candidate = distance + weight_fn(node, neighbor, edge_data)
            if neighbor not in distances and (
                neighbor not in seen or candidate < seen[neighbor]
            ):
                seen[neighbor] = candidate
                sigma[neighbor] = 0.0
                predecessors[neighbor] = [node]
                _heappush(queue, (candidate, next(counter), node, neighbor))
            elif candidate == seen[neighbor]:
                sigma[neighbor] += sigma[node]
                predecessors[neighbor].append(node)
    return stack, predecessors, sigma, distances


def _rescale_betweenness_legacy_local(
    betweenness, n, *, normalized, directed, endpoints=False, k=None
):
    """Uniform scaling used before the source-aware node/edge estimators."""
    if normalized:
        if endpoints and n >= 2:
            scale = 1 / (n * (n - 1))
        elif not endpoints and n > 2:
            scale = 1 / ((n - 1) * (n - 2))
        else:
            scale = None
    else:
        scale = None if directed else 0.5
    if scale is not None:
        if k is not None:
            # Keep this association: scale * (n / k) changes float bits and
            # the exception text for an empty source sample.
            scale = scale * n / k
        for node in betweenness:
            betweenness[node] *= scale
    return betweenness


def _betweenness_centrality_inproc(
    G,
    k=None,
    normalized=True,
    weight=None,
    endpoints=False,
    seed=None,
):
    """Owned Brandes for multigraphs and general Python weight values."""
    rng = _create_py_random_state(seed)
    n = len(G)
    betweenness = dict.fromkeys(G, 0.0)
    source_aware = _networkx_release() >= (3, 5)
    sampled_nodes = None
    if k is not None and not (source_aware and k == n):
        sampled_nodes = _betweenness_sampled_sources(
            G, rng, k, endpoints, normalized, source_aware
        )
    sources = G if sampled_nodes is None else sampled_nodes
    for source in sources:
        if weight is None:
            stack, predecessors, sigma, _ = _single_source_shortest_path_basic_local(
                G, source
            )
        else:
            stack, predecessors, sigma, _ = _single_source_betweenness_dijkstra(
                G, source, weight
            )
        if endpoints:
            _accumulate_endpoints_local(
                betweenness, stack, predecessors, sigma, source
            )
            continue
        delta = dict.fromkeys(stack, 0.0)
        while stack:
            node = stack.pop()
            coefficient = (1.0 + delta[node]) / sigma[node]
            for parent in predecessors[node]:
                delta[parent] += sigma[parent] * coefficient
            if node != source:
                betweenness[node] += delta[node]
    if source_aware:
        return _rescale_betweenness_local(
            betweenness, n, normalized=normalized, directed=G.is_directed(),
            endpoints=endpoints, sampled_nodes=sampled_nodes,
        )
    return _rescale_betweenness_legacy_local(
        betweenness, n, normalized=normalized, directed=G.is_directed(),
        endpoints=endpoints, k=k,
    )


def _compute_networkx_release():
    import importlib.metadata as _im
    import re

    try:
        ver = _im.version("networkx")
    except Exception:
        ver = str(getattr(_sys.modules.get("networkx"), "__version__", "3.6"))
    match = re.match(r"^(\d+)\.(\d+)", ver)
    if match is None:
        return (3, 6)
    return tuple(map(int, match.groups()))


_CACHED_NX_RELEASE = _compute_networkx_release()


def _networkx_release():
    """Major/minor of the actual oracle, including prerelease/dev versions."""
    return _CACHED_NX_RELEASE


def betweenness_centrality(
    G,
    k=None,
    normalized=True,
    weight=None,
    endpoints=False,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute betweenness centrality for nodes."""
    # networkx's @py_random_state wraps its dispatcher, so the seed is
    # resolved - and an invalid one raises - before anything else. It is
    # only DRAWN from to sample k sources: with k=None it changes nothing,
    # and routing on `seed is not None` sent betweenness_centrality(G,
    # seed=1) to the Python port, 0.99x networkx where the same call without
    # the seed is 25.9x (br-r37-c1-quim8).
    rng = _create_py_random_state(seed)
    _validate_backend_dispatch_keywords("betweenness_centrality", backend, backend_kwargs)
    # br-r37-c1-y77dc: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # NetworkX 3.4 applies one uniform sampled scale and still samples at
    # k == n. From 3.5, excluding endpoints treats sampled nodes separately.
    source_aware = k is None or _networkx_release() >= (3, 5)

    # br-r37-c1-7iiky: weighted betweenness (a string `weight` key) previously
    # delegated to networkx's single-threaded Python Brandes (~540ms on n=400).
    # Run the native weighted Brandes kernel (Dijkstra SSSP, parallel,
    # byte-exact) instead. Mirror the dijkstra/astar family's weight contract:
    # only the native path for a simple Graph/DiGraph whose `weight` values are
    # all finite, non-negative built-ins inside the exact integer envelope
    # (nx requires weights > 0 for betweenness). The shared live-dict checker
    # also rejects custom arithmetic, NaNs and oversized integer sums: the
    # old three store-only gates lost those distinctions during projection.
    # Other inputs retain their Python arithmetic in the owned Brandes path.
    # br-r37-c1-quim8: a k-sampled call takes it too, over the sources
    # networkx samples.
    if isinstance(weight, str) and not G.is_multigraph():
        if not _should_delegate_dijkstra_to_networkx(G, weight):
            _sync_rust_edge_attrs(G)
            if k is None or (source_aware and k == len(G)):
                return _raw_betweenness_centrality(
                    G,
                    k=None,
                    normalized=normalized,
                    weight=weight,
                    endpoints=endpoints,
                    seed=None,
                )
            sampled_nodes = _betweenness_sampled_sources(
                G, rng, k, endpoints, normalized, source_aware
            )
            return _betweenness_centrality_sampled_rust(
                G,
                sampled_nodes,
                normalized=normalized,
                endpoints=endpoints,
                weight=weight,
                source_aware=source_aware,
            )

    # br-r37-c1-8ox3z: k-sampled unweighted betweenness was the remaining common
    # slow path: fnx converted the whole graph to nx and ran pure-Python Brandes,
    # even though the native full Brandes kernel is already the fast/correct
    # substrate. Keep nx's exact source sampling semantics in Python, then run the
    # sampled source list through native Brandes with nx's sampled rescale.
    if k is not None and weight is None and not G.is_multigraph():
        if source_aware and k == len(G):
            return _raw_betweenness_centrality(
                G,
                k=None,
                normalized=normalized,
                weight=None,
                endpoints=endpoints,
                seed=None,
            )
        sampled_nodes = _betweenness_sampled_sources(
            G, rng, k, endpoints, normalized, source_aware
        )
        return _betweenness_centrality_sampled_rust(
            G,
            sampled_nodes,
            normalized=normalized,
            endpoints=endpoints,
            source_aware=source_aware,
        )

    if k is not None or weight is not None:
        return _betweenness_centrality_inproc(
            G,
            k=k,
            normalized=normalized,
            weight=weight,
            endpoints=endpoints,
            seed=seed,
        )

    return _raw_betweenness_centrality(
        G,
        k=k,
        normalized=normalized,
        weight=weight,
        endpoints=endpoints,
        seed=None,
    )


def _betweenness_sampled_sources(G, rng, k, endpoints, normalized, source_aware):
    """networkx's ``seed.sample(list(G.nodes()), k)`` for sampled betweenness."""
    sampled_nodes = rng.sample(list(G.nodes()), k)
    if not isinstance(sampled_nodes, list):
        # br-r37-c1-cdf1v: networkx's wrapper for a numpy RandomState
        # samples with rng.choice, an ndarray ('if not sampled_nodes'
        # raised); tolist() gives the node values back.
        sampled_nodes = sampled_nodes.tolist()
    if not sampled_nodes:
        if source_aware:
            scales = (len(G) if endpoints else len(G) - 1) >= 2
            message = "division by zero"
        else:
            scales = ((len(G) >= 2 if endpoints else len(G) > 2)
                      if normalized else not G.is_directed())
            message = "float division by zero"
        if scales:
            # Python raises before returning scores; Rust float division
            # would silently produce NaNs. The message also changed upstream.
            raise ZeroDivisionError(message)
    return sampled_nodes


def voterank(G, number_of_nodes=None, *, backend=None, **backend_kwargs):
    """Select influential spreaders using VoteRank.

    Matches networkx's tie-breaking rule — ``max(G.nodes, key=score)``
    returns the first-iterated node with the maximum score, which on
    e.g. karate_club_graph means the lowest-labelled node wins a tie.
    The previous fnx path forwarded to the Rust helper whose internal
    tie-break ordered ties by a different criterion, so elections
    after the top few seeds diverged from networkx.

    br-r37-c1-vrcache: the outer ``for _ in range(number_of_nodes)``
    loop previously re-invoked ``G.nodes()``, ``G.edges()``, and
    ``G.edges(winner)`` every iteration — each a PyO3 round-trip
    materialising a fresh list.  On a 200-node 1k-edge graph this ran
    ~450ms (~10× slower than nx).  Snapshot the node list, the edge
    list, and a per-node neighbour map once; per-iteration cost drops
    to pure-Python dict accumulation.
    """
    _validate_backend_dispatch_keywords("voterank", backend, backend_kwargs)

    influential_nodes = []
    if len(G) == 0:
        return influential_nodes
    if number_of_nodes is None or number_of_nodes > len(G):
        number_of_nodes = len(G)

    is_directed = G.is_directed()
    nodes_snapshot = list(G.nodes())
    edges_snapshot = list(G.edges())
    if is_directed:
        avg_degree = sum(deg for _, deg in G.out_degree()) / len(G)
        # For directed voterank, ``G.edges(winner)`` yields out-edges,
        # which is the set we decrement.
        out_neighbours = {n: [] for n in nodes_snapshot}
        for u, v in edges_snapshot:
            out_neighbours[u].append(v)
    else:
        avg_degree = sum(deg for _, deg in G.degree()) / len(G)
        # Undirected: ``G.edges(winner)`` yields all incident edges.
        out_neighbours = {n: [] for n in nodes_snapshot}
        for u, v in edges_snapshot:
            out_neighbours[u].append(v)
            out_neighbours[v].append(u)

    vote_rank = {n: [0, 1] for n in nodes_snapshot}
    for _ in range(number_of_nodes):
        for n in nodes_snapshot:
            vote_rank[n][0] = 0
        for u, v in edges_snapshot:
            vote_rank[u][0] += vote_rank[v][1]
            if not is_directed:
                vote_rank[v][0] += vote_rank[u][1]
        for n in influential_nodes:
            vote_rank[n][0] = 0
        # Tie-break matches nx's max() over G.nodes iteration order
        # by walking the snapshot in the same order.
        winner = nodes_snapshot[0]
        winner_score = vote_rank[winner][0]
        for n in nodes_snapshot:
            score = vote_rank[n][0]
            if score > winner_score:
                winner = n
                winner_score = score
        if winner_score == 0:
            return influential_nodes
        influential_nodes.append(winner)
        vote_rank[winner] = [0, 0]
        decrement = 1 / avg_degree
        for nbr in out_neighbours[winner]:
            new_w = vote_rank[nbr][1] - decrement
            vote_rank[nbr][1] = new_w if new_w >= 0 else 0
    return influential_nodes


# Algorithm functions — clustering
from franken_networkx._fnx import (
    average_clustering as _raw_average_clustering,
    clustering as _raw_clustering,
    find_cliques as _raw_find_cliques,
    square_clustering,
    transitivity as _raw_transitivity,
    triangles as _raw_triangles,
    triangles_and_degrees_for as _native_triangles_and_degrees_for,
    directed_triangles_and_degrees_for as _native_directed_triangles_and_degrees_for,
)

try:
    from franken_networkx._fnx import (
        find_cliques_adjacency_sets as _raw_find_cliques_adjacency_sets,
    )
except ImportError:
    _raw_find_cliques_adjacency_sets = None

# Algorithm functions — matching
from franken_networkx._fnx import (
    max_weight_matching as _raw_max_weight_matching,
    maximal_matching as _raw_maximal_matching,
    min_edge_cover as _raw_min_edge_cover,
    min_weight_matching as _raw_min_weight_matching,
)


def maximal_matching(G):
    """Find a maximal matching in the graph.

    A matching is maximal if there is no edge that can be added that
    won't conflict with existing edges in the matching.

    br-r37-c1-2dwen: nx is decorated with
    ``@not_implemented_for('multigraph')`` outer and
    ``@not_implemented_for('directed')`` inner — the inner runs
    first, so MultiDiGraph yields the 'directed' message. Mirror
    that ordering: directed check fires first.
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-2dwen: nx's @not_implemented_for decorators apply
    # ``multigraph`` outer, ``directed`` inner — inner fires first,
    # so MultiDiGraph yields the 'directed' message.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    return _raw_maximal_matching(G)


def min_weight_matching(G, weight="weight", *, backend=None, **backend_kwargs):
    """Compute a minimum-weight matching in the graph.

    Returns a set of edges (2-tuples).

    br-r37-c1-fs3bl: same family pattern as br-r37-c1-kpnc8
    (max_weight_matching). The Rust binding returned matched pairs
    with different tuple directions than nx — the matching choice
    itself was correct (same nodes paired), but per-pair tuples
    flipped (e.g. ``(d, e)`` vs ``(e, d)``). Drop-in code comparing
    the result against a reference set broke. Delegate to nx so the
    chosen matching and per-pair tuple direction match nx exactly.

    br-r37-c1-gt95l: nx's ``min_weight_matching`` carries the same
    ``@not_implemented_for("multigraph")`` / ``directed`` decorators
    as ``max_weight_matching`` and raises NetworkXNotImplemented on
    those input types. Previously fnx silently collapsed parallel
    edges (taking the *minimum* per pair) and returned a matching —
    a fnx-only convenience that masked nx's documented contract.
    Sister of br-r37-c1-mwm-mg (which fixed max_weight_matching);
    mirror the same eager rejection here.
    """
    _validate_backend_dispatch_keywords("min_weight_matching", backend, backend_kwargs)
    # Check directed first to match nx's decorator ordering.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    # br-r37-c1-fs3bl (structural): the delegation above stays - nx's per-pair tuple
    # DIRECTION comes from the insertion order of the blossom algorithm's internal `mate`
    # dict (matching_dict_to_set keeps whichever orientation it meets first), which no
    # native kernel reproduces, and that is exactly what this bead reverted the Rust
    # binding for. What does NOT need to be faithful is the CONVERSION: a matching depends
    # only on structure and the weight attribute, so the node/edge attribute copy that
    # `_networkx_graph_for_parity` performs is pure overhead here.
    #
    # Edge insertion ORDER is preserved because it is load-bearing: nx builds an inverted
    # graph with `add_weighted_edges_from` over `G.edges(...)`, so the order edges arrive
    # decides the blossom traversal and hence which orientation each pair ends up with.
    # Verified byte-identical to the faithful path over 120 random graphs including
    # permuted node insertion order and attributed graphs.
    #
    # 1g0lj.1: max_weight_matching now reproduces the mate order natively, so this is
    # networkx's own body over it: the inverted graph is built the way networkx builds it
    # (an fnx Graph keeps networkx's node and adjacency order for the same insertions).
    if len(G.edges) == 0:
        native = _max_weight_matching_native(G, True, weight, min_weight=True)
        if native is not None:
            return native
        return max_weight_matching(G, maxcardinality=True, weight=weight)
    g_edges = list(G.edges(data=weight, default=1))
    max_weight = 1 + max(w for _, _, w in g_edges)
    inverted = Graph()
    inverted.add_weighted_edges_from(((u, v, max_weight - w) for u, v, w in g_edges), weight=weight)
    native = _max_weight_matching_native(inverted, True, weight, min_weight=True)
    if native is not None:
        return native
    return _max_weight_matching_structural_nx(
        inverted, maxcardinality=True, weight=weight
    )


_min_weight_matching_impl = min_weight_matching


def _max_weight_matching_native(G, maxcardinality, weight, min_weight=False):
    """networkx's ``max_weight_matching`` through the native port (1g0lj.1).

    ``networkx_max_weight_matching_mate`` repeats networkx's blossom
    algorithm step for step over ``list(G)`` positions and ``G.neighbors``
    order and returns its ``mate`` dict items in insertion order; this is
    networkx's ``matching_dict_to_set`` over them, so the matching and every
    pair's direction match. Returns None, for networkx's own code to run,
    where f64 arithmetic would not equal networkx's: a weight that is not an
    int or a finite float, or an int beyond 2**48.
    """
    nodes = list(G)
    index = {n: i for i, n in enumerate(nodes)}
    adjacency = []
    for u in nodes:
        row = []
        for v, d in G.adj[u].items():
            w = d.get(weight, 1)
            kind = type(w)
            if kind is float:
                if not _math.isfinite(w):
                    return None
            elif (kind is int or kind is bool) and -(2**48) <= w <= 2**48:
                w = float(w)
            else:
                return None
            row.append((index[v], w))
        adjacency.append(row)
    edges = set()
    for u, v in _raw_networkx_max_weight_matching_mate(
        adjacency, bool(maxcardinality), bool(min_weight)
    ):
        edge = (nodes[u], nodes[v])
        if (edge[1], edge[0]) in edges or edge in edges:
            continue
        edges.add(edge)
    return edges


def _max_weight_matching_structural_nx(G, maxcardinality, weight):
    """In-process nx delegation for ``max_weight_matching`` preserving exact adjacency order."""
    from franken_networkx.backend import _fnx_to_nx

    _H = G if isinstance(G, _nx.Graph) else _fnx_to_nx(G)
    try:
        return _nx.algorithms.matching.max_weight_matching(
            _H, maxcardinality=maxcardinality, weight=weight, backend="networkx"
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def max_weight_matching(G, maxcardinality=False, weight="weight", *, backend=None, **backend_kwargs):
    """Compute a maximum-weight matching in the graph.

    Returns a set of edges (2-tuples).

    br-r37-c1-kpnc8: the Rust binding's matching returned tuples in a
    different direction than nx (e.g. (u, v) where nx returns (v, u))
    and on graphs with multiple equally-optimal matchings, picked a
    different valid choice from nx's DFS-augmenting-path traversal.
    Drop-in code that compared the matching against a reference set
    of (u, v) pairs broke. Delegate to nx so the chosen matching and
    the per-pair tuple direction match nx's contract exactly.

    br-r37-c1-mwm-mg: nx's ``max_weight_matching`` carries
    ``@not_implemented_for("multigraph")`` and raises
    ``NetworkXNotImplemented`` on MultiGraph input.  Previously
    fnx silently collapsed parallel edges (taking the max
    weight per pair) and returned a matching — a fnx-only
    "convenience" that masked nx's documented contract.
    Drop-in callers expecting nx's NetworkXNotImplemented saw
    a working result on fnx.  Sister of the recent namespace-
    parity family — this is a behavioural-parity sister.
    Mirror nx's eager rejection.
    """
    _validate_backend_dispatch_keywords("max_weight_matching", backend, backend_kwargs)
    # Check directed first (matches nx's @not_implemented_for
    # decorator ordering: ``directed`` decorator was applied last,
    # so it fires first when both directed AND multigraph apply).
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    native = _max_weight_matching_native(G, maxcardinality, weight)
    if native is not None:
        return native
    return _max_weight_matching_structural_nx(
        G, maxcardinality=maxcardinality, weight=weight
    )


_max_weight_matching_impl = max_weight_matching


def min_edge_cover(G, matching_algorithm=None, *, backend=None, **backend_kwargs):
    """Return a minimum edge cover of the graph.

    Parameters
    ----------
    G : graph
        An undirected graph (raises for directed/multigraph).
    matching_algorithm : function, optional
        A function taking ``G`` and returning either a set of 2-tuples
        (matching edges) or a dict mapping each matched node to its
        mate. Defaults to :func:`max_weight_matching` with
        ``maxcardinality=True``.

    Returns
    -------
    set
        _Set of edges forming a minimum edge cover. Bipartite matching
        algorithms (dict-returning) produce both ``(u, v)`` and
        ``(v, u)`` directions per edge, matching nx's contract.
    """
    _validate_backend_dispatch_keywords("min_edge_cover", backend, backend_kwargs)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    # br-r37-c1-mec-iso: nx raises ``NetworkXException`` (not
    # NetworkXError) the moment any node has degree 0 — covering
    # both "no edges with isolated nodes" and "some edges but at
    # least one isolated node."  fnx's previous guard only caught
    # the former and used the wrong typed error class; the latter
    # leaked an uncaught ``StopIteration`` from ``next(nbrs)``
    # inside the uncovered loop below, which is doubly bad —
    # generic Python exception, no message, callers using
    # ``except NetworkXException:`` (the documented contract)
    # silently fail to catch it.
    if any(d == 0 for _, d in G.degree()):
        raise NetworkXException(
            "Graph has a node with no edge incident on it, "
            "so no edge cover exists."
        )

    if matching_algorithm is None:
        matching = max_weight_matching(G, maxcardinality=True)
    else:
        matching = matching_algorithm(G)

    try:
        # bipartite algos return dict — convert
        min_cover = set(matching.items())
        bipartite_cover = True
    except AttributeError:
        min_cover = set(matching)
        bipartite_cover = False

    covered = {u for e in min_cover for u in e}
    uncovered = set(G.nodes()) - covered
    for v in uncovered:
        nbrs = iter(G.neighbors(v))
        u = next(nbrs)
        min_cover.add((u, v))
        if bipartite_cover:
            min_cover.add((v, u))
    return min_cover


# Algorithm functions — flow
from franken_networkx._fnx import (
    maximum_flow as _raw_maximum_flow,
    maximum_flow_value as _raw_maximum_flow_value,
    minimum_cut as _minimum_cut_raw,
    minimum_cut_value as _minimum_cut_value_raw,
)


def _all_flow_caps_integral(G, capacity):
    """Return True when every edge in G has an integer capacity under
    the given attr name (or the default 1). Used to decide whether the
    flow result can be coerced back to int for nx-type parity
    (br-flowt).
    """
    import numbers as _numbers
    for _, _, data in G.edges(data=True):
        val = data.get(capacity, 1) if isinstance(data, dict) else 1
        # br-r37-c1-31tby: ``isinstance(x, numbers.Integral)`` is an ABC check
        # (~5x a concrete isinstance and a major cost when this scans the whole
        # flow graph on every max_flow call). Python ``int`` is the overwhelming
        # capacity type — short-circuit it before paying the ABC machinery; the
        # ABC fallback preserves parity for numpy ints / other Integral types.
        if type(val) is int:
            continue
        if not isinstance(val, _numbers.Integral):
            return False
    return True


def _coerce_flow_value(value, all_int):
    # NetworkX initializes a zero flow/cut as an integer even when every
    # capacity is a float.  Non-zero values retain the capacity's float type,
    # while integral-capacity inputs retain the existing integer coercion.
    if isinstance(value, float) and value.is_integer() and (all_int or value == 0.0):
        return int(value)
    return value


def _coerce_flow_dict(flow_dict, all_int):
    if not all_int:
        return flow_dict
    out = {}
    for u, inner in flow_dict.items():
        out[u] = {v: _coerce_flow_value(w, True) for v, w in inner.items()}
    return out




def _flow_has_infinite_capacity(flowG, capacity):
    """br-flowinf: the Rust max-flow residual-network builder treated
    missing / +inf edge capacities as effectively 1 (or 0), so any
    graph with an uncapacitated edge had its max-flow value silently
    undervalued (e.g. s->a(cap=5)->t(no cap) returned 1 instead of 5).
    Detect that case up-front and route to nx for correctness. Negative
    capacities also need the nx path because the native high-level flow
    wrappers treat them as augmentable unit edges instead of zero-capacity
    edges.
    """
    import math as _math
    import numbers as _numbers
    for _, _, attrs in flowG.edges(data=True):
        cap = attrs.get(capacity, float("inf"))
        # br-r37-c1-31tby: fast-path the concrete numeric types so the per-edge
        # scan avoids the ``numbers.Real`` ABC isinstance (hit on every max_flow
        # call over the whole flow graph). A finite non-negative int/float passes
        # immediately; everything else falls to the exact (slower) checks.
        tc = type(cap)
        if tc is int:
            if cap < 0:
                return True
            continue
        if tc is float:
            if cap < 0.0 or _math.isinf(cap) or _math.isnan(cap):
                return True
            continue
        if cap is None:
            return True
        if not isinstance(cap, _numbers.Real):
            return True
        cap_f = float(cap)
        if _math.isinf(cap_f) or _math.isnan(cap_f) or cap_f < 0:
            return True
    return False


def _flow_caps_summary(flowG, capacity):
    """Select an exact native flow domain and output type in one edge scan.

    Returns ``(needs_nx, all_int)``:

    * Native capacities are finite, nonnegative builtin int, float, or
      bool values. Fractions, Decimals, numeric subclasses, missing values,
      and other domains stay in Python so conversion cannot change their
      arithmetic, exceptions, or result types.
    * The sum of integer capacities bounds integral excess and, for
      directed graphs, opposing-arc residual capacity. An undirected edge
      has capacity in both directions, so twice that sum is a safe bound.
      Keep the bound within i64 before calling the native preflow kernel:
      its overflow fallback uses floats and would silently round integers.
      This bound is independent of f64's exact-integer range; large i64
      flows remain integers through the native binding.
    * ``all_int`` is consumed only on the native path. A builtin float
      capacity makes it False even if that float has an integral value.
    """
    import math as _math
    if not isinstance(capacity, str):
        # networkx accepts any hashable attribute key (``capacity=0``); the
        # native kernels read capacity by string name only.
        return True, False
    all_int = True
    integer_capacity_sum = 0
    integer_capacity_limit = (1 << 63) - 1
    if not flowG.is_directed():
        integer_capacity_limit //= 2
    for _u, _v, attrs in flowG.edges(data=True):
        cap = attrs.get(capacity, None) if isinstance(attrs, dict) else None
        tc = type(cap)
        if tc is int or tc is bool:
            if cap < 0:
                return True, all_int
            integer_capacity_sum += cap
            if integer_capacity_sum > integer_capacity_limit:
                return True, all_int
            continue
        if tc is float:
            if cap < 0.0 or _math.isinf(cap) or _math.isnan(cap):
                return True, all_int
            all_int = False  # a finite non-negative float is not Integral
            continue
        return True, all_int
    return False, all_int


def _reject_multigraph_flow(flowG):
    if flowG.is_multigraph():
        raise NetworkXError("MultiGraph and MultiDiGraph not supported (yet).")


def _check_flow_endpoints(flowG, source, sink):
    """Raise nx-shaped NetworkXError when source/sink isn't in the graph.

    br-r37-c1-uvkmm: the raw flow bindings raise NetworkXError(
    "node str:1:s not in graph") — the Rust binding's typed-node
    representation (type:lineage:value) leaks instead of the bare
    value nx uses ("node s not in graph"). Pre-check at the Python
    boundary so every flow wrapper (maximum_flow / maximum_flow_value
    / minimum_cut / minimum_cut_value) raises the same message nx
    raises, regardless of whether it falls to the raw or nx path.
    """
    if source not in flowG:
        raise NetworkXError(f"node {source} not in graph")
    if sink not in flowG:
        raise NetworkXError(f"node {sink} not in graph")


def _flow_residual_inproc(
    flowG, source, target, capacity, flow_func, kwargs, value_only, cut
):
    """Run the selected residual solver on the original graph.

    The Python solvers retain exact capacities (including arbitrary integers,
    Fraction, and Decimal) and can reuse a caller-owned residual network. Do
    not copy either graph: callbacks and residual attributes are observable.
    """
    from franken_networkx.flow import preflow_push

    if flow_func is None:
        if kwargs:
            raise NetworkXError(
                "You have to explicitly set a flow_func if you need to pass "
                "parameters via kwargs."
            )
        flow_func = preflow_push
    _validate_flow_func_selector(flow_func)
    if (
        cut
        and "cutoff" in kwargs
        and (
            flow_func is preflow_push
            or flow_func is _nx.algorithms.flow.preflow_push
        )
    ):
        raise NetworkXError("cutoff should not be specified.")
    try:
        return flow_func(
            flowG, source, target, capacity=capacity, value_only=value_only, **kwargs
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def _maximum_flow_inproc(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    from franken_networkx.flow import build_flow_dict

    residual = _flow_residual_inproc(
        flowG, _s, _t, capacity, flow_func, kwargs, False, False
    )
    return residual.graph["flow_value"], build_flow_dict(flowG, residual)


def _maximum_flow_value_inproc(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    residual = _flow_residual_inproc(
        flowG, _s, _t, capacity, flow_func, kwargs, True, False
    )
    return residual.graph["flow_value"]


def maximum_flow(flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs):
    """Compute the maximum flow and flow dict between ``_s`` and ``_t``.

    Native preflow preserves Python int/float arithmetic in both the
    value and flow dictionary. Capacities outside its exact numeric
    domain stay in Python, retaining arbitrary integer precision and
    the arithmetic of Fraction, Decimal, and custom numeric types.
    """
    _validate_backend_dispatch_keywords("maximum_flow", backend, {})
    # br-r37-c1-0555d: accept nx-typed inputs.
    flowG = _coerce_arg_to_fnx_graph(flowG)
    _reject_multigraph_flow(flowG)
    _check_flow_endpoints(flowG, _s, _t)
    if flow_func is not None or kwargs:
        return _maximum_flow_inproc(
            flowG, _s, _t, capacity=capacity,
            flow_func=flow_func, **kwargs,
        )
    # br-r37-c1-31tby: one edge scan yields both the route-to-nx decision
    # and the int-coercion flag (was two full-graph scans).
    needs_nx, all_int = _flow_caps_summary(flowG, capacity)
    if needs_nx:
        return _maximum_flow_inproc(
            flowG, _s, _t, capacity=capacity,
            flow_func=flow_func, **kwargs,
        )
    _sync_rust_edge_attrs(flowG, edge_only=True)
    flow_value, flow_dict = _raw_maximum_flow(flowG, _s, _t, capacity)
    return _coerce_flow_value(flow_value, all_int), _coerce_flow_dict(flow_dict, all_int)


def maximum_flow_value(flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs):
    """Return just the max-flow value. nx-int parity when all caps int."""
    _validate_backend_dispatch_keywords("maximum_flow_value", backend, {})
    # br-r37-c1-0555d: accept nx-typed inputs.
    flowG = _coerce_arg_to_fnx_graph(flowG)
    _reject_multigraph_flow(flowG)
    _check_flow_endpoints(flowG, _s, _t)
    if flow_func is not None or kwargs:
        return _maximum_flow_value_inproc(
            flowG, _s, _t, capacity=capacity,
            flow_func=flow_func, **kwargs,
        )
    # br-r37-c1-31tby: single fused capacity scan.
    needs_nx, all_int = _flow_caps_summary(flowG, capacity)
    if needs_nx:
        return _maximum_flow_value_inproc(
            flowG, _s, _t, capacity=capacity,
            flow_func=flow_func, **kwargs,
        )
    _sync_rust_edge_attrs(flowG, edge_only=True)
    return _coerce_flow_value(
        _raw_maximum_flow_value(flowG, _s, _t, capacity),
        all_int,
    )


def _validate_flow_func_selector(flow_func):
    if flow_func is not None and not callable(flow_func):
        raise NetworkXError("flow_func has to be callable.")
    return flow_func




















def _minimum_cut_inproc(flowG, _s, _t, capacity="capacity", flow_func=None, **kwargs):
    residual = _flow_residual_inproc(
        flowG, _s, _t, capacity, flow_func, kwargs, True, True
    )
    # A value-only preflow can retain excess away from the sink. The sink side
    # is therefore all nodes that can still reach t across unsaturated arcs,
    # rather than the complement of a forward walk from s. This also places
    # disconnected nodes on NetworkX's source side. Inspect the residual in
    # place without removing/re-adding edges, which would invalidate held
    # attribute dictionaries and reorder a caller-supplied residual.
    sink_side = {_t}
    frontier = [_t]
    predecessors = residual.pred
    while frontier:
        node = frontier.pop()
        for predecessor, attrs in predecessors[node].items():
            if (
                predecessor not in sink_side
                and attrs["flow"] != attrs["capacity"]
            ):
                sink_side.add(predecessor)
                frontier.append(predecessor)
    return residual.graph["flow_value"], (set(flowG) - sink_side, sink_side)
