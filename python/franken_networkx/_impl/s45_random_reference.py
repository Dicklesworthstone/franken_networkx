

def random_reference(G, niter=1, connectivity=True, seed=None):
    """Random reference graph preserving degree sequence (Maslov-Sneppen)."""
    rng = _create_py_random_state(seed)
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if G.number_of_edges() < 2:
        raise NetworkXError("Graph has fewer that 2 edges")
    return _random_reference_inproc(
        G, niter=niter, connectivity=connectivity, seed=rng,
    )


def random_labeled_rooted_tree(n, *, seed=None):
    """A random labeled tree with a root drawn after it, as networkx.

    br-r37-c1-rut-zero: nx raises NetworkXPointlessConcept on n=0.
    br-r37-c1-cdf1v: networkx draws the tree and then
    ``t.graph["root"] = seed.randint(0, n - 1)`` from the same RNG; fnx set no
    root at all.
    """
    rng = _generator_random_state(seed)  # resolved first, as nx's decorator
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")
    tree = _random_tree_internal(n, seed=rng)
    tree.graph["root"] = rng.randint(0, n - 1)
    return tree


def random_labeled_rooted_forest(n, *, seed=None):
    """Random labeled rooted forest with *n* nodes.

    Matches networkx's public signature ``(n, *, seed=None)``. The
    earlier fnx signature carried a stray ``q`` arg leaked from
    ``random_unlabeled_rooted_forest``; nx has no such parameter
    (br-r37-c1-rrf-tut).

    br-r37-c1-cdf1v: networkx's algorithm, verbatim - pick the number of roots
    k by the cumulative count of labeled rooted forests, sample the roots, then
    decode a Prüfer-like sequence over the non-roots. fnx returned
    random_unlabeled_rooted_forest's answer, a different distribution (a
    path for small n) with other roots.
    """
    rng = _generator_random_state(seed)

    def _select_k(n, seed):
        r = seed.randint(0, (n + 1) ** (n - 1) - 1)
        cum_sum = 0
        for k in range(1, n):
            cum_sum += (_math.factorial(n - 1) * n ** (n - k)) // (
                _math.factorial(k - 1) * _math.factorial(n - k)
            )
            if r < cum_sum:
                return k
        return n

    F = empty_graph(n)
    if n == 0:
        F.graph["roots"] = {}
        return F
    k = _select_k(n, rng)
    if k == n:
        F.graph["roots"] = set(range(n))
        return F
    roots = rng.sample(range(n), k)
    p = set(range(n)).difference(roots)
    N = [rng.randint(0, n - 1) for i in range(n - k - 1)]
    degree = _Counter([x for x in N if x in p])
    iterator = iter(x for x in p if degree[x] == 0)
    u = last = next(iterator)
    for v in N:
        F.add_edge(u, v)
        degree[v] -= 1
        if v < last and degree[v] == 0:
            u = v
        else:
            last = u = next(iterator)
    F.add_edge(u, roots[0])
    F.graph["roots"] = set(roots)
    return F


