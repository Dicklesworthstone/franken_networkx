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


_UPSTREAM_PUBLIC = getattr(
    _nx_community,
    "__all__",
    tuple(name for name in dir(_nx_community) if not name.startswith("_")),
)
__all__ = sorted(set(_UPSTREAM_PUBLIC) | {"label_propagation_communities"})


def __getattr__(name):  # pragma: no cover — defensive passthrough
    try:
        return getattr(_nx_community, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module 'franken_networkx.community' has no attribute {name!r}"
        ) from exc


def __dir__():
    return sorted(set(__all__) | set(name for name in globals() if not name.startswith("_")))
