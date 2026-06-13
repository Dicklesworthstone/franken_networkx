"""FrankenNetworkX community submodule.

Re-exports the upstream ``networkx.algorithms.community`` surface so
existing ``franken_networkx.community.*`` call sites keep working, but
overrides specific functions with fnx-native implementations as the
native port lands.

br-r37-c1-rq36c: previously ``franken_networkx.community`` was a
direct alias for ``networkx.algorithms.community``, so calls like
``fnx.community.label_propagation_communities(G)`` ran nx's pure-Python
implementation against an fnx Graph (paying dispatch overhead on top
of the algorithm's own runtime). This module fronts the same surface
but routes the algorithms with fnx fast paths through them.
"""

from __future__ import annotations

import math as _math

import networkx.algorithms.community as _nx_community
from networkx.algorithms.community import *  # noqa: F401,F403

import franken_networkx as _fnx


def modularity(G, communities, weight="weight", resolution=1, *, backend=None, **backend_kwargs):
    """Return the modularity of a partition of ``G``.

    br-r37-c1-modsubmod: this module's ``from
    networkx.algorithms.community import *`` re-exported nx's pure-Python
    ``modularity``, so ``fnx.community.modularity(fnx_graph)`` ran nx's
    algorithm against the fnx Graph's adjacency views (~30x nx on a
    1200-node graph). Route to the registered native backend impl
    (``_modularity_backend_impl`` -> Rust ``_raw_modularity``), which is
    byte-for-byte equal to nx (weighted / resolution / directed / the
    NotAPartition + zero-edge ZeroDivisionError contracts) and ~30x faster.
    """
    _fnx._validate_backend_dispatch_keywords("modularity", backend, backend_kwargs)
    return _fnx._modularity_backend_impl(
        G, communities, weight=weight, resolution=resolution
    )


def kernighan_lin_bisection(
    G, partition=None, max_iter=10, weight="weight", seed=None, *, backend=None, **backend_kwargs
):
    """Partition ``G`` into two blocks via the Kernighan-Lin algorithm.

    br-r37-c1-wxy3x: ``from networkx...community import *`` re-exported nx's
    pure-Python ``kernighan_lin_bisection``, whose only hot cost is building
    ``edge_info`` from ``G._adj.items()`` — on an fnx Graph that walks the slow
    AtlasView adjacency, making it ~2x slower than nx. Build ``edge_info`` from
    the native ``to_dict_of_dicts`` snapshot instead and reuse nx's exact
    ``_kernighan_lin_sweep`` and RNG, so the result is byte-identical to nx (same
    ``list(G)`` node order, same seeded shuffle, same sweep / tie-break) while
    closing the gap (2x slower -> nx parity, 1.34x self-speedup).

    Simple ``Graph`` with a string ``weight`` only; multigraph / callable weight /
    subclass / view delegate to nx (exact path + contract). Directed raises like
    nx's ``@not_implemented_for('directed')``; explicit ``partition`` keeps nx's
    validation.
    """
    _fnx._validate_backend_dispatch_keywords(
        "kernighan_lin_bisection", backend, backend_kwargs
    )
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if type(G) is not _fnx.Graph or callable(weight):
        return _nx_community.kernighan_lin_bisection(
            _fnx._networkx_graph_for_parity(G),
            partition=partition,
            max_iter=max_iter,
            weight=weight,
            seed=seed,
        )

    import inspect as _inspect

    from networkx.utils import create_py_random_state as _create_py_random_state

    # nx keeps the sweep + RNG conversion private; reach the exact same helpers so
    # the heuristic and seeded shuffle match byte-for-byte.
    _sweep = _inspect.unwrap(_nx_community.kernighan_lin_bisection).__globals__[
        "_kernighan_lin_sweep"
    ]

    nodes = list(G)
    if partition is None:
        rng = _create_py_random_state(seed)
        rng.shuffle(nodes)
        mid = len(nodes) // 2
        A, B = nodes[:mid], nodes[mid:]
    else:
        try:
            A, B = partition
        except (TypeError, ValueError) as err:
            raise _fnx.NetworkXError("partition must be two sets") from err
        if not _nx_community.is_partition(G, [A, B]):
            raise _fnx.NetworkXError("partition invalid")

    side = {node: (node in A) for node in nodes}

    # Native bulk snapshot instead of the slow per-node AtlasView walk; identical
    # {u: {v: weight}} structure (node + adjacency order preserved) as nx builds
    # from ``G._adj`` for the simple-graph string-weight case.
    dod = _fnx.to_dict_of_dicts(G)
    edge_info = {
        u: {v: wt for v, d in nbrs.items() if (wt := d.get(weight, 1)) is not None}
        for u, nbrs in dod.items()
    }

    for _ in range(max_iter):
        costs = list(_sweep(edge_info, side))
        min_cost, min_i, _ = min(costs)
        if min_cost >= 0:
            break
        for _cost, _idx, (u, v) in costs[:min_i]:
            side[u] = 1
            side[v] = 0

    part1 = {u for u, s in side.items() if s == 0}
    part2 = {u for u, s in side.items() if s == 1}
    return part1, part2


