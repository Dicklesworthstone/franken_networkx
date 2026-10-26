

def tree_data(G, root, ident="id", children="children"):
    """Serialize a rooted directed tree to nested data."""
    if G.number_of_nodes() != G.number_of_edges() + 1:
        raise TypeError("G is not a tree.")
    if not G.is_directed():
        raise TypeError("G is not directed.")

    # br-r37-c1-treedatabulk: snapshot the successor adjacency (and node attrs)
    # in ONE native crossing each, then run BOTH the weakly-connected validation
    # and the nested-payload build off those snapshots — instead of a per-node
    # ``list(G[node])`` AdjacencyView crossing + ``{**G.nodes[child]}`` AtlasView
    # crossing for every node (the build) AND a per-node ``G[node]`` /
    # ``G.predecessors`` crossing for every node (the weakly-connected DFS), which
    # together dominated vs nx's plain dict access. The predecessor adjacency is
    # the cheap O(E) transpose of the successor snapshot (no extra crossing).
    # Pinned 0.40x -> ~2.4x, byte-exact incl id/children attr-key collisions,
    # custom ident/children kwargs, and the not-a-tree/undirected/disconnected
    # error contracts (700/700). Exact ``DiGraph`` only; subclasses / MultiDiGraph
    # keep the per-node view path.
    if type(G) is DiGraph:
        _adj = {node: list(neighbors) for node, neighbors in G.adjacency()}
        _pred = {node: [] for node in _adj}
        for _u, _vs in _adj.items():
            for _v in _vs:
                _pred[_v].append(_u)
        _nodes = list(_adj)
        if _nodes:
            _seen = {_nodes[0]}
            _stack = [_nodes[0]]
            while _stack:
                _n = _stack.pop()
                for _nb in _itertools.chain(_adj[_n], _pred[_n]):
                    if _nb not in _seen:
                        _seen.add(_nb)
                        _stack.append(_nb)
            _connected = len(_seen) == len(_nodes)
        else:
            _connected = False
        if not _connected:
            raise TypeError("G is not weakly connected.")
        if ident == children:
            raise NetworkXError(
                "The values for `id` and `children` must be different."
            )
        _node_attrs = dict(G.nodes(data=True))

        def add_children(node):
            child_nodes = _adj[node]
            if not child_nodes:
                return []
            payload = []
            for child in child_nodes:
                child_payload = {**_node_attrs[child], ident: child}
                nested = add_children(child)
                if nested:
                    child_payload[children] = nested
                payload.append(child_payload)
            return payload

        return {**_node_attrs[root], ident: root, children: add_children(root)}

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
        neighbors = _itertools.chain(G[node], G.predecessors(node))
        for neighbor in neighbors:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(nodes)


def tree_graph(data, ident="id", children="children"):
    """Reconstruct tree from nested dict data."""
    graph = DiGraph()

    # br-r37-c1-treegraphbatch: collect the (parent, child) edges and per-node
    # data in DFS pre-order, then BUILD in one batch instead of a per-node
    # ``add_edge`` + ``add_node`` PyO3 round-trip during the recursion (the
    # construction tax). When NO node carries attrs, ``add_edges_from`` alone
    # creates every node in the exact nx order (root first via add_node, then each
    # child when its parent edge is added) — the common tree round-trip case:
    # 0.42x -> ~1.2x. When attrs are present, ``add_nodes_from`` (attrs) before
    # ``add_edges_from`` keeps them cheap (0.40x -> ~0.89x; the residual is the
    # construction floor vs nx's native-dict per-element build). Byte-exact 700/700
    # incl attrs, id/children key collisions, custom kwargs, and single-node trees.
    nodes_batch = []
    edges_batch = []
    has_attrs = False

    def collect(parent, children_):
        nonlocal has_attrs
        for child_data in children_:
            child = child_data[ident]
            edges_batch.append((parent, child))
            node_data = {
                str(key): value
                for key, value in child_data.items()
                if key != ident and key != children
            }
            if node_data:
                has_attrs = True
            nodes_batch.append((child, node_data))
            grandchildren = child_data.get(children, [])
            if grandchildren:
                collect(child, grandchildren)

    root = data[ident]
    root_data = {
        str(key): value for key, value in data.items() if key != ident and key != children
    }
    if root_data:
        has_attrs = True
    nodes_batch.insert(0, (root, root_data))
    collect(root, data.get(children, []))

    if has_attrs:
        graph.add_nodes_from(nodes_batch)
        graph.add_edges_from(edges_batch)
    elif edges_batch:
        graph.add_node(root)
        graph.add_edges_from(edges_batch)
    else:
        graph.add_node(root)
    return graph


