"""FrankenNetworkX regular submodule.

Re-exports the upstream ``networkx.algorithms.regular`` surface so
existing ``franken_networkx.regular.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``k_factor`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.regular import *  # noqa: F401,F403
import networkx.algorithms.regular as _nx_regular

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def k_factor(G, k, matching_weight='weight', *, backend=None, **backend_kwargs):
    """Compute a k-factor of a graph.

    Wraps ``networkx.algorithms.regular.k_factor`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("k_factor", backend, backend_kwargs)
    nx_result = _nx_regular.k_factor(G, k, matching_weight=matching_weight)
    return _from_nx_graph(nx_result)
