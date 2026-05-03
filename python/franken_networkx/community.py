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

from networkx.algorithms.community import *  # noqa: F401,F403

import franken_networkx as _fnx


def label_propagation_communities(G):
    """Yield community sets determined by asynchronous label propagation.

    Native fnx implementation: dispatches to the same Rust binding that
    ``franken_networkx.label_propagation_communities`` uses, returning
    a generator-of-sets matching ``networkx.algorithms.community``'s
    documented contract.
    """
    return _fnx.label_propagation_communities(G)


__all__ = sorted(
    set(globals())
    | set(dir(__import__("networkx.algorithms.community", fromlist=["*"])))
)


def __getattr__(name):  # pragma: no cover — defensive passthrough
    import networkx.algorithms.community as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module 'franken_networkx.community' has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.algorithms.community as _src

    return sorted(set(globals()) | set(dir(_src)))
