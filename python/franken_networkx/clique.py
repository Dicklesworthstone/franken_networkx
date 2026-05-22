"""FrankenNetworkX clique submodule.

Re-exports the upstream ``networkx.algorithms.clique`` surface so
existing ``franken_networkx.clique.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``make_clique_bipartite`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.clique import *  # noqa: F401,F403
import networkx.algorithms.clique as _nx_clique

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def make_clique_bipartite(G, fpos=None, create_using=None, name=None, *, backend=None, **backend_kwargs):
    """Return the bipartite clique graph corresponding to G.

    Wraps ``networkx.algorithms.clique.make_clique_bipartite`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("make_clique_bipartite", backend, backend_kwargs)
    nx_result = _nx_clique.make_clique_bipartite(G, fpos=fpos, create_using=create_using, name=name)
    return _from_nx_graph(nx_result, create_using=create_using)
