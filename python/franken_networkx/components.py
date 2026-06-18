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

__all__ = list(
    getattr(_nx_components, "__all__", ())
    or [name for name in dir(_nx_components) if not name.startswith("_")]
)


def condensation(G, scc=None, *, backend=None, **backend_kwargs):
    """Return the condensation of G.

    Returns the same fnx-native graph as ``franken_networkx.condensation``.
    """
    _fnx._validate_backend_dispatch_keywords("condensation", backend, backend_kwargs)
    return _fnx.condensation(G, scc=scc)
