"""FrankenNetworkX components submodule.

Re-exports the upstream ``networkx.algorithms.components`` surface so
existing ``franken_networkx.components.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``condensation`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.components import *  # noqa: F401,F403
import networkx.algorithms.components as _nx_components

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def condensation(G, scc=None, *, backend=None, **backend_kwargs):
    """Return the condensation of G.

    Wraps ``networkx.algorithms.components.condensation`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("condensation", backend, backend_kwargs)
    nx_result = _nx_components.condensation(G, scc=scc)
    return _from_nx_graph(nx_result)