def label_propagation_communities(G, *, backend=None, **backend_kwargs):
    """Community sets via the semi-synchronous label-propagation method.

    br-r37-c1-0upl7: the previous override (br-r37-c1-lpstruct) still built a
    structural ``nx.Graph`` and ran nx's pure-Python algorithm on it (~1.8x
    nx). Fully de-delegate for the simple ``Graph``: the algorithm only reads
    a graph colouring (native ``greedy_color``, already byte-exact with nx)
    plus per-node neighbour-label frequencies, so run it in index space over a
    one-time key-only adjacency snapshot with a reusable mark-array.

    Byte-identical to nx: colour classes are processed in nx's exact order
    (``greedy_color`` dict-iteration order, mirroring ``_color_network``);
    within a colour class the update order is irrelevant (a proper colouring
    makes each class an independent set, so updates don't see each other);
    labels are the same 0..n-1 ints; the Prec-Max tie-break (``max`` of the
    most-frequent label set) and the final node-order grouping all match.

    Directed graphs raise (nx is ``@not_implemented_for('directed')``);
    multigraph / view / non-fnx graphs delegate to nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "label_propagation_communities", backend, backend_kwargs
    )
    if type(G) is not _fnx.Graph:
        return _nx_community.label_propagation_communities(
            _fnx._networkx_graph_for_parity(G)
        )

    from collections import defaultdict

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}
    adj = [None] * n
    _nak = getattr(G, "_native_adjacency_keys", None)
    if _nak is not None:
        for node, nbrs in _nak():
            adj[idx[node]] = [idx[v] for v in nbrs]
    else:
        for u in node_list:
            adj[idx[u]] = [idx[v] for v in G._adj[u]]

    # Colour classes in nx's exact order (greedy_color dict order).
    colors = _fnx.coloring.greedy_color(G)
    color_buckets = {}
    color_order = []
    for node, color in colors.items():
        bucket = color_buckets.get(color)
        if bucket is None:
            bucket = []
            color_buckets[color] = bucket
            color_order.append(color)
        bucket.append(idx[node])

    labels = list(range(n))
    freq = [0] * n

    def _most_frequent(node):
        # Returns the list of max-frequency neighbour labels (order-immaterial:
        # callers use only membership, length and max).
        touched = []
        for v in adj[node]:
            lab = labels[v]
            if freq[lab] == 0:
                touched.append(lab)
            freq[lab] += 1
        max_freq = freq[touched[0]]
        for lab in touched:
            if freq[lab] > max_freq:
                max_freq = freq[lab]
        best = [lab for lab in touched if freq[lab] == max_freq]
        for lab in touched:
            freq[lab] = 0
        return best

    def _complete():
        for v in range(n):
            if not adj[v]:
                continue
            if labels[v] not in _most_frequent(v):
                return False
        return True

    while not _complete():
        for color in color_order:
            for node in color_buckets[color]:
                if not adj[node]:
                    continue
                best = _most_frequent(node)
                if len(best) == 1:
                    labels[node] = best[0]
                elif len(best) > 1 and labels[node] not in best:
                    labels[node] = max(best)  # Prec-Max tie-break

    clusters = defaultdict(set)
    for i in range(n):
        clusters[labels[i]].add(node_list[i])
    return clusters.values()


def louvain_communities(
    G,
    weight="weight",
    resolution=1,
    threshold=1e-07,
    max_level=None,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Find communities via the Louvain algorithm.

    br-r37-c1-louvainsubmod / br-r37-c1-cy2me: nx's multi-level
    Louvain produces wrong partitions when called on an fnx Graph
    without conversion. Convert via ``_networkx_graph_for_parity``
    then dispatch through nx.algorithms.community.louvain_communities.
    Previously this routed through ``_fnx.louvain_communities``
    (top-level), which was hidden in br-r37-c1-uwm5v.

    Accepts ``backend=`` and arbitrary backend kwargs to match nx's
    public signature (``nx.community.louvain_communities`` exposes
    ``*, backend=None, **backend_kwargs``). They are validated via
    the shared dispatch-keyword guard, then discarded — fnx is the
    backend.
    """
    _fnx._validate_backend_dispatch_keywords(
        "louvain_communities", backend, backend_kwargs
    )
    native_seed = (
        seed
        if isinstance(seed, int)
        and not isinstance(seed, bool)
        and 0 <= seed <= 0xFFFF_FFFF_FFFF_FFFF
        else None
    )
    native_max_level = (
        max_level
        if max_level is None
        or (
            isinstance(max_level, int)
            and not isinstance(max_level, bool)
            and max_level > 0
        )
        else None
    )
    if (
        type(G) is _fnx.Graph
        and native_seed is not None
        and native_max_level == max_level
        and isinstance(weight, str)
        and isinstance(resolution, (int, float))
        and isinstance(threshold, (int, float))
        and not isinstance(resolution, bool)
        and not isinstance(threshold, bool)
        and _math.isfinite(float(resolution))
        and _math.isfinite(float(threshold))
        and float(threshold) >= 0.0
        and G.number_of_edges() > 0
        and _fnx.number_of_selfloops(G) == 0
        and not _fnx._graph_has_edge_attribute(G, weight)
    ):
        return [
            set(community)
            for community in _fnx._raw_louvain_communities(
                G,
                weight,
                float(resolution),
                float(threshold),
                native_max_level,
                native_seed,
            )
        ]

    return _nx_community.louvain_communities(
        _fnx._networkx_graph_for_parity(G),
        weight=weight,
        resolution=resolution,
        threshold=threshold,
        max_level=max_level,
        seed=seed,
    )