def complete_to_chordal_graph(G):
    """Return a chordal completion and elimination ordering map.

    Uses MCS-M (maximum cardinality search with minimal fill-in) per Berry,
    Blair, Heggernes, Peyton (2004) to produce a chordal supergraph H and an
    elimination ordering alpha. For inputs that are already chordal, returns
    H equal to G and alpha mapping every node to 0.

    br-r37-c1-i8qr5: nx's _is_complete_graph helper raises
    NetworkXError on self-loop input when is_chordal (called below)
    reaches that branch; mirror that selective raise pattern by
    delegating any self-loop input to nx.
    """
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    H = G.copy()
    # Use the original graph's node order — on franken_networkx, Graph.copy()
    # does not preserve insertion order, which shifts tie-breaking in MCS-M
    # away from NetworkX's expected alpha mapping.
    node_order = list(G.nodes())
    alpha = {node: 0 for node in node_order}
    if is_chordal(H):
        return H, alpha
    chords = set()
    weight = {node: 0 for node in node_order}
    unnumbered_nodes = list(node_order)
    # br-ctcg-localadj: the MCS-M inner test (is there a y->z path through
    # strictly-lower-weight nodes?) was implemented as
    # ``has_path(H.subgraph(lower_nodes + [z, y]).copy(), y, z)``. The
    # ``.copy()`` — added because fnx's native ``has_path`` rejects filtered
    # views — pays the full graph-construction tax O(|V|^2) times, which made
    # this ~77x slower than networkx (49.8s vs 0.64s on
    # watts_strogatz(200, 6)). ``H`` is unchanged during the loop (chords are
    # only applied afterward), so snapshot G's adjacency once into plain
    # Python sets and run the reachability test locally: identical result, no
    # per-iteration graph construction.
    adjacency = {node: set(G[node]) for node in node_order}

    def _reachable_through(src, dst, allowed):
        # BFS from ``src`` to ``dst`` using only edges among ``allowed`` nodes
        # — i.e. ``has_path(G.subgraph(allowed), src, dst)``.
        if src == dst:
            return True
        seen = {src}
        stack = [src]
        while stack:
            node = stack.pop()
            for nbr in adjacency[node]:
                if nbr in allowed and nbr not in seen:
                    if nbr == dst:
                        return True
                    seen.add(nbr)
                    stack.append(nbr)
        return False

    for i in range(len(node_order), 0, -1):
        z = max(unnumbered_nodes, key=lambda node: weight[node])
        unnumbered_nodes.remove(z)
        alpha[z] = i
        update_nodes = []
        for y in unnumbered_nodes:
            if z in adjacency[y]:
                update_nodes.append(y)
            else:
                y_weight = weight[y]
                allowed = {
                    node for node in unnumbered_nodes if weight[node] < y_weight
                }
                allowed.add(z)
                allowed.add(y)
                if _reachable_through(y, z, allowed):
                    update_nodes.append(y)
                    chords.add((z, y))
        for node in update_nodes:
            weight[node] += 1
    H.add_edges_from(chords)
    return H, alpha


# Structural Generators (br-rfd)
def _harary_graph_from_edges(n, edges, create_using=None):
    graph = _empty_graph_from_create_using(create_using, default=Graph)
    graph.add_nodes_from(range(n))

    # br-r37-c1-genbatch (cc): batch through one add_edges_from (LIST) instead of the
    # per-edge add_edge loop — preserve the exact interleaved order (each edge's
    # forward, then its reverse for directed / its duplicate for multigraph) so the
    # result is byte-identical across all create_using types.
    directed = graph.is_directed()
    multigraph = graph.is_multigraph()
    batch = []
    for u, v in edges:
        batch.append((u, v))
        if directed:
            batch.append((v, u))
        elif multigraph:
            batch.append((u, v))
    graph.add_edges_from(batch)
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


def _gomory_hu_prepare_fallback(G, capacity, flow_func):
    from franken_networkx.backend import _fnx_to_nx

    python_graph = _fnx_to_nx(G)
    if flow_func is None:
        flow_func = _nx.algorithms.flow.edmonds_karp
    try:
        residual = _nx.algorithms.flow.build_residual_network(
            python_graph, capacity
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)
    return python_graph, flow_func, residual


def _gomory_hu_cut_fallback(
    python_graph, source, target, capacity, flow_func, residual
):
    try:
        return _nx.algorithms.flow.maxflow.minimum_cut(
            python_graph,
            source,
            target,
            capacity=capacity,
            flow_func=flow_func,
            residual=residual,
            backend="networkx",
        )
    except Exception as exc:
        _raise_translated_networkx_exception(exc)


