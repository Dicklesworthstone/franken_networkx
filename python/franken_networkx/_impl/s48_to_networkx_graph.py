

def to_networkx_graph(data, create_using=None, multigraph_input=False):
    """Convert supported input data to a graph."""
    if hasattr(data, "adj"):
        try:
            result = from_dict_of_dicts(
                data.adj,
                create_using=create_using,
                multigraph_input=data.is_multigraph(),
            )
            result.graph.update(data.graph)
            for node, attrs in data.nodes(data=True):
                result.nodes[node].update(attrs)
            return result
        except Exception as err:
            raise NetworkXError("Input is not a correct NetworkX graph.") from err

    if isinstance(data, dict):
        try:
            return from_dict_of_dicts(
                data,
                create_using=create_using,
                multigraph_input=multigraph_input,
            )
        except Exception as err1:
            if isinstance(multigraph_input, bool) and multigraph_input:
                raise NetworkXError(
                    f"converting multigraph_input raised:\n{type(err1)}: {err1}"
                )
            try:
                return from_dict_of_lists(data, create_using=create_using)
            except Exception as err2:
                raise TypeError("Input is not known type.") from err2

    if isinstance(data, (list, tuple, _Iterator)):
        try:
            return from_edgelist(data, create_using=create_using)
        except Exception:
            pass

    try:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            if data.shape[0] == data.shape[1]:
                try:
                    return from_pandas_adjacency(data, create_using=create_using)
                except Exception as err:
                    msg = "Input is not a correct Pandas DataFrame adjacency matrix."
                    raise NetworkXError(msg) from err
            else:
                try:
                    return from_pandas_edgelist(
                        data,
                        edge_attr=True,
                        create_using=create_using,
                    )
                except Exception as err:
                    msg = "Input is not a correct Pandas DataFrame edge-list."
                    raise NetworkXError(msg) from err
    except ImportError:
        pass

    try:
        import numpy as np

        if isinstance(data, np.ndarray):
            try:
                return from_numpy_array(data, create_using=create_using)
            except Exception as err:
                raise NetworkXError("Failed to interpret array as an adjacency matrix.") from err
    except ImportError:
        pass

    try:
        if hasattr(data, "format"):
            return from_scipy_sparse_array(data, create_using=create_using)
    except Exception as err:
        raise NetworkXError("Input is not a correct scipy sparse array type.") from err

    if isinstance(data, (_Collection, _Generator, _Iterator)):
        try:
            return from_edgelist(data, create_using=create_using)
        except Exception as err:
            raise NetworkXError("Input is not a valid edge list") from err

    raise NetworkXError("Input is not a known data type for conversion.")


def prominent_group(
    G,
    k,
    weight=None,
    C=None,
    endpoints=False,
    normalized=True,
    greedy=False,
):
    """Return a prominent group of k nodes maximizing group betweenness.

    br-r37-c1-64xcg: networkx's algorithm (Puzis et al.'s depth-first branch
    and bound over the path-betweenness matrix), verbatim. fnx ran its own - a
    greedy scan for k > 5, every k-subset otherwise - which, on a tie of group
    betweenness, returned another group than networkx's search order finds;
    and it read ``C`` as the candidate list, where networkx's ``C`` is the set
    of nodes EXCLUDED from the group. The decision tree is a dict of node
    records (networkx keeps them as node attributes of an nx.Graph it never
    queries as a graph).
    """
    from copy import deepcopy

    import numpy as np
    import pandas as pd

    if C is not None:
        C = set(C)
        if C - set(G.nodes):
            raise NodeNotFound(f"The node(s) {C - set(G.nodes)} are in C but not in G.")
        nodes = list(set(G.nodes) - C)
    else:
        nodes = list(G.nodes)
    DF_tree = {}
    PB, sigma, D = _prominent_group_preprocessing(G, nodes, weight)
    betweenness = pd.DataFrame.from_dict(PB)
    if C is not None:
        for node in C:
            betweenness = betweenness.drop(index=node)
            betweenness = betweenness.drop(columns=node)
    CL = [node for _, node in sorted(zip(np.diag(betweenness), nodes), reverse=True)]
    max_GBC = 0
    max_group = []
    DF_tree[1] = {
        "CL": CL,
        "betweenness": betweenness,
        "GBC": 0,
        "GM": [],
        "sigma": sigma,
        "cont": dict(zip(nodes, np.diag(betweenness))),
    }
    DF_tree[1]["heu"] = 0
    for i in range(k):
        DF_tree[1]["heu"] += DF_tree[1]["cont"][DF_tree[1]["CL"][i]]

    def _heuristic(root):
        node_p = len(DF_tree) + 1
        node_m = len(DF_tree) + 2
        added_node = DF_tree[root]["CL"][0]
        DF_tree[node_p] = deepcopy(DF_tree[root])
        DF_tree[node_p]["GM"].append(added_node)
        DF_tree[node_p]["GBC"] += DF_tree[node_p]["cont"][added_node]
        root_node = DF_tree[root]
        for x in nodes:
            for y in nodes:
                dxvy = 0
                dxyv = 0
                dvxy = 0
                if not (
                    root_node["sigma"][x][y] == 0
                    or root_node["sigma"][x][added_node] == 0
                    or root_node["sigma"][added_node][y] == 0
                ):
                    if D[x][added_node] == D[x][y] + D[y][added_node]:
                        dxyv = (
                            root_node["sigma"][x][y]
                            * root_node["sigma"][y][added_node]
                            / root_node["sigma"][x][added_node]
                        )
                    if D[x][y] == D[x][added_node] + D[added_node][y]:
                        dxvy = (
                            root_node["sigma"][x][added_node]
                            * root_node["sigma"][added_node][y]
                            / root_node["sigma"][x][y]
                        )
                    if D[added_node][y] == D[added_node][x] + D[x][y]:
                        dvxy = (
                            root_node["sigma"][added_node][x]
                            * root_node["sigma"][x][y]
                            / root_node["sigma"][added_node][y]
                        )
                DF_tree[node_p]["sigma"][x][y] = root_node["sigma"][x][y] * (1 - dxvy)
                DF_tree[node_p]["betweenness"].loc[y, x] = (
                    root_node["betweenness"][x][y] - root_node["betweenness"][x][y] * dxvy
                )
                if y != added_node:
                    DF_tree[node_p]["betweenness"].loc[y, x] -= (
                        root_node["betweenness"][x][added_node] * dxyv
                    )
                if x != added_node:
                    DF_tree[node_p]["betweenness"].loc[y, x] -= (
                        root_node["betweenness"][added_node][y] * dvxy
                    )
        DF_tree[node_p]["CL"] = [
            node
            for _, node in sorted(
                zip(np.diag(DF_tree[node_p]["betweenness"]), nodes), reverse=True
            )
            if node not in DF_tree[node_p]["GM"]
        ]
        DF_tree[node_p]["cont"] = dict(zip(nodes, np.diag(DF_tree[node_p]["betweenness"])))
        DF_tree[node_p]["heu"] = 0
        for i in range(k - len(DF_tree[node_p]["GM"])):
            DF_tree[node_p]["heu"] += DF_tree[node_p]["cont"][DF_tree[node_p]["CL"][i]]
        if not greedy:
            DF_tree[node_m] = deepcopy(DF_tree[root])
            DF_tree[node_m]["CL"].pop(0)
            DF_tree[node_m]["cont"].pop(added_node)
            DF_tree[node_m]["heu"] = 0
            for i in range(k - len(DF_tree[node_m]["GM"])):
                DF_tree[node_m]["heu"] += DF_tree[node_m]["cont"][DF_tree[node_m]["CL"][i]]
        else:
            node_m = None
        return node_p, node_m

    def _dfbnb(max_GBC, root, max_group):
        if len(DF_tree[root]["GM"]) == k and DF_tree[root]["GBC"] > max_GBC:
            return DF_tree[root]["GBC"], DF_tree[root]["GM"]
        if (
            len(DF_tree[root]["GM"]) == k
            or len(DF_tree[root]["CL"]) <= k - len(DF_tree[root]["GM"])
            or DF_tree[root]["GBC"] + DF_tree[root]["heu"] <= max_GBC
        ):
            return max_GBC, max_group
        node_p, node_m = _heuristic(root)
        if greedy:
            max_GBC, max_group = _dfbnb(max_GBC, node_p, max_group)
        elif (
            DF_tree[node_p]["GBC"] + DF_tree[node_p]["heu"]
            > DF_tree[node_m]["GBC"] + DF_tree[node_m]["heu"]
        ):
            max_GBC, max_group = _dfbnb(max_GBC, node_p, max_group)
            max_GBC, max_group = _dfbnb(max_GBC, node_m, max_group)
        else:
            max_GBC, max_group = _dfbnb(max_GBC, node_m, max_group)
            max_GBC, max_group = _dfbnb(max_GBC, node_p, max_group)
        return max_GBC, max_group

    max_GBC, max_group = _dfbnb(max_GBC, 1, max_group)
    v = len(G)
    if not endpoints:
        scale = 0
        if G.is_directed():
            if is_strongly_connected(G):
                scale = k * (2 * v - k - 1)
        elif is_connected(G):
            scale = k * (2 * v - k - 1)
        if scale == 0:
            for group_node1 in max_group:
                for node in D[group_node1]:
                    if node != group_node1:
                        if node in max_group:
                            scale += 1
                        else:
                            scale += 2
        max_GBC -= scale
    if normalized:
        scale = 1 / ((v - k) * (v - k - 1))
        max_GBC *= scale
    elif not G.is_directed():
        max_GBC /= 2
    max_GBC = float(f"{max_GBC:.2f}")
    return max_GBC, max_group


