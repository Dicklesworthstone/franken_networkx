"""FrankenNetworkX flow submodule.

Re-exports the upstream ``networkx.algorithms.flow`` surface so
existing ``franken_networkx.flow.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``gomory_hu_tree`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.flow import *  # noqa: F401,F403
import networkx.algorithms.flow as _nx_flow

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def gomory_hu_tree(G, capacity="capacity", flow_func=None, *, backend=None, **backend_kwargs):
    """Return the Gomory-Hu tree of an undirected graph.

    Wraps ``networkx.algorithms.flow.gomory_hu_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("gomory_hu_tree", backend, backend_kwargs)
    nx_result = _nx_flow.gomory_hu_tree(G, capacity=capacity, flow_func=flow_func)
    return _from_nx_graph(nx_result)
