"""FrankenNetworkX euler submodule.

Re-exports the upstream ``networkx.algorithms.euler`` surface so
existing ``franken_networkx.euler.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``eulerize`` — returns fnx.MultiGraph
"""

from __future__ import annotations

from networkx.algorithms.euler import *  # noqa: F401,F403
import networkx.algorithms.euler as _nx_euler

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def eulerize(G, *, backend=None, **backend_kwargs):
    """Transform a graph into an Eulerian graph.

    Wraps ``networkx.algorithms.euler.eulerize`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("eulerize", backend, backend_kwargs)
    nx_result = _nx_euler.eulerize(G)
    return _from_nx_graph(nx_result)