def _prominent_group_preprocessing(G, set_v, weight):
    """networkx's centrality.group._group_preprocessing, verbatim (br-r37-c1-64xcg)."""
    sigma = {}
    delta = {}
    D = {}
    betweenness = dict.fromkeys(G, 0)
    for s in G:
        if weight is None:
            S, P, sigma[s], D[s] = _single_source_shortest_path_basic_local(G, s)
        else:
            S, P, sigma[s], D[s] = _single_source_dijkstra_path_basic_local(G, s, weight)
        betweenness, delta[s] = _accumulate_endpoints_local(betweenness, S, P, sigma[s], s)
        for i in delta[s]:
            if s != i:
                delta[s][i] += 1
            if weight is not None:
                sigma[s][i] = sigma[s][i] / 2
    PB = dict.fromkeys(G)
    for group_node1 in set_v:
        PB[group_node1] = dict.fromkeys(G, 0.0)
        for group_node2 in set_v:
            if group_node2 not in D[group_node1]:
                continue
            for node in G:
                if group_node2 in D[node] and group_node1 in D[node]:
                    if D[node][group_node2] == D[node][group_node1] + D[group_node1][group_node2]:
                        PB[group_node1][group_node2] += (
                            delta[node][group_node2]
                            * sigma[node][group_node1]
                            * sigma[group_node1][group_node2]
                            / sigma[node][group_node2]
                        )
    return PB, sigma, D