def gomory_hu_tree(G, capacity="capacity", flow_func=None):
    """Return the Gomory-Hu tree of an undirected graph.

    Tree construction preserves Python node identities and exact cut
    values. Bounded integer capacities use the native Edmonds-Karp probe;
    other numeric domains and custom flow functions share one Python
    residual network across the pairwise cuts.
    """
    _validate_flow_func_selector(flow_func)

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    # br-r37-c1-yj4b3: nx rejects MultiGraph/MultiDiGraph explicitly
    # before any capacity check with NetworkXError. Previously fnx's
    # MultiGraph path fell through to the infinite-capacity check and
    # raised NetworkXUnbounded — wrong error class. Match nx contract.
    if G.is_multigraph():
        raise NetworkXError("MultiGraph and MultiDiGraph not supported (yet).")
    if len(G) == 0:
        raise NetworkXError("Empty Graph does not have a Gomory-Hu tree representation")

    # br-r37-c1-4bkzp: a 1-node graph has no pairs of distinct nodes to
    # cut, so the Gomory-Hu tree is trivially empty (the single node,
    # no edges) regardless of any selfloop's capacity.  Short-circuit
    # *before* the infinite-capacity check so a selfloop without a
    # ``capacity`` attribute does not falsely trigger NetworkXUnbounded
    # (nx returns an empty tree on this same shape).
    if len(G) == 1:
        tree = Graph()
        tree.add_nodes_from(G.nodes(data=True))
        return tree

    # br-r37-c1-ght-disc / br-r37-c1-smmml: nx raises
    # NetworkXUnbounded("Infinite capacity path, flow unbounded
    # above.") whenever some non-selfloop edge carries no capacity
    # (default missing / +inf). fnx's tree-construction loop called
    # the Rust min-cut binding directly, which didn't propagate the
    # unbounded error — producing a meaningless tree.
    #
    # Earlier this gate also short-circuited on ``not is_connected(G)``,
    # which over-fired on graphs where nx returns a valid tree:
    # isolated nodes (no edges → trivially zero-cut tree), a
    # disconnected graph with explicit capacities (cross-component
    # cuts are 0), and graphs whose only edges are selfloops
    # (selfloops do not contribute to any inter-node cut).
    # ``_minimum_cut_raw`` correctly returns 0 with a valid partition
    # for cross-component / selfloop-only pairs, so the loop builds
    # the right tree on its own — the connectivity short-circuit was
    # unnecessary and produced false-positive unbounded errors.  The
    # inf-capacity check excludes selfloops for the same reason.
    if any(
        attrs.get(capacity, float("inf")) in (None, float("inf"), float("nan"))
        for u, v, attrs in G.edges(data=True) if u != v
    ):
        raise NetworkXUnbounded(
            "Infinite capacity path, flow unbounded above."
        )

    native = (
        flow_func is None
        and type(G) is Graph
        and not _has_networkx_private_storage(G)
        and isinstance(capacity, str)
    )
    if native:
        capacity_total = 0
        for u, v, attrs in G.edges(data=True):
            if u == v:
                continue
            value = attrs.get(capacity)
            if type(value) is not int or value < 0:
                native = False
                break
            capacity_total += value
            # The Edmonds-Karp probe uses f64. Undirected reverse residual
            # capacities can double, so keep twice the total exactly integral.
            if capacity_total > (1 << 52):
                native = False
                break
    if native:
        _sync_rust_edge_attrs(G, edge_only=True)
    else:
        python_graph, flow_func, residual = _gomory_hu_prepare_fallback(
            G, capacity, flow_func
        )

    tree = {}
    labels = {}
    iter_nodes = iter(G)
    root = next(iter_nodes)
    for node in iter_nodes:
        tree[node] = root

    for source in tree:
        target = tree[source]
        if native:
            cut_value, partition = _minimum_cut_raw(
                G, source, target, capacity=capacity, edmonds_karp=True
            )
            cut_value = _coerce_flow_value(cut_value, True)
        else:
            cut_value, partition = _gomory_hu_cut_fallback(
                python_graph, source, target, capacity, flow_func, residual
            )
        labels[(source, target)] = cut_value

        for node in partition[0]:
            if node != source and node in tree and tree[node] == target:
                tree[node] = source
                labels[(node, source)] = labels.get((node, target), cut_value)

        if target != root and tree[target] in partition[0]:
            labels[(source, tree[target])] = labels[(target, tree[target])]
            labels[(target, source)] = cut_value
            tree[source] = tree[target]
            tree[target] = source

    result = Graph()
    result.add_nodes_from(G)
    result.add_weighted_edges_from((u, v, labels[(u, v)]) for u, v in tree.items())
    return result


def visibility_graph(series):
    """Visibility graph of a time *series*.

    Parameter renamed from ``sequence`` to ``series`` to match networkx's
    public signature ``visibility_graph(series)``.
    """
    G = Graph()
    n = len(series)
    values = list(series)
    for i, value in enumerate(values):
        G.add_node(i, value=value)
    for i in range(n):
        for j in range(i + 1, n):
            visible = True
            for k in range(i + 1, j):
                if values[k] >= values[i] + (values[j] - values[i]) * (
                    k - i
                ) / (j - i):
                    visible = False
                    break
            if visible:
                G.add_edge(i, j)
    return G


def random_k_out_graph(n, k, alpha, self_loops=True, seed=None):
    """Random graph where each node picks k out-edges."""
    return _random_k_out_graph_impl(
        n,
        k,
        alpha,
        self_loops=self_loops,
        seed=seed,
    )


