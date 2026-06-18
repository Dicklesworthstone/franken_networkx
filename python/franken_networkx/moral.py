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
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(getattr(_nx_moral, "__all__", ("moral_graph",)))


def moral_graph(G, *, backend=None, **backend_kwargs):
    """Return the moral graph of a directed acyclic graph.

    Wraps ``networkx.algorithms.moral.moral_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("moral_graph", backend, backend_kwargs)
    nx_result = _nx_moral.moral_graph(G)
    return _from_nx_graph(nx_result)
