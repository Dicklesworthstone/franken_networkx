"""FrankenNetworkX hybrid submodule.

Re-exports the upstream ``networkx.algorithms.hybrid`` surface so
existing ``franken_networkx.hybrid.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``kl_connected_subgraph`` — returns fnx.Graph
- ``is_kl_connected`` — returns fnx-native boolean parity
"""

from __future__ import annotations

from networkx.algorithms.hybrid import *  # noqa: F401,F403
import networkx.algorithms.hybrid as _nx_hybrid

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_hybrid,
        "__all__",
        ("kl_connected_subgraph", "is_kl_connected"),
    )
)


def is_kl_connected(G, k, l, low_memory=False, *, backend=None, **backend_kwargs):
    """Return whether G is locally (k, l)-connected via the fnx-native route."""
    return _fnx.is_kl_connected(
        G,
        k,
        l,
        low_memory=low_memory,
        backend=backend,
        **backend_kwargs,
    )


def kl_connected_subgraph(
    G, k, l, low_memory=False, same_as_graph=False, *, backend=None, **backend_kwargs
):
    """Return the maximum locally (k, l)-connected subgraph of G.

    Routes through ``franken_networkx.kl_connected_subgraph`` so the standalone
    hybrid module path preserves fnx graph types without a NetworkX round trip.
    """
    return _fnx.kl_connected_subgraph(
        G,
        k,
        l,
        low_memory=low_memory,
        same_as_graph=same_as_graph,
        backend=backend,
        **backend_kwargs,
    )