def within_inter_cluster(G, ebunch=None, delta=0.001, community="community"):
    """Compute within/inter-cluster common neighbor ratio (WIC measure).

    If u and v are in different communities, score is 0.
    Otherwise, score = |within| / (|inter| + delta) where within are common
    neighbors in the same community as u/v, and inter are those in different.

    br-r37-c1-fa5tf: nx is @not_implemented_for('directed',
    'multigraph'). Type guard fires eagerly (on call) so iteration
    never reaches the per-node community-attr check on multi/
    directed inputs.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if delta <= 0:
        # br-r37-c1-fa5tf: nx raises NetworkXAlgorithmError (not
        # NetworkXError) for this precondition; match exactly.
        raise NetworkXAlgorithmError("Delta must be greater than zero")

    if ebunch is None:
        # Default: all non-existing edges.
        ebunch_iter = non_edges(G)
    else:
        ebunch_iter = ebunch

    adjacency_cache = {}
    community_cache = {}

    def _neighbors(node):
        cached = adjacency_cache.get(node)
        if cached is None:
            cached = set(G.neighbors(node))
            adjacency_cache[node] = cached
        return cached

    def _community_of(node):
        # br-shcomm: nx raises NetworkXAlgorithmError, not NetworkXError,
        # with a specific message. Match the contract so callers catching
        # the algorithm-error base class don't diverge.
        if node in community_cache:
            return community_cache[node]
        attrs = G.nodes[node]
        try:
            value = attrs[community]
        except (KeyError, TypeError) as err:
            raise NetworkXAlgorithmError(
                f"No community information available for Node {node}"
            ) from err
        community_cache[node] = value
        return value

    def _generate():
        for u, v in ebunch_iter:
            cu = _community_of(u)
            cv = _community_of(v)
            if cu != cv:
                yield (u, v, 0)
                continue
            common = (_neighbors(u) & _neighbors(v)) - {u, v}
            within_count = sum(1 for w in common if _community_of(w) == cu)
            inter_count = len(common) - within_count
            yield (u, v, within_count / (inter_count + delta))

    return _generate()


def gnc_graph(n, create_using=None, seed=None):
    """Return a growing network with copying (GNC) digraph."""
    from franken_networkx import _fnx

    # br-r37-c1-ols3t: the kernel draws from an int or streams a random.Random
    # (None is the global random._inst); a numpy-backed seed runs the body.
    kernel_seed = _kernel_seed(seed)
    if kernel_seed is None or create_using is not None:
        # br-r37-c1-cdf1v: networkx's draws on networkx's seed handling - for
        # a numpy-backed seed, or a create_using graph built in place (a copy
        # of the kernel's graph re-derived its predecessor rows). A node's
        # successors are its target's successors then the target, all
        # distinct, so plain lists stand in for G.successors and the edges go
        # in as one batch in networkx's order.
        rng = _generator_random_state(seed)
        G = empty_graph(1, create_using=_checked_directed_create_using(create_using), default=DiGraph)
        succs = [[]]
        edges = []
        for source in range(1, n):
            target = rng.randrange(0, source)
            row = succs[target] + [target]
            succs.append(row)
            edges.extend((source, succ) for succ in row)
        G.add_edges_from(edges)
        return G

    # br-gnrempty: nx.gnc_graph(0) returns a 1-node DiGraph {0} (the seed
    # node before the growth loop); the kernel returned the empty graph.
    if n == 0:
        return empty_graph(1, create_using=DiGraph(), default=DiGraph)
    return _fnx.gnc_graph(n, seed=kernel_seed, create_using=None)


def gnr_graph(n, p, create_using=None, seed=None):
    """Return a growing network with redirection (GNR) digraph."""
    from franken_networkx import _fnx

    # br-r37-c1-ols3t: see gnc_graph.
    kernel_seed = _kernel_seed(seed)
    if kernel_seed is None or create_using is not None:
        # br-r37-c1-cdf1v: networkx's draws on networkx's seed handling (a
        # create_using graph is built in place - see gnc_graph). Every node
        # but 0 has exactly one successor, so a list stands in for
        # next(G.successors(target)) and the edges go in as one batch.
        rng = _generator_random_state(seed)
        G = empty_graph(1, create_using=_checked_directed_create_using(create_using), default=DiGraph)
        succ = [None]
        for source in range(1, n):
            target = rng.randrange(0, source)
            if rng.random() < p and target != 0:
                target = succ[target]
            succ.append(target)
        G.add_edges_from(zip(range(1, n), succ[1:]))
        return G

    # br-gnrempty: see gnc_graph above.
    if n == 0:
        return empty_graph(1, create_using=DiGraph(), default=DiGraph)
    return _fnx.gnr_graph(n, p, seed=kernel_seed, create_using=None)


def dual_barabasi_albert_graph(
    n,
    m1,
    m2,
    p,
    seed=None,
    initial_graph=None,
    *,
    create_using=None,
    backend=None,
    **backend_kwargs,
):
    """Return a dual Barabasi-Albert preferential attachment graph."""
    _validate_backend_dispatch_keywords(
        "dual_barabasi_albert_graph", backend, backend_kwargs
    )
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    target = _empty_graph_from_create_using(create_using, default=Graph)
    if target.is_directed():
        raise NetworkXError("create_using must not be directed")
    if target.is_multigraph():
        raise NetworkXError("create_using must not be a multi-graph")

    if m1 < 1 or m1 >= n:
        raise NetworkXError(
            f"Dual Barabási–Albert must have m1 >= 1 and m1 < n, m1 = {m1}, n = {n}"
        )
    if m2 < 1 or m2 >= n:
        raise NetworkXError(
            f"Dual Barabási–Albert must have m2 >= 1 and m2 < n, m2 = {m2}, n = {n}"
        )
    if p < 0 or p > 1:
        raise NetworkXError(
            f"Dual Barabási–Albert network must have 0 <= p <= 1, p = {p}"
        )

    # br-r37-c1-rustseed (sister): NaN seed must surface nx's
    # ``ValueError("nan cannot be used to generate a random.Random
    # instance")`` rather than silently fall through ``random.Random(NaN)``.
    if isinstance(seed, float) and _math.isnan(seed):
        raise ValueError(
            "nan cannot be used to generate a random.Random instance"
        )

    if p == 1:
        return barabasi_albert_graph(
            n,
            m1,
            seed=seed,
            initial_graph=initial_graph,
            create_using=create_using,
        )
    if p == 0:
        return barabasi_albert_graph(
            n,
            m2,
            seed=seed,
            initial_graph=initial_graph,
            create_using=create_using,
        )

    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: nx's py_random_state
    if initial_graph is None:
        # cc-dualbastarbatch: same lever as barabasi_albert_graph
        # (cc-bastarbatch) — don't pre-build ``star_graph(max(m1,m2))`` then
        # bulk-extend, which makes the final ``add_edges_from`` pay the O(bunch)
        # touches-existing pre-scan against the star even though no attachment
        # edge can touch it (every source is a fresh node > max(m1,m2)). Prepend
        # the star edges to the batch, seed ``repeated_nodes`` from the star's
        # known degree sequence (center 0 has degree mm; each leaf 1..mm degree 1),
        # and build on the EMPTY graph so the scan short-circuits (edge_count == 0)
        # and the fresh-batch fast path applies. Node/edge insertion order (star
        # first, then sources in increasing order) is byte-identical.
        mm = max(m1, m2)
        graph = Graph()
        _edge_accum = [(0, leaf) for leaf in range(1, mm + 1)]
        repeated_nodes = [0] * mm + list(range(1, mm + 1))
        source = mm + 1
    else:
        if len(initial_graph) < max(m1, m2) or len(initial_graph) > n:
            raise NetworkXError(
                f"Barabási–Albert initial graph must have between "
                f"max(m1, m2) = {max(m1, m2)} and n = {n} nodes"
            )
        graph = Graph()
        graph.graph.update(dict(initial_graph.graph))
        for node, attrs in initial_graph.nodes(data=True):
            graph.add_node(node, **dict(attrs))
        for u, v, attrs in initial_graph.edges(data=True):
            graph.add_edge(u, v, **dict(attrs))
        repeated_nodes = [
            node for node, degree_value in graph.degree for _ in range(degree_value)
        ]
        source = len(graph)
        _edge_accum = []
    # br-r37-c1-yrdso: preferential attachment reads only ``repeated_nodes``
    # (never the graph) inside the loop, so accumulate every new edge and commit
    # through ONE add_edges_from instead of ``n`` tiny per-source calls that each
    # fell below the batch threshold (8) and ran per-edge add_edge PyO3. Same
    # source-ascending, targets-set insertion order -> byte-identical. (``_edge_accum``
    # is seeded above — with the star edges in the cc-dualbastarbatch fast path.)
    while source < n:
        m = m1 if rng.random() < p else m2
        targets = set()
        while len(targets) < m:
            targets.add(rng.choice(repeated_nodes))
        _edge_accum.extend((source, target) for target in targets)
        repeated_nodes.extend(targets)
        repeated_nodes.extend([source] * m)
        source += 1
    graph.add_edges_from(_edge_accum)

    if create_using is None:
        return graph

    target.graph.update(dict(graph.graph))
    for node, attrs in graph.nodes(data=True):
        target.add_node(node, **dict(attrs))
    for u, v, attrs in graph.edges(data=True):
        target.add_edge(u, v, **dict(attrs))
    return target


def extended_barabasi_albert_graph(
    n, m, p, q, seed=None, *, create_using=None, backend=None, **backend_kwargs
):
    """Return an extended Barabasi-Albert graph."""
    _validate_backend_dispatch_keywords(
        "extended_barabasi_albert_graph", backend, backend_kwargs
    )
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    graph = _checked_create_using(create_using, directed=False, multigraph=False, default=Graph)
    if m < 1 or m >= n:
        raise NetworkXError(
            f"Extended Barabasi-Albert network needs m>=1 and m<n, m={m}, n={n}"
        )
    if p + q >= 1:
        raise NetworkXError(
            f"Extended Barabasi-Albert network needs p + q <= 1, p={p}, q={q}"
        )

    rng = _generator_random_state(seed)
    graph.add_nodes_from(range(m))
    attachment_preference = list(range(m))
    new_node = m

    def random_subset(population, _count):
        targets = set()
        while len(targets) < _count:
            targets.add(rng.choice(population))
        return targets

    while new_node < n:
        a_probability = rng.random()
        clique_degree = len(graph) - 1
        clique_size = (len(graph) * clique_degree) / 2

        if a_probability < p and graph.size() <= clique_size - m:
            eligible_nodes = [
                node for node, degree_value in graph.degree if degree_value < clique_degree
            ]
            for _ in range(m):
                src_node = rng.choice(eligible_nodes)
                prohibited_nodes = list(graph[src_node])
                prohibited_nodes.append(src_node)
                dest_node = rng.choice(
                    [node for node in attachment_preference if node not in prohibited_nodes]
                )
                graph.add_edge(src_node, dest_node)
                attachment_preference.append(src_node)
                attachment_preference.append(dest_node)

                if graph.degree[src_node] == clique_degree:
                    eligible_nodes.remove(src_node)
                if graph.degree[dest_node] == clique_degree and dest_node in eligible_nodes:
                    eligible_nodes.remove(dest_node)

        elif p <= a_probability < (p + q) and m <= graph.size() < clique_size:
            eligible_nodes = [
                node
                for node, degree_value in graph.degree
                if 0 < degree_value < clique_degree
            ]
            for _ in range(m):
                node = rng.choice(eligible_nodes)
                nbr_nodes = list(graph[node])
                src_node = rng.choice(nbr_nodes)
                nbr_nodes.append(node)
                dest_node = rng.choice(
                    [
                        candidate
                        for candidate in attachment_preference
                        if candidate not in nbr_nodes
                    ]
                )
                graph.remove_edge(node, src_node)
                graph.add_edge(node, dest_node)
                attachment_preference.remove(src_node)
                attachment_preference.append(dest_node)

                if graph.degree[src_node] == 0 and src_node in eligible_nodes:
                    eligible_nodes.remove(src_node)
                if dest_node in eligible_nodes:
                    if graph.degree[dest_node] == clique_degree:
                        eligible_nodes.remove(dest_node)
                elif graph.degree[dest_node] == 1:
                    eligible_nodes.append(dest_node)

        else:
            targets = random_subset(attachment_preference, m)
            graph.add_edges_from([(new_node, target) for target in targets])
            attachment_preference.extend(targets)
            attachment_preference.extend([new_node] * (m + 1))
            new_node += 1

    return graph


def scale_free_graph(
    n,
    alpha=0.41,
    beta=0.54,
    gamma=0.05,
    delta_in=0.2,
    delta_out=0,
    seed=None,
    initial_graph=None,
):
    """Return a directed scale-free MultiDiGraph."""
    # br-r37-c1-ols3t: the kernel draws from an int or streams a random.Random
    # (None is the global random._inst); a numpy seed or an initial_graph runs
    # networkx's body.
    kernel_seed = _kernel_seed(seed)
    if initial_graph is None and kernel_seed is not None:
        _check_scale_free_params(alpha, beta, gamma, delta_in, delta_out)
        return _fnx.scale_free_graph(
            n,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta_in=delta_in,
            delta_out=delta_out,
            seed=kernel_seed,
            initial_graph=None,
        )
    return _scale_free_graph_python(
        n, alpha, beta, gamma, delta_in, delta_out, _generator_random_state(seed), initial_graph
    )


def _check_scale_free_params(alpha, beta, gamma, delta_in, delta_out):
    # br-sfgval: validate with nx-shaped ValueError messages before the Rust
    # branch; without this, invalid params leak the Rust
    # `ValueError("FailClosed { ... }")` text instead of nx's terse wording.
    # Validation order and wording match networkx exactly so regex-matched
    # tests on the drop-in surface keep working.
    if alpha <= 0:
        raise ValueError("alpha must be > 0.")
    if beta <= 0:
        raise ValueError("beta must be > 0.")
    if gamma <= 0:
        raise ValueError("gamma must be > 0.")
    if abs(alpha + beta + gamma - 1.0) >= 1e-9:
        raise ValueError("alpha+beta+gamma must equal 1.")
    if delta_in < 0:
        raise ValueError("delta_in must be >= 0.")
    if delta_out < 0:
        raise ValueError("delta_out must be >= 0.")


def _scale_free_graph_python(n, alpha, beta, gamma, delta_in, delta_out, seed, initial_graph):
    """networkx's scale_free_graph body, verbatim, on an fnx MultiDiGraph.

    br-r37-c1-cdf1v: the kernel takes a u64 seed only (TypeError on a
    random.Random or numpy RNG), and its initial_graph handling was not
    networkx's: networkx grows the MultiDiGraph it is handed and returns that
    object, and raises NetworkXError for any other graph before checking the
    parameters, where the kernel copied - converting a Graph - and returned
    node labels as internal keys ('str:1:a') for a string-labelled seed graph.
    A networkx MultiDiGraph is grown as networkx would grow it.

    New nodes come only from the cursor, which is past every numeric label,
    so len(G) is len(node_list) throughout; the loop runs on that and the
    edges go in as one add_edges_from, which adds nodes and assigns multiedge
    keys in the order networkx's per-edge add_edge does.
    """

    def _choose_node(candidates, node_list, delta):
        if delta > 0:
            bias_sum = len(node_list) * delta
            p_delta = bias_sum / (bias_sum + len(candidates))
            if seed.random() < p_delta:
                return seed.choice(node_list)
        return seed.choice(candidates)

    if initial_graph is not None and (
        isinstance(initial_graph, (Graph, DiGraph, MultiGraph, MultiDiGraph))
        or hasattr(initial_graph, "_adj")
    ):
        if not isinstance(initial_graph, (MultiDiGraph, _nx.MultiDiGraph)):
            raise NetworkXError("initial_graph must be a MultiDiGraph.")
        G = initial_graph
        _check_scale_free_params(alpha, beta, gamma, delta_in, delta_out)
        vs = sum((count * [idx] for idx, count in G.out_degree()), [])
        ws = sum((count * [idx] for idx, count in G.in_degree()), [])
        node_list = list(G.nodes())
        edges = []
    else:
        # networkx's start, the 3-cycle, held as its edges and degree lists:
        # it goes into a fresh graph with the grown edges as one batch, which
        # fnx's multigraph batch kernel takes only on a fresh graph.
        G = None
        _check_scale_free_params(alpha, beta, gamma, delta_in, delta_out)
        vs = [0, 1, 2]
        ws = [0, 1, 2]
        node_list = [0, 1, 2]
        edges = [(0, 1), (1, 2), (2, 0)]
    numeric_nodes = [v for v in node_list if isinstance(v, _numbers.Number)]
    if len(numeric_nodes) > 0:
        cursor = max(int(v.real) for v in numeric_nodes) + 1
    else:
        cursor = 0

    while len(node_list) < n:
        r = seed.random()
        if r < alpha:
            v = cursor
            cursor += 1
            node_list.append(v)
            w = _choose_node(ws, node_list, delta_in)
        elif r < alpha + beta:
            v = _choose_node(vs, node_list, delta_out)
            w = _choose_node(ws, node_list, delta_in)
        else:
            v = _choose_node(vs, node_list, delta_out)
            w = cursor
            cursor += 1
            node_list.append(w)
        edges.append((v, w))
        vs.append(v)
        ws.append(w)
    if G is None:
        G = MultiDiGraph()
    G.add_edges_from(edges)
    return G


def random_powerlaw_tree(n, gamma=3, seed=None, tries=100, *, create_using=None, backend=None, **backend_kwargs):
    """Return a random tree with a power-law degree distribution."""
    _validate_backend_dispatch_keywords("random_powerlaw_tree", backend, backend_kwargs)
    if create_using is None:
        sequence = _random_powerlaw_tree_sequence_impl(n, gamma=gamma, seed=seed, tries=tries)
        return _degree_sequence_tree_impl(sequence)

    graph = _checked_create_using(
        create_using,
        directed=False,
        multigraph=False,
        default=Graph,
    )
    sequence = _random_powerlaw_tree_sequence_impl(n, gamma=gamma, seed=seed, tries=tries)
    return _degree_sequence_tree_impl(sequence, create_using=graph)


def _random_powerlaw_tree_sequence_impl(n, gamma=3, seed=None, tries=100):
    # br-r37-c1-rpts-neg: nx raises ValueError("empty range in
    # randrange(0, n)") leaked from internal rng.randint/randrange
    # for n <= 0; fnx previously silently returned ``[]`` (range(n)
    # yielded nothing and is_valid_tree_degree_sequence([]) returns
    # True).  Match nx's structural-error contract — same defect
    # family as br-r37-c1-{rgg-neg, pjf7g, srgg-neg, trgg-neg, 60f9n,
    # waxman-neg, gtg-neg, hszkp, 48hex}.
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: resolved first, as nx's decorator
    if isinstance(n, int) and n <= 0:
        raise ValueError(f"empty range in randrange(0, {n})")
    zseq = [min(n, max(round(rng.paretovariate(gamma - 1)), 0)) for _ in range(n)]
    swap = [min(n, max(round(rng.paretovariate(gamma - 1)), 0)) for _ in range(tries)]
    degree_sum = sum(zseq)
    nonpositive_degrees = sum(degree < 1 for degree in zseq)
    target_sum = 2 * (len(zseq) - 1)

    for _ in range(len(swap)):
        if len(zseq) == 1:
            if zseq[0] == 0:
                return zseq
        elif nonpositive_degrees == 0 and degree_sum == target_sum:
            return zseq
        index = rng.randint(0, n - 1)
        old_degree = zseq[index]
        new_degree = swap.pop()
        zseq[index] = new_degree
        degree_sum += new_degree - old_degree
        if old_degree < 1:
            nonpositive_degrees -= 1
        if new_degree < 1:
            nonpositive_degrees += 1

    raise NetworkXError(f"Exceeded max ({tries}) attempts for a valid tree sequence.")


def random_powerlaw_tree_sequence(n, gamma=3, seed=None, tries=100):
    """Return a degree sequence suitable for a random power-law tree."""
    return _random_powerlaw_tree_sequence_impl(n, gamma=gamma, seed=seed, tries=tries)


def gn_graph(n, kernel=None, create_using=None, seed=None):
    """Return a growing network (GN) digraph."""
    import bisect

    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    from franken_networkx import _fnx

    # NetworkX initializes the GN graph with edge (1, 0) for every
    # integral n <= 0.  The Rust fast path takes usize and either
    # returns the empty graph for 0 or rejects negative values before
    # the wrapper can preserve that observable seed-graph contract.
    if kernel is None and isinstance(n, _numbers.Integral) and n <= 0:
        graph = _checked_directed_create_using(create_using, default=DiGraph)
        graph = empty_graph(1, create_using=graph, default=DiGraph)
        graph.add_edge(1, 0)
        return graph

    if kernel is None and create_using is None:
        return _fnx.gn_graph(n, seed=seed, create_using=None)

    graph = _checked_directed_create_using(create_using, default=DiGraph)
    if kernel is None and n != 0:
        return _copy_graph_into(_fnx.gn_graph(n, seed=seed, create_using=None), graph)

    if kernel is None:

        def kernel(x):
            return x

    rng = _generator_random_state(seed)
    graph = empty_graph(1, create_using=graph, default=DiGraph)
    if n == 1:
        return graph

    graph.add_edge(1, 0)
    degree_sequence = [1, 1]

    for source in range(2, n):
        cumulative = [0.0]
        total = 0.0
        for degree in degree_sequence:
            total += kernel(degree)
            cumulative.append(total)
        cumulative = [value / total for value in cumulative]
        target = bisect.bisect_left(cumulative, rng.random()) - 1
        graph.add_edge(source, target)
        degree_sequence.append(1)
        degree_sequence[target] += 1
    return graph


def LCF_graph(n, shift_list, repeats, create_using=None):
    """Return the cubic Hamiltonian graph defined by Lederberg-Coxeter-Fruchte."""
    if n <= 0:
        return empty_graph(0, create_using)

    graph = cycle_graph(n, create_using=create_using)
    if graph.is_directed():
        raise NetworkXError("Directed Graph not supported")
    graph.graph["name"] = "LCF_graph"
    nodes = sorted(graph)

    n_extra_edges = repeats * len(shift_list)
    if n_extra_edges < 1:
        return graph

    # br-r37-c1-genbatch (cc): batch the chord edges through one add_edges_from (LIST)
    # instead of a per-edge add_edge loop — same order, byte-identical. 0.59x -> 1.15x
    # (beats nx).
    extra_edges = []
    for i in range(n_extra_edges):
        shift = shift_list[i % len(shift_list)]
        v1 = nodes[i % n]
        v2 = nodes[(i + shift) % n]
        extra_edges.append((v1, v2))
    graph.add_edges_from(extra_edges)
    return graph


def _lfr_zipf_rv(alpha, xmin, rng):
    if xmin < 1:
        raise ValueError("xmin < 1")
    if alpha <= 1:
        raise ValueError("a <= 1.0")
    alpha_minus_one = alpha - 1.0
    base = 2**alpha_minus_one
    while True:
        u = 1.0 - rng.random()
        v = rng.random()
        value = int(xmin * u ** -(1.0 / alpha_minus_one))
        threshold = (1.0 + (1.0 / value)) ** alpha_minus_one
        if v * value * (threshold - 1.0) / (base - 1.0) <= threshold / base:
            return value


def _lfr_zipf_rv_below(gamma, xmin, threshold, rng):
    value = _lfr_zipf_rv(gamma, xmin, rng)
    while value > threshold:
        value = _lfr_zipf_rv(gamma, xmin, rng)
    return value


def _lfr_powerlaw_sequence(gamma, low, high, condition, length, max_iters, rng):
    for _ in range(max_iters):
        sequence = []
        while not length(sequence):
            sequence.append(_lfr_zipf_rv_below(gamma, low, high, rng))
        if condition(sequence):
            return sequence
    raise NetworkXError("Could not create power law sequence")


def _lfr_hurwitz_zeta(x, q, tolerance):
    total = 0
    previous = -float("inf")
    k = 0
    while abs(total - previous) > tolerance:
        previous = total
        total += 1 / ((k + q) ** x)
        k += 1
    return total


def _lfr_generate_min_degree(gamma, average_degree, max_degree, tolerance, max_iters):
    try:
        from scipy.special import zeta
    except ImportError:

        def zeta(x, q):
            return _lfr_hurwitz_zeta(x, q, tolerance)

    min_degree_top = max_degree
    min_degree_bottom = 1
    min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
    iterations = 0
    mid_average_degree = 0
    while abs(mid_average_degree - average_degree) > tolerance:
        if iterations > max_iters:
            raise NetworkXError("Could not match average_degree")
        mid_average_degree = 0
        for x in range(int(min_degree_mid), max_degree + 1):
            mid_average_degree += (x ** (-gamma + 1)) / zeta(gamma, min_degree_mid)
        if mid_average_degree > average_degree:
            min_degree_top = min_degree_mid
            min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
        else:
            min_degree_bottom = min_degree_mid
            min_degree_mid = (min_degree_top - min_degree_bottom) / 2 + min_degree_bottom
        iterations += 1
    return round(min_degree_mid)


def _lfr_generate_communities(degree_sequence, community_sizes, mu, max_iters, rng):
    result = [set() for _ in community_sizes]
    free = list(range(len(degree_sequence)))
    for _ in range(max_iters):
        node = free.pop()
        community_index = rng.choice(range(len(community_sizes)))
        internal_degree = round(degree_sequence[node] * (1 - mu))
        if internal_degree < community_sizes[community_index]:
            result[community_index].add(node)
        else:
            free.append(node)
        if len(result[community_index]) > community_sizes[community_index]:
            free.append(result[community_index].pop())
        if not free:
            return result
    # br-r37-c1-lfr-emi: nx raises ExceededMaxIterations (subclass
    # of NetworkXException, NOT NetworkXError) when the community
    # assignment fails to converge.  Match nx's exact exception
    # class so callers using ``except nx.ExceededMaxIterations:``
    # catch the right error.
    from networkx import ExceededMaxIterations as _EMI
    raise _EMI(
        "Could not assign communities; try increasing min_community"
    )


def LFR_benchmark_graph(
    n,
    tau1,
    tau2,
    mu,
    average_degree=None,
    min_degree=None,
    max_degree=None,
    min_community=None,
    max_community=None,
    tol=1e-07,
    max_iters=500,
    seed=None,
):
    """Return an LFR benchmark graph."""
    if not tau1 > 1:
        raise NetworkXError("tau1 must be greater than one")
    if not tau2 > 1:
        raise NetworkXError("tau2 must be greater than one")
    if not 0 <= mu <= 1:
        raise NetworkXError("mu must be in the interval [0, 1]")

    if max_degree is None:
        max_degree = n
    elif not 0 < max_degree <= n:
        raise NetworkXError("max_degree must be in the interval (0, n]")
    if not ((min_degree is None) ^ (average_degree is None)):
        raise NetworkXError(
            "Must assign exactly one of min_degree and average_degree",
        )

    rng = _generator_random_state(seed)
    if min_degree is None:
        min_degree = _lfr_generate_min_degree(
            tau1,
            average_degree,
            max_degree,
            tol,
            max_iters,
        )

    degree_sequence = _lfr_powerlaw_sequence(
        tau1,
        min_degree,
        max_degree,
        lambda sequence: sum(sequence) % 2 == 0,
        lambda sequence: len(sequence) >= n,
        max_iters,
        rng,
    )

    if min_community is None:
        min_community = min(degree_sequence)
    if max_community is None:
        max_community = max(degree_sequence)

    community_sizes = _lfr_powerlaw_sequence(
        tau2,
        min_community,
        max_community,
        lambda sequence: sum(sequence) == n,
        lambda sequence: sum(sequence) >= n,
        max_iters,
        rng,
    )
    communities = _lfr_generate_communities(
        degree_sequence,
        community_sizes,
        mu,
        max_iters * 10 * n,
        rng,
    )

    graph = Graph()
    graph.add_nodes_from(range(n))
    for community in communities:
        community_nodes = list(community)
        for node in community:
            while graph.degree[node] < round(degree_sequence[node] * (1 - mu)):
                graph.add_edge(node, rng.choice(community_nodes))
            while graph.degree[node] < degree_sequence[node]:
                target = rng.choice(range(n))
                if target not in community:
                    graph.add_edge(node, target)
            graph.nodes[node]["community"] = community
    return graph


def hexagonal_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a hexagonal lattice graph."""
    graph = empty_graph(0, create_using)
    if m == 0 or n == 0:
        return graph
    if periodic and (n % 2 == 1 or m < 2 or n < 2):
        raise NetworkXError(
            "periodic hexagonal lattice needs m > 1, n > 1 and even n"
        )

    height = 2 * m
    if (
        not periodic
        and create_using is None
        and _fnx is not None
        and hasattr(_fnx, "hexagonal_lattice_graph_simple")
        and type(m) is int
        and type(n) is int
        and m >= 0
        and n >= 0
    ):
        return _fnx.hexagonal_lattice_graph_simple(m, n, with_positions)

    rows = range(height + 2)
    cols = range(n + 1)

    col_edges = (
        ((i, j), (i, j + 1))
        for i in cols
        for j in rows[: height + 1]
    )
    row_edges = (
        ((i, j), (i + 1, j))
        for i in cols[:n]
        for j in rows
        if i % 2 == j % 2
    )
    graph.add_edges_from(col_edges)
    graph.add_edges_from(row_edges)
    graph.remove_node((0, height + 1))
    graph.remove_node((n, (height + 1) * (n % 2)))

    if periodic:
        for i in cols[:n]:
            graph = contracted_nodes(graph, (i, 0), (i, height), copy=True)
        for i in cols[1:]:
            graph = contracted_nodes(graph, (i, 1), (i, height + 1), copy=True)
        for j in rows[1:height]:
            graph = contracted_nodes(graph, (0, j), (n, j), copy=True)
        graph.remove_node((n, height))

    if with_positions:
        sqrt3_over_2 = _math.sqrt(3) / 2
        positions = {}
        for i in cols:
            for j in rows:
                if (i, j) not in graph:
                    continue
                x = 0.5 + i + i // 2 + (j % 2) * ((i % 2) - 0.5)
                if periodic:
                    y = sqrt3_over_2 * j + 0.01 * i * i
                else:
                    y = sqrt3_over_2 * j
                positions[(i, j)] = (x, y)
        set_node_attributes(graph, positions, "pos")
    return graph


