"""FrankenNetworkX sparsifiers submodule.

Re-exports the upstream ``networkx.algorithms.sparsifiers`` surface so
existing ``franken_networkx.sparsifiers.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``spanner`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.sparsifiers import *  # noqa: F401,F403
import networkx.algorithms.sparsifiers as _nx_sparsifiers

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def spanner(G, stretch, weight=None, seed=None, *, backend=None, **backend_kwargs):
    """Return a spanner of the given graph.

    Wraps ``networkx.algorithms.sparsifiers.spanner`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("spanner", backend, backend_kwargs)
    nx_result = _nx_sparsifiers.spanner(G, stretch, weight=weight, seed=seed)
    return _from_nx_graph(nx_result)
