"""FrankenNetworkX dag submodule.

Re-exports the upstream ``networkx.algorithms.dag`` surface so
existing ``franken_networkx.dag.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``dag_to_branching`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.dag import *  # noqa: F401,F403
import networkx.algorithms.dag as _nx_dag

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def dag_to_branching(G, *, backend=None, **backend_kwargs):
    """Return a branching representing the DAG.

    Wraps ``networkx.algorithms.dag.dag_to_branching`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("dag_to_branching", backend, backend_kwargs)
    nx_result = _nx_dag.dag_to_branching(G)
    return _from_nx_graph(nx_result)