def triangular_lattice_graph(
    m,
    n,
    periodic=False,
    with_positions=True,
    create_using=None,
):
    """Return a triangular lattice graph."""
    graph = empty_graph(0, create_using)
    if n == 0 or m == 0:
        return graph
    if periodic and (n < 5 or m < 3):
        raise NetworkXError(f"m > 2 and n > 4 required for periodic. m={m}, n={n}")

    width = (n + 1) // 2
    if (
        not periodic
        and create_using is None
        and _fnx is not None
        and hasattr(_fnx, "triangular_lattice_graph_simple")
        and type(m) is int
        and type(n) is int
        and m >= 0
        and n >= 0
    ):
        return _fnx.triangular_lattice_graph_simple(m, n, with_positions)

    rows = range(m + 1)
    cols = range(width + 1)

    graph.add_edges_from(((i, j), (i + 1, j)) for j in rows for i in cols[:width])
    graph.add_edges_from(((i, j), (i, j + 1)) for j in rows[:m] for i in cols)
    graph.add_edges_from(
        ((i, j), (i + 1, j + 1))
        for j in rows[1:m:2]
        for i in cols[:width]
    )
    graph.add_edges_from(
        ((i + 1, j), (i, j + 1))
        for j in rows[:m:2]
        for i in cols[:width]
    )

    if periodic:
        for i in cols:
            graph = contracted_nodes(graph, (i, 0), (i, m), copy=True)
        for j in rows[:m]:
            graph = contracted_nodes(graph, (0, j), (width, j), copy=True)
    elif n % 2:
        graph.remove_nodes_from((width, j) for j in rows[1::2])

    if with_positions:
        sqrt3_over_2 = _math.sqrt(3) / 2
        positions = {}
        for i in cols:
            for j in rows:
                if (i, j) not in graph:
                    continue
                x = 0.5 * (j % 2) + i
                if periodic:
                    y = sqrt3_over_2 * j + 0.01 * i * i
                else:
                    y = sqrt3_over_2 * j
                positions[(i, j)] = (x, y)
        set_node_attributes(graph, positions, "pos")
    return graph


