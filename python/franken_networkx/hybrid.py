"""FrankenNetworkX hybrid submodule.

Re-exports the upstream ``networkx.algorithms.hybrid`` surface so
existing ``franken_networkx.hybrid.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``kl_connected_subgraph`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.hybrid import *  # noqa: F401,F403
import networkx.algorithms.hybrid as _nx_hybrid

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_hybrid,
        "__all__",
        ("kl_connected_subgraph", "is_kl_connected"),
    )
)


def kl_connected_subgraph(
    G, k, l, low_memory=False, same_as_graph=False, *, backend=None, **backend_kwargs
):
    """Return the maximum locally (k, l)-connected subgraph of G.

    Wraps ``networkx.algorithms.hybrid.kl_connected_subgraph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("kl_connected_subgraph", backend, backend_kwargs)
    nx_result = _nx_hybrid.kl_connected_subgraph(G, k, l, low_memory=low_memory, same_as_graph=same_as_graph)
    return _from_nx_graph(nx_result)
