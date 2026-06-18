"""FrankenNetworkX swap submodule.

Re-exports the upstream ``networkx.algorithms.swap`` surface so
existing ``franken_networkx.swap.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that preserve
NetworkX's mutating return identity.

Current native overrides:
- ``double_edge_swap`` — mutates and returns the input graph
- ``directed_edge_swap`` — mutates and returns the input graph
"""

from __future__ import annotations

from networkx.algorithms.swap import *  # noqa: F401,F403
import networkx.algorithms.swap as _nx_swap

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_swap,
        "__all__",
        ("double_edge_swap", "connected_double_edge_swap", "directed_edge_swap"),
    )
)


def double_edge_swap(G, nswap=1, max_tries=100, seed=None, *, backend=None, **backend_kwargs):
    """Swap two edges in the graph while keeping the node degrees fixed.

    Wraps ``networkx.algorithms.swap.double_edge_swap`` and preserves the
    mutating in-place return identity.
    """
    _fnx._validate_backend_dispatch_keywords("double_edge_swap", backend, backend_kwargs)
    nx_result = _nx_swap.double_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return nx_result


def connected_double_edge_swap(
    G, nswap=1, _window_threshold=3, seed=None, *, backend=None, **backend_kwargs
):
    """Swap edges through the fnx guarded connected-swap implementation."""
    _fnx._validate_backend_dispatch_keywords(
        "connected_double_edge_swap", backend, backend_kwargs
    )
    return _fnx.connected_double_edge_swap(
        G, nswap=nswap, _window_threshold=_window_threshold, seed=seed
    )


def directed_edge_swap(G, *, nswap=1, max_tries=100, seed=None, backend=None, **backend_kwargs):
    """Swap three edges in a directed graph while keeping the node degrees fixed.

    Wraps ``networkx.algorithms.swap.directed_edge_swap`` and preserves the
    mutating in-place return identity.
    """
    _fnx._validate_backend_dispatch_keywords("directed_edge_swap", backend, backend_kwargs)
    nx_result = _nx_swap.directed_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return nx_result
