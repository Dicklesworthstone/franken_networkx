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


def label_propagation_communities(G, *, backend=None, **backend_kwargs):
    """Yield community sets determined by asynchronous label propagation.

    Native fnx implementation: dispatches to the same Rust binding that
    ``franken_networkx.label_propagation_communities`` uses, returning
    a generator-of-sets matching ``networkx.algorithms.community``'s
    documented contract.

    br-r37-c1-bk-submod: backend dispatch surface match nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "label_propagation_communities", backend, backend_kwargs
    )
    return _fnx.label_propagation_communities(G)


def louvain_communities(
    G,
    weight="weight",
    resolution=1,
    threshold=1e-07,
    max_level=None,
    seed=None,
):
    """Find communities via the Louvain algorithm.

    br-r37-c1-louvainsubmod: ``fnx.community.louvain_communities``
    previously re-exported nx's function directly via the
    ``from networkx.algorithms.community import *`` line. Calling
    ``nx.community.louvain_communities`` on an fnx Graph (no
    conversion to a real nx Graph) produced WRONG partitions —
    nx's multi-level Louvain returns trivial 2-cluster partition
    on Karate (modularity ~0.40) instead of the canonical 4-cluster
    answer (modularity ~0.44).  Direct call via the top-level
    ``fnx.louvain_communities`` correctly converts and returns
    the 4-cluster answer.  Drop-in code using the canonical
    submodule path (``fnx.community.louvain_communities``) silently
    got the wrong answer.

    Fix: route this submodule entry-point through the top-level
    ``franken_networkx.louvain_communities`` (which goes through
    ``_louvain_impl`` → ``_call_networkx_submodule_for_parity`` →
    ``_fnx_to_nx`` conversion).
    """
    return _fnx.louvain_communities(
        G,
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