def greedy_modularity_communities(
    G,
    weight=None,
    resolution=1,
    cutoff=1,
    best_n=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Find communities using Clauset-Newman-Moore greedy modularity.

    br-r37-c1-wxy3x: the re-exported NetworkX implementation walks fnx
    adjacency views in the hot heap-update loop. The concrete simple,
    unweighted, no-self-loop default case can use the native CNM kernel after
    its NetworkX delta-Q scaling, zero-gain merge, and tie-survivor semantics
    were aligned. Weighted graphs, custom cutoffs, and non-simple graph
    variants delegate to NetworkX.
    """
    _fnx._validate_backend_dispatch_keywords(
        "greedy_modularity_communities", backend, backend_kwargs
    )
    if (
        type(G) is _fnx.Graph
        and weight is None
        and resolution == 1
        and cutoff == 1
        and best_n is None
        and G.number_of_edges() > 0
        and _fnx.number_of_selfloops(G) == 0
    ):
        return [
            frozenset(community)
            for community in _fnx._raw_greedy_modularity_communities(G, resolution, "")
        ]

    graph = _fnx._networkx_graph_for_parity(G) if isinstance(
        G, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ) else G
    return _nx_community.greedy_modularity_communities(
        graph,
        weight=weight,
        resolution=resolution,
        cutoff=cutoff,
        best_n=best_n,
    )


def asyn_lpa_communities(G, weight=None, seed=None):
    """Communities via asynchronous label propagation.

    br-r37-c1-h4bad: the ``from networkx.algorithms.community import *``
    re-export ran nx's pure-Python LPA directly against the fnx Graph,
    rebuilding an adjacency view (``G[node]``) for every node on every
    round (~2.6x nx on a 400-node graph). nx's ``seed`` is already a real
    CPython ``random.Random`` (via ``py_random_state``), so the algorithm
    stays in Python and is byte-exact; the fix is two-fold:

    1. Snapshot the fnx adjacency ONCE via a single native crossing
       (``fnx_to_nx_adjacency``) instead of an ``O(rounds*V)`` view rebuild.
    2. Run the whole label-propagation loop in INDEX space (node -> 0..n-1):
       labels, the shuffle permutation, and the neighbour lists are all
       plain ints, so the hot inner loop never touches a Python node object
       or a dict-of-objects. This is byte-exact because Fisher-Yates
       ``shuffle`` draws depend only on ``len`` (not element values), nx's
       labels are themselves the same 0..n-1 ints, and the final
       ``groups`` mapping is rebuilt in node order.

    asyn_lpa supports directed graphs (unlike ``label_propagation_communities``);
    only the concrete simple undirected ``Graph`` takes the native fast path.
    Non-fnx graphs, directed / multigraph / subgraph-view fnx graphs fall
    through to nx for safety (directed/multigraph adjacency & weight
    semantics differ from the simple-graph fast path).
    """
    from networkx.utils import create_py_random_state, groups

    if not isinstance(
        G, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ):
        return _nx_community.asyn_lpa_communities(G, weight=weight, seed=seed)
    # Only the concrete simple Graph gets the native fast path: the native
    # key/adjacency helpers read the underlying Rust adjacency (bypassing
    # subgraph-view filtering), and directed / multigraph semantics differ.
    if type(G) is not _fnx.Graph:
        return _nx_community.asyn_lpa_communities(
            _fnx._networkx_graph_for_parity(G), weight=weight, seed=seed
        )

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}

    if weight is None:
        # Unweighted (the default): key-only native rows — ``_native_adjacency_keys``
        # is ~4x cheaper than the attr-bearing crossing (no per-edge attr dict
        # materialised). Build the index adjacency keyed by node index so row
        # order is irrelevant.
        _nak = getattr(G, "_native_adjacency_keys", None)
        adj = [None] * n
        if _nak is not None:
            for node, nbrs in _nak():
                adj[idx[node]] = [idx[v] for v in nbrs]
        else:  # defensive: native helper unavailable
            for u in node_list:
                adj[idx[u]] = [idx[v] for v in G._adj[u]]
    else:
        from franken_networkx.backend import (
            _native_fnx_to_nx_adjacency as _bulk_adjacency,
        )

        if _bulk_adjacency is not None:
            bulk = _bulk_adjacency(G)
            canon_to_idx = {canon: i for i, (canon, _nbrs) in enumerate(bulk)}
            adj = [
                [(canon_to_idx[nbr], attrs.get(weight, 1)) for nbr, attrs in nbrs]
                for _canon, nbrs in bulk
            ]
        else:  # defensive: native helper unavailable
            adj = [
                [(idx[v], dd.get(weight, 1)) for v, dd in G._adj[u].items()]
                for u in node_list
            ]

    rng = create_py_random_state(seed)
    unweighted = weight is None

    def _gen():
        labels = list(range(n))
        order = list(range(n))
        # Reusable mark-array keyed by label (labels live in 0..n-1): avoids
        # nx's per-node Counter/defaultdict (hashing + an ABC instancecheck
        # per node per round — ~half the runtime in cProfile). ``freq`` is
        # zeroed only at the touched entries, so reuse is O(degree) not O(n).
        # ``touched`` preserves first-seen label order, matching Counter /
        # defaultdict insertion order exactly, so the best-label tie set and
        # thus every ``seed.choice`` draw is byte-identical to nx.
        freq = [0] * n
        cont = True
        while cont:
            cont = False
            perm = order[:]
            rng.shuffle(perm)
            for node in perm:
                nbrs = adj[node]
                if not nbrs:
                    continue
                touched = []
                if unweighted:
                    for v in nbrs:
                        lab = labels[v]
                        if freq[lab] == 0:
                            touched.append(lab)
                        freq[lab] += 1
                else:
                    for v, wt in nbrs:
                        lab = labels[v]
                        if freq[lab] == 0:
                            touched.append(lab)
                        freq[lab] += wt
                max_freq = freq[touched[0]]
                for lab in touched:
                    if freq[lab] > max_freq:
                        max_freq = freq[lab]
                cur = labels[node]
                best_labels = [lab for lab in touched if freq[lab] == max_freq]
                for lab in touched:
                    freq[lab] = 0
                if cur not in best_labels:
                    labels[node] = rng.choice(best_labels)
                    cont = True
        # Rebuild node-keyed labels in node order so groups() yields the
        # exact communities (sets of node objects) nx would.
        label_by_node = {node_list[i]: labels[i] for i in range(n)}
        yield from groups(label_by_node).values()

    return _gen()


def fast_label_propagation_communities(G, *, weight=None, seed=None):
    """Communities via fast label propagation (Traag & Šubelj 2023).

    br-r37-c1-0gjy3: same ``import *`` re-export tax as
    ``asyn_lpa_communities`` (~2x nx) — nx's queue-driven LPA ran against the
    fnx Graph, rebuilding adjacency views. ``seed`` is a real CPython
    ``random.Random`` (``py_random_state``) so a Python in-process impl is
    byte-exact. Same three levers (key-only snapshot + index space + reusable
    mark-array), plus one extra: nx shuffles a ``deque`` (``deque[i]`` is
    O(n), so its initial shuffle is O(n^2)); shuffling a plain list of indices
    yields the IDENTICAL permutation (Fisher-Yates draws depend only on
    ``len``, not the container) in O(n), then seeds the work deque.

    Only the concrete simple unweighted ``Graph`` takes the fast path;
    everything else (weighted / directed / multigraph / view / non-fnx)
    delegates to nx (directed uses pred+succ and in_edges; weighted reads
    edge data — different code paths).
    """
    from collections import deque

    from networkx.utils import create_py_random_state, groups

    if (
        type(G) is not _fnx.Graph
        or weight is not None
        or getattr(G, "_native_adjacency_keys", None) is None
    ):
        if isinstance(
            G, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
        ):
            return _nx_community.fast_label_propagation_communities(
                _fnx._networkx_graph_for_parity(G), weight=weight, seed=seed
            )
        return _nx_community.fast_label_propagation_communities(
            G, weight=weight, seed=seed
        )

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}
    adj = [None] * n
    for node, nbrs in G._native_adjacency_keys():
        adj[idx[node]] = [idx[v] for v in nbrs]

    rng = create_py_random_state(seed)

    def _gen():
        comms = list(range(n))
        perm = list(range(n))
        rng.shuffle(perm)  # O(n); identical permutation to nx's deque shuffle
        queue = deque(perm)
        in_queue = [True] * n  # bool array mirrors nx's nodes_set membership
        freq = [0] * n
        while queue:
            node = queue.popleft()
            in_queue[node] = False
            nbrs = adj[node]
            if not nbrs:
                continue
            touched = []
            for v in nbrs:
                lab = comms[v]
                if freq[lab] == 0:
                    touched.append(lab)
                freq[lab] += 1
            max_freq = freq[touched[0]]
            for lab in touched:
                if freq[lab] > max_freq:
                    max_freq = freq[lab]
            best_labels = [lab for lab in touched if freq[lab] == max_freq]
            for lab in touched:
                freq[lab] = 0
            comm = rng.choice(best_labels)
            if comms[node] != comm:
                comms[node] = comm
                for v in nbrs:
                    if comms[v] != comm and not in_queue[v]:
                        queue.append(v)
                        in_queue[v] = True
        label_by_node = {node_list[i]: comms[i] for i in range(n)}
        yield from groups(label_by_node).values()

    return _gen()


def k_clique_communities(G, k, cliques=None, *, backend=None, **backend_kwargs):
    """Find k-clique communities via the clique-percolation method.

    br-r37-c1-emdlw: ``k_clique_communities`` is ``@nx._dispatchable``, so the
    ``from networkx... import *`` re-export converted the WHOLE fnx graph to
    nx (``_fnx_to_nx``, attrs and all) on every call (~78% of runtime in
    cProfile, ~2x nx). Two levers:

    1. The algorithm only needs ``G``'s maximal cliques; everything after is
       graph-free. Compute them with fnx's native ``find_cliques`` (already
       nx-order) — no whole-graph conversion.
    2. Replace nx's percolation graph + ``connected_components`` (which adds an
       ``nx.Graph`` node per clique and an edge per adjacent pair, then
       BFS — O(#cliques^2) on dense inputs) with a **union-find over the
       (k-1)-node subsets**: two maximal cliques of size >= k percolate iff
       they share >= k-1 nodes iff they share a common (k-1)-subset, so
       unioning all cliques that map to the same (k-1)-subset gives the exact
       same components in near-linear time (20-130x faster on dense graphs).

    Byte-identical to nx: components are emitted in first-clique-index order
    (matching ``connected_components``, which starts each component at the
    lowest-index unvisited clique in percolation-graph node order = clique
    order), and each community is the ``frozenset`` union of its cliques.

    Non-fnx graphs fall through to nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "k_clique_communities", backend, backend_kwargs
    )
    if not isinstance(
        G, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ):
        return _nx_community.k_clique_communities(G, k, cliques=cliques)

    import networkx as _nx
    from itertools import combinations

    def _gen():
        if k < 2:
            raise _nx.NetworkXError(f"k={k}, k must be greater than 1.")
        nonlocal cliques
        if cliques is None:
            cliques = _fnx.find_cliques(G)
        clique_list = [frozenset(c) for c in cliques if len(c) >= k]
        m = len(clique_list)

        # Union-find over clique indices, merged via shared (k-1)-subsets.
        parent = list(range(m))

        def _find(x):
            root = x
            while parent[root] != root:
                root = parent[root]
            while parent[x] != root:
                parent[x], x = root, parent[x]
            return root

        km1 = k - 1
        subset_first = {}
        for i, clique in enumerate(clique_list):
            for sub in combinations(sorted(clique), km1):
                j = subset_first.get(sub)
                if j is None:
                    subset_first[sub] = i
                else:
                    ri, rj = _find(i), _find(j)
                    if ri != rj:
                        parent[ri] = rj

        # Emit each component in order of its lowest clique index (==
        # connected_components yield order over the percolation graph).
        root_nodes = {}
        order = []
        for i in range(m):
            r = _find(i)
            bucket = root_nodes.get(r)
            if bucket is None:
                bucket = set()
                root_nodes[r] = bucket
                order.append(r)
            bucket |= clique_list[i]

        for r in order:
            yield frozenset(root_nodes[r])

    return _gen()


