"""FrankenNetworkX swap submodule.

Re-exports the upstream ``networkx.algorithms.swap`` surface so
existing ``franken_networkx.swap.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``double_edge_swap`` — returns fnx.Graph
- ``directed_edge_swap`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.swap import *  # noqa: F401,F403
import networkx.algorithms.swap as _nx_swap

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_swap,
        "__all__",
        ("double_edge_swap", "connected_double_edge_swap", "directed_edge_swap"),
    )
)


def double_edge_swap(G, nswap=1, max_tries=100, seed=None, *, backend=None, **backend_kwargs):
    """Swap two edges in the graph while keeping the node degrees fixed.

    Wraps ``networkx.algorithms.swap.double_edge_swap`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("double_edge_swap", backend, backend_kwargs)
    nx_result = _nx_swap.double_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return _from_nx_graph(nx_result)


def directed_edge_swap(G, *, nswap=1, max_tries=100, seed=None, backend=None, **backend_kwargs):
    """Swap three edges in a directed graph while keeping the node degrees fixed.

    Wraps ``networkx.algorithms.swap.directed_edge_swap`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("directed_edge_swap", backend, backend_kwargs)
    nx_result = _nx_swap.directed_edge_swap(G, nswap=nswap, max_tries=max_tries, seed=seed)
    return _from_nx_graph(nx_result)
