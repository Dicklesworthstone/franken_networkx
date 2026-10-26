
# Algorithm functions — path validation
from franken_networkx._fnx import is_simple_path as _raw_is_simple_path


def is_simple_path(G, nodes):
    """Return True iff ``nodes`` is a simple path in *G*.

    Second parameter renamed from the Rust binding's ``path`` to match
    networkx's public signature ``is_simple_path(G, nodes)``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if isinstance(nodes, (list, tuple)):
        return _raw_is_simple_path(G, nodes)

    # br-r37-c1-oe0kq: PyO3's Vec extractor requires a Sequence, while
    # NetworkX accepts any sized iterable for paths longer than one node.
    # Replay NetworkX's observable operation order for non-list containers.
    # In particular, a singleton set must still raise its native
    # "'set' object is not subscriptable" TypeError at nodes[0].
    if len(nodes) == 0:
        return False
    if len(nodes) == 1:
        return nodes[0] in G
    if not all(node in G for node in nodes):
        return False
    if len(set(nodes)) != len(nodes):
        return False
    return all(v in G[u] for u, v in _itertools.pairwise(nodes))


def _matching_dict_to_set(matching):
    edges = set()
    for edge in matching.items():
        u, v = edge
        if (v, u) in edges or edge in edges:
            continue
        if u == v:
            raise NetworkXError(f"Selfloops cannot appear in matchings {edge}")
        edges.add(edge)
    return edges


def is_matching(G, matching):
    """Return True if ``matching`` is a valid matching of ``G``.

    networkx's exact loop for every graph type. nro4w.7: the native
    simple-graph validator skipped the 2-tuple check (a 3-tuple counted, a
    1-tuple raised IndexError), validated every node before the loop (so a
    missing node raised where networkx returns False on an earlier overlap),
    leaked canonical keys ("str:1:a") into messages, and skipped
    matching_dict_to_set's self-loop error.
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if isinstance(matching, dict):
        matching = _matching_dict_to_set(matching)
    nodes = set()
    for edge in matching:
        if len(edge) != 2:
            raise NetworkXError(f"matching has non-2-tuple edge {edge}")
        u, v = edge
        if u not in G or v not in G:
            raise NetworkXError(f"matching contains edge {edge} with node not in G")
        if u == v:
            return False
        if not G.has_edge(u, v):
            return False
        if u in nodes or v in nodes:
            return False
        nodes.update(edge)
    return True