def grid_graph(dim, periodic=False):
    """Return an n-dimensional grid graph.

    The dimension n is the length of `dim` and the size in each dimension
    is the value of the corresponding list element.
    """
    if not dim:
        return Graph()

    dimensions = list(dim)
    native_dimensions = []
    native_periods = None
    if _fnx is not None and hasattr(_fnx, "grid_graph_native"):
        if type(periodic) is bool:
            native_periods = [periodic] * len(dimensions)
        elif isinstance(periodic, (list, tuple)) and len(periodic) >= len(dimensions):
            native_periods = [bool(value) for value in periodic[: len(dimensions)]]
        if native_periods is not None:
            for axis in dimensions:
                if type(axis) is not int or axis < 0:
                    native_dimensions = []
                    break
                native_dimensions.append(axis)
            else:
                return _fnx.grid_graph_native(native_dimensions, native_periods)

    periodic_flags = (
        iter(periodic) if isinstance(periodic, _Iterable) else _itertools.repeat(periodic)
    )

    axes = []
    periods = []
    for axis in dimensions:
        periods.append(bool(next(periodic_flags)))
        if isinstance(axis, _numbers.Integral):
            # br-r37-c1-grid-neg: nx routes grid_graph through
            # cartesian_product of path_graph(d) for each d; a
            # negative ``d`` raises NetworkXError("Negative number
            # of nodes not valid: {d}") on the first negative
            # encountered.  fnx previously silently produced an
            # empty graph (range(-3) yielded nothing).  Same
            # defect family as br-r37-c1-{rgg-neg, ...}.
            if axis < 0:
                raise NetworkXError(
                    f"Negative number of nodes not valid: {axis}"
                )
            axes.append(list(range(axis)))
        else:
            axes.append(list(axis))

    graph = Graph()
    output_axes = list(reversed(axes))
    if not output_axes or any(len(axis) == 0 for axis in output_axes):
        return graph

    index_axes = [range(len(axis)) for axis in output_axes]

    def make_node(positions):
        values = [
            output_axes[index][position]
            for index, position in enumerate(positions)
        ]
        return values[0] if len(values) == 1 else tuple(values)

    for positions in _itertools.product(*index_axes):
        graph.add_node(make_node(positions))

    for positions in _itertools.product(*index_axes):
        left = make_node(positions)
        for output_index, axis in enumerate(output_axes):
            axis_pos = positions[output_index]
            right_positions = list(positions)
            if axis_pos + 1 < len(axis):
                right_positions[output_index] = axis_pos + 1
            elif periods[len(output_axes) - 1 - output_index]:
                if len(axis) == 1:
                    graph.add_edge(left, left)
                    continue
                if len(axis) == 2:
                    continue
                right_positions[output_index] = 0
            else:
                continue
            graph.add_edge(left, make_node(right_positions))

    return graph


