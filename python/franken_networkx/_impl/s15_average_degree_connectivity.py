

def average_degree_connectivity(
    G,
    source="in+out",
    target="in+out",
    nodes=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Compute the average degree connectivity of graph."""
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "average_degree_connectivity", backend, backend_kwargs
    )
    # br-r37-c1-jmjs7: simple-case fast path. Was 680x slower than nx
    # because the slow per-node _adc_weighted_degree walked AtlasView
    # for every neighbor of every source node — O(|V| · avg_deg²)
    # AtlasView accesses. For undirected, unweighted, nodes=None
    # (the most common call), the algorithm reduces to:
    #
    #   for u: degree_key = deg[u]
    #          dnorm[degree_key] += deg[u]
    #          dsum[degree_key]  += sum(deg[v] for v in neighbors(u))
    #
    # which is O(|E|) using a materialized degree dict.
    if (
        not G.is_directed()
        and weight is None
        and nodes is None
        and source == "in+out"
        and target == "in+out"
        and _raw_neighbors_dispatch(G) is not None
    ):
        _raw_nbrs = _raw_neighbors_dispatch(G)
        deg = dict(G.degree())
        dsum: dict[int, int] = _defaultdict(int)
        dnorm: dict[int, int] = _defaultdict(int)
        for u, du in deg.items():
            dnorm[du] += du
            dsum[du] += sum(deg[v] for v in _raw_nbrs(G, u))
        return {
            k: avg if dnorm[k] == 0 else avg / dnorm[k]
            for k, avg in dsum.items()
        }

    # br-r37-c1-mgisol (cc): undirected unweighted MULTIgraph fast path. The
    # simple branch above is gated to plain Graph (_raw_neighbors_dispatch),
    # so multigraphs fell to the per-node AtlasView fallback (~13.6ms / 0.11x
    # vs nx at n=200). nx sums over DISTINCT neighbors (G.neighbors yields each
    # once) weighted by MULTI degree, so: take multi-degree from the native
    # G.degree() view, take distinct neighbor pairs from the cheap simple
    # projection's edges, and accumulate both directions per edge. The per-node
    # bucket init mirrors nx's ``dsum[k] += s`` for every node (so degree-0 /
    # isolated nodes keep their bucket). Byte-identical (integer arithmetic,
    # 0/400 maxdiff 0.0 incl. self-loops/parallels/isolates). ~10x self-speedup.
    if (
        not G.is_directed()
        and weight is None
        and nodes is None
        and source == "in+out"
        and target == "in+out"
        and G.is_multigraph()
    ):
        _proj = Graph()
        _proj.add_nodes_from(G.nodes())
        _proj.add_edges_from(G.edges())
        deg = dict(G.degree())
        dsum: dict[int, int] = _defaultdict(int)
        dnorm: dict[int, int] = _defaultdict(int)
        for _u, _du in deg.items():
            dnorm[_du] += _du
            dsum[_du] += 0
        for _u, _v in _proj.edges():
            if _u != _v:
                dsum[deg[_u]] += deg[_v]
                dsum[deg[_v]] += deg[_u]
            else:
                dsum[deg[_u]] += deg[_u]
        return {
            k: avg if dnorm[k] == 0 else avg / dnorm[k]
            for k, avg in dsum.items()
        }

    # br-r37-c1-wqhqr-adc: weighted undirected fast path. The fallback's
    # per-node ``_adc_weighted_degree`` AtlasView walks (target degree per
    # neighbour, weighted source degree per node) made undir weighted 0.038x
    # vs nx. Snapshot the weighted adjacency ONCE (native
    # ``_native_adjacency_dict`` -> {n: {nbr: {attrs}}}) and the unweighted
    # degree map ONCE; derive the weighted source degree from the snapshot
    # (avoiding the slow ``degree(weight=...)`` view) and the inner
    # weighted-neighbour sum from dict lookups. Per-degree-bucket sums =>
    # order-invariant; byte-identical to nx (self-loop weight doubles in the
    # weighted degree, counted once in the inner sum).
    if (
        not G.is_directed()
        and weight is not None
        and nodes is None
        and source == "in+out"
        and target == "in+out"
        and type(G) is Graph
        and getattr(G, "_native_adjacency_dict", None) is not None
    ):
        adj = G._native_adjacency_dict()
        td = dict(G.degree())  # unweighted degree: bucket key AND target degree
        dsum = _defaultdict(float)
        dnorm = _defaultdict(float)
        for n, nbrd in adj.items():
            k = td[n]
            total = 0.0
            sw = 0.0
            for nbr, attrs in nbrd.items():
                w = attrs.get(weight, 1)
                total += w * td[nbr]
                sw += w
                if nbr == n:
                    sw += w  # undirected self-loop doubles in the weighted degree
            dnorm[k] += sw
            dsum[k] += total
        return {k: avg if dnorm[k] == 0 else avg / dnorm[k] for k, avg in dsum.items()}

    # br-r37-c1-wqhqr-adc: directed unweighted fast path (the per-node
    # ``_adc_weighted_degree`` AtlasView walks made directed in+out/in-out
    # 0.013x-0.10x vs nx). Bulk native degree dicts (dict(degree()) ~0.4ms) +
    # one ``_native_adjacency_keys`` successor snapshot, then O(V+E) dict
    # lookups. The result is a per-degree-bucket SUM dictionary — fully
    # order-invariant — so neighbour order (incl. the inverted predecessor
    # adjacency for source="in") is irrelevant. Byte-identical to nx, which
    # uses the very same in/out/total DegreeViews.
    if (
        G.is_directed()
        and weight is None
        and nodes is None
        and type(G) is DiGraph
        and source in ("in", "out", "in+out")
        and target in ("in", "out", "in+out")
        and getattr(G, "_native_adjacency_keys", None) is not None
    ):
        _dir = {"out": G.out_degree, "in": G.in_degree, "in+out": G.degree}
        sk = dict(_dir[source]())  # unweighted source degree == dnorm contribution
        td = dict(_dir[target]())  # unweighted target degree
        succ = dict(G._native_adjacency_keys())  # successors, node order
        if source == "in":
            # neighbours = predecessors: invert the successor snapshot (order
            # irrelevant — only the per-bucket sums matter).
            nbrs = {n: [] for n in sk}
            for _u, _vs in succ.items():
                for _v in _vs:
                    nbrs[_v].append(_u)
        else:
            # source in {"out", "in+out"}: nx uses G.successors / G.neighbors,
            # both == successors for a DiGraph.
            nbrs = succ
        dsum = _defaultdict(int)
        dnorm = _defaultdict(int)
        for n, k in sk.items():
            dsum[k] += sum(td[v] for v in nbrs[n])
            dnorm[k] += k
        return {k: avg if dnorm[k] == 0 else avg / dnorm[k] for k, avg in dsum.items()}

    # br-r37-c1-wqhqr-adc: directed weighted fast path. Same lever: snapshot the
    # weighted successor adjacency ONCE, invert it for predecessors (order
    # irrelevant — per-bucket sums), take UNWEIGHTED degrees from the fast
    # native views and derive WEIGHTED degrees from the snapshot (avoiding the
    # slow ``degree(weight=...)`` view). Byte-identical to nx.
    if (
        G.is_directed()
        and weight is not None
        and nodes is None
        and type(G) is DiGraph
        and source in ("in", "out", "in+out")
        and target in ("in", "out", "in+out")
        and getattr(G, "_native_adjacency_dict", None) is not None
    ):
        sadj = G._native_adjacency_dict()  # {n: {succ: attrs}}
        # Predecessor inversion is only needed when the source side touches
        # in-edges (source "in" walks predecessors; "in"/"in+out" need weighted
        # in-degree). source="out" skips it entirely.
        need_pred = source in ("in", "in+out")
        padj = None
        if need_pred:
            padj = {n: {} for n in sadj}  # inverted: {n: {pred: attrs}}
            for _u, _nbrd in sadj.items():
                for _v, _attrs in _nbrd.items():
                    padj[_v][_u] = _attrs
        und = {"out": dict(G.out_degree()), "in": dict(G.in_degree()), "in+out": dict(G.degree())}
        sk = und[source]   # unweighted source degree (bucket key)
        td = und[target]   # unweighted target degree
        out_w = {n: sum(a.get(weight, 1) for a in nbrd.values()) for n, nbrd in sadj.items()}
        if source == "out":
            sw = out_w
        elif source == "in":
            sw = {n: sum(a.get(weight, 1) for a in nbrd.values()) for n, nbrd in padj.items()}
        else:
            in_w = {n: sum(a.get(weight, 1) for a in nbrd.values()) for n, nbrd in padj.items()}
            sw = {n: out_w[n] + in_w[n] for n in sadj}
        # source="in" walks predecessors (weight w(nbr->n)); otherwise nx uses
        # G.successors / G.neighbors (== successors for a DiGraph), weight w(n->nbr).
        nbr_adj = padj if source == "in" else sadj
        dsum = _defaultdict(float)
        dnorm = _defaultdict(float)
        for n, k in sk.items():
            total = 0.0
            for nbr, a in nbr_adj[n].items():
                total += a.get(weight, 1) * td[nbr]
            dnorm[k] += sw[n]
            dsum[k] += total
        return {k: avg if dnorm[k] == 0 else avg / dnorm[k] for k, avg in dsum.items()}

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

    dsum = _defaultdict(int)
    dnorm = _defaultdict(int)
    source_nodes = _adc_iter_nodes(G, nodes)

    # br-r37-c1-wqhqr-adc: nx recomputes ``target_degree(neighbor)`` for EVERY
    # neighbor of every source node — O(E·avg_deg) AtlasView degree walks (the
    # directed in+out and weighted cases measured 0.013x / 0.038x vs nx). Memoize
    # it: each node's target degree is computed at most once and reused across
    # all incident references, collapsing the inner cost to O(V·avg_deg). Values
    # are byte-identical (same ``_adc_weighted_degree``); only redundant
    # recomputation is removed. Lazy cache so a small ``nodes`` subset only pays
    # for the neighbours it actually touches.
    _td_cache: dict = {}
    _missing = object()

    def _tdeg(nbr):
        v = _td_cache.get(nbr, _missing)
        if v is _missing:
            v = target_degree(nbr)
            _td_cache[nbr] = v
        return v

    for node in source_nodes:
        degree_key = source_degree(node, weighted=False)
        if weight is None:
            total = sum(_tdeg(neighbor) for neighbor in neighbors(node))
        else:
            if reverse:
                total = sum(
                    G[neighbor][node].get(weight, 1) * _tdeg(neighbor)
                    for neighbor in neighbors(node)
                )
            else:
                total = sum(
                    G[node][neighbor].get(weight, 1) * _tdeg(neighbor)
                    for neighbor in neighbors(node)
                )
        dnorm[degree_key] += source_degree(node, weighted=True)
        dsum[degree_key] += total

    return {k: avg if dnorm[k] == 0 else avg / dnorm[k] for k, avg in dsum.items()}


def _compute_rich_club_coefficients(G):
    """Return the rich-club coefficient by degree threshold."""
    # br-r37-c1-richclub: the native kernel now does nx's exact O(|V|+|E|) sweep
    # in Rust (no Python G.edges() iteration + sort). Use it for simple undirected
    # fnx graphs; fall back to the Python port below otherwise.
    try:
        Gc = _coerce_arg_to_fnx_graph(G)
        if not Gc.is_directed() and not Gc.is_multigraph():
            return _fnx.rich_club_coefficient(Gc)
    except Exception:
        pass
    deghist = degree_histogram(G)
    total = sum(deghist)
    nks = (total - cs for cs in _itertools.accumulate(deghist) if total - cs > 1)

    # br-r37-c1-smetricdegcache: snapshot degrees once instead of
    # calling G.degree(u) per edge endpoint.
    deg = dict(G.degree())

    edge_degrees = sorted(
        (sorted((deg[u], deg[v])) for u, v in G.edges()),
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


def _rich_club_rc_from_adjacency(adj, nodes, idx):
    """Rich-club coefficient by degree threshold computed directly from an
    ordered-dict adjacency snapshot (no graph object). Identical formula and
    accumulation order to ``_compute_rich_club_coefficients``."""
    deg = {n: len(adj[n]) for n in nodes}
    max_deg = max(deg.values()) if deg else 0
    deghist = [0] * (max_deg + 1)
    for node in nodes:
        deghist[deg[node]] += 1
    total = sum(deghist)
    nks = (total - cs for cs in _itertools.accumulate(deghist) if total - cs > 1)
    edge_degrees = sorted(
        (
            (deg[u], deg[v]) if deg[u] <= deg[v] else (deg[v], deg[u])
            for u in nodes
            for v in adj[u]
            if idx[v] > idx[u]
        ),
        reverse=True,
    )
    ek = len(edge_degrees)
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


def _rich_club_randomized_coefficients(G, Q, seed):
    """br-r37-c1-richclubswap: run nx's `double_edge_swap` loop (Q*m swaps) on a
    LOCAL ordered-dict adjacency snapshot instead of mutating the fnx graph.

    The previous normalization path copied G then did per-swap
    ``list(G[u])`` + ``x in G[u]`` + 4 ``add/remove_edge`` calls — many PyO3
    round-trips per attempt over ~Q*m attempts (~10x slower than nx). A
    snapshot in G.copy()'s adjacency order (below) makes ``rng.choice`` select
    the same neighbors, so the swap sequence — hence the randomized graph — is
    byte-identical for a given seed. Rich-club is then computed straight from
    the final adjacency. No per-swap PyO3.
    """
    import bisect

    # br-r37-c1-cdf1v: double_edge_swap's @py_random_state resolves the seed
    # before its checks (a bad seed on a 3-node graph is ValueError).
    rng = _generator_random_state(seed)
    edge_count = G.number_of_edges()
    nswap = Q * edge_count
    max_tries = Q * edge_count * 10
    if nswap > max_tries:
        raise NetworkXError("Number of swaps > number of tries allowed.")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if edge_count < 2:
        raise NetworkXError("Graph has fewer than 2 edges")

    nodes = list(G)
    idx = {node: i for i, node in enumerate(nodes)}
    # br-r37-c1-cdf1v: networkx swaps on R = G.copy(), and copy() re-adds the
    # edges in adjacency-iteration order, so a node's neighbours are in
    # first-seen-edge order there, not G's (karate's 33 lists 22 after 20, not
    # last). seed.choice indexes that order, so the snapshot is built the way
    # copy() builds it - from G's order every seed drew another graph once a
    # choice landed on a reordered row.
    adj = {node: {} for node in nodes}
    for u in nodes:
        row = adj[u]
        for v in G[u]:
            row[v] = None
            adj[v][u] = None

    def choice(seq):
        if hasattr(rng, "choice"):
            return rng.choice(seq)
        return seq[rng.randint(0, len(seq) - 1)]

    degree_view = G.degree
    degree_items = degree_view() if callable(degree_view) else degree_view
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
        v = choice(list(adj[u]))
        y = choice(list(adj[x]))
        if v == y:
            continue
        if (x not in adj[u]) and (y not in adj[v]):
            adj[u][x] = None
            adj[x][u] = None
            adj[v][y] = None
            adj[y][v] = None
            del adj[u][v]
            del adj[v][u]
            del adj[x][y]
            del adj[y][x]
            swapcount += 1
        if n >= max_tries:
            raise NetworkXAlgorithmError(
                f"Maximum number of swap attempts ({n}) exceeded "
                f"before desired swaps achieved ({nswap})."
            )
        n += 1
    return _rich_club_rc_from_adjacency(adj, nodes, idx)


def rich_club_coefficient(
    G, normalized=True, Q=100, seed=None, *, backend=None, **backend_kwargs
):
    """Return the rich-club coefficient of the graph."""
    _validate_backend_dispatch_keywords(
        "rich_club_coefficient", backend, backend_kwargs
    )
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if number_of_selfloops(G) > 0:
        raise Exception(
            "rich_club_coefficient is not implemented for graphs with self loops."
        )

    rc = _compute_rich_club_coefficients(G)
    if normalized:
        # br-r37-c1-richclubswap: Q*m edge swaps run on a local adjacency
        # snapshot (byte-identical randomized graph per seed) — no per-swap
        # graph mutation, ~10x faster than the old copy+mutate path.
        randomized_rc = _rich_club_randomized_coefficients(G, Q, seed)
        rc = {k: v / randomized_rc[k] for k, v in rc.items()}
    return rc


def s_metric(G, *, backend=None, **backend_kwargs):
    """Return the s-metric of the graph."""
    _validate_backend_dispatch_keywords("s_metric", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-yxmdc: route to the native integer-CSR Rust kernel
    # ``_fnx.s_metric`` — sums deg(u)*deg(v) over each undirected edge with NO
    # Python edge iteration and NO String-keyed lookups, ~11x FASTER than nx's
    # pure-Python loop. The kernel now uses nx's self-loop-aware degree
    # (degree_by_index) + a v>=u each-edge-once sum, so self-loops are correct;
    # only directed / multigraph (different degree+edge semantics) keep the
    # Python loop below.
    if not G.is_directed() and not G.is_multigraph():
        try:
            return _fnx.s_metric(G)
        except Exception:
            pass
    # br-r37-c1-smetricdegcache: snapshot degrees once into a plain
    # dict; the previous per-edge ``degree_of(u)``/``degree_of(v)``
    # calls were ~2× as many PyO3 round-trips as edges, dominating
    # wall time on ~1k-edge graphs.  dict(G.degree()) is a single
    # native call (~0.05ms for 200 nodes).
    deg = dict(G.degree())
    return float(sum(deg[u] * deg[v] for (u, v) in G.edges()))

# Algorithm functions — graph metrics (expansion, conductance, volume)
from franken_networkx._fnx import (
    volume,
    boundary_expansion,
    conductance,
    edge_expansion as _raw_edge_expansion,
    node_expansion as _raw_node_expansion,
    mixing_expansion,
    non_edges as _raw_non_edges,
    average_node_connectivity as _raw_average_node_connectivity,
    is_k_edge_connected as _raw_is_k_edge_connected,
    all_pairs_dijkstra as _raw_all_pairs_dijkstra,
    # br-r37-c1-ccr8k: number_of_spanning_arborescences removed from
    # fnx top level (not in nx anywhere). _fnx Rust binding still has
    # it; callers can reach it via franken_networkx._fnx if needed.
    global_node_connectivity as _raw_global_node_connectivity,
)




def is_k_edge_connected(G, k, *, backend=None, **backend_kwargs):
    """Return True if *G* is k-edge-connected.

    br-ikeck0: nx.is_k_edge_connected raises
    ``ValueError('k must be positive, not {k}')`` for k<1. fnx's
    Rust binding accepted k=0 and returned True (vacuously). Match
    nx's validation.
    """
    _validate_backend_dispatch_keywords("is_k_edge_connected", backend, backend_kwargs)
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if k < 1:
        raise ValueError(f"k must be positive, not {k}")
    # br-r37-c1-6hvhl: the native ``_raw_is_k_edge_connected`` computed a full
    # edge_connectivity max-flow even for k <= 2, ~10-19x slower than nx, which
    # uses smart early-exits: k==1 is plain connectivity, k==2 is connectivity
    # with no bridge, and only k>=3 needs the flow-based edge_connectivity.
    # Reproduce nx's exact algorithm (byte-identical bool) over fnx's fast
    # native is_connected / has_bridges / edge_connectivity (k<=2 becomes
    # 50-100x FASTER than nx; k>=3 stays parity-or-faster). This was already the
    # path for non-int k; route every k through it.
    if G.number_of_nodes() < k + 1:
        return False
    if any(degree < k for _, degree in G.degree()):
        return False
    if k == 1:
        return is_connected(G)
    if k == 2:
        return is_connected(G) and not has_bridges(G)
    return edge_connectivity(G) >= k


def average_node_connectivity(G, flow_func=None, *, backend=None, **backend_kwargs):
    """Return the average node connectivity of the graph.

    Parameters
    ----------
    G : graph
        An undirected graph.
    flow_func : function, optional
        A function for computing the maximum flow between a pair of nodes.

    Returns
    -------
    float
        The average node connectivity of G.
    """
    _validate_backend_dispatch_keywords(
        "average_node_connectivity", backend, backend_kwargs
    )
    # br-r37-c1-qz40o: the standalone Rust BFS local_node_connectivity is a
    # heuristic that misvalues some pairs. But the bulk
    # ``all_pairs_node_connectivity`` (native undirected, byte-correct vs nx;
    # directed delegates) already computes the per-pair max-flow connectivity
    # ~2x faster than nx's pure-Python O(n^2) loop. nx's average is just the
    # mean of those per-pair values over combinations (undirected) /
    # permutations (directed), so average over that result instead of
    # re-delegating the whole O(n^2)-flow computation to nx (br-anc-allpairs).
    G = _coerce_arg_to_fnx_graph(G)
    apnc = all_pairs_node_connectivity(G, flow_func=flow_func)
    iter_func = _itertools.permutations if G.is_directed() else _itertools.combinations
    num = den = 0
    for u, v in iter_func(G, 2):
        num += apnc[u][v]
        den += 1
    if den == 0:
        return 0
    return num / den

def all_pairs_dijkstra(G, cutoff=None, weight="weight"):
    """_Iterator of ``(source, (distances, paths))`` pairs via Dijkstra.

    For every node ``source`` in ``G``, yields the same ``(distances, paths)``
    dicts as ``single_source_dijkstra(G, source, cutoff=cutoff, weight=weight)``.
    Mirrors ``networkx.all_pairs_dijkstra``.
    """
    # Single-source routing already preserves exact weight domains, cutoff,
    # tie order and private rows. Re-evaluate it for each consumed source so
    # a partial iterator never constructs all paths or freezes later weights.
    for node in G:
        yield node, single_source_dijkstra(G, node, cutoff=cutoff, weight=weight)

# Algorithm functions — strongly connected components
from franken_networkx._fnx import (
    strongly_connected_components as _raw_strongly_connected_components,
    number_strongly_connected_components as _raw_number_strongly_connected_components,
    is_strongly_connected as _raw_is_strongly_connected,
)


def number_strongly_connected_components(G):
    """Number of strongly connected components in directed graph ``G``."""
    # Reversal preserves the SCC partition, but not component emission order.
    # Only this scalar consumer may use the concrete root without a copy.
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        return _raw_number_strongly_connected_components(G)
    except NetworkXNotImplemented as exc:
        # br-r37-c1-4elbw: align Rust binding's custom message with
        # nx's standard '@not_implemented_for' format.
        if "not defined for undirected" in str(exc):
            raise NetworkXNotImplemented(
                "not implemented for undirected type"
            ) from exc
        raise


def is_strongly_connected(G):
    """Return True if the directed graph ``G`` is strongly connected.

    br-isokw: parameter name ``G`` matches nx; the Rust binding exposed
    it as lowercase ``g`` so ``is_strongly_connected(G=digraph)``
    kwarg-style drop-in calls broke.
    """
    # Strong connectivity is invariant under reversing every edge.
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        return _raw_is_strongly_connected(G)
    except NetworkXNotImplemented as exc:
        # br-r37-c1-yf4tf: the Rust binding raises a custom message
        # ('is_strongly_connected is not defined for undirected graphs.
        # Use is_connected instead.'). nx's @not_implemented_for
        # decorator uses the standard 'not implemented for <type> type'
        # format. Translate so drop-in code matching the message text
        # works on both libraries.
        if "not defined for undirected" in str(exc):
            raise NetworkXNotImplemented(
                "not implemented for undirected type"
            ) from exc
        raise


def strongly_connected_components(G):
    """Generate strongly connected components as sets of nodes.

    Matches upstream's ``generator[set]`` contract (franken_networkx-v1nwd).
    br-r37-c1-brzgi: the Rust binding emits components in nx's
    Tarjan/Nuutila discovery order, avoiding the previous NetworkX
    delegation on the public path.
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: nx wraps these directed-only generators with
    # @not_implemented_for, so the NetworkXNotImplemented is raised EAGERLY on
    # the call — not when the generator is first iterated. A generator function
    # here would defer the check (a ``try: g = scc(undirected) except`` around
    # the *call* would miss it). Do the type check eagerly and return an inner
    # generator, matching nx's contract.
    if not G.is_directed():
        # Preserve the standard '@not_implemented_for' error format so
        # callers see a stable message (br-r37-c1-4elbw).
        raise NetworkXNotImplemented("not implemented for undirected type")

    def _gen():
        yield from _raw_strongly_connected_components(G)

    return _gen()


# Algorithm functions — weakly connected components
from franken_networkx._fnx import (
    weakly_connected_components as _raw_weakly_connected_components,
    number_weakly_connected_components as _raw_number_weakly_connected_components,
    is_weakly_connected as _raw_is_weakly_connected,
)


def number_weakly_connected_components(G):
    """Number of weakly connected components in directed graph ``G``."""
    # Weak connectivity ignores edge orientation; component order does not.
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        return _raw_number_weakly_connected_components(G)
    except NetworkXNotImplemented as exc:
        # br-r37-c1-1ewpw: align Rust binding's custom message with
        # nx's standard '@not_implemented_for' format.
        if "not defined for undirected" in str(exc):
            raise NetworkXNotImplemented(
                "not implemented for undirected type"
            ) from exc
        raise


def is_weakly_connected(G):
    """Return True if the directed graph ``G`` is weakly connected."""
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        return _raw_is_weakly_connected(G)
    except NetworkXNotImplemented as exc:
        # br-r37-c1-yf4tf: align Rust binding's custom message with
        # nx's standard '@not_implemented_for' format.
        if "not defined for undirected" in str(exc):
            raise NetworkXNotImplemented(
                "not implemented for undirected type"
            ) from exc
        raise


def weakly_connected_components(G):
    """Generate weakly connected components as sets of nodes.

    Matches upstream's ``generator[set]`` contract (franken_networkx-v1nwd).
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-scceager: raise the directed-only error EAGERLY (nx contract),
    # not lazily on first iteration. See strongly_connected_components.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    def _gen():
        for component in _raw_weakly_connected_components(G):
            yield set(component)

    return _gen()

# Algorithm functions — link prediction
from franken_networkx._fnx import (
    common_neighbors as _raw_common_neighbors,
    jaccard_coefficient as _raw_jaccard_coefficient,
    adamic_adar_index as _raw_adamic_adar_index,
    preferential_attachment as _raw_preferential_attachment,
    resource_allocation_index as _raw_resource_allocation_index,
    link_pred_common_neighbor_degrees as _raw_link_pred_common_neighbor_degrees,
    link_pred_jaccard_counts as _raw_link_pred_jaccard_counts,
)


def _jaccard_native_scores(G, materialized):
    # br-r37-c1-lpjaccard (cc): native (common_count, union_size) + Python int-division
    # -> exact parity, no eager set(G[u])|set(G[v]) materialization. union==0 -> int 0.
    rows = _raw_link_pred_jaccard_counts(G, materialized)
    for (u, v), (_ru, _rv, common, union) in zip(materialized, rows):
        yield (u, v, common / union if union else 0)


def _ra_native_scores(G, materialized):
    # br-r37-c1-lpdegnative (cc): native common-neighbor degrees (index-native, in
    # nx's G[u] order) + Python sum(1/d) -> float parity GUARANTEED (Python does every
    # float op), avoiding the eager list(G.neighbors(u)) materialization. Lazy: the
    # native call fires on first iteration, matching nx's generator semantics.
    rows = _raw_link_pred_common_neighbor_degrees(G, materialized)
    for (u, v), (_ru, _rv, degs) in zip(materialized, rows):
        yield (u, v, sum(1.0 / d for d in degs))


def _aa_native_scores(G, materialized):
    import math

    rows = _raw_link_pred_common_neighbor_degrees(G, materialized)
    for (u, v), (_ru, _rv, degs) in zip(materialized, rows):
        yield (u, v, sum(1.0 / math.log(d) for d in degs))


def _pa_native_scores(G, materialized):
    """Explicit-ebunch scorer for ``preferential_attachment``.

    br-r37-c1-z00k8: this is the sibling the other three link-prediction
    metrics already had. `jaccard_coefficient`, `adamic_adar_index` and
    `resource_allocation_index` each short-circuit an explicit ebunch into a
    dedicated scorer; `preferential_attachment` alone fell through to the
    generic `_link_prediction_compute`, and measured `0.8635x` against live
    NetworkX while `jaccard_coefficient` — same graph, same 300 pairs, same
    validator — measured `3.2523x`.

    Stage attribution put the residual here rather than in ebunch validation
    (`+7.81us`) or the degree batch (a `1.6191x` win): `73.98us` of the deficit
    sat in the generic path's machinery. That machinery is real work this
    metric never needed — three neighbour caches, a four-way metric dispatch,
    and two closure frames per pair (`predict` -> `deg` -> `dict.get` plus a
    `None` test) — when the score is just the product of two endpoint degrees.

    Parity notes:
      * Generator, not a function returning a list, so the degree batch fires
        on first iteration exactly as the generic path's did. NetworkX's
        `_apply_prediction` also returns a generator, and the eager
        `NodeNotFound` / `NetworkXNotImplemented` raises already happened in
        `_link_prediction_validate_ebunch` (br-r37-c1-scceager).
      * Degrees are Python ints, so `deg(u) * deg(v)` is an int, matching
        NetworkX. No float ever enters.
      * The whole-graph-vs-endpoint-subset choice is carried over verbatim
        from the generic path: an ebunch at least as large as the node set
        touches enough nodes that one `G.degree()` snapshot beats an nbunch
        query (br-r37-c1-pa-degbatch), and a smaller one must not materialise
        degrees it will never read (br-r37-c1-pa-endpointbatch).
    """
    if not materialized:
        return
    # The native scorer snapshots the integer adjacency degrees once, then
    # resolves every endpoint pair through that vector.  Keeping the original
    # Python pair objects here preserves NetworkX's generator payload while
    # avoiding this wrapper's per-pair dictionary lookups.
    for (u, v), (_raw_u, _raw_v, score) in zip(
        materialized, _raw_preferential_attachment(G, materialized)
    ):
        yield (u, v, int(score))


def _link_prediction_validate_ebunch(G, ebunch):
    """Validate ebunch for link-prediction per nx contract (br-7f0fn).

    nx raises NodeNotFound if any endpoint in the ebunch is missing from
    G. fnx's native implementations silently return 0.0 scores. Also
    reject MultiGraph inputs with NetworkXNotImplemented to match nx.

    Materializes the ebunch into a list so the generator can be walked
    twice (once for validation, once inside the native call).
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    # br-r37-c1-scceager: nx's link-prediction functions are also
    # @not_implemented_for('directed') and raise EAGERLY on the call. The fnx
    # generator path deferred this to first iteration. Check here (this helper
    # runs eagerly before _link_prediction_lazy_delegate returns its generator).
    # multigraph is checked first so a MultiDiGraph reports 'multigraph', as nx.
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    materialized = list(ebunch) if ebunch is not None else None
    if materialized is not None:
        for u, v in materialized:
            if u not in G:
                raise NodeNotFound(f"Node {u} not in G.")
            if v not in G:
                raise NodeNotFound(f"Node {v} not in G.")
    return materialized


def _link_prediction_lazy_delegate(name, G, materialized):
    """br-r37-c1-8e60l: defer the fnx_to_nx graph conversion in
    in-process delegation until the user begins iterating the
    returned generator. Profiling on BA200 showed the eager-conversion
    variant was 1000+x slower than nx on the call alone (3.5 ms vs
    3 µs to construct nx's generator); deferring matches nx's
    O(1)-construction contract.
    """
    def _gen():
        from franken_networkx.backend import _fnx_to_nx
        H = _fnx_to_nx(G)
        fn = getattr(_nx.algorithms.link_prediction, name)
        try:
            if materialized is None:
                yield from fn(H, backend="networkx")
            else:
                yield from fn(H, ebunch=materialized, backend="networkx")
        except Exception as exc:
            _raise_translated_networkx_exception(exc)
    return _gen()


def _link_prediction_compute(G, materialized, metric):
    """Pure-Python link-prediction scorer over the fnx graph.

    br-r37-c1-lpconv: the previous path delegated to networkx, which performed
    a full fnx->nx graph conversion (O(V+E)) for EVERY call regardless of
    ebunch size -- so scoring a handful of candidate pairs on an n=2000 graph
    cost ~114 ms vs networkx's ~0.02 ms (thousands of times slower). This
    reproduces networkx's exact algorithm directly on the fnx graph:

    * pair order = networkx's ``non_edges`` (``nodes.pop()`` + ``nodes - N(u)``
      over CPython sets) for the default ebunch;
    * common neighbours iterate ``G.neighbors(u)`` (networkx's ``G[u]`` order),
      filtered by membership in ``N(v)`` and ``w not in (u, v)``;
    * scores use the builtin ``sum`` (same compensated summation as networkx),
      so the floats are byte-identical, and the empty sum is int ``0``.

    Adjacency sets / degrees are memoized lazily, so a small ebunch only touches
    its endpoints (no whole-graph materialization) while the default ebunch
    still computes each neighbour set once.
    """
    import math

    nbr_order_cache = {}
    nbr_set_cache = {}
    deg_cache = {}

    def nbr_order(n):
        r = nbr_order_cache.get(n)
        if r is None:
            r = list(G.neighbors(n))
            nbr_order_cache[n] = r
        return r

    def nbr_set(n):
        r = nbr_set_cache.get(n)
        if r is None:
            r = set(nbr_order(n))
            nbr_set_cache[n] = r
        return r

    def deg(n):
        r = deg_cache.get(n)
        if r is None:
            r = G.degree(n)
            deg_cache[n] = r
        return r

    # br-r37-c1-pa-degbatch (cc): degree-using metrics over a large/default ebunch
    # win from ONE batched G.degree() snapshot instead of N lazy per-node G.degree
    # PyO3 calls (preferential_attachment 0.78x -> WIN, ~3.4x on the degree path;
    # also speeds resource_allocation/adamic_adar's 1/deg(w) terms). jaccard uses
    # set-union not degree, so skip it. Small explicit ebunches stay lazy (the
    # whole-graph snapshot would materialize unused degrees); the default (None)
    # ebunch touches every node so it always pays. Same values as lazy G.degree(n).
    if metric != "jaccard_coefficient" and (
        materialized is None or len(materialized) >= G.number_of_nodes()
    ):
        deg_cache.update(G.degree())
    elif metric == "preferential_attachment" and materialized:
        # br-r37-c1-pa-endpointbatch (cc): preferential_attachment uses ONLY the
        # endpoint degrees deg(u)*deg(v). For an explicit ebunch smaller than the
        # graph (the prior branch's full-snapshot guard misses it) the lazy deg()
        # path made N per-node G.degree(n) PyO3 calls -> 0.24x. Batch the distinct
        # endpoints' degrees in ONE native G.degree(nbunch) call -> 0.24x -> 1.71x
        # (beats nx), byte-identical (same ints as lazy G.degree(n)).
        deg_cache.update(G.degree({endpoint for pair in materialized for endpoint in pair}))

    if metric == "resource_allocation_index":

        def predict(u, v):
            nv = nbr_set(v)
            return sum(1 / deg(w) for w in nbr_order(u) if w in nv and w != u and w != v)

    elif metric == "adamic_adar_index":

        def predict(u, v):
            nv = nbr_set(v)
            return sum(
                1 / math.log(deg(w))
                for w in nbr_order(u)
                if w in nv and w != u and w != v
            )

    elif metric == "jaccard_coefficient":

        def predict(u, v):
            nu = nbr_set(u)
            nv = nbr_set(v)
            union_size = len(nu | nv)
            if union_size == 0:
                return 0
            ncommon = sum(
                1 for w in nbr_order(u) if w in nv and w != u and w != v
            )
            return ncommon / union_size

    else:  # preferential_attachment

        def predict(u, v):
            return deg(u) * deg(v)

    if materialized is None:
        nodes = set(G)
        while nodes:
            u = nodes.pop()
            for v in nodes - nbr_set(u):
                yield (u, v, predict(u, v))
    else:
        for u, v in materialized:
            yield (u, v, predict(u, v))


def jaccard_coefficient(G, ebunch=None):
    """Compute the Jaccard coefficient of all node pairs in ebunch.

    Matches nx: raises NodeNotFound on missing endpoints and
    NetworkXNotImplemented on MultiGraph inputs (br-7f0fn). br-r37-c1-lpconv:
    computed directly on the fnx graph (no fnx->nx conversion) in nx's exact
    non_edges order.
    """
    G = _coerce_arg_to_fnx_graph(G)
    materialized = _link_prediction_validate_ebunch(G, ebunch)
    # br-r37-c1-lpjaccard (cc): explicit ebunch on a simple Graph -> native counts.
    if materialized is not None and type(G) is Graph:
        return _jaccard_native_scores(G, materialized)
    return _link_prediction_compute(G, materialized, "jaccard_coefficient")


def adamic_adar_index(G, ebunch=None):
    """Compute the Adamic-Adar index of all node pairs in ebunch.

    br-r37-c1-lpconv: computed directly on the fnx graph (no fnx->nx
    conversion); pair order matches nx's non_edges iteration order and
    zero-score values are int 0.
    """
    G = _coerce_arg_to_fnx_graph(G)
    materialized = _link_prediction_validate_ebunch(G, ebunch)
    # br-r37-c1-lpdegnative (cc): explicit ebunch on a simple Graph -> native
    # common-neighbor degrees + Python sum (float parity guaranteed). Default ebunch
    # keeps the Python non_edges path (delicate pop/set-diff order).
    if materialized is not None and type(G) is Graph:
        return _aa_native_scores(G, materialized)
    return _link_prediction_compute(G, materialized, "adamic_adar_index")


def preferential_attachment(G, ebunch=None):
    """Compute the preferential-attachment score of all node pairs in ebunch.

    br-r37-c1-lpconv: ``deg(u) * deg(v)`` computed directly on the fnx graph
    (no fnx->nx conversion); returns (u, v, int_score) in nx's non_edges order.
    """
    G = _coerce_arg_to_fnx_graph(G)
    materialized = _link_prediction_validate_ebunch(G, ebunch)
    # br-r37-c1-z00k8: explicit ebunch on a simple Graph -> dedicated endpoint-degree
    # scorer, the sibling jaccard/adamic_adar/resource_allocation already had. The
    # default (None) ebunch keeps the Python non_edges path (delicate pop/set-diff
    # order). Subclasses keep the generic path so any overridden accessor still runs.
    if materialized is not None and type(G) is Graph:
        return _pa_native_scores(G, materialized)
    return _link_prediction_compute(G, materialized, "preferential_attachment")


def resource_allocation_index(G, ebunch=None):
    """Compute the resource-allocation index of all node pairs in ebunch.

    br-r37-c1-lpconv: computed directly on the fnx graph (no fnx->nx
    conversion); pair order matches nx's non_edges iteration order and
    zero-score values are int 0.
    """
    G = _coerce_arg_to_fnx_graph(G)
    materialized = _link_prediction_validate_ebunch(G, ebunch)
    # br-r37-c1-lpdegnative (cc): explicit ebunch on a simple Graph -> native path.
    if materialized is not None and type(G) is Graph:
        return _ra_native_scores(G, materialized)
    return _link_prediction_compute(G, materialized, "resource_allocation_index")

# Algorithm functions — DAG
from franken_networkx._fnx import (
    ancestors as _raw_ancestors,
    dag_longest_path as _raw_dag_longest_path,
    dag_longest_path_length as _raw_dag_longest_path_length,
    descendants as _raw_descendants,
    is_directed_acyclic_graph as _raw_is_directed_acyclic_graph,
    lexicographic_topological_sort as _raw_lexicographic_topological_sort,
    topological_generations_state as _raw_topological_generations_state,
    networkx_maximum_branching_plan as _raw_networkx_maximum_branching_plan,
    networkx_max_weight_matching_mate as _raw_networkx_max_weight_matching_mate,
)


def is_directed_acyclic_graph(G):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``."""
    # Every directed cycle remains a directed cycle when all arcs reverse.
    root = _reverse_view_root(G)
    if root is not None:
        G = root
    # br-r37-c1-pf5vu: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_directed_acyclic_graph(G)
























# flow_matrix_row was an fnx-only public alias for the deeply-nested
# nx.algorithms.centrality.flow_matrix.flow_matrix_row helper. Removed
# in br-r37-c1-qy2r4 because nx top-level doesn't expose it; callers
# can use the nx-qualified path directly.










# pseudo_peripheral_node was an fnx-only public alias for the deeply
# nested nx.utils.rcm.pseudo_peripheral_node helper. Removed in
# br-r37-c1-qy2r4 because nx top-level doesn't expose it.


# edges_equal/graphs_equal/nodes_equal: nx exposes these only under
# nx.utils.X; fnx.utils.X still works via the auto-bound submodule
# fallback. The top-level fnx forms were removed in br-r37-c1-j57zz to
# mirror nx's namespacing.


# make_list_of_ints / powerlaw_sequence / zipf_rv / cumulative_distribution
# live only at nx.utils.X; removed from fnx top-level in br-r37-c1-qy2r4
# to mirror nx namespacing. fnx.utils.X still works via the auto-bound
# submodule fallback.






# br-r37-c1-bw-removed: ``branching_weight`` and ``minimal_branching``
# live only at ``nx.algorithms.tree.branchings.X`` in nx; nx top-level
# raises AttributeError.  fnx had top-level pure-delegate Python
# wrappers that masked the contract.  Available exclusively at
# ``fnx.algorithms.tree.branchings.X`` (which IS nx's submodule).
# Module ``__getattr__`` traps top-level access.














# The 11 subgraph_view filter constructors (hide_X / show_X / no_filter)
# live only at nx.classes.filters.X; nx top-level raises AttributeError.
# Removed from fnx top-level in br-r37-c1-32nso for drop-in parity. They
# remain accessible via fnx.classes.filters.X through the auto-bound
# submodule fallback.
#
# Use a private alias so subgraph_view can reference nx's ``no_filter``
# as its parameter default (preserving inspect.signature parity per
# br-r37-c1-svfilter) without leaking ``no_filter`` at fnx top level.
# Local import — the module-level ``_nx`` alias is bound far later.
from networkx.classes.filters import no_filter as _subgraph_view_no_filter_default  # noqa: E402


# br-r37-c1-4asgt: Heap classes (networkx.utils.heaps) live at
# nx.utils.X / nx.utils.heaps.X but not at nx top level. Imported
# privately so internal code (stoer_wagner default heap=, etc.)
# still works; the public surface remains fnx.utils.X.
from networkx.utils.heaps import (  # noqa: E402
    BinaryHeap as _BinaryHeap,
    MinHeap as _MinHeap,
    PairingHeap as _PairingHeap,
)


# ``frozen`` is the no-op raiser nx uses internally on frozen-graph
# mutators (nx.classes.function.frozen). nx doesn't re-export it at
# top level; removed from fnx top-level in br-r37-c1-qy2r4 to match.


# Greedy coloring strategies live at nx.coloring.X / nx.algorithms.coloring.X;
# nx top-level does not re-export them. The 8 strategy_X top-level wrappers
# were removed in br-r37-c1-xc6c2 for drop-in parity. They remain reachable
# via fnx.coloring.X / fnx.algorithms.coloring.X through the auto-bound
# submodule fallback (greedy_color still accepts the canonical string names
# as the ``strategy=`` kwarg).






def _ancestors_descendants_missing_node_msg(G, source):
    kind = "digraph" if G.is_directed() else "graph"
    return f"The node {source} is not in the {kind}."


def ancestors(G, source):
    """Return all nodes having a path to ``source`` in ``G``.

    Matches nx (br-7f0fn): accepts undirected and multigraph inputs as
    well as DiGraph, returning all nodes in the connected / reachable
    set (excluding ``source`` itself). Raises NetworkXError if source
    isn't in G (message distinguishes graph vs digraph). Returns a
    plain ``set`` (not ``frozenset``).

    br-r37-c1-i9whv: hash check up front for nx parity on unhashable
    inputs (TypeError, not NetworkXError).
    """
    # br-r37-c1-8xp4a: a reverse view's ancestors are its root's descendants.
    root = _reverse_view_root(G)
    if root is not None:
        return descendants(root, source)
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(source)
    if source not in G:
        raise NetworkXError(_ancestors_descendants_missing_node_msg(G, source))
    # br-r37-c1-descbfs: native kernel handles undirected (component BFS) and
    # directed (predecessor reachability) — see algorithms.rs::ancestors. The
    # previous undirected Python BFS over G[n] paid the per-neighbor PyO3 tax.
    # Returns a plain set built in networkx's order (br-r37-c1-n4j4k).
    # br-cc-descmg: undirected multigraph -> connected component minus source (the
    # native BFS is 0.03x there; ancestors == descendants on undirected). See
    # descendants().
    if not G.is_directed() and G.is_multigraph():
        return set(_raw_node_connected_component(G, source)[1:])
    return _raw_ancestors(G, source)


def descendants(G, source):
    """Return all nodes reachable from ``source`` in ``G``.

    Matches nx (br-7f0fn): on undirected / multigraph, returns the
    reachable node set (symmetric with ``ancestors``). Returns a
    plain ``set``.

    br-r37-c1-i9whv: hash check up front for nx parity.
    """
    # br-r37-c1-8xp4a: a reverse view's descendants are its root's ancestors.
    root = _reverse_view_root(G)
    if root is not None:
        return ancestors(root, source)
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(source)
    if source not in G:
        raise NetworkXError(_ancestors_descendants_missing_node_msg(G, source))
    # br-r37-c1-descbfs: the native kernel handles BOTH directed (successor
    # reachability) and undirected (component BFS via bfs_edges) — see
    # algorithms.rs::descendants. The previous undirected branch ran a Python
    # BFS over the lazy AtlasView (per-neighbor PyO3 tax, ~5x slower than nx);
    # route it through the native kernel too. Returns a plain set built in
    # networkx's order: each child added as bfs_edges discovers it
    # (br-r37-c1-n4j4k).
    # br-cc-descmg: on an UNDIRECTED MULTIGRAPH the native BFS re-walks the
    # parallel-edge adjacency (0.03x / 25-47x slower than nx). descendants there
    # is exactly the connected component minus source, and node_connected_component
    # is a fnx WIN on multigraphs — route it through that: its BFS list less the
    # source, its first entry, is bfs_edges' children in discovery order.
    if not G.is_directed() and G.is_multigraph():
        return set(_raw_node_connected_component(G, source)[1:])
    return _raw_descendants(G, source)


def topological_sort(G):
    """Yield nodes in topological order.

    networkx's definition: the nodes of ``topological_generations(G)`` in
    order, so its tie-break order, its acyclic prefix before
    ``NetworkXUnfeasible`` on a cyclic graph, and its ``RuntimeError`` when
    the caller mutates ``G`` mid-iteration all carry over (nro4w.11).
    """
    for generation in topological_generations(G):
        yield from generation


def topological_generations(G):
    """Yield the generations of ``G`` in topological order, as networkx does.

    networkx processes generation k on the LIVE graph just before yielding
    it: a node removed by then raises ``RuntimeError``, an edge added to a
    new child raises ``RuntimeError``, and nodes whose in-degree never
    reaches zero (a cycle, or an edge added among unprocessed nodes) raise
    ``NetworkXUnfeasible`` after the last generation. On fnx's own DiGraph
    and MultiDiGraph the generations come from the native kernel; if the
    graph's revision has moved when networkx would process generation k,
    networkx's loop continues on the live graph from the native kernel's
    in-degree state at that boundary (nro4w.11). Any other directed graph
    (a subclass, a view, a networkx graph) runs networkx's loop as written.
    """
    if type(G) is DiGraph or type(G) is MultiDiGraph:
        yield from _topological_generations_native(G)
    else:
        yield from _topological_generations_as_networkx(G)


def _topological_generations_native(G):
    generations, leftover, state = _raw_topological_generations_state(G)
    revision = G._fnx_revision
    start = revision()
    for k, generation in enumerate(generations):
        if revision() != start:
            yield from _topological_generations_live(
                G, generation, state.indegree_map(k), G.is_multigraph()
            )
            return
        yield generation
    if leftover:
        raise NetworkXUnfeasible(
            "Graph contains a cycle or graph changed during iteration"
        )


def _topological_generations_as_networkx(G):
    if not G.is_directed():
        raise NetworkXError("Topological sort not defined on undirected graphs.")
    indegree_map = {v: d for v, d in G.in_degree() if d > 0}
    zero_indegree = [v for v, d in G.in_degree() if d == 0]
    yield from _topological_generations_live(
        G, zero_indegree, indegree_map, G.is_multigraph()
    )


def _topological_generations_live(G, zero_indegree, indegree_map, multigraph):
    """networkx's generation loop from a given state, on the live graph."""
    while zero_indegree:
        this_generation = zero_indegree
        zero_indegree = []
        for node in this_generation:
            if node not in G:
                raise RuntimeError("Graph changed during iteration")
            for child in G.neighbors(node):
                try:
                    indegree_map[child] -= len(G[node][child]) if multigraph else 1
                except KeyError as err:
                    raise RuntimeError("Graph changed during iteration") from err
                if indegree_map[child] == 0:
                    zero_indegree.append(child)
                    del indegree_map[child]
        yield this_generation
    if indegree_map:
        raise NetworkXUnfeasible(
            "Graph contains a cycle or graph changed during iteration"
        )


def _dag_longest_path_digraph_native(G, weight, default_weight):
    topo_pred_snapshot = getattr(G, "_native_dag_topo_pred_data_key", None)
    if topo_pred_snapshot is not None:
        topo_order, pred_groups = topo_pred_snapshot(weight, default_weight)
    else:
        topo_order = list(topological_sort(G))
        pred_map = {node: [] for node in topo_order}
        for u, v, edge_weight in G._native_in_edges_data_key(weight, default_weight):
            pred_map[v].append((u, edge_weight))
        pred_groups = [pred_map[node] for node in topo_order]

    dist = {}
    for v, preds in zip(topo_order, pred_groups):
        if preds:
            pred_iter = iter(preds)
            u, edge_weight = next(pred_iter)
            best_len = dist[u][0] + edge_weight
            maxu = (best_len, u)
            for u, edge_weight in pred_iter:
                candidate_len = dist[u][0] + edge_weight
                if candidate_len > best_len:
                    best_len = candidate_len
                    maxu = (candidate_len, u)
        else:
            maxu = (0, v)
        dist[v] = maxu if maxu[0] >= 0 else (0, v)

    u = None
    v = max(dist, key=lambda x: dist[x][0])
    path = []
    while u != v:
        path.append(v)
        u = v
        v = dist[v][1]
    path.reverse()
    return path


def dag_longest_path(G, weight="weight", default_weight=1, topo_order=None):
    """Return the longest path in a DAG.

    Parameters
    ----------
    G : DiGraph
        A directed acyclic graph (DAG).
    weight : str, optional
        Edge attribute name to use for weights. Default is 'weight'.
    default_weight : int, optional
        Default weight for edges without the weight attribute. Default is 1.
    topo_order : iterable, optional
        Precomputed topological order of the nodes.

    Returns
    -------
    list
        The longest path as a list of nodes.

    br-r37-c1-sn6tm: nx's algorithm is tie-break-sensitive — it picks
    the FIRST predecessor by iteration order when two paths have equal
    length (``max(us, key=lambda x: x[0])`` returns the first max).
    Previously we delegated to nx via ``_call_networkx_for_parity``
    which converts through ``_fnx_to_nx``; that conversion emits edges
    in per-node adj iteration order (``_topo_emit_edges_by_adj``),
    which does NOT preserve the ``pred[v]`` insertion order users
    actually built. nx then saw a different tie-break and returned a
    different (but equally valid) longest path. Implementing the
    algorithm directly on fnx's native ``G.pred[v]`` view sidesteps the
    conversion loss and reproduces nx semantics exactly.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented(
            "not implemented for undirected type"
        )
    if len(G) == 0:
        return []

    if topo_order is None and type(G) is DiGraph:
        native_in_edges = getattr(G, "_native_in_edges_data_key", None)
        if native_in_edges is not None:
            return _dag_longest_path_digraph_native(
                G, weight, default_weight
            )

    if topo_order is None:
        topo_order = topological_sort(G)

    is_multi = G.is_multigraph()
    dist = {}  # {v: (length, u)}
    multi_pred = None
    if is_multi:
        # br-r37-c1-5m18w (cc): build the predecessor adjacency (heaviest parallel-edge
        # weight per (u, v)) via the native _native_predecessor_row_dict(v) per node —
        # a row-ordered {u: keydict} that MATCHES G.pred[v]'s order exactly (so the
        # max() tie-break is byte-identical) and is ~3.5x faster than iterating the
        # MultiAdjacencyView (G.pred.items()), which re-materialises the whole adjacency
        # per row. (The native EDGE list is faster still but raw-insertion-order, which
        # diverges from the row-ordered G.pred on ties — this per-row accessor is both.)
        multi_pred = {}
        _prd = getattr(G, "_native_predecessor_row_dict", None)
        if _prd is not None:
            for _v in G:
                _pw = {}
                for _u, _keydict in _prd(_v).items():
                    _pw[_u] = max(
                        (
                            attrs.get(weight, default_weight)
                            if isinstance(attrs, dict)
                            else default_weight
                            for attrs in _keydict.values()
                        ),
                        default=default_weight,
                    )
                multi_pred[_v] = _pw
        else:
            for _v, _preds in G.pred.items():
                _pw = {}
                for _u, _keydict in _preds.items():
                    _pw[_u] = max(
                        (
                            attrs.get(weight, default_weight)
                            if isinstance(attrs, dict)
                            else default_weight
                            for attrs in _keydict.values()
                        ),
                        default=default_weight,
                    )
                multi_pred[_v] = _pw
    for v in topo_order:
        if is_multi:
            us = [(dist[u][0] + _w, u) for u, _w in multi_pred[v].items()]
        else:
            us = []
            for u, data in G.pred[v].items():
                edge_weight = (
                    data.get(weight, default_weight)
                    if isinstance(data, dict)
                    else default_weight
                )
                us.append((dist[u][0] + edge_weight, u))
        # nx's tie-break: max with key=x[0] returns the FIRST element
        # with the max first component (Python's max stability).
        maxu = max(us, key=lambda x: x[0]) if us else (0, v)
        dist[v] = maxu if maxu[0] >= 0 else (0, v)

    u = None
    v = max(dist, key=lambda x: dist[x][0])
    path = []
    while u != v:
        path.append(v)
        u = v
        v = dist[v][1]
    path.reverse()
    return path
