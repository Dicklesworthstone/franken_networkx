"""FrankenNetworkX connectivity submodule.

Re-exports the upstream ``networkx.algorithms.connectivity`` surface so
existing ``franken_networkx.connectivity.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``build_auxiliary_node_connectivity`` — returns fnx.DiGraph
- ``build_auxiliary_edge_connectivity`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.connectivity import *  # noqa: F401,F403
import networkx.algorithms.connectivity as _nx_connectivity

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def build_auxiliary_node_connectivity(G):
    """Return auxiliary digraph for computing node connectivity.

    Wraps ``networkx.algorithms.connectivity.build_auxiliary_node_connectivity``
    and converts the result to an fnx.DiGraph for drop-in compatibility.
    """
    nx_result = _nx_connectivity.build_auxiliary_node_connectivity(G)
    return _from_nx_graph(nx_result)


def build_auxiliary_edge_connectivity(G):
    """Return auxiliary digraph for computing edge connectivity.

    Wraps ``networkx.algorithms.connectivity.build_auxiliary_edge_connectivity``
    and converts the result to an fnx.DiGraph for drop-in compatibility.
    """
    nx_result = _nx_connectivity.build_auxiliary_edge_connectivity(G)
    return _from_nx_graph(nx_result)