def lattice_reference(G, niter=5, D=None, connectivity=True, seed=None):
    """Return a lattice-like rewiring of *G* preserving degree sequence."""
    import bisect
    import math

    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if G.number_of_edges() < 2:
        raise NetworkXError("Graph has fewer that 2 edges")

    def cumulative_distribution(distribution):
        cdf = [0.0]
        cumulative = 0.0
        for element in distribution:
            cumulative += element
            cdf.append(cumulative)
        return [element / cumulative for element in cdf]

    def discrete_sequence(_count, cdistribution, rng):
        return [
            bisect.bisect_left(cdistribution, rng.random()) - 1
            for _ in range(_count)
        ]

    def matrix_value(matrix, row, col):
        try:
            return matrix[row, col]
        except (TypeError, KeyError):
            return matrix[row][col]

    def has_path(graph, source, target):
        if source == target:
            return True
        seen = {source}
        queue = [source]
        index = 0
        while index < len(queue):
            node = queue[index]
            index += 1
            for neighbor in graph[node]:
                if neighbor == target:
                    return True
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return False

    graph = Graph()
    graph.graph.update(dict(G.graph))
    graph.add_nodes_from((node, dict(attrs)) for node, attrs in G.nodes(data=True))
    graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in G.edges(data=True))
    rng = _generator_random_state(seed)
    keys, degrees = zip(*graph.degree)
    cdf = cumulative_distribution(degrees)

    node_count = len(graph)
    edge_count = graph.number_of_edges()
    if D is None:
        distance = [[0 for _ in range(node_count)] for _ in range(node_count)]
        lower = list(range(1, node_count))
        upper = list(range(node_count - 1, 0, -1))
        wrapped = [0] + [min(left, right) for left, right in zip(lower, upper)]
        for v in range(_math.ceil(node_count / 2)):
            row = wrapped[v + 1 :] + wrapped[: v + 1]
            distance[node_count - v - 1] = row
            distance[v] = list(reversed(row))
    else:
        distance = D

    total_iterations = niter * edge_count
    max_attempts = int(node_count * edge_count / (node_count * (node_count - 1) / 2))

    for _ in range(total_iterations):
        attempts = 0
        while attempts < max_attempts:
            ai, ci = discrete_sequence(2, cdf, rng)
            if ai == ci:
                continue
            a = keys[ai]
            c = keys[ci]
            b = rng.choice(list(graph.neighbors(a)))
            d = rng.choice(list(graph.neighbors(c)))
            bi = keys.index(b)
            di = keys.index(d)

            if b in [a, c, d] or d in [a, b, c]:
                continue

            if d not in graph[a] and b not in graph[c]:
                if (
                    matrix_value(distance, ai, bi) + matrix_value(distance, ci, di)
                    >= matrix_value(distance, ai, ci) + matrix_value(distance, bi, di)
                ):
                    graph.add_edge(a, d)
                    graph.add_edge(c, b)
                    graph.remove_edge(a, b)
                    graph.remove_edge(c, d)

                    if connectivity and not has_path(graph, a, b):
                        graph.remove_edge(a, d)
                        graph.remove_edge(c, b)
                        graph.add_edge(a, b)
                        graph.add_edge(c, d)
                    else:
                        break
            attempts += 1

    return graph