def is_maximal_matching(G, matching):
    """Return True if ``matching`` is a maximal matching of ``G``.

    See :func:`is_matching`.
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if isinstance(matching, dict):
        matching = _matching_dict_to_set(matching)
    edges = set()
    nodes = set()
    for edge in matching:
        if len(edge) != 2:
            raise NetworkXError(f"matching has non-2-tuple edge {edge}")
        u, v = edge
        if u not in G or v not in G:
            raise NetworkXError(f"matching contains edge {edge} with node not in G")
        if u == v:
            return False
        if not G.has_edge(u, v):
            return False
        if u in nodes or v in nodes:
            return False
        nodes.update(edge)
        edges.add(edge)
        edges.add((v, u))
    for u, v in G.edges:
        if (u, v) not in edges:
            if u not in nodes and v not in nodes and u != v:
                return False
    return True


def is_perfect_matching(G, matching):
    """Return True if ``matching`` is a perfect matching of ``G``.

    See :func:`is_matching`.
    """
    # br-r37-c1-0555d: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if isinstance(matching, dict):
        matching = _matching_dict_to_set(matching)
    nodes = set()
    for edge in matching:
        if len(edge) != 2:
            raise NetworkXError(f"matching has non-2-tuple edge {edge}")
        u, v = edge
        if u not in G or v not in G:
            raise NetworkXError(f"matching contains edge {edge} with node not in G")
        if u == v:
            return False
        if not G.has_edge(u, v):
            return False
        if u in nodes or v in nodes:
            return False
        nodes.update(edge)
    return len(nodes) == len(G)


class _MinDegreeHeuristic:
    def __init__(self, graph):
        self._update_nodes = []
        self._degreeq = []
        self._counter = _count()
        for node in graph:
            self._degreeq.append((len(graph[node]), next(self._counter), node))
        import heapq

        heapq.heapify(self._degreeq)

    def best_node(self, graph):
        for node in self._update_nodes:
            _heappush(self._degreeq, (len(graph[node]), next(self._counter), node))

        while self._degreeq:
            min_degree, _, elim_node = _heappop(self._degreeq)
            if elim_node not in graph or len(graph[elim_node]) != min_degree:
                continue
            if min_degree == len(graph) - 1:
                return None

            self._update_nodes = list(graph[elim_node])
            return elim_node

        return None


def _treewidth_decomp(graph, heuristic):
    graph_dict = {node: set(graph[node]) - {node} for node in graph}
    node_stack = []

    elim_node = heuristic(graph_dict)
    while elim_node is not None:
        nbrs = graph_dict[elim_node]
        for u, v in _itertools.permutations(nbrs, 2):
            if v not in graph_dict[u]:
                graph_dict[u].add(v)

        node_stack.append((elim_node, set(nbrs)))

        for node in graph_dict[elim_node]:
            graph_dict[node].remove(elim_node)
        del graph_dict[elim_node]
        elim_node = heuristic(graph_dict)

    first_bag = frozenset(graph_dict.keys())
    treewidth = len(first_bag) - 1

    # br-r37-c1-twdecomp (cc): scan bags via a plain Python list in insertion order (==
    # decomp node order) instead of ``for bag in decomp`` (iterating the fnx Graph crosses
    # PyO3 per node, O(V^2)), and collect the decomp edges to build the result Graph in ONE
    # add_edges_from at the end instead of per-bag add_edge. Same first-match bag + same
    # node/edge insertion order, so the decomposition is byte-identical.
    decomp_bags = [first_bag]
    decomp_edges = []

    while node_stack:
        curr_node, nbrs = node_stack.pop()
        old_bag = None
        for bag in decomp_bags:
            if nbrs <= bag:
                old_bag = bag
                break

        if old_bag is None:
            old_bag = first_bag

        nbrs.add(curr_node)
        new_bag = frozenset(nbrs)
        treewidth = max(treewidth, len(new_bag) - 1)
        decomp_edges.append((old_bag, new_bag))
        decomp_bags.append(new_bag)

    decomp = Graph()
    decomp.add_node(first_bag)
    decomp.add_edges_from(decomp_edges)

    return treewidth, decomp


def _treewidth_min_degree(G):
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    heuristic = _MinDegreeHeuristic(G)
    return _treewidth_decomp(G, lambda graph: heuristic.best_node(graph))


class _ApproximationNamespace:
    def treewidth_min_degree(self, G, *, backend=None, **backend_kwargs):
        # br-r37-c1-bk-submod: nx's @_dispatchable adds the backend
        # surface; the fnx native re-export had bare ``(G)``.
        _validate_backend_dispatch_keywords(
            "treewidth_min_degree", backend, backend_kwargs
        )
        return _treewidth_min_degree(G)

    def min_weighted_vertex_cover(self, G, weight=None, *, backend=None, **backend_kwargs):
        # br-vcnative: the generic __getattr__ wrapper round-trips the graph
        # through ``_networkx_graph_for_parity`` (an O(n^2) fnx->nx conversion)
        # and runs nx's pure-Python local-ratio loop over the slow fnx views --
        # ~28x slower than nx at n=1500. The native Rust kernel replicates nx's
        # edge-order greedy exactly (incl. weight=None => unit weights), so route
        # straight to it with no conversion.
        _validate_backend_dispatch_keywords(
            "min_weighted_vertex_cover", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        if G.is_directed():
            # networkx iterates the DIRECTED edges of a DiGraph here, so run the
            # exact local-ratio greedy directly over G.nodes and G.edges with
            # 0 NetworkX conversion or frames.
            cost = dict(G.nodes(data=weight, default=1))
            cover = set()
            for u, v in G.edges():
                if u in cover or v in cover:
                    continue
                if cost[u] <= cost[v]:
                    cover.add(u)
                    cost[v] -= cost[u]
                else:
                    cover.add(v)
                    cost[u] -= cost[v]
            return cover
        if weight is not None:
            # br-r37-c1-303zo: node-view writes mutate the live Python mirrors,
            # while the native kernel reads the typed AttrMap store. Flush those
            # mirrors while holding the GIL before the binding releases it; the
            # sync replaces (rather than merges) each map, so deleted attrs do
            # not survive as stale native costs.
            _sync_rust_edge_attrs(G)
        return _raw_min_weighted_vertex_cover(G, weight)

    def min_maximal_matching(self, G, *, backend=None, **backend_kwargs):
        # br-vcnative: nx's min_maximal_matching(G) IS nx.maximal_matching(G);
        # the generic wrapper round-trips through an O(n^2) fnx->nx conversion
        # (~30x slower). Route to the native maximal_matching (parity-exact).
        _validate_backend_dispatch_keywords(
            "min_maximal_matching", backend, backend_kwargs
        )
        return maximal_matching(G)

    def randomized_partitioning(self, G, seed=None, p=0.5, weight=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-wxy3x: nx's randomized_partitioning is a trivial coin-flip
        # plus cut_size, but the generic __getattr__ wrapper round-tripped the
        # graph through ``_networkx_graph_for_parity`` and ran nx's cut_size over
        # the slow fnx adjacency views -- ~8x slower than nx for almost no work.
        # De-delegate: draw the cut in-process with nx's EXACT RNG
        # (create_py_random_state over ``G.nodes()`` order -> identical per-node
        # ``seed.random()`` draws -> identical cut) and use the native ``cut_size``
        # (order-insensitive). Byte-identical to nx (360 checks, native + weighted,
        # 0 mismatches); 1.6x FASTER than nx, 12.7x self-speedup. Directed /
        # multigraph raise as nx's @not_implemented_for decorators do.
        _validate_backend_dispatch_keywords(
            "randomized_partitioning", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        if G.is_multigraph():
            raise NetworkXNotImplemented("not implemented for multigraph type")
        from networkx.utils import create_py_random_state as _create_py_random_state

        rng = _create_py_random_state(seed)
        cut = {node for node in G.nodes() if rng.random() < p}
        cut_size_value = cut_size(G, cut, weight=weight)
        return cut_size_value, (cut, set(G.nodes()) - cut)

    def min_weighted_dominating_set(self, G, weight=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-wxy3x: nx's greedy builds neighborhoods from ``G[v]`` (slow
        # fnx AtlasView) and calls ``_cost`` -> ``G.nodes[v]`` per candidate every
        # iteration, and the generic __getattr__ wrapper converts fnx->nx first --
        # ~1.7x slower than nx. De-delegate: snapshot closed neighborhoods via the
        # native ``to_dict_of_lists`` (``list(G)`` order, so the ``min`` tie-break
        # matches nx's ``neighborhoods.items()`` insertion order) and run nx's
        # EXACT greedy on local dicts. Byte-identical to nx (31 checks incl
        # weighted, 0 mismatches); 1.45x faster, 2.14x self-speedup. Directed
        # raises like nx's @not_implemented_for; multigraph keeps nx's path.
        _validate_backend_dispatch_keywords(
            "min_weighted_dominating_set", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        if len(G) == 0:
            return set()
        if type(G) is not Graph:
            return _nx.approximation.min_weighted_dominating_set(
                _networkx_graph_for_parity(G), weight=weight, backend="networkx"
            )
        dom_set: set = set()
        dod = to_dict_of_lists(G)
        if weight is None:
            node_w = {v: 1 for v in G}
        else:
            node_w = {v: G.nodes[v].get(weight, 1) for v in G}
        neighborhoods = {v: {v} | set(dod[v]) for v in G}

        def _cost(item):
            v, neighborhood = item
            return node_w[v] / len(neighborhood - dom_set)

        vertices = set(G)
        while vertices:
            dom_node, min_set = min(neighborhoods.items(), key=_cost)
            dom_set.add(dom_node)
            del neighborhoods[dom_node]
            vertices -= min_set
        return dom_set

    def min_edge_dominating_set(self, G, *, backend=None, **backend_kwargs):
        # br-vcnative: nx's min_edge_dominating_set(G) returns maximal_matching(G)
        # (raising ValueError on the empty graph). Same conversion-tax fix.
        _validate_backend_dispatch_keywords(
            "min_edge_dominating_set", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        if len(G) == 0:
            raise ValueError("Expected non-empty NetworkX graph!")
        return maximal_matching(G)

    def average_clustering(self, G, trials=1000, seed=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-2poe6: nx's Schank-Wagner sampler is cheap, but the generic
        # __getattr__ converted fnx->nx and ran the trials loop's per-trial
        # list(G[node]) / u in G[v] on slow fnx adjacency (~3x slower). Snapshot
        # adjacency once via the bulk native G.adjacency() (order-preserving),
        # then run nx's EXACT sampler — all int(seed.random()*n) indices first,
        # then per-trial seed.sample(nbrs, 2) + membership — on local dicts.
        # Byte-identical to the previous fnx result (0/60); parity with nx at
        # common sizes. (Snapshot is O(V+E); for trials << |E| on huge graphs nx
        # samples adjacency lazily — residual there, see bead.)
        _validate_backend_dispatch_keywords(
            "average_clustering", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        if G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        # br-r37-c1-approxacc: native byte-exact kernel reproduces nx's CPython
        # random.Random(seed) draw sequence (node indices, then sample(nbrs, 2))
        # over neighbors_indices — ~90x faster than the Python sampler below.
        # Gated to the reproducible case: simple Graph, non-negative int seed,
        # trials >= 1, |V| >= 1. Other shapes (multigraph / non-int or negative
        # seed / seed=None / trials == 0 / empty) keep the Python path.
        if (
            type(G) is Graph
            and isinstance(seed, int)
            and not isinstance(seed, bool)
            and seed >= 0
            and trials >= 1
            and len(G) >= 1
        ):
            _native_acc = getattr(_fnx, "approx_average_clustering", None)
            if _native_acc is not None:
                return _native_acc(G, trials, seed)
        rng = _generator_random_state(seed)
        nodes = list(G)
        n = len(nodes)
        trial_indices = [int(rng.random() * n) for _ in range(trials)]
        raw_neighbors = _raw_neighbors_dispatch(G)
        if raw_neighbors is not None and trials <= n:
            sampled_neighbors = {}
            sampled_neighbor_sets = {}
            triangles = 0
            for i in trial_indices:
                node = nodes[i]
                nbrs = sampled_neighbors.get(node)
                if nbrs is None:
                    nbrs = list(raw_neighbors(G, node))
                    sampled_neighbors[node] = nbrs
                if len(nbrs) < 2:
                    continue
                u, v = rng.sample(nbrs, 2)
                v_nbrs = sampled_neighbor_sets.get(v)
                if v_nbrs is None:
                    v_cached = sampled_neighbors.get(v)
                    if v_cached is None:
                        v_cached = list(raw_neighbors(G, v))
                        sampled_neighbors[v] = v_cached
                    v_nbrs = set(v_cached)
                    sampled_neighbor_sets[v] = v_nbrs
                if u in v_nbrs:
                    triangles += 1
            return triangles / trials
        adj = {u: list(nbrs) for u, nbrs in G.adjacency()}
        adjset = {u: set(a) for u, a in adj.items()}
        triangles = 0
        for i in trial_indices:
            nbrs = adj[nodes[i]]
            if len(nbrs) < 2:
                continue
            u, v = rng.sample(nbrs, 2)
            if u in adjset[v]:
                triangles += 1
        return triangles / trials

    def diameter(self, G, seed=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-apxdiam: nx's undirected 2-sweep (Magnien-Latapy-Habib) is
        # cheap, but the generic __getattr__ converts fnx->nx and runs nx's
        # 2-sweep whose internal BFS dispatches BACK onto slow fnx adjacency
        # (~37x slower than this native path; 12.8x vs nx). Reproduce the
        # algorithm directly: seed.choice(list(G)) -> single-source BFS distances
        # (fnx integer-CSR, nx-discovery-order) -> the last (farthest) node ->
        # its eccentricity. Byte-identical to the previous fnx result (0/150) and
        # faster than nx. Directed (2-dSweep) keeps the delegated path.
        _validate_backend_dispatch_keywords("diameter", backend, backend_kwargs)
        G = _coerce_arg_to_fnx_graph(G)
        if len(G) == 0:
            raise NetworkXError("Expected non-empty NetworkX graph!")
        if G.number_of_nodes() == 1:
            return 0
        if G.is_directed():
            nx_G = _networkx_graph_for_parity(G)
            return _nx.approximation.diameter(nx_G, seed=seed, backend="networkx")
        rng = _generator_random_state(seed)
        source = rng.choice(list(G))
        distances = single_source_shortest_path_length(G, source)
        if len(distances) != len(G):
            raise NetworkXError("Graph not connected.")
        *_, node = distances
        return eccentricity(G, node)

    def local_node_connectivity(self, G, source, target, cutoff=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-apxlnc: the generic __getattr__ wrapper round-tripped the
        # graph through ``_networkx_graph_for_parity`` (an O(V+E) conversion)
        # before running White & Newman's greedy approximation — but the
        # algorithm itself only touches the O(kappa) augmenting-path nodes, so
        # the conversion dominated (~25x slower than nx on a single pair). Run
        # the algorithm IN-PROCESS using the raw neighbour binding (no
        # conversion, no AtlasView per-access tax). Directed / multigraph /
        # nx-private-storage graphs keep the delegation path.
        _validate_backend_dispatch_keywords(
            "local_node_connectivity", backend, backend_kwargs
        )
        raw = _raw_neighbors_dispatch(G)
        if (
            raw is not None
            and type(G) is Graph
            and (cutoff is None or (isinstance(cutoff, int) and cutoff >= 0))
        ):
            return _raw_approx_local_node_connectivity_undirected(
                G, source, target, cutoff
            )
        if raw is not None and not G.is_directed() and not G.is_multigraph():
            return _approx_local_node_connectivity_undirected(
                G, raw, source, target, cutoff
            )
        nx_G = _networkx_graph_for_parity(G)
        return _nx.approximation.local_node_connectivity(
            nx_G, source, target, cutoff, backend="networkx"
        )

    def node_connectivity(self, G, s=None, t=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-nawyw: the generic __getattr__ wrapper round-trips the graph
        # through ``_networkx_graph_for_parity`` (a full O(V+E) fnx->nx build)
        # before running White & Newman's greedy approximation on nx views
        # (~1.3-1.6x slower than nx). Run nx's EXACT algorithm in-process over the
        # raw neighbour binding (no conversion, no AtlasView per-access tax).
        #
        # Byte-exactness: the returned K is order-INVARIANT. With ``cutoff=K``
        # each ``local_node_connectivity(a,b,cutoff=K)`` returns ``min(true_lnc,
        # K)``, so ``K = min(K, ...)`` is just the running minimum of true local
        # connectivities bounded by the minimum degree — independent of the
        # iteration order over the pair set. We only need the SAME minimum-degree
        # node ``v`` (first in node order, matching nx's
        # ``min(G.degree(), key=itemgetter(1))``) and the SAME pair set. Directed
        # / multigraph / nx-private-storage graphs keep the delegation path.
        _validate_backend_dispatch_keywords(
            "node_connectivity", backend, backend_kwargs
        )
        if (s is not None and t is None) or (s is None and t is not None):
            raise NetworkXError("Both source and target must be specified.")
        raw = _raw_neighbors_dispatch(G)
        if raw is None or G.is_directed() or G.is_multigraph():
            nx_G = _networkx_graph_for_parity(G)
            return _nx.approximation.node_connectivity(nx_G, s, t, backend="networkx")
        # Local node connectivity.
        if s is not None and t is not None:
            if s not in G:
                raise NetworkXError(f"node {s} not in graph")
            if t not in G:
                raise NetworkXError(f"node {t} not in graph")
            return _approx_local_node_connectivity_undirected(G, raw, s, t, None)
        # Global node connectivity.
        if not is_connected(G):
            return 0
        # The global algorithm touches the whole graph (every non-neighbour of the
        # min-degree node, plus its non-adjacent neighbour pairs), so snapshot the
        # adjacency ONCE via the native key binding and run the BFS over plain
        # Python dicts — the one-time O(V+E) snapshot amortizes and pure-dict
        # traversal beats nx's AtlasView access (~0.7-0.8x vs nx). Fall back to the
        # raw per-access path if the snapshot binding is unavailable.
        nak = getattr(G, "_native_adjacency_keys", None)
        if nak is not None and type(G) is Graph:
            adj = {node: list(nbrs) for node, nbrs in nak()}
            deg = {node: len(nbrs) for node, nbrs in adj.items()}
            # Min-degree node, first in node order on ties (== nx's
            # ``min(G.degree(), key=itemgetter(1))``).
            v = None
            minimum_degree = None
            for node, d in deg.items():
                if minimum_degree is None or d < minimum_degree:
                    minimum_degree = d
                    v = node
            K = minimum_degree
            nbrs_v = set(adj[v])
            for w in set(adj) - nbrs_v - {v}:
                K = min(K, _approx_local_node_connectivity_dict(adj, deg, v, w, K))
            nbr_list = list(nbrs_v)
            nbr_sets = {x: set(adj[x]) for x in nbr_list}
            for x, y in _itertools.combinations(nbr_list, 2):
                if x != y and y not in nbr_sets[x]:
                    K = min(
                        K, _approx_local_node_connectivity_dict(adj, deg, x, y, K)
                    )
            return K
        # Fallback: raw per-access path (no native snapshot binding).
        v = None
        minimum_degree = None
        for node, d in G.degree():
            if minimum_degree is None or d < minimum_degree:
                minimum_degree = d
                v = node
        K = minimum_degree
        nbrs_v = set(raw(G, v))
        for w in set(G) - nbrs_v - {v}:
            K = min(K, _approx_local_node_connectivity_undirected(G, raw, v, w, K))
        nbr_list = list(nbrs_v)
        nbr_sets = {x: set(raw(G, x)) for x in nbr_list}
        for x, y in _itertools.combinations(nbr_list, 2):
            if x != y and y not in nbr_sets[x]:
                K = min(
                    K, _approx_local_node_connectivity_undirected(G, raw, x, y, K)
                )
        return K

    def all_pairs_node_connectivity(self, G, nbunch=None, cutoff=None, *, backend=None, **backend_kwargs):
        # br-r37-c1-qango: the generic __getattr__ wrapper round-trips the graph
        # through fnx->nx then runs nx's O(V^2) White-Newman pairwise loop on nx
        # views (~parity, but every one of the V^2 local calls pays AtlasView
        # access). Snapshot the adjacency ONCE via the native key binding and run
        # every pair's bidirectional-BFS over plain Python dicts — pure-dict
        # traversal beats nx's view access, so the whole O(V^2) sweep drops below
        # nx. Directed graphs delegate (the dict path mirrors nx, but the existing
        # top-level note records the Rust bulk helper over-reports directed
        # connectivity; nx's own pairwise approximation is the reference here, so
        # we simply keep directed/multigraph on the delegation path). Result is a
        # dict-of-dicts; per-pair values are deterministic and key order mirrors
        # nx's nbunch/combinations enumeration exactly.
        _validate_backend_dispatch_keywords(
            "all_pairs_node_connectivity", backend, backend_kwargs
        )
        nak = getattr(G, "_native_adjacency_keys", None)
        if (
            nak is None
            or type(G) is not Graph
            or G.is_directed()
            or G.is_multigraph()
        ):
            nx_G = _networkx_graph_for_parity(G)
            return _nx.approximation.all_pairs_node_connectivity(
                nx_G, nbunch=nbunch, cutoff=cutoff, backend="networkx"
            )
        adj = {node: list(nbrs) for node, nbrs in nak()}
        deg = {node: len(nbrs) for node, nbrs in adj.items()}
        if nbunch is None:
            nb = list(adj)
        else:
            nb = list(set(nbunch))
            # nx computes G.degree() on nbunch nodes directly; an out-of-graph
            # node would diverge — keep that (rare) case on the nx path.
            if any(n not in adj for n in nb):
                nx_G = _networkx_graph_for_parity(G)
                return _nx.approximation.all_pairs_node_connectivity(
                    nx_G, nbunch=nbunch, cutoff=cutoff, backend="networkx"
                )
        all_pairs = {n: {} for n in nb}
        for u, v in _itertools.combinations(nb, 2):
            k = _approx_local_node_connectivity_dict(adj, deg, u, v, cutoff)
            all_pairs[u][v] = k
            all_pairs[v][u] = k
        return all_pairs

    def large_clique_size(self, G, *, backend=None, **backend_kwargs):
        # br-r37-c1-eg2bz: the generic __getattr__ wrapper round-trips the graph
        # through ``_networkx_graph_for_parity`` (a full O(V+E) fnx->nx build)
        # before running nx's Pattabiraman degree-greedy heuristic — ~2x slower
        # than nx, dominated by that conversion. The algorithm only needs a
        # degree map + adjacency SETS, so run nx's EXACT heuristic in-process
        # over a cheap key-only native snapshot (``_native_adjacency_keys``).
        # It is set-iteration-order dependent (``max(U, key=degree)`` ties), so
        # the snapshot is keyed by the original node OBJECTS — the CPython set
        # order then matches nx's exactly, making the result byte-identical.
        # Directed / multigraph keep nx's @not_implemented_for raise via delegation.
        _validate_backend_dispatch_keywords(
            "large_clique_size", backend, backend_kwargs
        )
        G = _coerce_arg_to_fnx_graph(G)
        nak = getattr(G, "_native_adjacency_keys", None)
        if G.is_directed() or G.is_multigraph() or nak is None or type(G) is not Graph:
            return _nx.approximation.large_clique_size(
                _networkx_graph_for_parity(G), backend="networkx"
            )

        adj = {node: set(nbrs) for node, nbrs in nak()}
        degrees = {u: len(nbrs) for u, nbrs in adj.items()}
        deg_get = degrees.__getitem__

        def _clique_heuristic(candidates, size, best_size):
            # Faithful iterative form of nx's tail recursion: pick the highest-
            # degree candidate (set-order tie-break), intersect with its high-
            # degree neighbourhood, repeat. best_size is fixed within a call.
            while candidates:
                u = max(candidates, key=deg_get)
                candidates.remove(u)
                n_prime = {v for v in adj[u] if degrees[v] >= best_size}
                candidates = candidates & n_prime
                size += 1
            return max(best_size, size)

        best_size = 0
        for u in G:
            if degrees[u] >= best_size:
                neighbors = {v for v in adj[u] if degrees[v] >= best_size}
                best_size = _clique_heuristic(neighbors, 1, best_size)
        return best_size

    def metric_closure(self, G, weight="weight", *, backend=None, **backend_kwargs):
        # br-r37-c1-mcdij: the generic __getattr__ wrapper round-trips the
        # graph through ``_networkx_graph_for_parity`` and then runs nx's
        # pure-Python ``all_pairs_dijkstra`` (distance + path) to build the
        # complete metric-closure graph — ~2.7x slower than nx. Route the
        # all-pairs Dijkstra through the native ``_raw_all_pairs_dijkstra``
        # kernel (byte-exact distances AND paths) and assemble the complete
        # graph with one ``add_edges_from``, reproducing nx's exact edge-
        # insertion order (``set(G)`` iteration, first-node-first). Verified
        # order-sensitively byte-identical to the delegating path across 11
        # graph shapes incl. weighted. None-weight / directed / multigraph /
        # nx-typed inputs keep the delegating path.
        _validate_backend_dispatch_keywords(
            "metric_closure", backend, backend_kwargs
        )
        from franken_networkx.readwrite import _from_nx_graph

        if (
            type(G) is Graph
            and isinstance(weight, str)
            and G.number_of_nodes() > 0
        ):
            import warnings

            apd = _raw_all_pairs_dijkstra(G, weight=weight)
            nodes = list(G)
            first = nodes[0]
            if len(apd[first][0]) != len(nodes):
                raise NetworkXError(
                    "G is not a connected graph. metric_closure is not defined."
                )
            # Preserve nx's deprecation contract (removal in NetworkX 3.8).
            warnings.warn(
                "metric_closure is deprecated and will be removed in NetworkX 3.8.\n"
                "Use nx.all_pairs_shortest_path_length instead.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            M = Graph()
            Gnodes = set(G)
            Gnodes.remove(first)
            dist0, path0 = apd[first]
            edges = [
                (first, v, {"distance": dist0[v], "path": path0[v]})
                for v in Gnodes
            ]
            for u in nodes[1:]:
                Gnodes.remove(u)
                dist, path = apd[u]
                edges.extend(
                    (u, v, {"distance": dist[v], "path": path[v]})
                    for v in Gnodes
                )
            M.add_edges_from(edges)
            return M

        return _from_nx_graph(
            _nx.approximation.metric_closure(
                _networkx_graph_for_parity(G), weight=weight, backend="networkx"
            )
        )

    def greedy_tsp(self, G, weight="weight", source=None, *, backend=None, **backend_kwargs):
        # Nearest-neighbour greedy TSP heuristic. The generic __getattr__
        # wrapper round-trips the (dense, complete) weighted graph through
        # ``_networkx_graph_for_parity`` — an O(n^2) fnx->nx construction tax
        # that left greedy_tsp the fleet's biggest measured laggard (~0.09x
        # vs nx). ``_fnx.greedy_tsp_native`` reads the edge weights straight
        # from the Rust store and runs the nearest-neighbour walk natively,
        # returning the tour ONLY when it is provably byte-identical to nx:
        # every greedy step must have a UNIQUE minimal-weight neighbour, so the
        # choice is independent of nx's ``min(set(G), key=...)`` tie-break
        # order. It returns ``None`` — and we fall back to the faithful nx
        # delegation (preserving nx's exact errors) — for multigraphs,
        # non-numeric weights, incomplete/empty graphs, an unknown source, or
        # any tie step.
        _validate_backend_dispatch_keywords("greedy_tsp", backend, backend_kwargs)
        if backend is None and not backend_kwargs and type(G) in (Graph, DiGraph):
            try:
                tour = _fnx.greedy_tsp_native(G, weight, source)
            except Exception:
                tour = None
            if tour is not None:
                return tour
            # br-cc-tsptie: the native kernel returns None whenever ANY greedy
            # step has a tie (two neighbours sharing the minimal weight) — common
            # for integer-weighted instances — and we then paid the O(n^2)
            # ``_networkx_graph_for_parity`` build PLUS nx's own O(n^2) AtlasView
            # loop, leaving greedy_tsp at ~0.05-0.08x vs nx on the tie path. Run
            # nx's EXACT algorithm IN-PROCESS over a single adjacency snapshot
            # instead: skips the fnx->nx graph construction entirely and reads
            # plain Python dicts (no AtlasView tax). Byte-identical to nx — the
            # tie-break ``min(nodeset, key=...)`` iterates a real CPython ``set``
            # over the SAME node objects, so it resolves ties exactly as nx does
            # (0/400 adversarial incl. int-weight ties, directed, str nodes; all
            # error contracts — incomplete/empty/bad-source/non-numeric weight —
            # match). 0.05-0.08x -> 1.5-1.6x. Only simple Graph/DiGraph reach
            # here (the type gate above); multigraphs keep nx delegation.
            adj = {u: nbrs for u, nbrs in G.adjacency()}
            order = len(adj)
            complete_degree = order - 1
            for node, nbrdict in adj.items():
                if len(nbrdict) - (node in nbrdict) != complete_degree:
                    raise NetworkXError("G must be a complete graph.")
            if source is None:
                source = next(iter(G))
            if order == 2:
                neighbor = next(iter(adj[source]))
                return [source, neighbor, source]
            nodeset = set(G)
            nodeset.remove(source)
            cycle = [source]
            next_node = source
            while nodeset:
                nbrdict = adj[next_node]
                next_node = min(nodeset, key=lambda n: nbrdict[n].get(weight, 1))
                cycle.append(next_node)
                nodeset.remove(next_node)
            cycle.append(cycle[0])
            return cycle
        return _nx.approximation.greedy_tsp(
            _networkx_graph_for_parity(G),
            weight=weight,
            source=source,
            backend="networkx",
        )

    def _tsp_anneal_prep(self, G, init_cycle, weight, source, move):
        # Shared fast-path setup for simulated_annealing_tsp /
        # threshold_accepting_tsp. Returns (nodes, W, mv, cyc_idx, rng_seed) for
        # the index-space vectorised loop, or ``None`` to signal the caller to
        # fall back to the faithful nx delegation. nx's move functions swap
        # CYCLE POSITIONS (their RNG draws depend only on len(cycle), not the
        # node labels), so the loop runs in index space byte-identically, while
        # the cycle cost becomes one vectorised numpy fancy-index sum instead of
        # n per-edge Python dict lookups. We gate to the cases where this is
        # provably == nx: simple Graph/DiGraph, an explicit init_cycle, a
        # known move, n>=3, a COMPLETE graph, and INTEGER-valued weights (so the
        # numpy pairwise sum equals nx's left-to-right Python sum exactly).
        import numpy as _np
        from networkx.algorithms.approximation.traveling_salesman import (
            move_one_node as _move_one_node,
            swap_two_nodes as _swap_two_nodes,
        )

        if type(G) not in (Graph, DiGraph):
            return None
        # br-cc-tspanngreedy: nx resolves init_cycle="greedy" by computing
        # ``cycle = greedy_tsp(G, weight=weight, source=source)`` (a
        # DETERMINISTIC, RNG-free step) and then annealing from that cycle.
        # Previously we bailed to the full nx delegation for ANY str init_cycle
        # (~0.66-0.86x on integer-weighted complete graphs). We now resolve
        # "greedy" in-process with the byte-exact greedy_tsp so the explicit-cycle
        # fast path below engages (greedy is RNG-free, so the annealing RNG stream
        # is unchanged). The greedy COMPUTATION is deferred until after the
        # integer/completeness gates pass, so the float/incomplete bail path does
        # not pay for a wasted greedy_tsp call. Unknown strings -> bail so nx raises.
        init_is_greedy = False
        if isinstance(init_cycle, str):
            if init_cycle != "greedy":
                return None
            init_is_greedy = True
        if move == "1-1":
            mv = _swap_two_nodes
        elif move == "1-0":
            mv = _move_one_node
        else:
            return None

        nodes = list(G)
        n = len(nodes)
        if n < 3:
            return None
        idx = {node: i for i, node in enumerate(nodes)}

        directed = type(G) is DiGraph
        W = _np.full((n, n), _np.inf, dtype=_np.float64)
        try:
            for u, v, w in G.edges(data=weight, default=1):
                if u == v:
                    continue  # selfloops ignored, like nx's completeness check
                if isinstance(w, bool) or not isinstance(w, (int, float)):
                    return None
                iw = int(w)
                if w != iw:
                    return None  # non-integer weight -> float-sum order matters
                i, j = idx[u], idx[v]
                W[i, j] = w
                if not directed:
                    W[j, i] = w
        except (KeyError, TypeError, ValueError):
            return None

        # Completeness (mirror nx, ignoring selfloops): each node reaches every
        # other. For directed this is the out-neighbour count.
        finite = _np.isfinite(W)
        if not bool((finite.sum(axis=1) == (n - 1)).all()):
            return None

        # Fast path is viable -> NOW resolve "greedy" (deferred to here so the
        # bail paths above never pay for it). If greedy can't run (it won't here,
        # the weights are numeric+complete) we still bail and nx reproduces it.
        if init_is_greedy:
            try:
                init_cycle = self.greedy_tsp(G, weight=weight, source=source)
            except Exception:
                return None

        # Validate the explicit init_cycle exactly as nx does; on any deviation
        # fall back so nx raises the precise error.
        cyc = list(init_cycle)
        src = cyc[0] if source is None else source
        if src != cyc[0] or cyc[0] != cyc[-1]:
            return None
        if len(cyc) - 1 != n:
            return None
        body = cyc[:-1]
        if len(set(body)) != n or any(node not in idx for node in body):
            return None

        cyc_idx = [idx[node] for node in body] + [idx[cyc[-1]]]
        return nodes, W, mv, cyc_idx

    def simulated_annealing_tsp(
        self,
        G,
        init_cycle,
        weight="weight",
        source=None,
        temp=100,
        move="1-1",
        max_iterations=10,
        N_inner=100,
        alpha=0.01,
        seed=None,
        *,
        backend=None,
        **backend_kwargs,
    ):
        # simulated_annealing_tsp delegates through __getattr__ at ~0.26x vs nx:
        # the O(n^2) _networkx_graph_for_parity conversion dominates AND nx's
        # inner loop recomputes the full O(n) cycle cost (per-edge Python dict
        # lookups) N_inner*max_iterations times. De-delegate with an index-space
        # loop reusing nx's exact move functions + RNG (byte-identical draws)
        # and a vectorised numpy cycle cost. At nx's default config
        # (N_inner=100) this is ~2x faster than nx; it strictly beats the old
        # delegated path in every config. Falls back to nx for any case
        # _tsp_anneal_prep can't prove byte-exact (see its doc-comment).
        _validate_backend_dispatch_keywords(
            "simulated_annealing_tsp", backend, backend_kwargs
        )
        if backend is None and not backend_kwargs:
            prep = self._tsp_anneal_prep(G, init_cycle, weight, source, move)
            if prep is not None:
                import math as _math

                from networkx.utils import create_py_random_state as _cprs

                nodes, W, mv, cyc = prep
                rng = _cprs(seed)
                cost = float(W[cyc[:-1], cyc[1:]].sum())
                best_cycle = cyc.copy()
                best_cost = cost
                count = 0
                t = temp
                while count <= max_iterations and t > 0:
                    count += 1
                    for _ in range(N_inner):
                        # nx's move() mutates the cycle IN PLACE and nx passes
                        # the live cycle, so a rejected move is NOT reverted —
                        # only `cost` gates on acceptance. Mirror that exactly.
                        mv(cyc, rng)
                        adj_cost = float(W[cyc[:-1], cyc[1:]].sum())
                        delta = adj_cost - cost
                        if delta <= 0:
                            cost = adj_cost
                            if cost < best_cost:
                                count = 0
                                best_cycle = cyc.copy()
                                best_cost = cost
                        elif _math.exp(-delta / t) >= rng.random():
                            cost = adj_cost
                    t -= t * alpha
                return [nodes[i] for i in best_cycle]
        return _nx.approximation.simulated_annealing_tsp(
            _networkx_graph_for_parity(G),
            init_cycle,
            weight=weight,
            source=source,
            temp=temp,
            move=move,
            max_iterations=max_iterations,
            N_inner=N_inner,
            alpha=alpha,
            seed=seed,
            backend="networkx",
        )

    def threshold_accepting_tsp(
        self,
        G,
        init_cycle,
        weight="weight",
        source=None,
        threshold=1,
        move="1-1",
        max_iterations=10,
        N_inner=100,
        alpha=0.1,
        seed=None,
        *,
        backend=None,
        **backend_kwargs,
    ):
        # Same de-delegation as simulated_annealing_tsp (~0.42x -> >1x at the
        # default config); threshold-accepting differs only in the accept rule
        # (delta <= threshold) and the threshold cooldown (only on an accepted
        # iteration).
        _validate_backend_dispatch_keywords(
            "threshold_accepting_tsp", backend, backend_kwargs
        )
        if backend is None and not backend_kwargs:
            prep = self._tsp_anneal_prep(G, init_cycle, weight, source, move)
            if prep is not None:
                from networkx.utils import create_py_random_state as _cprs

                nodes, W, mv, cyc = prep
                rng = _cprs(seed)
                cost = float(W[cyc[:-1], cyc[1:]].sum())
                best_cycle = cyc.copy()
                best_cost = cost
                count = 0
                thr = threshold
                while count <= max_iterations:
                    count += 1
                    accepted = False
                    for _ in range(N_inner):
                        # In-place move with no revert on reject (see SA note).
                        mv(cyc, rng)
                        adj_cost = float(W[cyc[:-1], cyc[1:]].sum())
                        delta = adj_cost - cost
                        if delta <= thr:
                            accepted = True
                            cost = adj_cost
                            if cost < best_cost:
                                count = 0
                                best_cycle = cyc.copy()
                                best_cost = cost
                    if accepted:
                        thr -= thr * alpha
                return [nodes[i] for i in best_cycle]
        return _nx.approximation.threshold_accepting_tsp(
            _networkx_graph_for_parity(G),
            init_cycle,
            weight=weight,
            source=source,
            threshold=threshold,
            move=move,
            max_iterations=max_iterations,
            N_inner=N_inner,
            alpha=alpha,
            seed=seed,
            backend="networkx",
        )

    def __getattr__(self, name):
        nx_func = getattr(_nx.approximation, name)

        # Preserve nx's exact signature on the wrapper so
        # ``inspect.signature(fnx.approximation.X)`` matches upstream
        # (br-r37-c1-approxsig). Earlier versions used a generic
        # ``(G, *args, **kwargs)`` shape that hid every kwarg from
        # introspection and let typos through silently.
        import functools as _functools
        from franken_networkx.readwrite import _from_nx_graph

        @_functools.wraps(nx_func)
        def wrapper(G, *args, **kwargs):
            nx_G = _networkx_graph_for_parity(G)
            kwargs.setdefault("backend", "networkx")
            result = nx_func(nx_G, *args, **kwargs)
            # br-r37-c1-apxret: convert graph results to fnx types
            if isinstance(result, _nx.Graph):
                return _from_nx_graph(result)
            # br-r37-c1-treewidth: handle (int, Graph) tuple returns
            if isinstance(result, tuple) and len(result) == 2:
                first, second = result
                if isinstance(second, _nx.Graph):
                    return (first, _from_nx_graph(second))
            return result

        return wrapper

    def __dir__(self):
        return sorted(set(dir(_nx.approximation)) | {"treewidth_min_degree"})


_approx_ns = _ApproximationNamespace()
approximation = _approx_ns


def _approx_local_node_connectivity_undirected(G, raw, source, target, cutoff):
    """In-process White & Newman greedy node-connectivity approximation for an
    undirected simple graph, mirroring
    ``networkx.algorithms.approximation.connectivity.local_node_connectivity``
    EXACTLY (same level-alternating bidirectional BFS, same neighbour iteration
    order via the raw binding, same exclude-set update) so the returned count is
    byte-identical. ``raw(G, v)`` yields v's neighbours in G's adjacency order.
    """
    if target == source:
        raise NetworkXError("source and target have to be different nodes.")
    # Maximum possible node independent paths (undirected: min of the degrees).
    possible = min(G.degree(source), G.degree(target))
    if not possible:
        return 0
    if cutoff is None:
        cutoff = float("inf")
    exclude = set()
    k = 0
    for _i in range(min(possible, cutoff)):
        path = _approx_bidirectional_shortest_path_excl(G, raw, source, target, exclude)
        if path is None:
            break
        exclude.update(path)
        k += 1
    return k


def _approx_local_node_connectivity_dict(adj, deg, source, target, cutoff):
    """White & Newman greedy local node-connectivity over a plain Python int->list
    adjacency snapshot (``adj``) and degree map (``deg``). Identical algorithm to
    :func:`_approx_local_node_connectivity_undirected` but with zero PyO3 access —
    used by the global node_connectivity loops where adjacency is touched many
    times, so the one-time snapshot amortizes and pure-dict BFS beats nx's
    AtlasView traversal."""
    possible = min(deg[source], deg[target])
    if not possible:
        return 0
    if cutoff is None:
        cutoff = float("inf")
    exclude = set()
    k = 0
    for _i in range(min(possible, cutoff)):
        path = _approx_bbfs_dict(adj, source, target, exclude)
        if path is None:
            break
        exclude.update(path)
        k += 1
    return k


def _approx_bbfs_dict(adj, source, target, exclude):
    """Level-alternating bidirectional BFS over a plain ``adj`` dict avoiding
    ``exclude``; returns the path list or ``None`` (mirrors nx's
    ``_bidirectional_pred_succ`` exactly)."""
    pred = {source: None}
    succ = {target: None}
    forward_fringe = [source]
    reverse_fringe = [target]
    level = 0
    found = None
    while forward_fringe and reverse_fringe and found is None:
        level += 1
        if level % 2 != 0:
            this_level = forward_fringe
            forward_fringe = []
            for v in this_level:
                for w in adj[v]:
                    if w in exclude:
                        continue
                    if w not in pred:
                        forward_fringe.append(w)
                        pred[w] = v
                    if w in succ:
                        found = w
                        break
                if found is not None:
                    break
        else:
            this_level = reverse_fringe
            reverse_fringe = []
            for v in this_level:
                for w in adj[v]:
                    if w in exclude:
                        continue
                    if w not in succ:
                        succ[w] = v
                        reverse_fringe.append(w)
                    if w in pred:
                        found = w
                        break
                if found is not None:
                    break
    if found is None:
        return None
    w = found
    path = []
    while w is not None:
        path.append(w)
        w = pred[w]
    path.reverse()
    w = succ[path[-1]]
    while w is not None:
        path.append(w)
        w = succ[w]
    return path


def _approx_bidirectional_shortest_path_excl(G, raw, source, target, exclude):
    """Bidirectional BFS shortest path avoiding ``exclude`` nodes; returns the
    path list or ``None`` (nx raises NetworkXNoPath). Level-alternates forward /
    reverse exactly as nx's ``_bidirectional_pred_succ``."""
    pred = {source: None}
    succ = {target: None}
    forward_fringe = [source]
    reverse_fringe = [target]
    level = 0
    found = None
    while forward_fringe and reverse_fringe and found is None:
        level += 1
        if level % 2 != 0:
            this_level = forward_fringe
            forward_fringe = []
            for v in this_level:
                for w in raw(G, v):
                    if w in exclude:
                        continue
                    if w not in pred:
                        forward_fringe.append(w)
                        pred[w] = v
                    if w in succ:
                        found = w
                        break
                if found is not None:
                    break
        else:
            this_level = reverse_fringe
            reverse_fringe = []
            for v in this_level:
                for w in raw(G, v):
                    if w in exclude:
                        continue
                    if w not in succ:
                        succ[w] = v
                        reverse_fringe.append(w)
                    if w in pred:
                        found = w
                        break
                if found is not None:
                    break
    if found is None:
        return None
    w = found
    path = []
    while w is not None:
        path.append(w)
        w = pred[w]
    path.reverse()
    w = succ[path[-1]]
    while w is not None:
        path.append(w)
        w = succ[w]
    return path


