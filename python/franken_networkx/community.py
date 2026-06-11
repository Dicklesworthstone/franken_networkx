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
    return _nx_community.louvain_communities(
        _fnx._networkx_graph_for_parity(G),
        weight=weight,
        resolution=resolution,
        threshold=threshold,
        max_level=max_level,
        seed=seed,
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


def __dir__():
    return sorted(set(__all__) | set(name for name in globals() if not name.startswith("_")))