def margulis_gabber_galil_graph(n, create_using=None):
    """Return a Margulis-Gabber-Galil expander graph."""
    graph = empty_graph(0, create_using, default=MultiGraph)
    if graph.is_directed() or not graph.is_multigraph():
        raise NetworkXError("`create_using` must be an undirected multigraph.")

    # br-r37-c1-genbatch (cc): batch the 4*n^2 edges through one add_edges_from (a
    # LIST — the multigraph-safe form) instead of a per-edge add_edge PyO3 crossing.
    # Same edge order + auto-keys -> byte-identical (1.57x self; still <nx = tuple-key
    # construction tax, but a real reduction from 0.34x -> 0.54x).
    edges = [
        ((x, y), (u, v))
        for x, y in _itertools.product(range(n), repeat=2)
        for u, v in (
            ((x + 2 * y) % n, y),
            ((x + (2 * y + 1)) % n, y),
            (x, (y + 2 * x) % n),
            (x, (y + (2 * x + 1)) % n),
        )
    ]
    graph.add_edges_from(edges)
    graph.graph["name"] = f"margulis_gabber_galil_graph({n})"
    return graph


def sudoku_graph(n=3):
    """Return the Sudoku constraint graph of order *n*.

    The n-Sudoku graph has n^4 vertices (cells of an n^2 × n^2 grid).
    Two cells are adjacent iff they share a row, column, or n×n box.
    """
    return _rust_sudoku_graph(n)