# Algorithm functions — cycles
from franken_networkx._fnx import (
    find_cycle as _raw_find_cycle,
    girth as _raw_girth,
)


def girth(G):
    """Return the length of the shortest cycle in ``G``.

    Matches nx contract (br-girthinf): acyclic graphs return
    ``_math.inf`` (float), not ``None``, so ``girth(G) < k`` works
    without TypeError.

    br-r37-c1-tqimg: nx is @not_implemented_for('multigraph').
    """
    import math

    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    value = _raw_girth(G)
    if value is None:
        return _math.inf
    return value


def find_negative_cycle(G, source, weight="weight"):
    """Return a negative cycle reachable from ``source`` using Bellman-Ford.

    Every graph runs networkx's own detector and cycle walk in-process, so
    the returned cycle is the one networkx returns. The former native
    undirected path found a valid negative cycle but a different one in 189
    of 400 random graphs, and panicked on a lone negative edge (nro4w.7).

    br-r37-c1-39gx2 / br-r37-c1-gxu9x: hash-validate and membership-check
    ``source`` up front for nx's TypeError / ``NodeNotFound`` contracts.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(source)
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    return _find_negative_cycle_inprocess(G, source, weight)


def _find_negative_cycle_inprocess(G, source, weight):
    """nx ``find_negative_cycle`` in-process: the heuristic SPFA Bellman-Ford detector
    (``_inner_bellman_ford``) followed by nx's exact cycle-reconstruction walk.
    Returns the byte-identical cycle list."""
    from collections import deque as _deque

    if callable(weight):
        wt = weight
    elif G.is_multigraph():
        wt = lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    else:
        wt = lambda u, v, d: d.get(weight, 1)

    # Weighted successors are read lazily, per node, the first time the search
    # reaches it: networkx's detector usually stops long before visiting the
    # whole graph, so an up-front O(V + E) weight table cost ~50x nx.
    succ_cache = {}

    def succ_of(u):
        weighted = succ_cache.get(u)
        if weighted is None:
            weighted = succ_cache[u] = {v: wt(u, v, d) for v, d in G[u].items()}
        return weighted

    n = len(G)
    inf = float("inf")
    dist = {source: 0}
    pred = {source: []}

    # nx's _inner_bellman_ford, heuristic=True (the find_negative_cycle default).
    nonexistent_edge = (None, None)
    pred_edge = {source: None}
    recent_update = {source: nonexistent_edge}
    count = {}
    q = _deque([source])
    in_q = {source}
    found = None
    while q:
        u = q.popleft()
        in_q.remove(u)
        if all(pred_u not in in_q for pred_u in pred[u]):
            dist_u = dist[u]
            for v, w in succ_of(u).items():
                dist_v = dist_u + w
                if dist_v < dist.get(v, inf):
                    if v in recent_update[u]:
                        pred[v].append(u)
                        found = v
                        break
                    if v in pred_edge and pred_edge[v] == u:
                        recent_update[v] = recent_update[u]
                    else:
                        recent_update[v] = (u, v)
                    if v not in in_q:
                        q.append(v)
                        in_q.add(v)
                        count_v = count.get(v, 0) + 1
                        if count_v == n:
                            found = v
                            break
                        count[v] = count_v
                    dist[v] = dist_v
                    pred[v] = [u]
                    pred_edge[v] = u
                elif dist.get(v) is not None and dist_v == dist.get(v):
                    pred[v].append(u)
        if found is not None:
            break

    if found is None:
        raise NetworkXError("No negative cycles detected.")

    # nx's cycle reconstruction from the predecessor lists.
    v = found
    neg_cycle = []
    stack = [(v, list(pred[v]))]
    seen = {v}
    while stack:
        node, preds = stack[-1]
        if v in preds:
            neg_cycle.extend([node, v])
            return list(reversed(neg_cycle))
        if preds:
            nbr = preds.pop()
            if nbr not in seen:
                stack.append((nbr, list(pred[nbr])))
                neg_cycle.append(node)
                seen.add(nbr)
        else:
            stack.pop()
            if neg_cycle:
                neg_cycle.pop()
            elif v in succ_of(v) and succ_of(v)[v] < 0:
                return [v, v]
            else:
                raise NetworkXError("Negative cycle is detected but not found")
    raise NetworkXUnbounded("negative cycle detected but not identified")

# Algorithm functions — graph predicates
from franken_networkx._fnx import (
    is_graphical,
    is_digraphical as _raw_is_digraphical,
    is_multigraphical,
    is_pseudographical,
    is_k_regular as _raw_is_k_regular,
    is_weighted,
    is_negatively_weighted,
    is_distance_regular as _raw_is_distance_regular,
)


def is_k_regular(G, k):
    """Determines whether the graph ``G`` is a k-regular graph.

    A k-regular graph is a graph where each vertex has degree k.

    Parameters
    ----------
    G : NetworkX graph
    k : int
        Target degree.

    Returns
    -------
    bool
        Whether ``G`` is k-regular.

    br-r37-c1-akzum: wraps the Rust binding so users get a help()
    docstring matching nx.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_k_regular(G, k)


