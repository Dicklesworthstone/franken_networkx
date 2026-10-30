

def common_neighbors(G, u, v):
    """Returns the common neighbors of two nodes in a graph."""
    if type(G) is Graph and not _has_networkx_private_storage(G):
        # br-r37-c1-comnbr (bt): native integer-adjacency-row intersection — no
        # per-neighbour attr-dict materialisation, no Python-level `in G` round-trips,
        # one FFI call. Raises NetworkXError (u-before-v) for missing nodes; returns
        # None only for a hash-mixed-key graph (adj_py_keys), which keeps the row-dict
        # path below (z6uka row-display objects).
        _native = getattr(G, "_native_common_neighbors", None)
        if _native is not None:
            _common = _native(u, v)
            if _common is not None:
                return _common
        if u not in G:
            raise NetworkXError("u is not in the graph.")
        if v not in G:
            raise NetworkXError("v is not in the graph.")
        # br-r37-c1-ceqev: networkx's expression over the same row dicts, so the
        # set iterates in its order too.
        return G._native_adjacency_row_dict(u).keys() & (
            G._native_adjacency_row_dict(v).keys() - {u, v}
        )
    # br-r37-c1-ceqev: networkx's expression over rows of the type networkx
    # has, so the set iterates in its order too. That type is a view's, not
    # the concrete graph's a view materialises to, whose rows are the same
    # in the same order. A networkx graph or view handed in is its own
    # answer: its rows as they are, no copy.
    if _is_networkx_graph(G):
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        if u not in G:
            raise NetworkXError("u is not in the graph.")
        if v not in G:
            raise NetworkXError("v is not in the graph.")
        return G._adj[u].keys() & G._adj[v].keys() - {u, v}
    rows_are_dicts = _nx_rows_are_dicts(G)
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if u not in G:
        raise NetworkXError("u is not in the graph.")
    if v not in G:
        raise NetworkXError("v is not in the graph.")
    # br-r37-c1-qkq2h: bypass AtlasView via raw _GRAPH_NEIGHBORS for
    # the common case. nx uses ``G._adj[u].keys() & G._adj[v].keys()``
    # — direct dict access; fnx had to go through AtlasView's per-
    # element PyO3 fetch. Same wrapper-bypass pattern as the rest of
    # the family.
    _raw_nbrs = _raw_neighbors_dispatch(G)
    if _raw_nbrs is not None:
        u_row, v_row = _raw_nbrs(G, u), _raw_nbrs(G, v)
    else:
        u_row, v_row = G.adj[u], G.adj[v]
    if rows_are_dicts:
        return dict.fromkeys(u_row).keys() & (dict.fromkeys(v_row).keys() - {u, v})
    # KeysView's - and & : each side a set grown one add at a time, the &
    # walking the rest.
    uv = {u, v}
    rest = {w for w in v_row if w not in uv}
    u_keys = dict.fromkeys(u_row)
    return {w for w in rest if w in u_keys}


def _is_networkx_graph(G):
    """Whether ``G`` is a networkx graph or view handed to an fnx function -
    networkx is not imported for the question."""
    nx_module = _sys.modules.get("networkx")
    return nx_module is not None and isinstance(G, nx_module.Graph)


def _nx_rows_are_dicts(G):
    """Whether networkx's ``G._adj[u]`` is a dict for this undirected graph - a
    graph's own row, which ``copy(as_view=True)`` and an undirected graph's
    ``to_undirected(as_view=True)`` share - rather than a coreview Mapping: a
    filtered view's FilterAtlas, or the UnionAtlas of a digraph's undirected
    view (br-r37-c1-ceqev)."""
    while True:
        if isinstance(G, _FilteredGraphView):
            # copy(as_view=True) is the one view built with no filter at all;
            # subgraph_view passes its no_filter default explicitly.
            if not (G._filter_node_is_default and G._filter_edge_is_default) or (
                _subgraph_view_no_filter_default in (G._filter_node, G._filter_edge)
            ):
                return False
        elif isinstance(G, _ConversionGraphViewBase):
            if G._graph.is_directed():
                return False
        else:
            return True
        G = G._graph


def neighbors(G, n):
    """Return neighbors of n (global function form)."""
    try:
        _HASH_PROBE.get(n)
    except TypeError:
        raise
    if n not in G:
        graph_name = "digraph" if G.is_directed() else "graph"
        raise NetworkXError(f"The node {n} is not in the {graph_name}.")
    return iter(G.neighbors(n))


def describe(G, describe_hook=None):
    """Print a description of the graph G.

    Parameters
    ----------
    G : graph
        A NetworkX graph.
    describe_hook : callable, optional (default=None)
        A function that takes a graph as input and returns a dictionary of
        additional properties to include in the description.

    Notes
    -----
    Matches nx.describe's surface (br-r37-c1-pyx0a). The describe_hook
    output is merged into the info dict in iteration order before
    printing.
    """
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

    if describe_hook is not None:
        extra = describe_hook(G)
        if extra:
            info.update(extra)

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