_UPSTREAM_PUBLIC = getattr(
    _nx_community,
    "__all__",
    tuple(name for name in dir(_nx_community) if not name.startswith("_")),
)
__all__ = sorted(
    set(_UPSTREAM_PUBLIC)
    | {
        "label_propagation_communities",
        "louvain_communities",
        "asyn_lpa_communities",
        "fast_label_propagation_communities",
        "greedy_modularity_communities",
        "k_clique_communities",
    }
)


def __getattr__(name):  # pragma: no cover — defensive passthrough
    try:
        return getattr(_nx_community, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module 'franken_networkx.community' has no attribute {name!r}"
        ) from exc


def is_partition(G, communities):
    """Return True iff ``communities`` is a partition of the nodes of ``G``.

    br-r37-c1-commpart: re-exported from networkx as ``@nx._dispatchable``, so
    ``fnx.community.is_partition(fnx_graph, ...)`` round-tripped the WHOLE graph
    through ``_fnx_to_nx`` (full O(V+E) conversion) for an O(V) membership check
    — ~52x slower than nx. networkx's exact predicate run in-process (uses only
    ``len(G)`` and ``n in G``, no nx helpers) — byte-identical.
    """
    if not isinstance(communities, list):
        communities = list(communities)
    # Snapshot the node set ONCE so per-element membership is a pure-Python set
    # lookup rather than a PyO3 ``n in G`` crossing for every node in every block.
    gnodes = set(G)
    nodes = {n for c in communities for n in c if n in gnodes}
    return len(gnodes) == len(nodes) == sum(len(c) for c in communities)