def simple_cycles(G, length_bound=None):
    """Yield simple cycles as lists of nodes.

    Matches upstream's generator contract (franken_networkx-v1nwd) — the
    Rust impl returns cycles in different iteration order than nx.

    br-r37-c1-sccnv: simple_cycles is purely structural (node/edge attrs are
    irrelevant), so the only cost of delegating to nx is the conversion. The full
    ``_fnx_to_nx`` materializes every node/edge attr dict (~3x heavier than a
    bare structure build, ~12.6ms vs ~4ms on 1500n/7000e). For the graph types
    where a structure-only ``add_nodes_from``/``add_edges_from`` build reproduces
    nx's exact node + adjacency order — DiGraph, Graph, MultiDiGraph (verified
    0 mismatches over 1500+ random graphs per type incl. self-loops, parallels,
    and every ``length_bound``) — build the bare nx graph and run nx's algorithm
    directly. Undirected MultiGraph keeps the full conversion: its frozenset
    edge-dedup order in ``_fnx_to_nx`` differs from ``add_edges_from``.
    """
    yield from _simple_cycles_structure_only_via_networkx(G, length_bound)


class _SimpleCyclesNeighborhoodCache(dict):
    def __init__(self, G):
        self.G = G

    def __missing__(self, v):
        Gv = self[v] = list(self.G[v])
        return Gv