def _mutual_weight(G, u, v, weight=None):
    """networkx's mutual_weight: ``G[u][v].get(weight, 1)`` each way, 0 where
    there is no edge.

    On a multigraph ``G[u][v]`` is the keydict, so networkx counts an edge 1
    whatever its weights or its multiplicity; this keeps that reading
    (br-r37-c1-14vcl). Summing the parallel edges' weights instead gave
    local_constraint 0.056756 where networkx gives 0.036338.
    """
    try:
        a_uv = G[u][v].get(weight, 1)
    except KeyError:
        a_uv = 0
    try:
        a_vu = G[v][u].get(weight, 1)
    except KeyError:
        a_vu = 0
    return a_uv + a_vu


def _normalized_mutual_weight(G, u, v, weight=None, norm=sum):
    """Normalize mutual weight relative to all neighbors of ``u``."""
    scale = norm(_mutual_weight(G, u, w, weight) for w in set(all_neighbors(G, u)))
    return 0 if scale == 0 else _mutual_weight(G, u, v, weight) / scale


def local_constraint(G, u, v, weight=None, *, backend=None, **backend_kwargs):
    """Burt's local constraint for edge ``(u, v)``."""
    _validate_backend_dispatch_keywords("local_constraint", backend, backend_kwargs)
    graph_kind = "digraph" if G.is_directed() else "graph"
    if u not in G:
        raise NetworkXError(f"The node {u} is not in the {graph_kind}.")

    # br-r37-c1-localconstraint (cc): the old form re-derived ``set(all_neighbors(G, u))``
    # and its normalisation scale inside every ``_normalized_mutual_weight(G, u, .)`` call
    # (deg(u)+1 times -> O(deg(u)^2) slow fnx adjacency walks). Snapshot u's neighbours and
    # its scale ONCE; ``nmw_u`` is byte-identical to ``_normalized_mutual_weight(G, u, x)``.
    nbrs_u = set(all_neighbors(G, u))
    scale_u = sum(_mutual_weight(G, u, w, weight) for w in nbrs_u)

    def nmw_u(x):
        return 0 if scale_u == 0 else _mutual_weight(G, u, x, weight) / scale_u

    direct = nmw_u(v)
    indirect = sum(
        nmw_u(w) * _normalized_mutual_weight(G, w, v, weight=weight)
        for w in nbrs_u
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


def communicability_exp(G, *, backend=None, **backend_kwargs):
    """Communicability via scipy.linalg.expm."""
    _validate_backend_dispatch_keywords(
        "communicability_exp",
        backend,
        backend_kwargs,
    )
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

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

    # br-egrnocopy: only copy when edge weights are actually mutated. nx
    # inverts weights on a copy when invert_weight is True AND a weight key is
    # given; for the default weight=None path the shallow copy was pure
    # construction-tax waste (~5x slower than nx on a 300-node graph; washes
    # out only once the O(n^3) eigvalsh dominates). Read the spectrum directly
    # off G when no inversion is needed -- bit-identical result.
    if invert_weight and weight is not None:
        H = _copy_graph_shallow(G)
        if H.is_multigraph():
            for _, _, _, attrs in H.edges(keys=True, data=True):
                attrs[weight] = 1 / attrs[weight]
        else:
            for _, _, attrs in H.edges(data=True):
                attrs[weight] = 1 / attrs[weight]
    else:
        H = G

    mu = np.sort(laplacian_spectrum(H, weight=weight))
    return float(np.sum(1 / mu[1:]) * H.number_of_nodes())


def graph_edit_distance(
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
    roots=None,
    upper_bound=None,
    timeout=None,
):
    """Return the graph edit distance between *G1* and *G2*.

    Matches networkx's full positional + keyword surface so
    ``inspect.signature`` introspection is identical (br-r37-c1-gedsig).

    br-r37-c1-jwdzp: accept nx-typed inputs so cross-library calls
    don't get rejected by the Rust kernel's strict type check.
    The native fast path handles common small-graph cases;
    ``timeout`` requires the iterative algorithm and is delegated to
    networkx.
    """
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
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
        roots=roots,
        timeout=timeout,
    )
    if handled:
        if native_result is None:
            return None
        _, cost = native_result
        return cost

    if timeout is not None:
        # nx's timeout cutoff requires the iterative variant we don't
        # ship; project policy is to surface NetworkXNotImplemented
        # rather than fall back to the upstream Python implementation
        # (test_graph_edit_directed_mismatch_and_unsupported_modes_do_not_fallback
        # locks this contract).
        raise NetworkXNotImplemented(
            "timeout is not supported by local graph_edit_distance",
        )
    _, cost = _graph_edit_exact_paths_python(
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
        roots=roots,
    )
    return cost