def partition_quality(G, partition):
    """Return ``(coverage, performance)`` of ``partition`` of ``G``.

    br-r37-c1-commpart: same ``@nx._dispatchable`` conversion tax as
    :func:`is_partition` (~14x slower). networkx's exact O(C^2 + L) algorithm run
    in-process — byte-identical, including the exact ``NetworkXError`` message
    networkx's ``@require_partition`` raises on an invalid partition and the
    multigraph ``performance == -1.0`` contract.
    """
    from itertools import combinations as _combinations

    if not is_partition(G, partition):
        raise _fnx.NetworkXError(
            "`partition` is not a valid partition of the nodes of G"
        )

    node_community = {}
    for i, community in enumerate(partition):
        for node in community:
            node_community[node] = i

    if not G.is_multigraph():
        possible_inter_community_edges = sum(
            len(p1) * len(p2) for p1, p2 in _combinations(partition, 2)
        )
        if G.is_directed():
            possible_inter_community_edges *= 2
    else:
        possible_inter_community_edges = 0

    n = len(G)
    total_pairs = n * (n - 1)
    if not G.is_directed():
        total_pairs //= 2

    intra_community_edges = 0
    inter_community_non_edges = possible_inter_community_edges
    for e in G.edges():
        if node_community[e[0]] == node_community[e[1]]:
            intra_community_edges += 1
        else:
            inter_community_non_edges -= 1

    coverage = intra_community_edges / len(G.edges)
    if G.is_multigraph():
        performance = -1.0
    else:
        performance = (intra_community_edges + inter_community_non_edges) / total_pairs
    return coverage, performance


def __dir__():
    return sorted(set(__all__) | set(name for name in globals() if not name.startswith("_")))
