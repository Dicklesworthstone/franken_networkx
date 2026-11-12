"""FrankenNetworkX regular submodule.

Re-exports the upstream ``networkx.algorithms.regular`` surface so
existing ``franken_networkx.regular.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``is_regular`` — fnx-native predicate
- ``is_k_regular`` — fnx-native predicate
- ``k_factor`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.regular import *  # noqa: F401,F403
import networkx.algorithms.regular as _nx_regular

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_regular,
        "__all__",
        ("is_regular", "is_k_regular", "k_factor"),
    )
)


def is_regular(G, *, backend=None, **backend_kwargs):
    """Determines whether the graph ``G`` is regular."""
    _fnx._validate_backend_dispatch_keywords("is_regular", backend, backend_kwargs)
    return _fnx.is_regular(G)


def is_k_regular(G, k, *, backend=None, **backend_kwargs):
    """Determines whether the graph ``G`` is a k-regular graph."""
    _fnx._validate_backend_dispatch_keywords("is_k_regular", backend, backend_kwargs)
    return _fnx.is_k_regular(G, k)


def k_factor(G, k, matching_weight='weight', *, backend=None, **backend_kwargs):
    """Compute a k-factor of a graph.

    Routes to ``franken_networkx.k_factor`` for fnx-native parity.
    """
    _fnx._validate_backend_dispatch_keywords("k_factor", backend, backend_kwargs)
    return _fnx.k_factor(G, k, matching_weight=matching_weight)
