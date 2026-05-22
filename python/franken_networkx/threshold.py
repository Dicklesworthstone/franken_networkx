"""FrankenNetworkX threshold submodule.

Re-exports the upstream ``networkx.algorithms.threshold`` surface so
existing ``franken_networkx.threshold.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``find_threshold_graph`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.threshold import *  # noqa: F401,F403
import networkx.algorithms.threshold as _nx_threshold

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

# br-r37-c1-ukwgj: find_alternating_4_cycle and find_creation_sequence
# are dispatchable but absent from threshold.__all__ (which lists only
# is_threshold_graph / find_threshold_graph), so the star import skips
# them.  Re-export for fnx.algorithms.threshold parity.
find_alternating_4_cycle = _nx_threshold.find_alternating_4_cycle
find_creation_sequence = _nx_threshold.find_creation_sequence


def find_threshold_graph(G, create_using=None, *, backend=None, **backend_kwargs):
    """Find a threshold subgraph of the given graph.

    Wraps ``networkx.algorithms.threshold.find_threshold_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("find_threshold_graph", backend, backend_kwargs)
    nx_result = _nx_threshold.find_threshold_graph(G, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)


def threshold_graph(creation_sequence, create_using=None, *, backend=None, **backend_kwargs):
    """Build a threshold graph from a creation sequence.

    Wraps ``networkx.algorithms.threshold.threshold_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("threshold_graph", backend, backend_kwargs)
    nx_result = _nx_threshold.threshold_graph(creation_sequence, create_using=create_using)
    return _from_nx_graph(nx_result, create_using=create_using)