def _random_k_out_graph_impl(n, k, alpha, self_loops=True, seed=None):
    """Private nx parity helper so the public wrapper stays PY_WRAPPER."""
    # br-r37-c1-koutnative: de-delegate the default (numpy) path. nx's
    # _random_k_out_graph_numpy is @np_random_state-seeded, so
    # ``networkx.utils.create_random_state(seed)`` reproduces its EXACT numpy draw
    # sequence (uniform seed.choice over remaining sources + weighted
    # seed.choice(p=weights/total) preferential targets, with the in-place weight /
    # out-strength / remaining-mask updates). Run the algorithm verbatim to collect
    # edges in nx's exact order and build the fnx MultiDiGraph directly, skipping
    # nx's per-edge add_edge AND the nx->fnx conversion. If numpy is unavailable nx
    # uses its pure-Python variant -> delegate so the draw model still matches.
    if alpha < 0:
        raise ValueError("alpha must be positive")
    try:
        import numpy as _np
        from networkx.utils import create_random_state as _create_random_state
    except ImportError:
        from franken_networkx.readwrite import _from_nx_graph

        nx_result = _nx.random_k_out_graph(
            n, k, alpha, self_loops=self_loops, seed=seed, backend="networkx"
        )
        return _from_nx_graph(nx_result, create_using=MultiDiGraph())

    rng = _create_random_state(seed)
    G = MultiDiGraph()
    G.add_nodes_from(range(n))
    nodes = _np.arange(n)
    remaining_mask = _np.full(n, True)
    weights = _np.full(n, float(alpha))
    total_weight = n * alpha
    out_strengths = _np.zeros(n)
    edges = []
    for _ in range(k * n):
        u = rng.choice(nodes[remaining_mask])
        if self_loops:
            v = rng.choice(nodes, p=weights / total_weight)
        else:
            u_weight = weights[u]
            weights[u] = 0
            v = rng.choice(nodes, p=weights / (total_weight - u_weight))
            weights[u] = u_weight
        edges.append((u.item(), v.item()))
        weights[v] += 1
        total_weight += 1
        out_strengths[u] += 1
        if out_strengths[u] == k:
            remaining_mask[u] = False
    G.add_edges_from(edges)
    return G


# Similarity (br-poy)
def simrank_similarity(
    G,
    source=None,
    target=None,
    importance_factor=0.9,
    max_iterations=1000,
    tolerance=1e-4,
):
    """SimRank similarity between nodes.

    br-simrankvals: the Rust simrank_similarity_rust gave numerically
    different scores than nx even at tight tolerance (1e-9) — diffs of
    ~0.5-8% across karate pairs, persistent across max_iterations and
    tolerance settings, so it's an algorithmic mismatch (likely a
    different iteration structure than nx's matrix formulation) rather
    than a convergence issue. Delegate to nx for exact parity.
    """
    if source is not None and source not in G:
        raise NodeNotFound(f"Source node {source} not in G")
    if target is not None and target not in G:
        raise NodeNotFound(f"Target node {target} not in G")
    return _simrank_impl(
        G,
        source=source,
        target=target,
        importance_factor=importance_factor,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )


def _simrank_impl(G, *, source, target, importance_factor, max_iterations, tolerance):
    """Compute SimRank in-process via nx's exact numpy matrix iteration.

    br-simrank-inproc: previously delegated to nx through a full fnx->nx
    conversion on every call (the native ``simrank_similarity_rust`` kernel
    used a different iteration structure than nx's matrix formulation, so it
    diverged numerically — delegation was the safe default). But nx's
    ``_simrank_similarity_numpy`` is just ``S = max(C * (A.T @ S @ A), I)`` on
    the column-normalized adjacency matrix — pure numpy that we can run on the
    fnx graph directly via the native ``to_numpy_array`` (which is faster than
    nx's and already byte-identical), dropping the per-call graph rebuild.

    Byte-for-byte transcription of nx's algorithm (same matrix, same
    ``np.allclose(atol=tolerance)`` convergence, same ``ExceededMaxIterations``
    contract, same float/dict/dict-of-dicts return shapes), so outputs match the
    delegated path exactly while skipping the conversion. ~1.35x vs the delegated
    path and ~1.8x faster than genuine nx at n=300 (fnx's COO ``to_numpy_array``
    plus no rebuild).
    """
    import numpy as np

    nodelist = list(G)
    s_indx = nodelist.index(source) if source is not None else None
    t_indx = nodelist.index(target) if target is not None else None

    # ``S = max(C * (A.T * S * A), I)`` with A the column-normalized adjacency.
    adjacency_matrix = to_numpy_array(G)
    s = np.array(adjacency_matrix.sum(axis=0))
    s[s == 0] = 1
    adjacency_matrix /= s
    AT = np.ascontiguousarray(adjacency_matrix.T)

    n = len(nodelist)
    newsim = np.eye(n, dtype=np.float64)
    prevsim = np.empty_like(newsim)
    tmp = np.empty_like(newsim)
    its = 0
    for its in range(max_iterations):
        prevsim, newsim = newsim, prevsim
        np.matmul(AT, prevsim, out=tmp)
        np.matmul(tmp, adjacency_matrix, out=newsim)
        newsim *= importance_factor
        np.fill_diagonal(newsim, 1.0)
        if not (np.abs(prevsim - newsim) > (tolerance + 1e-05 * np.abs(newsim))).any():
            break

    if its + 1 == max_iterations:
        # br-r37-c1-s13m9: ExceededMaxIterations is not in this module's
        # namespace — referencing it raised NameError instead of nx's
        # exception. Import the upstream class so callers catching
        # ``nx.ExceededMaxIterations`` work (same pattern as elsewhere).
        from networkx import ExceededMaxIterations

        raise ExceededMaxIterations(
            f"simrank did not converge after {max_iterations} iterations."
        )

    if s_indx is not None and t_indx is not None:
        return float(newsim[s_indx, t_indx])
    if s_indx is not None:
        return dict(zip(nodelist, newsim[s_indx].tolist()))
    return {u: dict(zip(nodelist, row)) for u, row in zip(nodelist, newsim.tolist())}