from collections import defaultdict as _sc_defaultdict


def _johnson_cycle_search_fnx(G, path):
    G = _SimpleCyclesNeighborhoodCache(G)
    blocked = set(path)
    B = _sc_defaultdict(set)
    start = path[0]
    stack = [iter(G[path[-1]])]
    closed = [False]
    while stack:
        nbrs = stack[-1]
        for w in nbrs:
            if w == start:
                yield path[:]
                closed[-1] = True
            elif w not in blocked:
                path.append(w)
                closed.append(False)
                stack.append(iter(G[w]))
                blocked.add(w)
                break
        else:
            stack.pop()
            v = path.pop()
            if closed.pop():
                if closed:
                    closed[-1] = True
                unblock_stack = {v}
                while unblock_stack:
                    u = unblock_stack.pop()
                    if u in blocked:
                        blocked.remove(u)
                        unblock_stack.update(B[u])
                        B[u].clear()
            else:
                for w in G[v]:
                    B[w].add(v)


def _bounded_cycle_search_fnx(G, path, length_bound):
    G = _SimpleCyclesNeighborhoodCache(G)
    lock = {v: 0 for v in path}
    B = _sc_defaultdict(set)
    start = path[0]
    stack = [iter(G[path[-1]])]
    blen = [length_bound]
    while stack:
        nbrs = stack[-1]
        for w in nbrs:
            if w == start:
                yield path[:]
                blen[-1] = 1
            elif len(path) < lock.get(w, length_bound):
                path.append(w)
                blen.append(length_bound)
                lock[w] = len(path)
                stack.append(iter(G[w]))
                break
        else:
            stack.pop()
            v = path.pop()
            bl = blen.pop()
            if blen:
                blen[-1] = min(blen[-1], bl)
            if bl < length_bound:
                relax_stack = [(bl, v)]
                while relax_stack:
                    bl, u = relax_stack.pop()
                    if lock.get(u, length_bound) < length_bound - bl + 1:
                        lock[u] = length_bound - bl + 1
                        relax_stack.extend((bl + 1, w) for w in B[u].difference(path))
            else:
                for w in G[v]:
                    B[w].add(v)


