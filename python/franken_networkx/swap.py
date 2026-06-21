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
import networkx as _nx

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

    Routes fnx graphs to the native top-level implementation; genuine NetworkX
    inputs keep NetworkX's algorithm. Both mutate and return the input graph.
    """
    _fnx._validate_backend_dispatch_keywords("double_edge_swap", backend, backend_kwargs)
    # br-r37-c1-swaproute: the native top-level ``fnx.double_edge_swap`` uses a fast
    # uniform edge-pick (an intentional, documented divergence from nx's degree-CDF
    # algorithm — only the degree sequence is contracted, not exact output). The
    # submodule previously delegated EVERY input to nx's degree-CDF algorithm, which
    # for an fnx graph ran through fnx's per-access adjacency views (slow) AND
    # produced results inconsistent with the top-level fnx function. Route fnx
    # graphs to the native top-level (fast + the documented fnx behaviour); genuine
    # nx-typed inputs keep nx's algorithm so the nx-parity contract holds.
    if isinstance(G, _nx.Graph):
        return _nx_swap.double_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return _fnx.double_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)


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

    Routes fnx graphs to the native top-level implementation; genuine NetworkX
    inputs keep NetworkX's algorithm. Both mutate and return the input graph.
    """
    _fnx._validate_backend_dispatch_keywords("directed_edge_swap", backend, backend_kwargs)
    # br-r37-c1-swaproute: see double_edge_swap. Route fnx graphs to the native
    # top-level; genuine nx-typed inputs keep nx's algorithm.
    if isinstance(G, _nx.Graph):
        return _nx_swap.directed_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return _fnx.directed_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