def _numpy_random_state(seed):
    import numpy as np

    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, np.random.RandomState | np.random.Generator):
        return seed
    if isinstance(seed, int):
        return np.random.RandomState(seed)
    # br-r37-c1-cdf1v: networkx's create_random_state wording.
    raise ValueError(
        f"{seed} cannot be used to create a numpy.random.RandomState or\n"
        "numpy.random.Generator instance"
    )


def _panther_isolates(G):
    return {node for node in G if G.degree[node] == 0}


def _panther_induced_ordered_copy(G, nodes):
    node_set = set(nodes)
    # br-r37-c1-s8w2p: SubgraphView class can't be empty-constructed.
    graph = _concrete_class_for(G)()
    graph.graph.update(dict(G.graph))
    graph.add_nodes_from((node, dict(G.nodes[node])) for node in G if node in node_set)
    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            if u in node_set and v in node_set:
                graph.add_edges_from([(u, v, key, dict(attrs))])
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
    t_choose_2 = _math.comb(path_length, 2)
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
    roots=None,
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
    best_cost = _math.inf
    best_mappings = []
    initial_mapping = {}

    if roots is not None:
        root_left, root_right = roots
        if root_left not in G1 or root_right not in G2:
            raise NodeNotFound("Root node not in graph.")
        initial_mapping[root_left] = root_right
        left_nodes = [node for node in left_nodes if node != root_left]
        right_nodes = [node for node in right_nodes if node != root_right]

    def evaluate(mapping):
        matched_right_nodes = set(mapping.values())
        # br-r37-c1-ged-flt: nx's graph_edit_distance always returns
        # ``float`` (the recursive minimization in nx uses ``min`` over
        # float costs so int-zero never bubbles up).  fnx's local
        # accumulator started at int 0 and stayed int when all costs
        # were zero (identical graphs with ``roots=`` set).  Initialize
        # at ``0.0`` so the type matches nx.
        cost = 0.0
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
                subst_cost = _graph_edit_edge_subst_cost(
                    G1,
                    G2,
                    left_edge,
                    right_edge,
                    edge_match,
                    edge_subst_cost,
                )
                edit_as_delete_insert = _graph_edit_edge_del_cost(
                    G1,
                    left_edge,
                    edge_del_cost,
                ) + _graph_edit_edge_ins_cost(G2, right_edge, edge_ins_cost)
                cost += min(subst_cost, edit_as_delete_insert)
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

    search(0, tuple(right_nodes), dict(initial_mapping))
    if not best_mappings:
        return [], None
    return [
        _graph_edit_distance_paths_from_mapping(
            G1,
            G2,
            mapping,
            normalize_undirected_right_edges=roots is not None,
        )
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
    # br-r37-c1-jwdzp: accept nx-typed inputs.
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


def optimize_edit_paths(
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
    strictly_decreasing=True,
    roots=None,
    timeout=None,
):
    """_Iterator yielding final edit paths from the local optimal-path
    wrapper.

    Matches networkx's full positional + keyword surface so
    ``inspect.signature`` introspection is identical (br-r37-c1-gedsig).
    The native exact-paths search runs the full solver; ``timeout``
    requires the iterative algorithm and is delegated to networkx.
    """
    if timeout is not None:
        # Same policy as graph_edit_distance: surface NotImplemented
        # rather than fall back to nx (locked in
        # test_graph_edit_directed_mismatch_and_unsupported_modes_do_not_fallback).
        raise NetworkXNotImplemented(
            "timeout is not supported by local optimize_edit_paths",
        )
    if roots is None:
        paths, cost = optimal_edit_paths(
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
    else:
        paths, cost = _graph_edit_exact_paths_python(
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
    if cost is None:
        return
    if strictly_decreasing:
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
            nb_list = list(nbunch)
        except TypeError as exc:
            message = exc.args[0] if exc.args else ""
            if "object is not iterable" in message:
                raise NetworkXError(f"Node {nbunch} is not in the graph.") from exc
            raise NetworkXError("nbunch is not a node or a sequence of nodes.") from exc
        # br-r37-c1-50w8n: the per-node membership test dominated subgraph
        # construction — fnx's ``node in G`` is a Python ``__contains__`` (via
        # _private_override + vars(), ~0.8us each), vs nx's C-dict lookup, so a
        # V/2-node nbunch was 5-6x slower than nx. Build ``set(G)`` ONCE and test
        # membership at C speed, but only when nbunch is large enough to amortize
        # the O(V) build (>= ~V/4 nodes); a tiny nbunch on a large graph keeps
        # the per-node path (no whole-graph over-build). ~2.4-2.7x faster.
        # br-r37-c1-w4754: nx's ``nbunch_iter`` filters a SEQUENCE nbunch against
        # ``self._adj``, while the single-node form above tests ``nbunch in self``
        # (``_node``) — an asymmetry mirrored here deliberately. The two mappings can
        # only disagree when NetworkX private storage is assigned to one of them, so
        # an ordinary graph keeps the ``set(G)`` fast path above untouched; a
        # private-storage graph switches to the adjacency mapping, which excludes an
        # assigned ``_node`` key that has no adjacency row exactly as nx excludes it.
        private = _has_networkx_private_storage(G)
        container = G.adj if private else G
        if type(G) in _CONCRETE_FNX_GRAPH_TYPES and not private and (
            len(nb_list) * 4 >= len(G)
            or vars(G).get("_fnx_native_node_key_set_state") == G.nodes_seq
        ):
            # br-r37-c1-5c2qc: the node set this filters against was rebuilt,
            # set(G), on every subgraph() - 11.5 us of a 36 us
            # DiGraph.subgraph(333 of 1000), which networkx makes in 18 us. The
            # graph's cached node-key set (the one non_neighbors reads) is the
            # same set, rebuilt only when nodes_seq moves; a small nbunch on a
            # large graph still takes the per-node path unless the set is
            # already built.
            gnodes = _cached_native_node_key_set(G, G._native_node_keys)
        else:
            gnodes = set(container) if len(nb_list) * 4 >= len(G) else None
        if gnodes is not None:
            # br-r37-c1-yioox: the per-node loop hashed every node THREE times
            # — an explicit hash() for the error contract, again for the
            # membership test, and again for the add. The comprehension does
            # two, dropping the Python-level hash() CALL, which was the
            # expensive one.
            #
            # NOT an intersection, though it looks like one: `set(nb_list) &
            # gnodes` builds the set in an order determined by the operands, so
            # the induced subgraph's NODE ITERATION ORDER stopped matching
            # networkx's — seed-dependently, since string hashing is randomised
            # per process. It passed on 2 of 5 PYTHONHASHSEED values and failed
            # on 3. The comprehension adds in nbunch order exactly as the old
            # loop did, so insertion order is preserved.
            #
            # The unhashable check rides on the set membership here, which DOES
            # raise TypeError — unlike `n in G`, whose __contains__ answers
            # False for an unhashable argument exactly as networkx's does. The
            # offender is located only on the error path, where cost is
            # irrelevant.
            try:
                allowed_nodes = {node for node in nb_list if node in gnodes}
            except TypeError as exc:
                for node in nb_list:
                    try:
                        _HASH_PROBE.get(node)
                    except TypeError:
                        raise NetworkXError(
                            f"Node {node} in sequence nbunch is not a valid node."
                        ) from exc
                raise
            else:
                # br-r37-c1-c99d9: `gnodes` is a SET, and a set is the ONE
                # unhashable shape a set cannot see. CPython converts a `set`
                # (and a set SUBCLASS) to a `frozenset` for `x in aset`, so
                # `set() in gnodes` answers False instead of raising — the
                # `except TypeError` above never fires, the node is silently
                # DROPPED, and `G.subgraph([set()])` returned an empty subgraph
                # where networkx raises. Every other unhashable shape — list,
                # dict, bytearray — does raise there and is already handled.
                #
                # NOT FIXED BY MAKING `gnodes` A DICT, which is the obvious
                # move and was measured: `dict.fromkeys(G)` costs 1.72x
                # `set(G)` to build and 1.09x to filter through, 35 percent on
                # the whole branch — and this branch exists precisely because
                # it is the fast one (br-r37-c1-50w8n, ~2.4-2.7x).
                #
                # A set can NEVER be a node, so it is always among the dropped;
                # the walk therefore runs only when something was dropped, and
                # each step is a C type check rather than the `_HASH_PROBE.get`
                # CALL the sibling branch below makes. Duplicates shorten the
                # set too and pay one cheap pass that finds nothing, exactly as
                # they do there.
                if len(allowed_nodes) != len(nb_list):
                    for node in nb_list:
                        if isinstance(node, set):
                            raise NetworkXError(
                                f"Node {node} in sequence nbunch is not a valid node."
                            )
        else:
            # Small nbunch on a large graph: no whole-graph set was built, so
            # membership stays per-node and the explicit hash stays with it.
            # br-r37-c1-subhash: the explicit hash runs only on a MISS. A node
            # the membership test FOUND was located by its hash, so hashing it
            # again to prove it is hashable is work whose answer the lookup
            # already gave -- and this branch is the common one for a subgraph,
            # since it is taken whenever the nbunch is small relative to the
            # graph. Measured: the per-node walk is 66ns a node at k=64, of
            # which the hash CALL is about 19ns, so roughly 29% of this loop.
            #
            # Equivalent on all three inputs, which is the whole argument:
            #   hashable + present -> found, added; the old hash could not have
            #     raised for a node the lookup just located by hash.
            #   hashable + absent  -> not found, hash succeeds, not added.
            #   UNHASHABLE         -> `node in container` answers False WITHOUT
            #     raising (fnx's __contains__ matches networkx's here), so the
            #     miss path is reached and the hash raises exactly as before.
            # The third case is why the hash cannot simply be deleted, and it is
            # covered by a probe on both container kinds -- the node view and,
            # under assigned private storage, `G.adj`.
            # br-r37-c1-subcomp: the membership walk is a set COMPREHENSION,
            # so the accumulate happens in C instead of through a bound
            # `set.add` per node. Measured on a 64-node nbunch: 3.733us for the
            # loop against 3.020us for the comprehension.
            #
            # The unhashable contract still holds, and the verification pass is
            # only reached when something was actually dropped. `node in
            # container` answers False for an unhashable node WITHOUT raising,
            # so a drop is the only signal that one may have been present -
            # and a drop is equally what an absent-but-hashable node produces,
            # which is why the pass re-hashes rather than assuming.
            #
            # DUPLICATES also shorten the set, so `[1, 1, 2]` takes the pass
            # too. That costs one extra O(k) walk on a duplicated nbunch and
            # keeps the answer right; it never changes one.
            allowed_nodes = {node for node in nb_list if node in container}
            if len(allowed_nodes) != len(nb_list):
                for node in nb_list:
                    try:
                        _HASH_PROBE.get(node)
                    except TypeError as exc:
                        raise NetworkXError(
                            f"Node {node} in sequence nbunch is not a valid node."
                        ) from exc

    return _NodeSetFilter(allowed_nodes, copy_nodes=False)


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

    filter_edge._fnx_edge_subgraph_selected_edges = edges

    return subgraph_view(
        G,
        # NetworkX passes this set through ``show_nodes``, which constructs a
        # second set.  Its CPython table layout is observable when the filtered
        # view uses the sparse-node iteration shortcut, and in turn determines
        # directed edge emission order.
        filter_node=_NodeSetFilter(nodes),
        filter_edge=filter_edge,
    )


def subgraph_view(G, *, filter_node=_subgraph_view_no_filter_default, filter_edge=_subgraph_view_no_filter_default):
    """Filtered live view of graph.

    br-r37-c1-svfilter: nx's signature uses ``no_filter`` (a callable
    that always returns True) as the default for both ``filter_node``
    and ``filter_edge``.  fnx had used ``None`` as the default, so
    ``inspect.signature(fnx.subgraph_view)`` reported
    ``filter_node=None`` instead of ``filter_node=<no_filter>`` —
    breaking signature-parity-introspecting code.  Match nx's default
    callable.  Behavior unchanged: ``_generic_filtered_graph_view``
    treats ``no_filter`` (which always returns True) and ``None``
    (interpreted as no filter) identically.
    """
    return _generic_filtered_graph_view(
        G,
        filter_node=filter_node,
        filter_edge=filter_edge,
    )


def restricted_view(G, nodes, edges):
    """View with specified nodes and edges removed.

    Parameter names match networkx's public signature
    ``restricted_view(G, nodes, edges)`` — earlier fnx used
    ``nodes_to_remove``/``edges_to_remove`` which broke keyword calls.
    """
    nodes_to_remove = nodes
    edges_to_remove = edges
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
    """View with reversed edges.

    br-r37-c1-n7rgh: nx is @not_implemented_for('undirected'); the
    underlying reverse() raises NetworkXError for undirected
    inputs, but nx raises NetworkXNotImplemented before reaching
    that code.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return reverse(G, copy=False)


def non_neighbors(graph, node):
    """Returns the non-neighbors of the node in the graph."""
    _HASH_PROBE.get(node)
    # br-r37-c1-n4j4k: networkx returns G._adj.keys() - G._adj[node].keys() -
    # {node}. On dict rows that is a set of the node dict (its table sized once
    # for every node), the row discarded from it, then a set difference that
    # copies what is left into a table of its own size - a result that iterates
    # in networkx's order only when those operations run, as here, on a set laid
    # out as set(node dict) is.
    if type(graph) is DiGraph and not _has_networkx_private_storage(graph):
        nodes = _cached_native_node_key_set(graph, graph._native_node_keys).copy()
        nodes.difference_update(graph._native_successor_row_dict(node))
        return nodes - {node}
    if type(graph) is Graph and not _has_networkx_private_storage(graph):
        nodes = _cached_native_node_key_set(graph, graph._native_node_keys).copy()
        nodes.difference_update(graph._native_adjacency_row_dict(node))
        return nodes - {node}
    if node not in graph:
        raise KeyError(node)
    # br-r37-c1-qkq2h: bypass AdjacencyView/AtlasView via raw Rust
    # neighbors binding when the graph has no nx-private storage and
    # isn't a multigraph. Profiling on BA200 showed the AdjacencyView
    # path was 6-10x slower than nx's direct dict access; same
    # wrapper-bypass family as find_cliques (lgyq8), square_clustering
    # (7t95c), dominating_set (02djy).
    _raw_nbrs = _raw_neighbors_dispatch(graph)
    if _raw_nbrs is not None:
        row = _raw_nbrs(graph, node)
    elif type(graph) in _CONCRETE_FNX_GRAPH_TYPES:
        # multigraph: G[node] is the native O(deg) adjacency row;
        # G.adj[node] would re-materialise the whole AdjacencyView
        # (~900x slower on a 2k-node MultiGraph).
        row = graph[node]
    else:
        row = graph.adj[node]
    if not _nx_rows_are_dicts(graph):
        # A filtered or undirected view's rows are coreview Mappings, whose
        # KeysView difference grows its set one add at a time.
        row = set(row)
        return {w for w in graph if w not in row} - {node}
    # br-r37-c1-nodekeys: enumerate ALL node display objects in ONE native call
    # instead of crossing PyO3 per node.
    native_keys = getattr(graph, "_native_node_keys", None)
    if native_keys is not None and type(graph) in _CONCRETE_FNX_GRAPH_TYPES:
        nodes = dict.fromkeys(native_keys())
    else:
        nodes = dict.fromkeys(graph)
    return nodes.keys() - row - {node}


_NON_EDGES_ROW_CACHE_MIN_NODES = 128
_NON_EDGES_ROW_CACHE_MAX_PAIRS = 1_000_000


def _non_edges_undirected_row_cached(graph):
    if len(graph) < _NON_EDGES_ROW_CACHE_MIN_NODES:
        nodes = set(graph)
        while nodes:
            u = nodes.pop()
            for v in nodes - set(graph[u]):
                yield (u, v)
        return

    token = (graph.nodes_seq, graph.edges_seq)
    graph_vars = vars(graph)
    cached = graph_vars.get("_fnx_non_edges_row_cache")
    if cached is not None and cached[0] == token:
        pop_order, row_values = cached[1], cached[2]
        for index, u in enumerate(pop_order):
            if (graph.nodes_seq, graph.edges_seq) == token:
                for v in row_values[index]:
                    yield (u, v)
                continue

            remaining = set(pop_order[index + 1 :])
            for v in remaining - set(graph[u]):
                yield (u, v)
            for u in pop_order[index + 1 :]:
                remaining.remove(u)
                for v in remaining - set(graph[u]):
                    yield (u, v)
            return
        return

    nodes = set(graph)
    token = (graph.nodes_seq, graph.edges_seq)
    cacheable = True
    pair_count = 0
    pop_order = []
    row_values = []
    while nodes:
        u = nodes.pop()
        row = nodes - set(graph[u])
        if cacheable:
            row_tuple = tuple(row)
            pair_count += len(row_tuple)
            if pair_count <= _NON_EDGES_ROW_CACHE_MAX_PAIRS:
                pop_order.append(u)
                row_values.append(row_tuple)
                for v in row_tuple:
                    yield (u, v)
            else:
                cacheable = False
                pop_order = None
                row_values = None
                for v in row_tuple:
                    yield (u, v)
        else:
            for v in row:
                yield (u, v)

    if cacheable and (graph.nodes_seq, graph.edges_seq) == token:
        graph_vars["_fnx_non_edges_row_cache"] = (token, tuple(pop_order), tuple(row_values))


def non_edges(graph):
    """Returns the nonexistent edges in the graph."""
    if graph.is_directed():
        native_keys = getattr(graph, "_native_node_keys", None)
        if native_keys is not None:
            nodes = set(native_keys())
            _raw_nbrs = _raw_neighbors_dispatch(graph)
            if _raw_nbrs is not None:
                for u in graph:
                    for v in nodes - set(_raw_nbrs(graph, u)) - {u}:
                        yield (u, v)
                return
            for u in graph:
                for v in nodes - set(graph[u]) - {u}:
                    yield (u, v)
            return
        for u in graph:
            for v in non_neighbors(graph, u):
                yield (u, v)
        return

    if (
        type(graph) is Graph
        and not _has_networkx_private_storage(graph)
        and hasattr(graph, "nodes_seq")
        and hasattr(graph, "edges_seq")
    ):
        yield from _non_edges_undirected_row_cached(graph)
        return

    nodes = set(graph)
    while nodes:
        u = nodes.pop()
        for v in nodes - set(graph[u]):
            yield (u, v)
