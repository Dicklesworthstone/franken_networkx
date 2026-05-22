"""FrankenNetworkX tournament submodule.

Re-exports the upstream ``networkx.algorithms.tournament`` surface so
existing ``franken_networkx.tournament.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``random_tournament`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.tournament import *  # noqa: F401,F403
import networkx.algorithms.tournament as _nx_tournament

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def random_tournament(n, seed=None, *, backend=None, **backend_kwargs):
    """Return a random tournament graph on n nodes.

    Wraps ``networkx.algorithms.tournament.random_tournament`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("random_tournament", backend, backend_kwargs)
    nx_result = _nx_tournament.random_tournament(n, seed=seed)
    return _from_nx_graph(nx_result)
