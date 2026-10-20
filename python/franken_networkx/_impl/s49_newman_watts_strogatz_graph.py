

def newman_watts_strogatz_graph(n, k, p, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Return a Newman-Watts-Strogatz small-world graph."""
    _validate_backend_dispatch_keywords(
        "newman_watts_strogatz_graph", backend, backend_kwargs
    )
    # br-r37-c1-ols3t: nx's py_random_state, resolved first; the kernel draws
    # from an int or streams a random.Random (None is the global
    # random._inst), a numpy-backed seed runs networkx's body.
    kernel_seed = _kernel_seed(seed)
    # br-nwsval: validate with nx-shaped NetworkXError at the Python edge so
    # that the Rust ValueError(FailClosed{...}) doesn't leak. nx accepts
    # k=0 and k=1 (returns the empty graph on n nodes — the ring with
    # k//2=0 has no edges); the Rust binding rejects k<2 so we short-circuit
    # those cases here.
    if k > n:
        raise NetworkXError("k>=n, choose smaller k or larger n")
    if k == n:
        return complete_graph(n, create_using=create_using)
    if k < 2:
        return empty_graph(n, create_using=create_using)
    # br-r37-c1-nws-pnan: nx accepts NaN / inf / out-of-range p
    # silently — its weighted-flip ``random.random() < p`` evaluates
    # naturally (NaN → False / no rewiring; inf → True / full
    # rewiring; p<0 / p>1 → comparable extremes).  fnx's Rust
    # binding rejected these with leaky ``FailClosed`` formats.
    # Clamp / route to match nx's silent contract.
    import math as _math
    if isinstance(p, float) and _math.isnan(p):
        # NaN: nx's < comparison returns False → no rewiring →
        # equivalent to p=0
        p = 0.0
    elif isinstance(p, (int, float)) and p > 1:
        p = 1.0  # full rewiring
    elif isinstance(p, (int, float)) and p < 0:
        p = 0.0  # no rewiring
    # create_using is checked before any draw, as networkx checks it.
    target = None if create_using is None else _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    # A create_using graph is built in place by the body: copying the kernel's
    # result into it re-derived each adjacency row from the edge order.
    if kernel_seed is None or target is not None:
        return _newman_watts_strogatz_python(
            n, k, p, _generator_random_state(seed), empty_graph(n, create_using=target)
        )
    return _rust_newman_watts_strogatz_graph(n, k, p, seed=kernel_seed)


def _newman_watts_strogatz_python(n, k, p, seed, G):
    """networkx's newman_watts_strogatz_graph body on the empty ``G``.

    br-r37-c1-ols3t: for a numpy-backed seed, which has no MT19937 state for
    the kernel; the ring goes in as one batch in networkx's add_edge order.
    """
    nlist = list(G.nodes())
    fromv = nlist
    ring = []
    for j in range(1, k // 2 + 1):
        tov = fromv[j:] + fromv[0:j]
        ring.extend(zip(fromv, tov))
    G.add_edges_from(ring)
    for u, v in list(G.edges()):
        if seed.random() < p:
            w = seed.choice(nlist)
            while w == u or G.has_edge(u, w):
                w = seed.choice(nlist)
                if G.degree(u) >= n - 1:
                    break
            else:
                G.add_edge(u, w)
    return G


def connected_watts_strogatz_graph(n, k, p, tries=100, seed=None, *, create_using=None):
    """Return a connected Watts-Strogatz small-world graph."""
    # br-r37-c1-ols3t: nx's py_random_state, resolved first (see
    # newman_watts_strogatz_graph).
    kernel_seed = _kernel_seed(seed)
    # br-cwsval: validate at the Python edge so the Rust ValueError(FailClosed)
    # surface doesn't leak — nx raises NetworkXError for both k>n and the
    # tries-exceeded path.
    if k > n:
        raise NetworkXError("k>n, choose smaller k or larger n")
    if n == 0:
        raise NetworkXPointlessConcept("Connectivity is undefined for the null graph.")
    if n == 1 and k < 1:
        return empty_graph(n, create_using=create_using)
    if k == n:
        return complete_graph(n, create_using=create_using)
    if k < 2:
        raise NetworkXError("Maximum number of tries exceeded")
    # br-r37-c1-cws-tries: nx raises NetworkXError("Maximum number
    # of tries exceeded") for tries <= 0; fnx's Rust binding leaked
    # ``ValueError(FailClosed { ... })`` for tries=0 and
    # ``OverflowError("can't convert negative int to unsigned")``
    # for tries<0 (the unsigned Rust signature).  Validate at the
    # wrapper to match nx's contract.
    if isinstance(tries, int) and tries <= 0:
        raise NetworkXError("Maximum number of tries exceeded")
    if kernel_seed is None or create_using is not None:
        # networkx's loop - for a numpy-backed seed, or a create_using graph
        # built in place: watts_strogatz_graph draws from the same generator
        # each try, until one is connected.
        rng = _generator_random_state(seed)
        for _ in range(tries):
            graph = watts_strogatz_graph(n, k, p, rng, create_using=create_using)
            if is_connected(graph):
                return graph
        raise NetworkXError("Maximum number of tries exceeded")
    return _rust_connected_watts_strogatz_graph(n, k, p, tries=tries, seed=kernel_seed)


def random_regular_graph(d, n, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Return a random d-regular graph."""
    _validate_backend_dispatch_keywords("random_regular_graph", backend, backend_kwargs)
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    # br-codrgen: seeded output diverges from nx because the Rust native
    # uses MT19937 while nx uses Python's random.Random. Keeping native
    # per the "no nx fallback for generators" design invariant guarded
    # by test_native_random_generators_do_not_fallback_to_networkx.
    # Exact-output parity requires a Rust-side RNG port and is tracked
    # separately.
    # br-rrgval: validate with nx-shaped NetworkXError *before* the Rust
    # branch; without this, invalid (d, n) leak the Rust
    # `ValueError("FailClosed { ... }")` instead of nx's NetworkXError.
    # Order matches nx (n*d parity check first, then d<n) so that inputs
    # failing both — e.g. (d=3, n=3) — surface the same message nx does.
    if (n * d) % 2 != 0:
        raise NetworkXError("n * d must be even")
    if not 0 <= d < n:
        raise NetworkXError("the 0 <= d < n inequality must be satisfied")

    # br-r37-c1-rrgseed: nx.random_regular_graph(d, n, seed=) uses
    # ``random.Random(seed)`` (Python's MT19937 with Python-side
    # state).  fnx's no-``create_using`` fast path used the Rust
    # ``_rust_random_regular_graph`` which has its own MT19937 with
    # different state evolution — same seed produced different
    # graphs (a documented divergence labeled br-codrgen).  Drop-in
    # callers using ``seed=N`` for reproducibility hit silent graph
    # divergence.
    #
    # Fix: route the no-``create_using`` path through the Python
    # implementation below (which uses ``_generator_random_state``
    # = ``random.Random``) — same RNG semantics as nx — so seeded
    # output matches nx exactly.  No nx-fallback is used (the
    # ``test_native_random_generators_do_not_fallback_to_networkx``
    # lock-test still passes); the algorithm is fnx's own Python
    # implementation.
    use_native_edge_pyset = (
        create_using is None
        and type(d) is int
        and type(n) is int
        and type(seed) is int
        and 0 <= seed <= 0xFFFF_FFFF_FFFF_FFFF
        and n * d <= 1_000_000
    )
    if use_native_edge_pyset:
        return _rust_random_regular_graph_pyset_order(d, n, seed)

    if create_using is None:
        create_using = Graph

    rng = _generator_random_state(seed)
    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )

    graph = empty_graph(n, create_using=graph)
    if d == 0:
        return graph
    def _suitable(edges, potential_edges):
        if not potential_edges:
            return True
        for s1 in potential_edges:
            for s2 in potential_edges:
                if s1 == s2:
                    break
                if s1 > s2:
                    s1, s2 = s2, s1
                if (s1, s2) not in edges:
                    return True
        return False

    def _try_creation():
        edges = set()
        stubs = list(range(n)) * d

        while stubs:
            potential_edges = _defaultdict(lambda: 0)
            rng.shuffle(stubs)
            stubiter = iter(stubs)
            for s1, s2 in zip(stubiter, stubiter):
                if s1 > s2:
                    s1, s2 = s2, s1
                if s1 != s2 and (s1, s2) not in edges:
                    edges.add((s1, s2))
                else:
                    potential_edges[s1] += 1
                    potential_edges[s2] += 1

            if not _suitable(edges, potential_edges):
                return None

            return_stubs = []
            for node, potential in potential_edges.items():
                return_stubs.extend([node] * potential)
            stubs[:] = return_stubs

        return edges

    edges = _try_creation()
    while edges is None:
        edges = _try_creation()
    graph.add_edges_from(edges)
    return graph


