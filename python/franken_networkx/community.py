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


_UPSTREAM_PUBLIC = getattr(
    _nx_community,
    "__all__",
    tuple(name for name in dir(_nx_community) if not name.startswith("_")),
)
__all__ = sorted(
    set(_UPSTREAM_PUBLIC)
    | {"label_propagation_communities", "louvain_communities"}
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