def optimize_graph_edit_distance(
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
    """_Iterator yielding successive graph edit distance estimates.

    Matches networkx's signature; the local wrapper currently yields a
    single final cost. (br-r37-c1-gedsig)
    """
    cost = graph_edit_distance(
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
    if cost is not None:
        yield cost


_COMMON_GRAPH_EDIT_DISTANCE_MAX_NODES = 8


def _graph_edit_distance_edge_key(G, edge):
    if G.is_directed():
        return edge
    return frozenset(edge)


def _graph_edit_display_edge(G, edge):
    if G.is_directed():
        return edge
    wanted = frozenset(edge)
    for candidate in G.edges():
        if frozenset(candidate) == wanted:
            return candidate
    return edge


def _graph_edit_distance_paths_from_mapping(
    G1,
    G2,
    mapping,
    *,
    normalize_undirected_right_edges=False,
):
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
            if normalize_undirected_right_edges:
                right_edge = _graph_edit_display_edge(G2, right_edge)
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
    queue = _deque([nodes[0]])
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
    # br-r37-c1-tnzt9: nx validates the source up front with the exact wording
    # ``Node {source} is not found in the graph`` (before weight handling); the
    # internal bellman-ford call otherwise surfaces ``Source x not in G``.
    if source not in G:
        raise NodeNotFound(f"Node {source} is not found in the graph")
    if callable(weight) or G.is_multigraph():
        return _goldberg_radzik_inproc(G, source, weight=weight)
    return _goldberg_radzik_simple_inprocess(G, source, weight)


def _goldberg_radzik_inproc(G, source, weight="weight"):
    """Compute shortest path lengths and predecessors via Goldberg-Radzik in-process."""
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

    if len(G) == 1:
        return {source: None}, {source: 0}

    G_succ = G._adj

    inf = float("inf")
    d = {u: inf for u in G}
    d[source] = 0
    pred = {source: None}

    def topo_sort(relabeled):
        to_scan = []
        neg_count = {}
        for u in relabeled - neg_count.keys():
            d_u = d[u]
            if all(d_u + weight_fn(u, v, e) >= d[v] for v, e in G_succ[u].items()):
                continue
            stack = [(u, iter(G_succ[u].items()))]
            in_stack = {u}
            neg_count[u] = 0
            while stack:
                u, it = stack[-1]
                try:
                    v, e = next(it)
                except StopIteration:
                    to_scan.append(u)
                    stack.pop()
                    in_stack.remove(u)
                    continue
                t = d[u] + weight_fn(u, v, e)
                d_v = d[v]
                if t < d_v:
                    d[v] = t
                    pred[v] = u
                    if v not in neg_count:
                        neg_count[v] = neg_count[u] + 1
                        stack.append((v, iter(G_succ[v].items())))
                        in_stack.add(v)
                    elif v in in_stack and neg_count[u] + 1 > neg_count[v]:
                        raise NetworkXUnbounded("Negative cycle detected.")
        to_scan.reverse()
        return to_scan

    def relax(to_scan):
        relabeled = set()
        for u in to_scan:
            d_u = d[u]
            for v, e in G_succ[u].items():
                w_e = weight_fn(u, v, e)
                if d_u + w_e < d[v]:
                    d[v] = d_u + w_e
                    pred[v] = u
                    relabeled.add(v)
        return relabeled

    relabeled = {source}
    while relabeled:
        to_scan = topo_sort(relabeled)
        relabeled = relax(to_scan)

    d = {u: d[u] for u in pred}
    return pred, d


def _goldberg_radzik_simple_inprocess(G, source, weight):
    """br-grport: faithful in-process port of networkx's Goldberg-Radzik scan
    algorithm for a simple fnx graph, directed or not. Replaces the previous naive O(V*E)
    Bellman-Ford (which re-walked the EdgeView every pass AND picked different
    predecessors than nx on ties). Operates on a one-time plain-dict adjacency
    snapshot with weights resolved, so it avoids both the fnx->nx conversion and
    the per-access view tax, and reproduces nx's exact (pred, dist) — including
    the predecessor tie-breaks — for the same adjacency order. A simple graph's
    weight function is ``data.get(weight, 1)``, which is what the snapshot
    resolves; an undirected Graph walked its adjacency views calling it per edge
    at 0.46-0.52x networkx (br-r37-c1-ad5r8)."""
    # Adjacency snapshot {u: {v: w}} in fnx adjacency order (== what nx iterates).
    # Use the native to_dict_of_dicts bulk reader (kernel, ~22x cheaper than walking
    # G.adj[u] per node, which otherwise dominates and leaves us 3x slower than nx).
    # A view walks its own adjacency: to_dict_of_dicts raises on a filtered view,
    # as networkx's does (br-r37-c1-7jhpr).
    rows = to_dict_of_dicts(G) if type(G) in (Graph, DiGraph) else dict(G.adjacency())
    g_succ = {
        u: {v: attrs.get(weight, 1) for v, attrs in row.items()}
        for u, row in rows.items()
    }

    # Self-loop of negative weight is a negative cycle (matches nx).
    for u, nbrs in g_succ.items():
        if u in nbrs and nbrs[u] < 0:
            raise NetworkXUnbounded("Negative cycle detected.")

    if len(g_succ) == 1:
        return {source: None}, {source: 0}

    inf = float("inf")
    d = dict.fromkeys(g_succ, inf)
    d[source] = 0
    pred = {source: None}

    def topo_sort(relabeled):
        to_scan = []
        neg_count = {}
        for u in relabeled - neg_count.keys():
            d_u = d[u]
            if all(d_u + w >= d[v] for v, w in g_succ[u].items()):
                continue
            stack = [(u, iter(g_succ[u].items()))]
            in_stack = {u}
            neg_count[u] = 0
            while stack:
                u, it = stack[-1]
                try:
                    v, w = next(it)
                except StopIteration:
                    to_scan.append(u)
                    stack.pop()
                    in_stack.remove(u)
                    continue
                t = d[u] + w
                if t < d[v]:
                    d[v] = t
                    pred[v] = u
                    if v not in neg_count:
                        neg_count[v] = neg_count[u] + 1
                        stack.append((v, iter(g_succ[v].items())))
                        in_stack.add(v)
                    elif v in in_stack and neg_count[u] + 1 > neg_count[v]:
                        raise NetworkXUnbounded("Negative cycle detected.")
        to_scan.reverse()
        return to_scan

    def relax(to_scan):
        relabeled = set()
        for u in to_scan:
            d_u = d[u]
            for v, w in g_succ[u].items():
                if d_u + w < d[v]:
                    d[v] = d_u + w
                    pred[v] = u
                    relabeled.add(v)
        return relabeled

    relabeled = {source}
    while relabeled:
        relabeled = relax(topo_sort(relabeled))

    d = {u: d[u] for u in pred}
    return pred, d


def _graphml_native_edge_count(payload):
    """Admit only XML shapes whose native decoding matches the full reader.

    ElementTree checks structure without constructing a NetworkX graph. This
    is deliberately conservative: defaults, extension data, unusual encodings,
    and XML constructs normalized differently by the two readers fall back.
    """
    import re
    from xml.etree.ElementTree import fromstring

    if type(payload) not in (str, bytes):
        return None
    try:
        text = payload.decode("utf-8") if type(payload) is bytes else payload
    except UnicodeDecodeError:
        return None
    if any(marker in text for marker in ("&", "<!", "\r", "\x00")):
        return None
    declaration = re.match(r"\A(?:\ufeff)?<\?xml\s+[^?]*\?>", text)
    if declaration is not None:
        encoding = re.search(r"\bencoding\s*=\s*(['\"])(.*?)\1", declaration[0])
        if encoding is not None:
            name = encoding[2].lower()
            if name not in {"utf-8", "utf8", "ascii", "us-ascii"}:
                return None
            if name in {"ascii", "us-ascii"} and not text.isascii():
                return None
    if "<?" in text[declaration.end() if declaration is not None else 0:]:
        return None
    # ElementTree removes namespace declarations, but native attribute lookup
    # uses local names: xmlns:id can otherwise overwrite an ordinary node id.
    if any(prefix != "xsi" for prefix in re.findall(r"\bxmlns:([^\s=]+)\s*=", text)):
        return None
    try:
        root = fromstring(payload)
    except Exception:
        # Let the requested public decoder raise its own exception and wording.
        return None
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    if root.tag != ns + "graphml" or set(root.attrib) - {
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    }:
        return None
    keys = {}
    graph = None
    scalar_types = {"boolean", "int", "long", "float", "double", "string"}
    for child in root:
        if child.tag == ns + "graph" and graph is None:
            graph = child
        elif child.tag == ns + "key" and graph is None:
            if set(child.attrib) != {"id", "for", "attr.name", "attr.type"} or len(child):
                return None
            key_id, scope = child.get("id"), child.get("for")
            name, value_type = child.get("attr.name"), child.get("attr.type")
            if (
                not key_id or not name or key_id in keys
                or any(char.isspace() for char in key_id + name)
                or scope not in {"graph", "node", "edge"}
                or value_type not in scalar_types
                or (scope == "graph" and name in {"node_default", "edge_default"})
            ):
                return None
            keys[key_id] = (scope, value_type)
        else:
            return None
    if graph is None or set(graph.attrib) != {"edgedefault"}:
        return None
    if graph.get("edgedefault") not in {"directed", "undirected"}:
        return None
    nodes = set()
    edge_count = 0
    for child in graph:
        if child.tag == ns + "node":
            node_id = child.get("id")
            if (
                edge_count or set(child.attrib) != {"id"} or not node_id
                or node_id in nodes or any(char.isspace() for char in node_id)
            ):
                return None
            nodes.add(node_id)
        elif child.tag == ns + "edge":
            if set(child.attrib) != {"source", "target"}:
                return None
            if child.get("source") not in nodes or child.get("target") not in nodes:
                return None
            edge_count += 1
        elif child.tag != ns + "data":
            return None
    for element in root.iter():
        if element.tail and element.tail.strip():
            return None
        if element.tag != ns + "data" and element.text and element.text.strip():
            return None
        if element.tag in {ns + "graph", ns + "node", ns + "edge"}:
            scope = element.tag[len(ns):]
            for data in element:
                if element is graph and data.tag in {ns + "node", ns + "edge"}:
                    continue
                if data.tag != ns + "data" or set(data.attrib) != {"key"} or len(data):
                    return None
                key = keys.get(data.get("key"))
                value = data.text
                if key is None or key[0] != scope or not value or value != value.strip():
                    return None
                if key[1] == "boolean" and value.lower() not in {"true", "false", "0", "1"}:
                    return None
                if key[1] in {"int", "long"}:
                    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
                        return None
                    try:
                        fits_native = -(1 << 63) <= int(value) < (1 << 63)
                    except ValueError:
                        return None
                    if not fits_native:
                        return None
                if key[1] in {"float", "double"}:
                    try:
                        if not _math.isfinite(float(value)):
                            return None
                    except ValueError:
                        return None
    return edge_count


def parse_graphml(
    graphml_string,
    node_type=str,
    edge_key_type=int,
    force_multigraph=False,
    *,
    backend=None,
    **backend_kwargs,
):
    """Parse a GraphML string."""
    _validate_backend_dispatch_keywords("parse_graphml", backend, backend_kwargs)
    return _parse_graphml_payload(
        graphml_string, node_type=node_type,
        edge_key_type=edge_key_type, force_multigraph=force_multigraph,
    )


def _parse_graphml_payload(
    payload, *, node_type=str, edge_key_type=int, force_multigraph=False,
    parse_string=True, file_source=None,
):
    """Share native admission while retaining string/file decoder contracts."""
    stream_type = _io.StringIO if isinstance(payload, str) else _io.BytesIO
    if (
        (node_type is str or node_type is int)
        and edge_key_type is int
        and not force_multigraph
        and _rust_get_compatibility_mode() != "hardened"
    ):
        edge_count = _graphml_native_edge_count(payload)
        if edge_count is not None:
            try:
                _native = _fnx.read_graphml(stream_type(payload))
            except Exception:
                _native = None
            if (
                _native is not None
                and not _native.is_multigraph()
                and _native.number_of_edges() == edge_count
            ):
                if node_type is str:
                    return _native
                # Integer labels can use the same native parser when the
                # conversion is one-to-one. A merge ("01" and "1") must be
                # decoded from the original XML: relabeling the simple graph
                # would otherwise collapse edges before multigraph detection.
                mapping = {node: int(node) for node in _native}
                converted = _native._native_relabel_copy(mapping)
                if converted is not None:
                    return converted

    # Apply conversion options while the document still has its original IDs.
    # Parsing first with defaults irreversibly merges lexical edge keys such
    # as "01" and "1", and relabeling a simple graph afterwards can discard
    # parallel edges introduced by node_type. The mode-aware reader also owns
    # recovery decisions, so keep its ledger instead of rebuilding its result.
    if _rust_get_compatibility_mode() == "hardened":
        return _graphml_from_mode_payload(
            payload, node_type=node_type,
            edge_key_type=edge_key_type, force_multigraph=force_multigraph,
            parse_string=parse_string,
        )
    if parse_string:
        from .readwrite import _parse_graphml_via_nx

        return _parse_graphml_via_nx(
            payload, node_type=node_type,
            edge_key_type=edge_key_type, force_multigraph=force_multigraph,
        )
    return _read_graphml_via_nx(
        stream_type(payload) if file_source is None else _GraphMLBufferedInput(payload, file_source),
        node_type=node_type,
        edge_key_type=edge_key_type,
        force_multigraph=force_multigraph,
    )


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
    # GraphML accepts NumPy's fixed-width integer and ordinary float scalars.
    # Use exact types: bool_, complex, datetime, and extended floats have no
    # corresponding entry in the format's scalar contract. Import lazily so
    # ordinary graph serialization still works without NumPy installed.
    try:
        import numpy as np
    except ImportError:
        pass
    else:
        if value_type in (
            np.int8, np.int16, np.int32, np.int64,
            np.uint8, np.uint16, np.uint32, np.uint64,
            np.int_, np.intc, np.intp,
        ):
            return "int"
        if value_type in (np.float16, np.float32, np.float64):
            return "float"
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
    attributes = _defaultdict(list)

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
def mycielskian(G, iterations=1):
    """Return the Mycielskian of G applied ``iterations`` times.

    Each application increases the chromatic number by 1. ``iterations``
    matches networkx's public signature; default 1 preserves the
    single-step behaviour fnx shipped previously.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    # br-r37-c1-mycorder: mirror networkx exactly. nx relabels nodes to
    # integers ONCE (convert_node_labels_to_integers) before iterating, then
    # per step adds the shadow edges in a TWO-PASS order: all (u, v+n) for the
    # old edges, then all (u+n, v). The previous impl kept the original node
    # labels (diverging from nx's integer relabel for non-int graphs) and
    # interleaved the two passes (diverging on edge order even for int graphs).
    M = convert_node_labels_to_integers(G)
    for _ in range(iterations):
        M = _mycielskian_step(M)
    return M


def _mycielskian_step(M):
    # ``M`` is integer-labeled (0..n-1 contiguous); shadow of node u is u+n,
    # apex is 2n. Matches networkx's in-place construction order exactly.
    # br-r37-c1-mycbatch: assemble the result with BATCH add_nodes_from /
    # add_edges_from instead of a per-edge add_edge loop (each a separate PyO3
    # crossing + per-edge dict/key construction). The node + edge order is
    # preserved, so the result is byte-identical — only the build path differs.
    # br-r37-c1-mycnative (cc): the attr-free case (Mycielskians are built on
    # unlabelled test graphs) assembles the whole 2n+1-node / 3E+n-edge structure in
    # Rust, skipping the per-edge PyO3 construction tax (batched Python build ~0.65x
    # vs nx). Only fires when M has no node/edge/graph attrs (the native kernel builds
    # pure structure); otherwise fall through to the attr-preserving Python build.
    if type(M) is Graph and not M.graph and not _graph_has_any_attrs(M):
        _fast = getattr(_fnx, "mycielskian_step_fast", None)
        if _fast is not None:
            _r = _fast(M)
            if _r is not None:
                return _r
    n = M.number_of_nodes()
    R = Graph()
    R.add_nodes_from((node, dict(data)) for node, data in M.nodes(data=True))
    old_edges = list(M.edges(data=True))
    R.add_edges_from((u, v, dict(data)) for u, v, data in old_edges)
    R.add_nodes_from(range(n, 2 * n))
    R.add_edges_from((u, v + n) for u, v, _data in old_edges)
    R.add_edges_from((u + n, v) for u, v, _data in old_edges)
    apex = 2 * n
    R.add_node(apex)
    R.add_edges_from((n + i, apex) for i in range(n))
    return R


def mycielski_graph(n):
    """Return the n-th Mycielski graph.

    br-myciel01: nx.mycielski_graph(1) returns the single-vertex graph
    (no edges) and nx.mycielski_graph(0) raises NetworkXError. fnx's
    "start from K2 then iterate n-2 times" recipe produced K2 (2 nodes,
    1 edge) for both n=0 and n=1, diverging from nx at the small-n
    boundary. Add explicit n<=0 / n==1 handling so the sequence is:
    n=0 -> error; n=1 -> 1 isolated vertex; n=2 -> K2; n>=3 -> iterate.
    """
    if n < 1:
        raise NetworkXError("must satisfy n >= 1")
    if n == 1:
        G = Graph()
        G.add_node(0)
        return G
    G = complete_graph(2)
    for _ in range(n - 2):
        G = mycielskian(G)
    return G


def _dorogovtsev_goltsev_mendes_edges(n):
    """Edge-addition sequence for the DGM graph, in nx's exact ``add_edge`` order.

    nx re-reads ``list(G.edges())`` (a node-major adjacency walk) at the start of
    each generation, then attaches each new node to both endpoints of every edge
    from the previous generation.  Reproducing that walk over integer adjacency
    lists (kept in insertion order) yields the identical edge sequence, so a
    single bulk ``add_edges_from`` builds a byte-exact graph — far cheaper than
    the per-edge / per-generation ``edges_ordered`` clone tax of the native
    kernel (br-r37-c1-tp7j4: ~2x slower than nx -> near parity).
    """
    adj = [[1], [0]]
    edge_seq = [(0, 1)]
    append = edge_seq.append
    new_node = 2
    for _ in range(n):
        # Snapshot previous-generation edges in node-major adjacency order.
        # For outer node u, the edges first emitted are exactly those to a
        # neighbour nbr > u (smaller-endpoint edges were emitted at that
        # endpoint), in u's adjacency insertion order.
        current = []
        cap = current.append
        for u in range(new_node):
            for nbr in adj[u]:
                if nbr > u:
                    cap((u, nbr))
        for u, v in current:
            k = new_node
            append((k, u))
            append((k, v))
            adj.append([u, v])
            adj[u].append(k)
            adj[v].append(k)
            new_node += 1
    return edge_seq


def dorogovtsev_goltsev_mendes_graph(n, create_using=None):
    """Return the Dorogovtsev-Goltsev-Mendes graph.

    A hierarchically constructed scale-free graph with deterministic structure.
    After n generations: (3^n + 3)/2 nodes, 3^n edges.
    """
    if n < 0:
        raise NetworkXError("n must be greater than or equal to 0")

    if create_using is None:
        target = Graph()
    else:
        target = _empty_graph_from_create_using(create_using, default=Graph)
        if target.is_directed():
            raise NetworkXError("directed graph not supported")
        if target.is_multigraph():
            raise NetworkXError("multigraph not supported")

    target.add_edges_from(_dorogovtsev_goltsev_mendes_edges(n))
    return target


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


def random_lobster(n, p1, p2, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Random lobster graph."""
    _validate_backend_dispatch_keywords("random_lobster", backend, backend_kwargs)
    rng = _generator_random_state(seed)
    p1, p2 = abs(p1), abs(p2)
    if any(p >= 1 for p in [p1, p2]):
        raise NetworkXError("Probability values for `p1` and `p2` must both be < 1.")

    if (
        create_using is None
        and seed is not None
        and isinstance(seed, _numbers.Integral)
        and not isinstance(seed, bool)
        and isinstance(n, _numbers.Integral)
        and not isinstance(n, bool)
    ):
        n_int = int(n)
        seed_int = int(seed)
        if 0 <= n_int and 0 <= seed_int <= 0xFFFF_FFFF_FFFF_FFFF:
            return _rust_random_lobster_graph_lazy_int(
                n_int,
                float(p1),
                float(p2),
                seed_int,
            )

    backbone_length = int(2 * rng.random() * n + 0.5)
    graph = path_graph(backbone_length)
    current_node = backbone_length - 1
    lobster_edges = []
    for backbone_node in range(backbone_length):
        while rng.random() < p1:
            current_node += 1
            lobster_edges.append((backbone_node, current_node))
            caterpillar_node = current_node
            while rng.random() < p2:
                current_node += 1
                lobster_edges.append((caterpillar_node, current_node))
    if lobster_edges:
        graph.add_edges_from(lobster_edges)
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


def random_lobster_graph(n, p1, p2, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Return a random lobster graph.

    br-r37-c1-rlgsig: nx exposes ``**backend_kwargs`` as a variadic
    catch-all on every @_dispatchable function.  fnx had previously
    declared ``backend_kwargs=None`` as a single named kwarg, so
    ``inspect.signature(fnx.random_lobster_graph)`` reported
    ``backend_kwargs=None`` instead of ``**backend_kwargs`` —
    breaking signature-parity-introspecting code.  Match nx's exact
    variadic shape and reject unknown kwargs with the nx-shaped
    ``TypeError`` from ``_validate_backend_dispatch_keywords``.
    """
    _validate_backend_dispatch_keywords(
        "random_lobster_graph", backend, backend_kwargs
    )
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


def random_shell_graph(constructor, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Multi-shell random graph."""
    _validate_backend_dispatch_keywords("random_shell_graph", backend, backend_kwargs)
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


def random_clustered_graph(joint_degree_sequence, create_using=None, seed=None):
    """Random graph from joint degree sequence.

    Positional order matches networkx: ``(seq, create_using, seed)``.
    Earlier fnx had ``(seq, seed, create_using)`` so a positional call
    like ``random_clustered_graph(seq, MultiGraph, 42)`` swapped the
    semantics of the second and third args (the seed was interpreted
    as create_using and vice versa).
    """
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
    """Return a random cograph with ``2 ** n`` nodes."""
    rng = _generator_random_state(seed)
    # br-r37-c1-cographonepass (cc): accumulate the edge list in plain Python and
    # commit it with ONE add_edges_from, instead of per-step copy() + relabel_nodes()
    # + full_join/disjoint_union (each rebuilds an fnx graph = construction tax;
    # 4.3x slower on sparse, ~up to 10x on dense). The rng.randint(0,1) draw order is
    # unchanged, node labels stay 0..2**n-1, and the shifted-edge then full_join
    # cross-edge (left x right) emission order matches the operator path exactly, so
    # the node + edge iteration order is byte-identical (verified 240 cases:
    # n in {0,1,2,3,5,7} x 40 seeds, vs both current fnx and networkx).
    size = 1
    edges = []
    for _ in range(n):
        shifted = [(u + size, v + size) for (u, v) in edges]
        if rng.randint(0, 1) == 0:
            edges = edges + shifted + [
                (u, v + size) for u in range(size) for v in range(size)
            ]
        else:
            edges = edges + shifted
        size *= 2

    graph = empty_graph(size)
    graph.add_edges_from(edges)
    return graph


def random_degree_sequence_graph(sequence, seed=None, tries=10):
    """Random graph with given degree sequence."""
    generator = _DegreeSequenceRandomGraph(sequence, _generator_random_state(seed))
    for _ in range(tries):
        try:
            return generator.generate()
        except NetworkXUnfeasible:
            pass
    raise NetworkXError(f"failed to generate graph in {tries} tries")


def random_internet_as_graph(n, seed=None, *, backend=None, **backend_kwargs):
    """Random Internet AS-level graph."""
    _validate_backend_dispatch_keywords(
        "random_internet_as_graph", backend, backend_kwargs
    )
    return _random_internet_as_graph_impl(n, seed=seed)


def _random_internet_as_graph_impl(n, seed=None):
    """In-process Elmokashfi et al. random Internet AS-level graph generator."""
    from math import floor

    rng = _create_py_random_state(seed)

    def _uniform_int_from_avg(a, m):
        b = 2 * m - a
        p = (b - floor(b)) / 2
        x1 = round(rng.random() * (floor(b) - a) + a)
        x2 = 1 if rng.random() < p else 0
        return x1 + x2

    def _choose_pref_attach(degs):
        if len(degs) == 0:
            return None
        s = sum(degs.values())
        if s == 0:
            return rng.choice(list(degs.keys()))
        v = rng.random() * s
        nodes = list(degs.keys())
        i = 0
        acc = degs[nodes[i]]
        while v > acc:
            i += 1
            acc += degs[nodes[i]]
        return nodes[i]

    n_t = min(n, round(rng.random() * 2 + 4))
    n_m = round(0.15 * n)
    n_cp = round(0.05 * n)
    n_c = max(0, n - n_t - n_m - n_cp)

    d_m = 2 + (2.5 * n) / 10000
    d_cp = 2 + (1.5 * n) / 10000
    d_c = 1 + (5 * n) / 100000

    p_m_m = 1 + (2 * n) / 10000
    p_cp_m = 0.2 + (2 * n) / 10000
    p_cp_cp = 0.05 + (2 * n) / 100000

    t_m = 0.375
    t_cp = 0.375
    t_c = 0.125

    regions = {f"REG{i}": set() for i in range(5)}
    customers = {}
    providers = {}
    nodes_by_kind = {"T": set(), "M": set(), "CP": set(), "C": set()}
    G = Graph()

    def _add_edge(i, j, kind):
        customer = str(i) if kind == "transit" else "none"
        G.add_edge(i, j, type=kind, customer=customer)

    def _choose_peer_pref_attach(node_list):
        d = {nd: G.nodes[nd]["peers"] for nd in node_list}
        return _choose_pref_attach(d)

    def _choose_node_pref_attach(node_list):
        degs = dict(G.degree(node_list))
        return _choose_pref_attach(degs)

    def _add_customer(i, j):
        customers[j].add(i)
        providers[i].add(j)
        for z in providers[j]:
            customers[z].add(i)
            providers[i].add(z)

    def _add_node(i, kind, reg2prob, avg_deg, t_edge_prob):
        regs = 2 if rng.random() < reg2prob else 1
        node_options = set()
        G.add_node(i, type=kind, peers=0)
        customers[i] = set()
        providers[i] = set()
        nodes_by_kind[kind].add(i)
        for r in rng.sample(list(regions), regs):
            node_options = node_options.union(regions[r])
            regions[r].add(i)
        edge_num = _uniform_int_from_avg(1, avg_deg)
        t_options = node_options.intersection(nodes_by_kind["T"])
        m_options = node_options.intersection(nodes_by_kind["M"])
        if i in m_options:
            m_options.remove(i)
        d = 0
        while d < edge_num and (len(t_options) > 0 or len(m_options) > 0):
            if len(m_options) == 0 or (
                len(t_options) > 0 and rng.random() < t_edge_prob
            ):
                j = _choose_node_pref_attach(t_options)
                t_options.remove(j)
            else:
                j = _choose_node_pref_attach(m_options)
                m_options.remove(j)
            _add_edge(i, j, "transit")
            _add_customer(i, j)
            d += 1
        return i

    def _add_m_peering_link(m, _to_kind):
        node_options = nodes_by_kind["M"].difference(customers[m])
        node_options = node_options.difference(providers[m])
        if m in node_options:
            node_options.remove(m)
        for j in G.neighbors(m):
            if j in node_options:
                node_options.remove(j)
        if len(node_options) > 0:
            j = _choose_peer_pref_attach(node_options)
            _add_edge(m, j, "peer")
            G.nodes[m]["peers"] += 1
            G.nodes[j]["peers"] += 1
            return True
        return False

    def _add_cp_peering_link(cp, to_kind):
        node_options = set()
        for r in regions:
            if cp in regions[r]:
                node_options = node_options.union(regions[r])
        node_options = nodes_by_kind[to_kind].intersection(node_options)
        if cp in node_options:
            node_options.remove(cp)
        node_options = node_options.difference(providers[cp])
        for j in G.neighbors(cp):
            if j in node_options:
                node_options.remove(j)
        if len(node_options) > 0:
            j = rng.sample(list(node_options), 1)[0]
            _add_edge(cp, j, "peer")
            G.nodes[cp]["peers"] += 1
            G.nodes[j]["peers"] += 1
            return True
        return False

    def _add_peering_links(from_kind, to_kind):
        peer_link_method = None
        if from_kind == "M":
            peer_link_method = _add_m_peering_link
            m = p_m_m
        if from_kind == "CP":
            peer_link_method = _add_cp_peering_link
            m = p_cp_m if to_kind == "M" else p_cp_cp
        for node_i in nodes_by_kind[from_kind]:
            num = _uniform_int_from_avg(0, m)
            for _ in range(num):
                peer_link_method(node_i, to_kind)

    for i in range(n_t):
        G.add_node(i, type="T")
        for r in regions:
            regions[r].add(i)
        for j in G.nodes():
            if i != j:
                _add_edge(i, j, "peer")
        customers[i] = set()
        providers[i] = set()
    nodes_by_kind["T"] = set(G.nodes())

    idx = len(nodes_by_kind["T"])
    for _ in range(n_m):
        nodes_by_kind["M"].add(_add_node(idx, "M", 0.2, d_m, t_m))
        idx += 1
    for _ in range(n_cp):
        nodes_by_kind["CP"].add(_add_node(idx, "CP", 0.05, d_cp, t_cp))
        idx += 1
    for _ in range(n_c):
        nodes_by_kind["C"].add(_add_node(idx, "C", 0, d_c, t_c))
        idx += 1

    _add_peering_links("M", "M")
    _add_peering_links("CP", "M")
    _add_peering_links("CP", "CP")
    return G


def _random_reference_inproc(G, niter=1, connectivity=True, seed=None):
    from bisect import bisect_left

    rng = _create_py_random_state(seed)
    G = G.copy()
    keys, degrees = zip(*G.degree())
    total_deg = float(sum(degrees))
    cdf = [0.0]
    acc = 0.0
    for deg in degrees:
        acc += deg
        cdf.append(acc / total_deg)
    nnodes = len(G)
    nedges = G.number_of_edges()
    niter = niter * nedges
    ntries = int(nnodes * nedges / (nnodes * (nnodes - 1) / 2))
    swapcount = 0

    for _ in range(niter):
        n = 0
        while n < ntries:
            ai = bisect_left(cdf, rng.random()) - 1
            ci = bisect_left(cdf, rng.random()) - 1
            if ai == ci:
                continue
            a = keys[ai]
            c = keys[ci]
            b = rng.choice(list(G.neighbors(a)))
            d = rng.choice(list(G.neighbors(c)))
            if b in [a, c, d] or d in [a, b, c]:
                continue

            if (d not in G[a]) and (b not in G[c]):
                G.add_edge(a, d)
                G.add_edge(c, b)
                G.remove_edge(a, b)
                G.remove_edge(c, d)

                if connectivity and not has_path(G, a, b):
                    G.remove_edge(a, d)
                    G.remove_edge(c, b)
                    G.add_edge(a, b)
                    G.add_edge(c, d)
                else:
                    swapcount += 1
                    break
            n += 1
    return G