def powerlaw_cluster_graph(n, m, p, seed=None, *, create_using=None, backend=None, **backend_kwargs):
    """Return a powerlaw-cluster graph."""
    _validate_backend_dispatch_keywords("powerlaw_cluster_graph", backend, backend_kwargs)
    # br-r37-c1-ols3t: nx's py_random_state, resolved first (see
    # newman_watts_strogatz_graph).
    kernel_seed = _kernel_seed(seed)
    # create_using is checked before the arguments, as networkx checks it.
    target = None if create_using is None else _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    # br-powerlawexc: nx raises NetworkXError with its own wording; fnx used
    # to surface the Rust 'ValueError(FailClosed{...})' on the default path.
    # Normalize to nx's exact message so regex-matched pytest.raises keeps
    # working on the drop-in surface. nx accepts m == n (returns n nodes
    # with 0 edges) — only m > n is rejected.
    if m < 1 or m > n:
        raise NetworkXError(
            f"NetworkXError must have m>1 and m<n, m={m},n={n}"
        )
    if p > 1 or p < 0:
        raise NetworkXError(f"NetworkXError p must be in [0,1], p={p}")
    # br-r37-c1-pcg-pnan: nx accepts p=NaN silently — its weighted
    # ``random.random() < p`` flip evaluates False (NaN comparison
    # always False), so triangle-closure never fires and the base
    # preferential-attachment graph is returned.  fnx's Rust binding
    # rejected NaN with the leaky ``FailClosed`` format.  Coerce
    # NaN → 0.0 to match nx's silent contract.  Same defect family
    # as br-r37-c1-r3ct1 (newman_watts_strogatz NaN).
    import math as _math
    if isinstance(p, float) and _math.isnan(p):
        p = 0.0
    # A create_using graph is built in place by the body (see
    # newman_watts_strogatz_graph).
    if kernel_seed is None or target is not None:
        return _powerlaw_cluster_python(
            n, m, p, _generator_random_state(seed), empty_graph(m, create_using=target)
        )
    return _rust_powerlaw_cluster_graph(n, m, p, seed=kernel_seed)


def _powerlaw_cluster_python(n, m, p, seed, G):
    """networkx's powerlaw_cluster_graph body on ``G`` = empty_graph(m).

    br-r37-c1-ols3t: for a numpy-backed seed, which has no MT19937 state for
    the kernel. ``_random_subset`` and its set ``pop()`` order are networkx's.
    """

    def _random_subset(seq, count):
        targets = set()
        while len(targets) < count:
            targets.add(seed.choice(seq))
        return targets

    repeated_nodes = list(G)
    source = m
    while source < n:
        possible_targets = _random_subset(repeated_nodes, m)
        target = possible_targets.pop()
        G.add_edge(source, target)
        repeated_nodes.append(target)
        count = 1
        while count < m:
            if seed.random() < p:
                neighborhood = [
                    nbr for nbr in G.neighbors(target) if not G.has_edge(source, nbr) and nbr != source
                ]
                if neighborhood:
                    nbr = seed.choice(neighborhood)
                    G.add_edge(source, nbr)
                    repeated_nodes.append(nbr)
                    count = count + 1
                    continue
            target = possible_targets.pop()
            G.add_edge(source, target)
            repeated_nodes.append(target)
            count = count + 1
        repeated_nodes.extend([source] * m)
        source += 1
    return G


def directed_configuration_model(
    in_degree_sequence,
    out_degree_sequence,
    create_using=None,
    seed=None,
):
    """Return a directed configuration model graph."""
    if sum(in_degree_sequence) != sum(out_degree_sequence):
        raise NetworkXError("Invalid degree sequences: sequences must have equal sums")

    graph = _empty_graph_from_create_using(
        create_using,
        default=MultiDiGraph,
    )
    return _configuration_model_local(
        out_degree_sequence,
        graph,
        directed=True,
        in_degree_sequence=in_degree_sequence,
        seed=seed,
    )


