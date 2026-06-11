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
    """Yield community sets determined by asynchronous label propagation.

    br-r37-c1-cy2me: re-routes to nx's algorithm against the converted
    graph. Previously called ``_fnx.label_propagation_communities``
    (top-level), which was hidden in br-r37-c1-02sx1.
    """
    _fnx._validate_backend_dispatch_keywords(
        "label_propagation_communities", backend, backend_kwargs
    )
    # br-r37-c1-lpstruct: label_propagation is unweighted and structure-only
    # (the semi-synchronous algorithm reads only node iteration order + the
    # neighbour SET via greedy_color + a Counter of neighbour labels). The full
    # `_networkx_graph_for_parity` faithful conversion (node/edge/graph attrs)
    # was ~17ms of the ~31ms call (55%); a structural nx.Graph built from G's
    # nodes (G's order) + edges (G's edge order) reproduces the same node and
    # adjacency iteration order — so greedy_color and the labeling are
    # byte-identical — for ~half the conversion cost. Gate to a plain simple
    # Graph; multigraph / views keep the faithful path.
    import networkx as _nx
    if type(G) is _fnx.Graph:
        structural = _nx.Graph()
        structural.add_nodes_from(G)
        structural.add_edges_from(G.edges())
        return _nx_community.label_propagation_communities(structural)
    return _nx_community.label_propagation_communities(
        _fnx._networkx_graph_for_parity(G)
    )


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


_UPSTREAM_PUBLIC = getattr(
    _nx_community,
    "__all__",
    tuple(name for name in dir(_nx_community) if not name.startswith("_")),
)
__all__ = sorted(
    set(_UPSTREAM_PUBLIC)
    | {"label_propagation_communities", "louvain_communities", "asyn_lpa_communities"}
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