def fast_gnp_random_graph(n, p, seed=None, directed=False, *, create_using=None, backend=None, **backend_kwargs):
    """Return a fast G(n,p) random graph (Batagelj-Brandes O(n+m) algorithm)."""
    _validate_backend_dispatch_keywords("fast_gnp_random_graph", backend, backend_kwargs)
    from franken_networkx._fnx import fast_gnp_random_graph as _rust_fast_gnp

    # br-r37-c1-ols3t: nx's py_random_state, resolved first; the kernel draws
    # from an int or streams a random.Random (None is the global
    # random._inst), a numpy-backed seed runs the body below.
    kernel_seed = _kernel_seed(seed)
    # br-gnpvalid: see gnp_random_graph.
    if n < 0:
        raise NetworkXError(f"Negative number of nodes not valid: {n}")

    # br-r37-c1-fgnp-pnan: nx leaks ValueError("cannot convert
    # float NaN to integer") from its internal ``int(log(1-p)/...)``
    # computation.  fnx silently routed NaN through the gnp
    # fallback (which silently returns 0).  Match nx's leaky-but-
    # stable contract.  Note: gnp_random_graph (the slower Erdős-
    # Rényi path) intentionally accepts NaN silently — only
    # fast_gnp's int-conversion path raises.
    import math as _math
    if isinstance(p, float) and _math.isnan(p):
        raise ValueError("cannot convert float NaN to integer")

    # br-r37-c1-lsdek: out-of-range p is silent in nx (p<=0 -> empty,
    # p>=1 -> complete). The Rust fast path raises FailClosed for those,
    # so route to the boundary-aware gnp_random_graph wrapper.
    if create_using is None and 0 < p < 1 and kernel_seed is not None:
        return _rust_fast_gnp(
            n,
            p,
            seed=kernel_seed,
            directed=directed,
        )

    if create_using is None and not (0 < p < 1):
        return gnp_random_graph(n, p, seed=seed, directed=directed)

    rng = _generator_random_state(seed)
    default = DiGraph if directed else Graph
    graph = _checked_create_using(
        create_using,
        directed=directed,
        multigraph=False,
        default=default,
    )
    if p <= 0 or p >= 1:
        return gnp_random_graph(
            n,
            p,
            seed=rng,
            directed=directed,
            create_using=graph,
        )

    graph = empty_graph(n, create_using=graph, default=default)
    lp = _math.log(1.0 - p)
    edges = []

    if directed:
        v = 1
        w = -1
        while v < n:
            lr = _math.log(1.0 - rng.random())
            w = w + 1 + int(lr / lp)
            while w >= v and v < n:
                w = w - v
                v += 1
            if v < n:
                edges.append((w, v))

    v = 1
    w = -1
    while v < n:
        lr = _math.log(1.0 - rng.random())
        w = w + 1 + int(lr / lp)
        while w >= v and v < n:
            w = w - v
            v += 1
        if v < n:
            edges.append((v, w))
    graph.add_edges_from(edges)
    return graph
