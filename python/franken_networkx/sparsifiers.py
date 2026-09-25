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
import networkx.algorithms.sparsifiers as _nx_sparsifiers  # noqa: F401

import franken_networkx as _fnx

__all__ = list(getattr(_nx_sparsifiers, "__all__", ("spanner",)))


def spanner(G, stretch, weight=None, seed=None, *, backend=None, **backend_kwargs):
    """Return a spanner of the given graph.

    Routes to the fnx top-level ``spanner``: networkx's Baswana-Sen step for
    step (the same edges for the same seed and node objects, nro4w.7) with
    networkx's exact input validation / not-implemented-for contracts.
    """
    _fnx._validate_backend_dispatch_keywords("spanner", backend, backend_kwargs)
    return _fnx.spanner(G, stretch, weight=weight, seed=seed)
