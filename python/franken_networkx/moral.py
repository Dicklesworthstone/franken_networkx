"""FrankenNetworkX moral submodule.

Re-exports the upstream ``networkx.algorithms.moral`` surface so
existing ``franken_networkx.moral.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``moral_graph`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.moral import *  # noqa: F401,F403
import networkx.algorithms.moral as _nx_moral

import franken_networkx as _fnx

__all__ = list(getattr(_nx_moral, "__all__", ("moral_graph",)))


def moral_graph(G, *, backend=None, **backend_kwargs):
    """Return the moral graph of a directed acyclic graph.

    Routes directly to the fnx-native ``moral_graph`` implementation,
    avoiding redundant NetworkX conversion overhead while preserving
    return type and dispatch semantics.
    """
    return _fnx.moral_graph(G, backend=backend, **backend_kwargs)