def directed_joint_degree_graph(in_degrees, out_degrees, nkk, seed=None):
    """Return a directed graph matching a directed joint-degree distribution."""
    if not is_valid_directed_joint_degree(in_degrees, out_degrees, nkk):
        raise NetworkXError("Input is not realizable as a simple graph")

    graph = DiGraph()
    degree_nodes_in = {}
    degree_nodes_out = {}
    degree_nodes_in_unsat = {}
    degree_nodes_out_unsat = {}
    residual_out = {}
    residual_in = {}
    partition_out = {}
    partition_in = {}
    non_chords = {}

    for idx, in_degree in enumerate(in_degrees):
        idx = int(idx)
        if in_degree > 0:
            degree_nodes_in.setdefault(in_degree, [])
            degree_nodes_in_unsat.setdefault(in_degree, set())
            degree_nodes_in[in_degree].append(idx)
            degree_nodes_in_unsat[in_degree].add(idx)
            residual_in[idx] = in_degree
            partition_in[idx] = in_degree

    for idx, out_degree in enumerate(out_degrees):
        non_chords[(out_degree, in_degrees[idx])] = (
            non_chords.get((out_degree, in_degrees[idx]), 0) + 1
        )
        idx = int(idx)
        if out_degree > 0:
            degree_nodes_out.setdefault(out_degree, [])
            degree_nodes_out_unsat.setdefault(out_degree, set())
            degree_nodes_out[out_degree].append(idx)
            degree_nodes_out_unsat[out_degree].add(idx)
            residual_out[idx] = out_degree
            partition_out[idx] = out_degree
        graph.add_node(idx)

    count_in = {degree: len(nodes) for degree, nodes in degree_nodes_in.items()}
    count_out = {degree: len(nodes) for degree, nodes in degree_nodes_out.items()}
    rng = _generator_random_state(seed)

    for out_degree in nkk:
        for in_degree in nkk[out_degree]:
            edges_to_add = nkk[out_degree][in_degree]
            if edges_to_add <= 0:
                continue

            chords = set()
            out_count = count_out[out_degree]
            in_count = count_in[in_degree]
            sample = rng.sample(
                range(out_count * in_count),
                edges_to_add + non_chords.get((out_degree, in_degree), 0),
            )

            sample_index = 0
            while len(chords) < edges_to_add:
                source = degree_nodes_out[out_degree][sample[sample_index] % out_count]
                target = degree_nodes_in[in_degree][sample[sample_index] // out_count]
                sample_index += 1
                if source != target:
                    chords.add((source, target))

            out_unsat = degree_nodes_out_unsat[out_degree]
            in_unsat = degree_nodes_in_unsat[in_degree]

            while edges_to_add > 0:
                source, target = chords.pop()
                chords.add((source, target))

                if residual_out[source] == 0:
                    switched = _directed_neighbor_switch_local(
                        graph,
                        source,
                        out_unsat,
                        residual_out,
                        chords,
                        partition_in,
                        in_degree,
                    )
                    if switched is not None:
                        source = switched

                if residual_in[target] == 0:
                    switched = _directed_neighbor_switch_rev_local(
                        graph,
                        target,
                        in_unsat,
                        residual_in,
                        chords,
                        partition_out,
                        out_degree,
                    )
                    if switched is not None:
                        target = switched

                graph.add_edge(source, target)
                residual_out[source] -= 1
                residual_in[target] -= 1
                edges_to_add -= 1
                chords.discard((source, target))

                if residual_out[source] == 0:
                    out_unsat.discard(source)
                if residual_in[target] == 0:
                    in_unsat.discard(target)

    return graph


def joint_degree_graph(joint_degrees, seed=None):
    """Return an undirected graph matching a joint-degree distribution."""
    if not is_valid_joint_degree(joint_degrees):
        raise NetworkXError("Input joint degree dict not realizable as a simple graph")

    degree_count = {
        degree: sum(edges.values()) // degree
        for degree, edges in joint_degrees.items()
        if degree > 0
    }
    graph = empty_graph(sum(degree_count.values()))

    degree_nodes = {}
    residual = {}
    node_id = 0
    for degree, num_nodes in degree_count.items():
        degree_nodes[degree] = range(node_id, node_id + num_nodes)
        for node in degree_nodes[degree]:
            residual[node] = degree
        node_id += int(num_nodes)

    rng = _generator_random_state(seed)
    for degree_left in joint_degrees:
        for degree_right in joint_degrees[degree_left]:
            edges_to_add = joint_degrees[degree_left][degree_right]
            if edges_to_add <= 0 or degree_left < degree_right:
                continue

            left_count = degree_count[degree_left]
            right_count = degree_count[degree_right]
            left_nodes = degree_nodes[degree_left]
            right_nodes = degree_nodes[degree_right]
            left_unsat = {node for node in left_nodes if residual[node] > 0}

            if degree_left != degree_right:
                right_unsat = {node for node in right_nodes if residual[node] > 0}
            else:
                right_unsat = left_unsat
                edges_to_add = joint_degrees[degree_left][degree_right] // 2

            while edges_to_add > 0:
                source = left_nodes[rng.randrange(left_count)]
                target = right_nodes[rng.randrange(right_count)]

                if graph.has_edge(source, target) or source == target:
                    continue

                if residual[source] == 0:
                    _neighbor_switch_local(graph, source, left_unsat, residual)
                if residual[target] == 0:
                    if degree_left != degree_right:
                        _neighbor_switch_local(graph, target, right_unsat, residual)
                    else:
                        _neighbor_switch_local(
                            graph,
                            target,
                            right_unsat,
                            residual,
                            avoid_node_id=source,
                        )

                graph.add_edge(source, target)
                residual[source] -= 1
                residual[target] -= 1
                edges_to_add -= 1

                if residual[source] == 0:
                    left_unsat.discard(source)
                if residual[target] == 0:
                    right_unsat.discard(target)

    return graph


def expected_degree_graph(w, seed=None, selfloops=True):
    """Return a Chung-Lu expected-degree random graph."""
    n = len(w)
    graph = empty_graph(n)
    if n == 0 or max(w) == 0:
        return graph

    rng = _generator_random_state(seed)
    rho = 1 / sum(w)
    order = sorted(enumerate(w), key=lambda item: item[1], reverse=True)
    mapping = {canonical: node for canonical, (node, _) in enumerate(order)}
    sequence = [weight for _, weight in order]
    last = n if selfloops else n - 1
    # br-r37-c1-yrdso: the Chung-Lu loop reads only sequence/mapping (never the
    # graph), so accumulate accepted edges in source-ascending order and commit
    # through ONE add_edges_from instead of per-edge add_edge PyO3. Byte-identical.
    _edge_accum = []
    for source in range(last):
        target = source if selfloops else source + 1
        factor = sequence[source] * rho
        probability = min(sequence[target] * factor, 1)
        while target < n and probability > 0:
            if probability != 1:
                target += _math.floor(_math.log(rng.random(), 1 - probability))
            if target < n:
                next_probability = min(sequence[target] * factor, 1)
                if rng.random() < next_probability / probability:
                    _edge_accum.append((mapping[source], mapping[target]))
                target += 1
                probability = next_probability
    graph.add_edges_from(_edge_accum)
    return graph


def directed_havel_hakimi_graph(in_deg_sequence, out_deg_sequence, create_using=None):
    """Return a directed graph with prescribed in/out degree sequences."""
    try:
        in_deg_sequence = [int(degree) for degree in in_deg_sequence]
        out_deg_sequence = [int(degree) for degree in out_deg_sequence]
    except (TypeError, ValueError):
        raise NetworkXError("Invalid degree sequences. Sequence values must be positive.")

    sumin = 0
    sumout = 0
    nin = len(in_deg_sequence)
    nout = len(out_deg_sequence)
    maxn = max(nin, nout)
    graph = _empty_graph_from_create_using(create_using, default=DiGraph)
    graph.add_nodes_from(range(maxn))
    if maxn == 0:
        return graph

    maxin = 0
    stubheap = []
    zeroheap = []
    for node in range(maxn):
        out_degree = out_deg_sequence[node] if node < nout else 0
        in_degree = in_deg_sequence[node] if node < nin else 0
        if in_degree < 0 or out_degree < 0:
            raise NetworkXError(
                "Invalid degree sequences. Sequence values must be positive."
            )
        sumin += in_degree
        sumout += out_degree
        maxin = max(maxin, in_degree)
        if in_degree > 0:
            _heappush(stubheap, (-out_degree, -in_degree, node))
        elif out_degree > 0:
            _heappush(zeroheap, (-out_degree, node))
    if sumin != sumout:
        raise NetworkXError("Invalid degree sequences. Sequences must have equal sums.")

    modified = [(0, 0, 0)] * (maxin + 1)
    # br-r37-c1-genbatch (cc): the heap loop never READS the graph (only add_edge),
    # so collect (source, target) into a list and commit ONE add_edges_from at the
    # end instead of a per-edge add_edge PyO3 crossing — byte-identical edge order.
    # 0.51x -> 1.34x (beats nx). On the "Non-digraphical" raise the graph is
    # discarded by the caller, so deferring the edge commit past the raise is safe.
    _edges = []
    while stubheap:
        freeout, freein, target = _heappop(stubheap)
        freein *= -1
        if freein > len(stubheap) + len(zeroheap):
            raise NetworkXError("Non-digraphical integer sequence")

        modified_len = 0
        for _ in range(freein):
            if zeroheap and (not stubheap or stubheap[0][0] > zeroheap[0][0]):
                stubout, source = _heappop(zeroheap)
                stubin = 0
            else:
                stubout, stubin, source = _heappop(stubheap)
            if stubout == 0:
                raise NetworkXError("Non-digraphical integer sequence")
            _edges.append((source, target))
            if stubout + 1 < 0 or stubin < 0:
                modified[modified_len] = (stubout + 1, stubin, source)
                modified_len += 1

        for i in range(modified_len):
            stub = modified[i]
            if stub[1] < 0:
                _heappush(stubheap, stub)
            else:
                _heappush(zeroheap, (stub[0], stub[2]))
        if freeout < 0:
            _heappush(zeroheap, (freeout, target))

    graph.add_edges_from(_edges)
    return graph


# stochastic_block_model, planted_partition_graph, gaussian_random_partition_graph,
# relaxed_caveman_graph, random_partition_graph defined earlier as standalone


__all__ = [
    "__version__",
    # Graph classes
    "Graph",
    "DiGraph",
    "MultiGraph",
    "MultiDiGraph",
    # Utilities
    "relabel_nodes",
    "to_numpy_array",
    "from_numpy_array",
    "to_scipy_sparse_array",
    "from_scipy_sparse_array",
    "from_dict_of_dicts",
    "from_dict_of_lists",
    "from_edgelist",
    "from_pandas_adjacency",
    "from_pandas_edgelist",
    "from_prufer_sequence",
    "from_nested_tuple",
    "to_dict_of_dicts",
    "to_dict_of_lists",
    "to_edgelist",
    "to_pandas_adjacency",
    "to_pandas_edgelist",
    "to_prufer_sequence",
    "to_nested_tuple",
    "cytoscape_data",
    "cytoscape_graph",
    "attr_sparse_matrix",
    "to_networkx_graph",
    "modularity_matrix",
    "directed_modularity_matrix",
    "modularity_spectrum",
    "prominent_group",
    "within_inter_cluster",
    "gnc_graph",
    "gnr_graph",
    "fast_gnp_random_graph",
    "directed_configuration_model",
    "directed_joint_degree_graph",
    "joint_degree_graph",
    "expected_degree_graph",
    "directed_havel_hakimi_graph",
    "stochastic_block_model",
    "planted_partition_graph",
    "gaussian_random_partition_graph",
    "relaxed_caveman_graph",
    "random_partition_graph",
    "convert_node_labels_to_integers",
    # Exceptions
    "HasACycle",
    "NetworkXAlgorithmError",
    "NetworkXError",
    "NetworkXException",
    "NetworkXNoCycle",
    "NetworkXNoPath",
    "NetworkXNotImplemented",
    "NetworkXPointlessConcept",
    "NetworkXTreewidthBoundExceeded",
    "NetworkXUnbounded",
    "NetworkXUnfeasible",
    "NotATree",
    "NodeNotFound",
    "PowerIterationFailedConvergence",
    # Algorithms — shortest path
    "average_shortest_path_length",
    "bellman_ford_path",
    "dijkstra_path",
    "has_path",
    "multi_source_dijkstra",
    "shortest_path",
    "shortest_path_length",
    # Algorithms — connectivity
    "articulation_points",
    "bridges",
    "connected_components",
    "edge_connectivity",
    "is_connected",
    "minimum_node_cut",
    "node_connectivity",
    "number_connected_components",
    # Algorithms — centrality
    "average_neighbor_degree",
    "betweenness_centrality",
    "closeness_centrality",
    "degree_assortativity_coefficient",
    "degree_centrality",
    "edge_betweenness_centrality",
    "eigenvector_centrality",
    "harmonic_centrality",
    "hits",
    "katz_centrality",
    "katz_centrality_many",
    "pagerank",
    "pagerank_many",
    "voterank",
    # Algorithms — clustering
    "average_clustering",
    "clustering",
    "find_cliques",
    "square_clustering",
    "transitivity",
    "triangles",
    # Algorithms — matching
    "max_weight_matching",
    "maximal_matching",
    "min_edge_cover",
    "min_weight_matching",
    # Algorithms — flow
    "maximum_flow",
    "maximum_flow_value",
    "minimum_cut",
    "minimum_cut_value",
    # Algorithms — distance measures
    "center",
    "density",
    "diameter",
    "eccentricity",
    "periphery",
    "radius",
    # Algorithms — tree, forest, bipartite, coloring, core
    # br-r37-c1-bipx-removed: bipartite_sets / bipartite_density
    # are only at nx.bipartite, not nx top-level; not exported.
    # br-r37-c1-bia-removed: biadjacency_matrix /
    # from_biadjacency_matrix are only at nx.bipartite, not nx
    # top-level; not exported.
    "projected_graph",
    "core_number",
    "EdgePartition",
    "SpanningTreeIterator",
    "ArborescenceIterator",
    "greedy_color",
    "is_bipartite",
    "is_forest",
    "is_tree",
    "maximum_branching",
    "maximum_spanning_arborescence",
    "number_of_spanning_trees",
    "minimum_spanning_edges",
    "minimum_branching",
    "minimum_spanning_arborescence",
    "minimum_spanning_tree",
    "partition_spanning_tree",
    "random_spanning_tree",
    # Algorithms — Euler
    "eulerian_circuit",
    "eulerian_path",
    "has_eulerian_path",
    "is_eulerian",
    "is_semieulerian",
    # Algorithms — paths and cycles
    "all_shortest_paths",
    "all_simple_paths",
    "cycle_basis",
    # Algorithms — graph operators
    "complement",
    # Algorithms — efficiency
    "efficiency",
    "global_efficiency",
    "local_efficiency",
    "tree_broadcast_center",
    "tree_broadcast_time",
    # Algorithms — reciprocity
    "overall_reciprocity",
    "reciprocity",
    # Algorithms — Wiener index
    "wiener_index",
    # Algorithms — trees
    "maximum_spanning_edges",
    "maximum_spanning_tree",
    # Algorithms — condensation
    "condensation",
    # Algorithms — all-pairs shortest paths
    "all_pairs_shortest_path",
    "all_pairs_shortest_path_length",
    "shortest_path_length_matrix",
    # Algorithms — graph predicates & utilities
    "is_empty",
    "non_neighbors",
    "number_of_cliques",
    "all_triangles",
    "node_clique_number",
    "enumerate_all_cliques",
    "find_cliques_recursive",
    "chordal_graph_cliques",
    "chordal_graph_treewidth",
    "make_max_clique_graph",
    "ring_of_cliques",
    # Classic graph generators
    "balanced_tree",
    "barbell_graph",
    "bull_graph",
    "chvatal_graph",
    "cubical_graph",
    "desargues_graph",
    "diamond_graph",
    "dodecahedral_graph",
    "frucht_graph",
    "heawood_graph",
    "house_graph",
    "house_x_graph",
    "icosahedral_graph",
    "krackhardt_kite_graph",
    "moebius_kantor_graph",
    "octahedral_graph",
    "pappus_graph",
    "petersen_graph",
    "sedgewick_maze_graph",
    "tetrahedral_graph",
    "truncated_cube_graph",
    "truncated_tetrahedron_graph",
    "tutte_graph",
    "hoffman_singleton_graph",
    "generalized_petersen_graph",
    "wheel_graph",
    "ladder_graph",
    "circular_ladder_graph",
    "lollipop_graph",
    "tadpole_graph",
    "turan_graph",
    "windmill_graph",
    "hypercube_graph",
    "complete_bipartite_graph",
    "complete_multipartite_graph",
    "grid_2d_graph",
    "null_graph",
    "trivial_graph",
    "binomial_tree",
    "full_rary_tree",
    "circulant_graph",
    "kneser_graph",
    "paley_graph",
    "chordal_cycle_graph",
    # Algorithms — single-source shortest paths
    "single_source_shortest_path",
    "single_source_shortest_path_length",
    # Algorithms — dominating set
    "dominating_set",
    "is_dominating_set",
    # Algorithms — community detection
    # br-r37-c1-ecua7: modularity removed from top-level __all__ to
    # mirror nx's namespace contract (nx.modularity raises
    # AttributeError; the function lives at nx.community.modularity).
    # Attribute helpers
    "set_node_attributes",
    "get_node_attributes",
    "set_edge_attributes",
    "get_edge_attributes",
    # Utility functions
    "create_empty_copy",
    "number_of_selfloops",
    "selfloop_edges",
    "nodes_with_selfloops",
    "all_neighbors",
    "voronoi_cells",
    "stoer_wagner",
    "dedensify",
    "quotient_graph",
    "snap_aggregation",
    "full_join",
    "identified_nodes",
    "inverse_line_graph",
    "add_path",
    "add_cycle",
    "add_star",
    # Graph products
    "cartesian_product",
    "tensor_product",
    "strong_product",
    "adjacency_matrix",
    "has_bridges",
    "local_bridges",
    "minimum_edge_cut",
    "stochastic_graph",
    "ego_graph",
    "k_core",
    "k_shell",
    "k_crust",
    "k_corona",
    "line_graph",
    "power",
    "disjoint_union",
    "compose_all",
    "union_all",
    # Spectral
    "laplacian_matrix",
    "normalized_laplacian_matrix",
    "laplacian_spectrum",
    "adjacency_spectrum",
    "algebraic_connectivity",
    "fiedler_vector",
    "incidence_matrix",
    "karate_club_graph",
    "florentine_families_graph",
    "caveman_graph",
    "connected_caveman_graph",
    # br-r37-c1-rt-removed: ``random_tree`` was removed from nx in
    # 3.4 (replaced by ``random_labeled_tree``); not exported.
    "constraint",
    "effective_size",
    "dispersion",
    "closeness_vitality",
    "spectral_ordering",
    "bellman_ford_predecessor_and_distance",
    "communicability",
    "subgraph_centrality",
    "degree_mixing_dict",
    "degree_mixing_matrix",
    "numeric_assortativity_coefficient",
    "attribute_assortativity_coefficient",
    "intersection_all",
    "disjoint_union_all",
    "rescale_layout",
    "freeze",
    "is_frozen",
    "binomial_graph",
    "gnm_random_graph",
    "check_planarity",
    "all_simple_edge_paths",
    "chain_decomposition",
    "bidirectional_dijkstra",
    "attribute_mixing_dict",
    "attribute_mixing_matrix",
    # Additional generators
    "dense_gnm_random_graph",
    "random_labeled_tree",
    # Additional conversion
    "adjacency_data",
    "adjacency_graph",
    # Additional algorithms
    "load_centrality",
    "degree_pearson_correlation_coefficient",
    "generalized_degree",
    "is_semiconnected",
    "all_pairs_node_connectivity",
    "contracted_nodes",
    "contracted_edge",
    "is_directed",
    "configuration_model",
    "havel_hakimi_graph",
    "degree_sequence_tree",
    "common_neighbor_centrality",
    "all_topological_sorts",
    "lowest_common_ancestor",
    "all_pairs_lowest_common_ancestor",
    "transitive_closure_dag",
    "dag_to_branching",
    # Additional shortest path
    "dijkstra_predecessor_and_distance",
    "multi_source_dijkstra_path",
    "multi_source_dijkstra_path_length",
    "single_source_all_shortest_paths",
    "all_pairs_all_shortest_paths",
    "reconstruct_path",
    "generate_random_paths",
    "johnson",
    # Spectral & Matrix
    "bethe_hessian_matrix",
    "bethe_hessian_spectrum",
    "google_matrix",
    "normalized_laplacian_spectrum",
    "directed_laplacian_matrix",
    "directed_combinatorial_laplacian_matrix",
    "attr_matrix",
    # Flow algorithms
    "cost_of_flow",
    "min_cost_flow",
    "min_cost_flow_cost",
    "max_flow_min_cost",
    "capacity_scaling",
    "network_simplex",
    "flow_hierarchy",
    # Triads
    "triadic_census",
    "all_triads",
    "triad_type",
    "is_triad",
    "triads_by_type",
    "double_edge_swap",
    "directed_edge_swap",
    # Graph predicates
    "is_valid_degree_sequence_erdos_gallai",
    "is_valid_degree_sequence_havel_hakimi",
    "is_valid_joint_degree",
    "is_strongly_regular",
    "is_at_free",
    "is_d_separator",
    "is_minimal_d_separator",
    # Graph products
    "corona_product",
    "modular_product",
    "rooted_product",
    "lexicographic_product",
    # Advanced metrics
    "estrada_index",
    "gutman_index",
    "schultz_index",
    "hyper_wiener_index",
    "resistance_distance",
    "kemeny_constant",
    "non_randomness",
    "sigma",
    "omega",
    # Connectivity & disjoint paths
    "edge_disjoint_paths",
    "node_disjoint_paths",
    "all_node_cuts",
    "connected_dominating_set",
    "is_connected_dominating_set",
    "is_kl_connected",
    "kl_connected_subgraph",
    "connected_double_edge_swap",
    # Advanced centrality
    "current_flow_betweenness_centrality",
    "edge_current_flow_betweenness_centrality",
    "approximate_current_flow_betweenness_centrality",
    "current_flow_closeness_centrality",
    "betweenness_centrality_subset",
    "edge_betweenness_centrality_subset",
    "edge_load_centrality",
    "laplacian_centrality",
    "percolation_centrality",
    "information_centrality",
    "second_order_centrality",
    "subgraph_centrality_exp",
    "communicability_betweenness_centrality",
    "trophic_levels",
    "trophic_differences",
    "trophic_incoherence_parameter",
    "group_betweenness_centrality",
    "group_closeness_centrality",
    # Traversal extras
    "bfs_beam_edges",
    "bfs_labeled_edges",
    "dfs_labeled_edges",
    "generic_bfs_edges",
    # Utility extras A
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "node_attribute_xy",
    "node_degree_xy",
    "number_of_walks",
    "recursive_simple_cycles",
    # Utility extras B
    "remove_node_attributes",
    "remove_edge_attributes",
    "floyd_warshall_numpy",
    "harmonic_diameter",
    "global_parameters",
    "intersection_array",
    # Small utilities
    "eulerize",
    "moral_graph",
    "equivalence_classes",
    "minimum_cycle_basis",
    "chordless_cycles",
    "to_undirected",
    "to_directed",
    "reverse",
    "nodes",
    "edges",
    "degree",
    "number_of_nodes",
    "number_of_edges",
    # Conversion extras
    # Community extras
    # exported earlier to preserve stable __all__ ordering
    # Predicates extras
    "find_minimal_d_separator",
    "is_valid_directed_joint_degree",
    # Social datasets & misc generators
    "les_miserables_graph",
    "davis_southern_women_graph",
    "triad_graph",
    "weisfeiler_lehman_graph_hash",
    "weisfeiler_lehman_subgraph_hashes",
    "lexicographical_topological_sort",
    # Structural decomposition
    "k_truss",
    "onion_layers",
    "k_edge_components",
    "k_edge_subgraphs",
    "spectral_bisection",
    "find_induced_nodes",
    "k_edge_augmentation",
    # Stochastic block models
    # exported earlier to preserve stable __all__ ordering
    # Lattice graphs
    # exported earlier to preserve stable __all__ ordering
    # Centrality extras
    "eigenvector_centrality_numpy",
    "katz_centrality_numpy",
    "incremental_closeness_centrality",
    "current_flow_betweenness_centrality_subset",
    "edge_current_flow_betweenness_centrality_subset",
    # Geometric graphs
    "random_geometric_graph",
    "soft_random_geometric_graph",
    "waxman_graph",
    "geographical_threshold_graph",
    "thresholded_random_geometric_graph",
    "navigable_small_world_graph",
    "geometric_edges",
    # Coloring & planarity
    "equitable_color",
    "chromatic_polynomial",
    "combinatorial_embedding_to_pos",
    # Isomorphism VF2/VF2++
    "GraphMatcher",
    "DiGraphMatcher",
    "MultiGraphMatcher",
    "MultiDiGraphMatcher",
    "ISMAGS",
    "TimeRespectingGraphMatcher",
    "TimeRespectingDiGraphMatcher",
    "isomorphism",
    "vf2pp_is_isomorphic",
    "vf2pp_isomorphism",
    "vf2pp_all_isomorphisms",
    # Tree/forest utilities
    "junction_tree",
    "join_trees",
    "random_unlabeled_tree",
    "random_unlabeled_rooted_tree",
    "random_unlabeled_rooted_forest",
    "tree_data",
    "tree_graph",
    "complete_to_chordal_graph",
    # Structural generators
    "hkn_harary_graph",
    "hnm_harary_graph",
    "gomory_hu_tree",
    "visibility_graph",
    "random_k_out_graph",
    # Similarity
    "simrank_similarity",
    "panther_similarity",
    "optimal_edit_paths",
    "optimize_edit_paths",
    # Final parity batch
    "subgraph",
    "induced_subgraph",
    "edge_subgraph",
    "subgraph_view",
    "restricted_view",
    "reverse_view",
    "neighbors",
    "config",
    "describe",
    "mixing_dict",
    "local_constraint",
    "apply_matplotlib_colors",
    "communicability_exp",
    "panther_vector_similarity",
    "effective_graph_resistance",
    "graph_edit_distance",
    "optimize_graph_edit_distance",
    "cd_index",
    "goldberg_radzik",
    "parse_graphml",
    "generate_graphml",
    "mycielskian",
    "mycielski_graph",
    "dorogovtsev_goltsev_mendes_graph",
    "prefix_tree",
    "prefix_tree_recursive",
    "nonisomorphic_trees",
    "number_of_nonisomorphic_trees",
    "random_lobster",
    "random_lobster_graph",
    "random_shell_graph",
    "random_clustered_graph",
    "random_cograph",
    "random_degree_sequence_graph",
    "random_internet_as_graph",
    "random_reference",
    "random_labeled_rooted_tree",
    "random_labeled_rooted_forest",
    "partial_duplication_graph",
    "duplication_divergence_graph",
    "interval_graph",
    "k_random_intersection_graph",
    "uniform_random_intersection_graph",
    "general_random_intersection_graph",
    "geometric_soft_configuration_graph",
    "graph_atlas",
    "graph_atlas_g",
    "find_asteroidal_triple",
    "is_perfect_graph",
    "is_regular_expander",
    "maybe_regular_expander",
    "maybe_regular_expander_graph",
    "random_regular_expander_graph",
    "make_clique_bipartite",
    "k_components",
    "k_factor",
    "spectral_graph_forge",
    "tutte_polynomial",
    "tree_all_pairs_lowest_common_ancestor",
    "random_kernel_graph",
    # Algorithms — graph operators
    "union",
    "intersection",
    "compose",
    "difference",
    "symmetric_difference",
    "degree_histogram",
    # Algorithms — transitive closure/reduction
    "transitive_closure",
    "transitive_reduction",
    # Algorithms — graph metrics
    "average_degree_connectivity",
    "rich_club_coefficient",
    "s_metric",
    "volume",
    "boundary_expansion",
    "conductance",
    "edge_expansion",
    "node_expansion",
    "mixing_expansion",
    "non_edges",
    "average_node_connectivity",
    "is_k_edge_connected",
    "all_pairs_dijkstra",
    # Algorithms — strongly connected components
    "strongly_connected_components",
    "number_strongly_connected_components",
    "is_strongly_connected",
    # Algorithms — weakly connected components
    "weakly_connected_components",
    "number_weakly_connected_components",
    "is_weakly_connected",
    # Algorithms — link prediction
    "common_neighbors",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "resource_allocation_index",
    # Algorithms — traversal (BFS)
    "bfs_edges",
    "bfs_layers",
    "bfs_predecessors",
    "bfs_successors",
    "bfs_tree",
    "descendants_at_distance",
    # Algorithms — traversal (DFS)
    "dfs_edges",
    "dfs_postorder_nodes",
    "dfs_predecessors",
    "dfs_preorder_nodes",
    "dfs_successors",
    "dfs_tree",
    # Algorithms — DAG
    "ancestors",
    "dag_longest_path",
    "dag_longest_path_length",
    "descendants",
    "is_directed_acyclic_graph",
    "topological_sort",
    "topological_generations",
    # Algorithms — graph isomorphism
    "is_isomorphic",
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
    # Algorithms — A* shortest path
    "astar_path",
    "astar_path_length",
    "shortest_simple_paths",
    # Algorithms — approximation
    "maximal_independent_set",
    "spanner",
    # Algorithms — tree recognition
    "is_arborescence",
    "is_branching",
    # Algorithms — isolates
    "is_isolate",
    "isolates",
    "number_of_isolates",
    # Algorithms — boundary
    "cut_size",
    "edge_boundary",
    "node_boundary",
    "normalized_cut_size",
    # Algorithms — path validation
    "is_simple_path",
    # Algorithms — matching validators
    "is_matching",
    "is_maximal_matching",
    "is_perfect_matching",
    # Algorithms — cycles
    "simple_cycles",
    "find_cycle",
    "girth",
    "find_negative_cycle",
    # Algorithms — graph predicates
    "is_graphical",
    "is_digraphical",
    "is_multigraphical",
    "is_pseudographical",
    "is_regular",
    "is_k_regular",
    "is_tournament",
    "is_weighted",
    "is_negatively_weighted",
    "is_path",
    "is_distance_regular",
    # Algorithms — traversal additional
    "edge_bfs",
    "edge_dfs",
    # Algorithms — matching additional
    "is_edge_cover",
    "max_weight_clique",
    # Algorithms — DAG additional
    "is_aperiodic",
    "antichains",
    "immediate_dominators",
    "dominance_frontiers",
    # Algorithms — additional shortest path
    "dijkstra_path_length",
    "bellman_ford_path_length",
    "single_source_dijkstra",
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
    "single_source_bellman_ford",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
    "single_target_shortest_path",
    "single_target_shortest_path_length",
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "floyd_warshall",
    "floyd_warshall_predecessor_and_distance",
    "bidirectional_shortest_path",
    "negative_edge_cycle",
    "predecessor",
    "path_weight",
    # Algorithms — additional centrality
    "in_degree_centrality",
    "out_degree_centrality",
    "local_reaching_centrality",
    "global_reaching_centrality",
    "group_degree_centrality",
    "group_in_degree_centrality",
    "group_out_degree_centrality",
    # Algorithms — component
    "node_connected_component",
    "is_biconnected",
    "biconnected_components",
    "biconnected_component_edges",
    "kosaraju_strongly_connected_components",
    "attracting_components",
    "number_attracting_components",
    "is_attracting_component",
    # Algorithms — planarity
    "is_planar",
    "is_chordal",
    # Algorithms — barycenter
    "barycenter",
    # Generators — classic
    "complete_graph",
    "cycle_graph",
    "empty_graph",
    "path_graph",
    "star_graph",
    # Generators — random
    "gnp_random_graph",
    "watts_strogatz_graph",
    "erdos_renyi_graph",
    "newman_watts_strogatz_graph",
    "connected_watts_strogatz_graph",
    "random_regular_graph",
    "powerlaw_cluster_graph",
    "barabasi_albert_graph",
    "dual_barabasi_albert_graph",
    "extended_barabasi_albert_graph",
    "scale_free_graph",
    "random_powerlaw_tree",
    "random_powerlaw_tree_sequence",
    "gn_graph",
    "LCF_graph",
    "LFR_benchmark_graph",
    "hexagonal_lattice_graph",
    "triangular_lattice_graph",
    "grid_graph",
    "lattice_reference",
    "margulis_gabber_galil_graph",
    "sudoku_graph",
    # Read/write — graph I/O
    "node_link_data",
    "node_link_graph",
    "read_adjlist",
    "read_edgelist",
    "read_graphml",
    "write_adjlist",
    "write_edgelist",
    "write_graphml",
    "read_gml",
    "write_gml",
    "from_graph6_bytes",
    "from_sparse6_bytes",
    "generate_adjlist",
    "generate_edgelist",
    "generate_gexf",
    "generate_gml",
    "generate_multiline_adjlist",
    "generate_pajek",
    "parse_adjlist",
    "parse_edgelist",
    "parse_gml",
    "parse_leda",
    "parse_multiline_adjlist",
    "parse_pajek",
    "read_gexf",
    "read_graph6",
    "read_leda",
    "read_multiline_adjlist",
    "read_pajek",
    "read_sparse6",
    "read_weighted_edgelist",
    "relabel_gexf_graph",
    "to_graph6_bytes",
    "to_sparse6_bytes",
    "write_gexf",
    "write_graph6",
    "write_graphml_lxml",
    "write_graphml_xml",
    "write_multiline_adjlist",
    "write_pajek",
    "write_sparse6",
    "write_weighted_edgelist",
    # Drawing
    "display",
    "draw",
    "draw_bipartite",
    "draw_circular",
    "draw_forceatlas2",
    "draw_kamada_kawai",
    "draw_networkx",
    "draw_networkx_edge_labels",
    "draw_networkx_edges",
    "draw_networkx_labels",
    "draw_networkx_nodes",
    "draw_planar",
    "draw_random",
    "draw_shell",
    "draw_spectral",
    "draw_spring",
    "generate_network_text",
    "arf_layout",
    "bfs_layout",
    "bipartite_layout",
    "circular_layout",
    "forceatlas2_layout",
    "fruchterman_reingold_layout",
    "kamada_kawai_layout",
    "multipartite_layout",
    "planar_layout",
    "random_layout",
    "rescale_layout_dict",
    "shell_layout",
    "spiral_layout",
    "spectral_layout",
    "spring_layout",
    "to_latex",
    "to_latex_raw",
    "write_latex",
    "write_network_text",
    "compatibility_mode",
    "get_compatibility_mode",
    "set_compatibility_mode",
    "decision_records",
    "drain_decision_records",
    "read_json_graph",
]

import networkx as _nx


class _FnxConfigContext:
    def __init__(self, wrapper, kwargs):
        self._wrapper = wrapper
        self._kwargs = kwargs
        self._old_thread_mode = None
        self._has_mode = "compatibility_mode" in kwargs
        self._mode_val = kwargs.get("compatibility_mode")
        self._nx_kwargs = {k: v for k, v in kwargs.items() if k != "compatibility_mode"}
        self._nx_ctx = None

    def __enter__(self):
        if self._nx_kwargs:
            self._nx_ctx = self._wrapper._nx_config(**self._nx_kwargs)
            self._nx_ctx.__enter__()
        if self._has_mode:
            self._old_thread_mode = _rust_get_thread_compatibility_mode()
            _rust_set_thread_compatibility_mode(self._mode_val)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._has_mode:
                _rust_set_thread_compatibility_mode(self._old_thread_mode)
        finally:
            if self._nx_ctx is not None:
                self._nx_ctx.__exit__(exc_type, exc_val, exc_tb)


class _FnxConfigWrapper:
    """Wrapper around NetworkX's config object that exposes `compatibility_mode`."""

    def __init__(self, nx_config):
        self._nx_config = nx_config

    def __getattr__(self, name):
        if name == "compatibility_mode":
            return _rust_get_compatibility_mode()
        return getattr(self._nx_config, name)

    def __setattr__(self, name, value):
        if name == "_nx_config":
            super().__setattr__(name, value)
        elif name == "compatibility_mode":
            _rust_set_compatibility_mode(value)
        else:
            setattr(self._nx_config, name, value)

    def __getitem__(self, key):
        if key == "compatibility_mode":
            return _rust_get_compatibility_mode()
        return self._nx_config[key]

    def __setitem__(self, key, value):
        if key == "compatibility_mode":
            _rust_set_compatibility_mode(value)
        else:
            self._nx_config[key] = value

    def __call__(self, **kwargs):
        return _FnxConfigContext(self, kwargs)

    def __repr__(self):
        return repr(self._nx_config)


config = _FnxConfigWrapper(_nx.config)