def partial_duplication_graph(
    N,
    n,
    p,
    q,
    seed=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Partial duplication graph (Chung–Lu).

    Matches networkx's public signature
    ``partial_duplication_graph(N, n, p, q, seed=None, *, create_using=None)``.

    Starts from a clique of *n* vertices and grows to *N* vertices.
    ``p`` is the probability of retaining an edge from the duplicated
    vertex's neighbour to the new vertex; ``q`` is the probability of
    adding a new edge from the new vertex to a random non-neighbour.
    """
    return _partial_duplication_graph_impl(
        N,
        n,
        p,
        q,
        seed=seed,
        create_using=create_using,
        backend=backend,
        **backend_kwargs,
    )


def _partial_duplication_graph_impl(
    N,
    n,
    p,
    q,
    seed=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Private nx parity helper so the public wrapper stays PY_WRAPPER."""
    _validate_backend_dispatch_keywords(
        "partial_duplication_graph", backend, backend_kwargs
    )
    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    if p < 0 or p > 1 or q < 0 or q > 1:
        raise NetworkXError(
            "partial duplication graph must have 0 <= p, q <= 1."
        )
    if n > N:
        raise NetworkXError("partial duplication graph must have n <= N.")
    return _partial_duplication_native(N, n, p, q, rng, result=graph)


def _partial_duplication_native(N, n, p, q, seed, result=None):
    """br-r37-c1-pdupnative: see _partial_duplication_graph_impl. Reproduces nx's
    partial_duplication_graph byte-for-byte."""
    import itertools as _it

    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: nx's py_random_state
    # dict-of-lists adjacency in insertion order == nx's per-node adj order, so
    # ``list(adj[src])`` matches nx's ``all_neighbors(G, src)`` at each step.
    adj = {i: [] for i in range(n)}
    edges = []
    for u, v in _it.combinations(range(n), 2):  # complete_graph(n) edge order
        adj[u].append(v)
        adj[v].append(u)
        edges.append((u, v))
    for new_node in range(n, N):
        src = rng.randint(0, new_node - 1)
        adj[new_node] = []
        for nbr in list(adj[src]):
            if rng.random() < p and nbr not in adj[new_node]:
                adj[new_node].append(nbr)
                adj[nbr].append(new_node)
                edges.append((new_node, nbr))
        if rng.random() < q:
            adj[new_node].append(src)
            adj[src].append(new_node)
            edges.append((new_node, src))
    if result is None:
        result = Graph()
    result.add_nodes_from(range(N))
    result.add_edges_from(edges)
    return result


def duplication_divergence_graph(
    n,
    p,
    seed=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Duplication-divergence graph.

    ``create_using`` is accepted for networkx signature parity; networkx
    treats it as a hint about the returned graph class. Internally this
    runs the classic duplication-with-divergence random walk (the
    simpler single-p variant), not the full Chung–Lu partial duplication
    (N, n, p, q) model exposed via :func:`partial_duplication_graph`.
    """
    return _duplication_divergence_graph_impl(
        n,
        p,
        seed=seed,
        create_using=create_using,
        backend=backend,
        **backend_kwargs,
    )


def _duplication_divergence_graph_impl(
    n,
    p,
    seed=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Private nx parity helper so the public wrapper stays PY_WRAPPER."""
    _validate_backend_dispatch_keywords(
        "duplication_divergence_graph", backend, backend_kwargs
    )
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first

    if p > 1 or p < 0:
        raise NetworkXError(f"NetworkXError p={p} is not in [0,1].")
    if n < 2:
        raise NetworkXError("n must be greater than or equal to 2")

    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    rng = _generator_random_state(seed)

    nodes = [0, 1]
    adjacency = [[1], [0]]
    edges = [(0, 1)]
    next_node = 2
    while next_node < n:
        random_node = rng.choice(nodes)
        retained_edges = []
        for neighbor in adjacency[random_node]:
            if rng.random() < p:
                retained_edges.append((next_node, neighbor))
        if retained_edges:
            adjacency.append([neighbor for _, neighbor in retained_edges])
            for _, neighbor in retained_edges:
                adjacency[neighbor].append(next_node)
            nodes.append(next_node)
            edges.extend(retained_edges)
            next_node += 1
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def interval_graph(intervals):
    """Interval graph: nodes are the interval tuples themselves.

    br-ivgnode: nx.interval_graph uses the input interval (a, b) tuples
    as the node labels. fnx previously indexed nodes by 0..n-1, so
    ``G.nodes[(1, 3)]`` worked on nx but raised KeyError on fnx and
    edge iteration yielded integer pairs instead of tuple pairs —
    silently breaking any caller that relied on the interval-as-label
    convention. Validate + store interval tuples as nodes.
    """
    intervals = list(intervals)
    # Validate — nx raises TypeError for non-iterable length-2 interval
    # (it reshapes via tuple() then checks length).
    tuples = []
    seen = set()
    for iv in intervals:
        iv_t = tuple(iv)
        if len(iv_t) != 2:
            raise TypeError("Each interval must have length 2")
        if iv_t[0] > iv_t[1]:
            raise ValueError(f"Interval must have lower bound first: {iv_t}")
        tuples.append(iv_t)
    G = Graph()
    G.add_nodes_from(tuples)
    n = len(tuples)
    # br-interval-batch: the overlap scan never reads the graph, so the
    # overlapping pairs accumulate in the exact (i<j) order and commit through
    # a single add_edges_from instead of an O(m) per-edge PyO3 add_edge loop.
    # Node order (add_nodes_from) and edge order are unchanged => byte-identical.
    edges = []
    for i in range(n):
        a1, b1 = tuples[i]
        ti = tuples[i]
        for j in range(i + 1, n):
            a2, b2 = tuples[j]
            if a1 <= b2 and a2 <= b1:
                edges.append((ti, tuples[j]))
    G.add_edges_from(edges)
    return G


def _intersection_projection_edges(drawn, holders):
    """Edges of networkx's ``projected_graph(B, range(n))``, in its order.

    ``drawn[u]`` lists node u's attributes in the order B gained them and
    ``holders[a]`` attribute a's nodes ascending - B's adjacency order.
    br-r37-c1-cdf1v: projected_graph adds, node by node, the SET of nodes
    sharing an attribute, so replaying that set gives networkx's G.edges()
    order (the attribute->holders cliques of kriproj / uriproj / griproj gave
    the same edge set in another order). It re-adds each edge from its larger
    endpoint, which moves nothing, so only v > u is kept, for one batch.
    """
    edges = []
    for u, attrs in enumerate(drawn):
        nbrs2 = {v for a in attrs for v in holders[a] if v != u}
        edges.extend((u, v) for v in nbrs2 if v > u)
    return edges


def k_random_intersection_graph(n, m, k, seed=None):
    """Random intersection graph: each node picks k of m attributes."""
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: nx's py_random_state
    G = Graph()
    G.add_nodes_from(range(n))
    # br-r37-c1-cdf1v: networkx draws seed.sample(range(n, n + m), k) per node
    # (k > m raises) and projects; the attribute->holders map keeps the
    # projection O(sum of degrees) rather than the all-pairs scan
    # (br-r37-c1-kriproj).
    drawn = []
    holders = {}
    for v in range(n):
        targets = rng.sample(range(n, n + m), k)
        drawn.append(targets)
        for a in targets:
            holders.setdefault(a, []).append(v)
    G.add_edges_from(_intersection_projection_edges(drawn, holders))
    return G


def uniform_random_intersection_graph(
    n,
    m,
    p,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Uniform random intersection graph."""
    return _uniform_random_intersection_graph_impl(
        n,
        m,
        p,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def _uniform_random_intersection_graph_impl(
    n,
    m,
    p,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Private nx parity helper so the public wrapper stays PY_WRAPPER."""
    _validate_backend_dispatch_keywords(
        "uniform_random_intersection_graph", backend, backend_kwargs
    )

    # br-r37-c1-uriproj: native byte-exact generation. Reproduces nx's
    # bipartite.random_graph geometric-skip edge sampling (w += 1 +
    # int(log(1-rand)/log(1-p)) over the row-major (node, attribute)
    # enumeration) to assign attributes, then replays nx.projected_graph through
    # _intersection_projection_edges. Nodes 0..n-1 carry bipartite=0 (as nx's
    # projected_graph copies from the bipartite graph). Skips nx's per-edge
    # add_edge, projected_graph, AND the nx->fnx conversion (~2x slower ->
    # ~0.5x). br-r37-c1-cdf1v: every seed kind - _generator_random_state is
    # nx's py_random_state, so a random.Random / numpy seed draws the same
    # stream here as in networkx and no longer delegates.
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: nx's py_random_state
    if p <= 0:
        G = Graph()
        G.add_nodes_from((v, {"bipartite": 0}) for v in range(n))
        G.graph["name"] = f"fast_gnp_random_graph({n},{m},{p})"
        return G
    if p >= 1:
        if n < 0 or m < 0:
            raise NetworkXError("Must have n >= 0 and m >= 0")
        G = Graph()
        G.add_nodes_from((v, {"bipartite": 0}) for v in range(n))
        if m > 0:
            drawn = [list(range(m)) for _ in range(n)]
            holders = {w: list(range(n)) for w in range(m)}
            G.add_edges_from(_intersection_projection_edges(drawn, holders))
        return G

    import math as _m

    G = Graph()
    G.add_nodes_from((v, {"bipartite": 0}) for v in range(n))
    # nx's bipartite.random_graph sets this name; projected_graph carries it.
    G.graph["name"] = f"fast_gnp_random_graph({n},{m},{p})"
    lp = _m.log(1.0 - p)
    drawn = [[] for _ in range(n)]
    holders = {}
    v = 0
    w = -1
    while v < n:
        w = w + 1 + int(_m.log(1.0 - rng.random()) / lp)
        while w >= m and v < n:
            w -= m
            v += 1
        if v < n:
            drawn[v].append(w)
            holders.setdefault(w, []).append(v)
    G.add_edges_from(_intersection_projection_edges(drawn, holders))
    return G


def general_random_intersection_graph(
    n,
    m,
    p,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """General random intersection graph."""
    return _general_random_intersection_graph_impl(
        n,
        m,
        p,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def _general_random_intersection_graph_impl(
    n,
    m,
    p,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Private nx parity helper so the public wrapper stays PY_WRAPPER."""
    _validate_backend_dispatch_keywords(
        "general_random_intersection_graph", backend, backend_kwargs
    )

    # br-r37-c1-griproj: native byte-exact generation — reproduces nx's
    # per-node, per-attribute Bernoulli draws (rng.random() < p[attr] over the
    # same node-major iteration) to assign attributes, then replays
    # nx.projected_graph through _intersection_projection_edges.
    # empty_graph(n+m) carries no node/graph attrs, so the projected nodes
    # (range(n)) have none either. Skips nx's per-edge add_edge +
    # projected_graph + the nx->fnx conversion. Validation message matches nx
    # exactly. br-r37-c1-cdf1v: every seed kind, and the seed is resolved
    # first, as nx's decorator does, so a bad seed raises before a bad p.
    rng = _generator_random_state(seed)
    if len(p) != m:
        raise ValueError("Probability list p must have m elements.")
    G = Graph()
    G.add_nodes_from(range(n))
    drawn = [[] for _ in range(n)]
    holders = {}
    for u in range(n):
        for attr_idx in range(m):
            if rng.random() < p[attr_idx]:
                drawn[u].append(attr_idx)
                holders.setdefault(attr_idx, []).append(u)
    G.add_edges_from(_intersection_projection_edges(drawn, holders))
    return G


def geometric_soft_configuration_graph(
    *,
    beta,
    n=None,
    gamma=None,
    mean_degree=None,
    kappas=None,
    seed=None,
):
    """Random graph from the geometric soft configuration model
    (the S^1 / hyperbolic H^2 model of Krioukov et al.).

    Matches networkx's public signature exactly: ``beta`` is required
    (keyword-only), and ``n`` / ``gamma`` / ``mean_degree`` / ``kappas``
    drive the hidden-degree distribution. The previous fnx stub
    silently re-routed to ``random_geometric_graph(n, 0.3)`` — a
    completely different model — so any caller relying on the
    documented contract got wrong results. Delegate to networkx so
    the well-tested upstream algorithm is used end-to-end
    (br-r37-c1-gsc-stub).
    """
    return _geometric_soft_configuration_graph_via_nx(
        beta, n, gamma, mean_degree, kappas, seed,
    )


def _geometric_soft_configuration_graph_via_nx(beta, n, gamma, mean_degree, kappas, seed):
    """In-process S^1 / H^2 geometric soft configuration model."""
    rng = _generator_random_state(seed)
    if beta <= 0:
        raise NetworkXError("The parameter beta cannot be smaller or equal to 0.")

    if kappas is not None:
        if not all((n is None, gamma is None, mean_degree is None)):
            raise NetworkXError(
                "When kappas is input, n, gamma and mean_degree must not be."
            )
        n = len(kappas)
        mean_degree = sum(kappas) / len(kappas)
    else:
        if any((n is None, gamma is None, mean_degree is None)):
            raise NetworkXError(
                "Please provide either kappas, or all 3 of: n, gamma and mean_degree."
            )
        gam_ratio = (gamma - 2) / (gamma - 1)
        kappa_0 = mean_degree * gam_ratio * (1 - 1 / n) / (1 - 1 / n**gam_ratio)
        base = 1 - 1 / n
        power = 1 / (1 - gamma)
        kappas = {i: kappa_0 * (1 - rng.random() * base) ** power for i in range(n)}

    G = Graph()
    R = n / (2 * _math.pi)

    if beta > 1:
        mu = beta * _math.sin(_math.pi / beta) / (2 * _math.pi * mean_degree)
    elif beta == 1:
        mu = 1 / (2 * mean_degree * _math.log(n))
    else:
        mu = (1 - beta) / (2**beta * mean_degree * n ** (1 - beta))

    thetas = {k: rng.uniform(0, 2 * _math.pi) for k in kappas}

    for u in kappas:
        for v in list(G):
            angle = _math.pi - _math.fabs(_math.pi - _math.fabs(thetas[u] - thetas[v]))
            dij = _math.pow(R * angle, beta)
            mu_kappas = _math.pow(mu * kappas[u] * kappas[v], max(1, beta))
            p_ij = 1 / (1 + dij / mu_kappas)
            if rng.random() < p_ij:
                G.add_edge(u, v)
        G.add_node(u)

    set_node_attributes(G, thetas, "theta")
    set_node_attributes(G, kappas, "kappa")

    zeta = 1 if beta > 1 else 1 / beta
    kappa_min = min(kappas.values())
    R_c = 2 * max(1, beta) / (beta * zeta)
    R_hat = (2 / zeta) * _math.log(n / _math.pi) - R_c * _math.log(mu * kappa_min)
    radii = {node: R_hat - R_c * _math.log(kappa) for node, kappa in kappas.items()}
    set_node_attributes(G, radii, "radius")
    return G


_GRAPH_ATLAS_NUM_GRAPHS = 1253
_GRAPH_ATLAS_DATA_GZ = (
    "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"
)
_GRAPH_ATLAS_RECORDS = None


def _graph_atlas_records():
    """Return cached graph-atlas records parsed from the local upstream data."""
    global _GRAPH_ATLAS_RECORDS
    if _GRAPH_ATLAS_RECORDS is not None:
        return _GRAPH_ATLAS_RECORDS

    lines = _gzip.decompress(_base64.b64decode(_GRAPH_ATLAS_DATA_GZ)).decode().splitlines()
    records = []
    index = 0
    while index < len(lines):
        graph_line = lines[index]
        if not graph_line.startswith("GRAPH "):
            raise NetworkXError("invalid graph atlas data")
        graph_index = int(graph_line.split()[1])
        index += 1

        if index >= len(lines) or not lines[index].startswith("NODES "):
            raise NetworkXError("invalid graph atlas data")
        node_count = int(lines[index].split()[1])
        index += 1

        edges = []
        while index < len(lines) and not lines[index].startswith("GRAPH "):
            edge_line = lines[index].strip()
            if edge_line:
                u, v = edge_line.split()
                edges.append((int(u), int(v)))
            index += 1
        records.append((graph_index, node_count, tuple(edges)))

    if len(records) != _GRAPH_ATLAS_NUM_GRAPHS:
        raise NetworkXError("invalid graph atlas data")
    _GRAPH_ATLAS_RECORDS = tuple(records)
    return _GRAPH_ATLAS_RECORDS


def _graph_atlas_from_record(record):
    graph_index, node_count, edges = record
    graph = Graph()
    graph.name = f"G{graph_index}"
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from(edges)
    return graph


def graph_atlas(i):
    """Return graph i from the atlas."""
    if not 0 <= i < _GRAPH_ATLAS_NUM_GRAPHS:
        raise ValueError(f"index must be between 0 and {_GRAPH_ATLAS_NUM_GRAPHS}")
    return _graph_atlas_from_record(_graph_atlas_records()[i])


def graph_atlas_g():
    """Return list of all graphs in the atlas."""
    return [_graph_atlas_from_record(record) for record in _graph_atlas_records()]


def find_asteroidal_triple(G, *, backend=None, **backend_kwargs):
    """Find an asteroidal triple (if exists).

    br-astertype: nx returns a list [u, v, w]; fnx's Rust binding
    returned a tuple. Coerce to list so isinstance / equality checks
    against nx's contract pass.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    _validate_backend_dispatch_keywords(
        "find_asteroidal_triple",
        backend,
        backend_kwargs,
    )
    from franken_networkx import _fnx

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-64xcg: networkx returns the FIRST triple its loops meet, and
    # both loops iterate Python sets - non_edges pops ``set(G)`` and the
    # third vertex runs over ``V - union_of_neighborhoods`` - so its answer
    # follows hash order (for str labels, the process's hash seed). The
    # native solver scans in index order and found another triple on str /
    # tuple labels (and on ints whose small difference sets wrap the table).
    # Whether a triple exists does not depend on the order, so the native
    # solver still answers "none" (its full scan is the expensive case, >100x
    # networkx); when one exists, networkx's loops run here on the same sets.
    # Only "same component of G - N[x]" is ever compared, so a plain BFS
    # labels the components.
    V = set(G.nodes)
    if len(V) < 6 or _fnx.find_asteroidal_triple_rust(G) is None:
        return None
    adj = {u: set(G[u]) for u in G}
    component_structure = {}
    for x in V:
        closed = adj[x] | {x}
        row = dict.fromkeys(closed, 0)
        label = 0
        for start in V - closed:
            if start in row:
                continue
            label += 1
            row[start] = label
            stack = [start]
            while stack:
                y = stack.pop()
                for z in adj[y]:
                    if z not in row:
                        row[z] = label
                        stack.append(z)
        component_structure[x] = row
    nodes = set(G)
    while nodes:
        u = nodes.pop()
        for v in nodes - adj[u]:
            union_of_neighborhoods = adj[u] | {u} | adj[v] | {v}
            for w in V - union_of_neighborhoods:
                if (
                    component_structure[u][v] == component_structure[u][w]
                    and component_structure[v][u] == component_structure[v][w]
                    and component_structure[w][u] == component_structure[w][v]
                ):
                    return [u, v, w]
    return None


def is_perfect_graph(G, *, backend=None, **backend_kwargs):
    """Check if G is perfect (no odd holes or odd anti-holes >= 5).

    Uses the Strong Perfect Graph Theorem: a graph is perfect iff neither
    it nor its complement contains an odd cycle of length >= 5 as an
    induced subgraph (a "hole" or "anti-hole").

    Enumerates chordless cycles of G and its complement (networkx's exact
    algorithm); a chordless odd cycle of length >= 5 in either is an odd hole.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    _validate_backend_dispatch_keywords("is_perfect_graph", backend, backend_kwargs)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # br-r37-c1-perfectchordless (cc): enumerate chordless cycles of G and
    # complement(G) (networkx's exact algorithm) instead of the bespoke per-node
    # DFS, which was exponential WITH a length-24 cap -> 1958ms / 0.046x on a
    # perfect path(60) AND silently WRONG for any odd hole longer than 24.
    # chordless_cycles short-circuits via `any` on the first odd hole; is_perfect_graph
    # is a boolean (order-invariant), so the result is byte-identical to nx (verified
    # 0/12 graph types). 0.046x -> 0.94x (path60, ~parity) / 1.70x (BA60), and odd
    # holes of length > 24 are now correctly detected.
    return not any(
        len(cycle) >= 5 and len(cycle) % 2 == 1
        for cycle in _itertools.chain(
            chordless_cycles(G), chordless_cycles(complement(G))
        )
    )


def is_regular_expander(G, *, epsilon=0):
    """Check if G is a regular expander graph."""
    import numpy as np
    import scipy as sp

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if epsilon < 0:
        raise NetworkXError("epsilon must be non negative")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")
    if not is_regular(G):
        return False

    _, degree = next(iter(G.degree))
    adjacency = adjacency_matrix(G, dtype=float)
    eigenvalues = sp.sparse.linalg.eigsh(
        adjacency,
        which="LM",
        k=2,
        return_eigenvectors=False,
    )
    lambda2 = min(eigenvalues)
    return bool(abs(lambda2) < 2 * np.sqrt(degree - 1) + epsilon)


def maybe_regular_expander(n, d, *, create_using=None, max_tries=100, seed=None):
    """Attempt to build a d-regular expander.

    Matches networkx's signature exactly:
    ``maybe_regular_expander(n, d, *, create_using=None, max_tries=100,
    seed=None)``. Earlier fnx had only ``(n, d, seed=None)``, breaking
    drop-in callers passing ``create_using=`` or ``max_tries=``.
    """
    return maybe_regular_expander_graph(
        n, d, create_using=create_using, max_tries=max_tries, seed=seed,
    )


def maybe_regular_expander_graph(n, d, *, create_using=None, max_tries=100, seed=None):
    """Utility for creating a random regular expander."""
    # br-r37-c1-cdf1v: networkx's @np_random_state resolves the seed before
    # the body's checks - a random.Random with an odd d raised
    # NetworkXError("d must be even") here, ValueError in networkx.
    seed = _numpy_random_state(seed)
    if n < 1:
        raise NetworkXError("n must be a positive integer")
    if not (d >= 2):
        raise NetworkXError("d must be greater than or equal to 2")
    if not (d % 2 == 0):
        raise NetworkXError("d must be even")
    if not (n - 1 >= d):
        raise NetworkXError(
            f"Need n-1>= d to have room for {d // 2} independent cycles with {n} nodes"
        )

    graph = empty_graph(n, create_using)
    if n < 2:
        return graph

    edges = set()

    for i in range(d // 2):
        iterations = max_tries
        while len(edges) != (i + 1) * n:
            iterations -= 1
            cycle = seed.permutation(n - 1).tolist()
            cycle.append(n - 1)
            new_edges = {
                (u, v)
                for u, v in _itertools.pairwise(cycle + [cycle[0]])
                if (u, v) not in edges and (v, u) not in edges
            }
            if len(new_edges) == n:
                edges.update(new_edges)
            if iterations == 0:
                raise NetworkXError("Too many iterations in maybe_regular_expander_graph")

    graph.add_edges_from(edges)
    return graph


def random_regular_expander_graph(
    n,
    d,
    *,
    epsilon=0,
    create_using=None,
    max_tries=100,
    seed=None,
):
    """Return a random regular expander graph on n nodes with degree d."""
    seed = _numpy_random_state(seed)
    graph = maybe_regular_expander_graph(
        n,
        d,
        create_using=create_using,
        max_tries=max_tries,
        seed=seed,
    )
    iterations = max_tries
    while not is_regular_expander(graph, epsilon=epsilon):
        iterations -= 1
        graph = maybe_regular_expander_graph(
            n,
            d,
            create_using=create_using,
            max_tries=max_tries,
            seed=seed,
        )
        if iterations == 0:
            raise NetworkXError("Too many iterations in random_regular_expander_graph")
    return graph


def make_clique_bipartite(G, fpos=None, create_using=None, name=None):
    """Returns the bipartite clique graph corresponding to ``G``."""
    B = empty_graph(0, create_using)
    B.add_nodes_from(G, bipartite=1)
    for i, clique in enumerate(find_cliques(G)):
        clique_node = -i - 1
        B.add_node(clique_node, bipartite=0)
        B.add_edges_from([(node, clique_node) for node in clique])
    return B


def _complete_multipartite_k_components(G):
    component_rows = []
    max_connectivity = 0
    for component in connected_components(G):
        nodes = list(component)
        if len(nodes) < 2:
            continue

        component_set = set(nodes)
        parts = {}
        for node in nodes:
            neighbors = set(G[node])
            neighbors.intersection_update(component_set)
            part = frozenset(component_set - neighbors)
            if node not in part:
                return None
            parts.setdefault(part, []).append(node)

        covered = set()
        max_part_size = 0
        for part, members in parts.items():
            member_set = set(members)
            part_set = set(part)
            if member_set != part_set or covered.intersection(member_set):
                return None
            covered.update(member_set)
            max_part_size = max(max_part_size, len(part_set))

        if covered != component_set or len(parts) < 2:
            return None
        connectivity = len(nodes) - max_part_size
        if connectivity < 1:
            return None
        component_rows.append((connectivity, component_set))
        max_connectivity = max(max_connectivity, connectivity)

    if not component_rows:
        return {}

    result = {}
    higher_components = []
    for k in range(max_connectivity, 2, -1):
        exact_components = [
            component for connectivity, component in component_rows if connectivity == k
        ]
        level = [set(component) for component in exact_components]
        level.extend(set(component) for component in higher_components)
        if level:
            result[k] = level
        higher_components = exact_components + higher_components

    if max_connectivity >= 2:
        result[2] = [
            set(component)
            for connectivity, component in component_rows
            if connectivity >= 2
        ]
    result[1] = [set(component) for _, component in component_rows]
    return result


def _is_biconnected_component_adjacency(nodes, adjacency):
    if len(nodes) < 3:
        return False

    root = nodes[0]
    discovery = {}
    low = {}
    parent = {}
    time = 0
    root_children = 0
    has_articulation = False

    def visit(node):
        nonlocal time, root_children, has_articulation
        discovery[node] = time
        low[node] = time
        time += 1
        for neighbor in adjacency[node]:
            if neighbor not in discovery:
                parent[neighbor] = node
                if node == root:
                    root_children += 1
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
                if node != root and low[neighbor] >= discovery[node]:
                    has_articulation = True
            elif parent.get(node) != neighbor:
                low[node] = min(low[node], discovery[neighbor])

    visit(root)
    return len(discovery) == len(nodes) and root_children <= 1 and not has_articulation


def _is_two_degenerate_component(nodes, adjacency):
    remaining = set(nodes)
    degrees = {node: len(adjacency[node]) for node in nodes}
    stack = [node for node in nodes if degrees[node] <= 2]
    removed = 0

    while stack:
        node = stack.pop()
        if node not in remaining or degrees[node] > 2:
            continue
        remaining.remove(node)
        removed += 1
        for neighbor in adjacency[node]:
            if neighbor in remaining:
                degrees[neighbor] -= 1
                if degrees[neighbor] <= 2:
                    stack.append(neighbor)

    return removed == len(nodes)


def _two_degenerate_biconnected_k_components(G):
    components = []
    for component in connected_components(G):
        nodes = list(component)
        if len(nodes) < 3:
            return None
        component_set = set(nodes)
        adjacency = {}
        for node in nodes:
            neighbors = set(G[node])
            neighbors.intersection_update(component_set)
            if len(neighbors) < 2:
                return None
            adjacency[node] = neighbors
        if not _is_biconnected_component_adjacency(nodes, adjacency):
            return None
        if not _is_two_degenerate_component(nodes, adjacency):
            return None
        components.append(component_set)

    if not components:
        return {}
    return {
        2: [set(component) for component in components],
        1: [set(component) for component in components],
    }


def _is_connected_after_removing(nodes, adjacency, removed):
    start = None
    for node in nodes:
        if node not in removed:
            start = node
            break

    if start is None:
        return True

    seen = {start}
    pending = [start]
    while pending:
        node = pending.pop()
        for neighbor in adjacency[node]:
            if neighbor not in removed and neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)

    return len(seen) == len(nodes) - len(removed)


def _cubic_three_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 5 or node_count > 128:
        return None
    if G.number_of_edges() * 2 != 3 * node_count:
        return None

    adjacency = {}
    for node in nodes:
        neighbors = set(G[node])
        if len(neighbors) != 3:
            return None
        adjacency[node] = neighbors

    if not _is_connected_after_removing(nodes, adjacency, set()):
        return None

    for index, first in enumerate(nodes):
        if not _is_connected_after_removing(nodes, adjacency, {first}):
            return None
        for second in nodes[index + 1:]:
            if not _is_connected_after_removing(nodes, adjacency, {first, second}):
                return None

    nodes_set = set(nodes)
    return {
        3: [set(nodes_set)],
        2: [set(nodes_set)],
        1: [set(nodes_set)],
    }


def _quartic_four_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 6 or node_count > 64:
        return None
    if G.number_of_edges() * 2 != 4 * node_count:
        return None

    adjacency = {}
    for node in nodes:
        neighbors = set(G[node])
        if len(neighbors) != 4:
            return None
        adjacency[node] = neighbors

    if not _is_connected_after_removing(nodes, adjacency, set()):
        return None

    for first_index, first in enumerate(nodes):
        if not _is_connected_after_removing(nodes, adjacency, {first}):
            return None
        for second_index in range(first_index + 1, node_count):
            second = nodes[second_index]
            if not _is_connected_after_removing(nodes, adjacency, {first, second}):
                return None
            for third in nodes[second_index + 1:]:
                if not _is_connected_after_removing(
                    nodes,
                    adjacency,
                    {first, second, third},
                ):
                    return None

    nodes_set = set(nodes)
    return {
        4: [set(nodes_set)],
        3: [set(nodes_set)],
        2: [set(nodes_set)],
        1: [set(nodes_set)],
    }


def _quintic_five_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 8 or node_count > 32:
        return None
    if G.number_of_edges() * 2 != 5 * node_count:
        return None

    adjacency = {}
    for node in nodes:
        neighbors = set(G[node])
        if len(neighbors) != 5:
            return None
        adjacency[node] = neighbors

    if not _is_connected_after_removing(nodes, adjacency, set()):
        return None

    for cut_size in range(1, 5):
        for removed in _combinations(nodes, cut_size):
            if not _is_connected_after_removing(nodes, adjacency, set(removed)):
                return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(5, 0, -1)}


def _six_regular_six_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 8 or node_count > 24:
        return None
    if G.number_of_edges() * 2 != 6 * node_count:
        return None

    node_to_index = {node: index for index, node in enumerate(nodes)}
    adjacency_masks = []
    for node in nodes:
        neighbors = list(G[node])
        if len(neighbors) != 6:
            return None
        mask = 0
        for neighbor in neighbors:
            index = node_to_index.get(neighbor)
            if index is None:
                return None
            mask |= 1 << index
        adjacency_masks.append(mask)

    all_nodes_mask = (1 << node_count) - 1

    def connected_after_removing(removed_mask):
        remaining_mask = all_nodes_mask & ~removed_mask
        if remaining_mask == 0:
            return True

        first = remaining_mask & -remaining_mask
        seen = first
        pending = first
        while pending:
            bit = pending & -pending
            pending ^= bit
            node_index = bit.bit_length() - 1
            new_neighbors = adjacency_masks[node_index] & remaining_mask & ~seen
            seen |= new_neighbors
            pending |= new_neighbors
        return seen == remaining_mask

    if not connected_after_removing(0):
        return None

    for cut_size in range(1, 6):
        for removed_indices in _combinations(range(node_count), cut_size):
            removed_mask = 0
            for index in removed_indices:
                removed_mask |= 1 << index
            if not connected_after_removing(removed_mask):
                return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(6, 0, -1)}


def _seven_regular_seven_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 9 or node_count > 22:
        return None
    if G.number_of_edges() * 2 != 7 * node_count:
        return None

    node_to_index = {node: index for index, node in enumerate(nodes)}
    adjacency_masks = []
    for node in nodes:
        neighbors = list(G[node])
        if len(neighbors) != 7:
            return None
        mask = 0
        for neighbor in neighbors:
            index = node_to_index.get(neighbor)
            if index is None:
                return None
            mask |= 1 << index
        adjacency_masks.append(mask)

    all_nodes_mask = (1 << node_count) - 1

    def connected_after_removing(removed_mask):
        remaining_mask = all_nodes_mask & ~removed_mask
        if remaining_mask == 0:
            return True

        first = remaining_mask & -remaining_mask
        seen = first
        pending = first
        while pending:
            bit = pending & -pending
            pending ^= bit
            node_index = bit.bit_length() - 1
            new_neighbors = adjacency_masks[node_index] & remaining_mask & ~seen
            seen |= new_neighbors
            pending |= new_neighbors
        return seen == remaining_mask

    if not connected_after_removing(0):
        return None

    for cut_size in range(1, 7):
        for removed_indices in _combinations(range(node_count), cut_size):
            removed_mask = 0
            for index in removed_indices:
                removed_mask |= 1 << index
            if not connected_after_removing(removed_mask):
                return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(7, 0, -1)}


def _eight_regular_eight_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 10 or node_count > 20:
        return None
    if G.number_of_edges() * 2 != 8 * node_count:
        return None

    node_to_index = {node: index for index, node in enumerate(nodes)}
    adjacency_masks = []
    for node in nodes:
        neighbors = list(G[node])
        if len(neighbors) != 8:
            return None
        mask = 0
        for neighbor in neighbors:
            index = node_to_index.get(neighbor)
            if index is None:
                return None
            mask |= 1 << index
        adjacency_masks.append(mask)

    all_nodes_mask = (1 << node_count) - 1

    def connected_after_removing(removed_mask):
        remaining_mask = all_nodes_mask & ~removed_mask
        if remaining_mask == 0:
            return True

        first = remaining_mask & -remaining_mask
        seen = first
        pending = first
        while pending:
            bit = pending & -pending
            pending ^= bit
            node_index = bit.bit_length() - 1
            new_neighbors = adjacency_masks[node_index] & remaining_mask & ~seen
            seen |= new_neighbors
            pending |= new_neighbors
        return seen == remaining_mask

    if not connected_after_removing(0):
        return None

    for cut_size in range(1, 8):
        for removed_indices in _combinations(range(node_count), cut_size):
            removed_mask = 0
            for index in removed_indices:
                removed_mask |= 1 << index
            if not connected_after_removing(removed_mask):
                return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(8, 0, -1)}


def _nine_regular_nine_connected_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 11 or node_count > 20:
        return None
    if G.number_of_edges() * 2 != 9 * node_count:
        return None

    node_to_index = {node: index for index, node in enumerate(nodes)}
    adjacency_masks = []
    for node in nodes:
        neighbors = list(G[node])
        if len(neighbors) != 9:
            return None
        mask = 0
        for neighbor in neighbors:
            index = node_to_index.get(neighbor)
            if index is None:
                return None
            mask |= 1 << index
        adjacency_masks.append(mask)

    all_nodes_mask = (1 << node_count) - 1

    def connected_after_removing(removed_mask):
        remaining_mask = all_nodes_mask & ~removed_mask
        if remaining_mask == 0:
            return True

        first = remaining_mask & -remaining_mask
        seen = first
        pending = first
        while pending:
            bit = pending & -pending
            pending ^= bit
            node_index = bit.bit_length() - 1
            new_neighbors = adjacency_masks[node_index] & remaining_mask & ~seen
            seen |= new_neighbors
            pending |= new_neighbors
        return seen == remaining_mask

    if not connected_after_removing(0):
        return None

    for cut_size in range(1, 9):
        for removed_indices in _combinations(range(node_count), cut_size):
            removed_mask = 0
            for index in removed_indices:
                removed_mask |= 1 << index
            if not connected_after_removing(removed_mask):
                return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(9, 0, -1)}


def _ordered_prism_k_components(G):
    node_count = len(G)
    if node_count < 6 or node_count % 2 != 0:
        return None

    half = node_count // 2
    if G.number_of_edges() != 3 * half:
        return None

    nodes = list(G)
    if any(degree != 3 for _, degree in G.degree()):
        return None

    for index in range(half):
        upper = nodes[index]
        next_upper = nodes[(index + 1) % half]
        lower = nodes[half + index]
        next_lower = nodes[half + ((index + 1) % half)]
        if (
            not G.has_edge(upper, next_upper)
            or not G.has_edge(lower, next_lower)
            or not G.has_edge(upper, lower)
        ):
            return None

    nodes_set = set(nodes)
    return {
        3: [set(nodes_set)],
        2: [set(nodes_set)],
        1: [set(nodes_set)],
    }


def _wheel_k_components(G):
    node_count = len(G)
    if node_count < 5:
        return None

    rim_count = node_count - 1
    if G.number_of_edges() != 2 * rim_count:
        return None

    degrees = dict(G.degree())
    hubs = [node for node, degree in degrees.items() if degree == rim_count]
    if len(hubs) != 1:
        return None

    hub = hubs[0]
    rim_nodes = [node for node in G if node != hub]
    rim_set = set(rim_nodes)
    rim_edge_degree_sum = 0
    for node in rim_nodes:
        if degrees[node] != 3 or not G.has_edge(hub, node):
            return None
        rim_degree = sum(1 for neighbor in G[node] if neighbor in rim_set)
        if rim_degree != 2:
            return None
        rim_edge_degree_sum += rim_degree

    if rim_edge_degree_sum // 2 != rim_count:
        return None

    pending = [rim_nodes[0]]
    seen = {rim_nodes[0]}
    while pending:
        node = pending.pop()
        for neighbor in G[node]:
            if neighbor in rim_set and neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    if len(seen) != rim_count:
        return None

    nodes_set = set(G)
    return {
        3: [set(nodes_set)],
        2: [set(nodes_set)],
        1: [set(nodes_set)],
    }


def _hypercube_k_components(G):
    nodes = list(G)
    node_count = len(nodes)
    if node_count < 8:
        return None

    first = nodes[0]
    if not isinstance(first, tuple):
        return None
    dimension = len(first)
    if dimension < 3 or node_count != 1 << dimension:
        return None

    expected_nodes = {()}
    for _ in range(dimension):
        expected_nodes = {
            prefix + (bit,)
            for prefix in expected_nodes
            for bit in (0, 1)
        }
    node_set = set(nodes)
    if node_set != expected_nodes:
        return None

    if G.number_of_edges() != dimension * (node_count // 2):
        return None

    for node in nodes:
        if (
            not isinstance(node, tuple)
            or len(node) != dimension
            or any(bit not in (0, 1) for bit in node)
            or G.degree(node) != dimension
        ):
            return None
        expected_neighbors = {
            node[:index] + (1 - node[index],) + node[index + 1:]
            for index in range(dimension)
        }
        if set(G[node]) != expected_neighbors:
            return None

    nodes_set = set(nodes)
    return {k: [set(nodes_set)] for k in range(dimension, 0, -1)}