def _simple_cycles_structure_only_via_networkx(G, length_bound):
    G = _coerce_arg_to_fnx_graph(G)
    if length_bound is not None:
        if length_bound == 0:
            return
        elif length_bound < 0:
            raise ValueError("length bound must be non-negative")

    directed = G.is_directed()
    yield from ([v] for v, Gv in G.adj.items() if v in Gv)

    if length_bound is not None and length_bound == 1:
        return

    if G.is_multigraph() and not directed:
        visited = set()
        for u, Gu in G.adj.items():
            multiplicity = ((v, len(Guv)) for v, Guv in Gu.items() if v in visited)
            yield from ([u, v] for v, m in multiplicity if m > 1)
            visited.add(u)

    if directed:
        H = DiGraph((u, v) for u, Gu in G.adj.items() for v in Gu if v != u)
    else:
        H = Graph((u, v) for u, Gu in G.adj.items() for v in Gu if v != u)

    if length_bound is not None and length_bound == 2:
        if directed:
            visited = set()
            for u, Hu in H.adj.items():
                yield from (
                    [v, u] for v in visited.intersection(Hu) if H.has_edge(v, u)
                )
                visited.add(u)
        return

    if directed:
        components = [c for c in strongly_connected_components(H) if len(c) >= 2]
        while components:
            c = components.pop()
            Hc = H.subgraph(c)
            v = next(iter(c))
            if length_bound is None:
                yield from _johnson_cycle_search_fnx(Hc, [v])
            else:
                yield from _bounded_cycle_search_fnx(Hc, [v], length_bound)
            H.remove_node(v)
            components.extend(c for c in strongly_connected_components(Hc) if len(c) >= 2)
    else:
        components = [c for c in biconnected_components(H) if len(c) >= 3]
        while components:
            c = components.pop()
            Hc = H.subgraph(c)
            uv = list(next(iter(Hc.edges)))
            H.remove_edge(*uv)
            if length_bound is None:
                yield from _johnson_cycle_search_fnx(Hc, uv)
            else:
                yield from _bounded_cycle_search_fnx(Hc, uv, length_bound)
            components.extend(c for c in biconnected_components(Hc) if len(c) >= 3)
