"""FrankenNetworkX chordal submodule.

Re-exports the upstream ``networkx.algorithms.chordal`` surface so
existing ``franken_networkx.chordal.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``complete_to_chordal_graph`` — returns (fnx.Graph, dict)
"""

from __future__ import annotations

from networkx.algorithms.chordal import *  # noqa: F401,F403
import networkx.algorithms.chordal as _nx_chordal

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_chordal,
        "__all__",
        (
            "is_chordal",
            "find_induced_nodes",
            "chordal_graph_cliques",
            "chordal_graph_treewidth",
            "NetworkXTreewidthBoundExceeded",
            "complete_to_chordal_graph",
        ),
    )
)


def complete_to_chordal_graph(G, *, backend=None, **backend_kwargs):
    """Return a chordal completion of G and the added fill-in edges.

    Wraps ``networkx.algorithms.chordal.complete_to_chordal_graph`` and converts
    the graph in the result tuple to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("complete_to_chordal_graph", backend, backend_kwargs)
    nx_graph, fill_in = _nx_chordal.complete_to_chordal_graph(G)
    return _from_nx_graph(nx_graph), fill_in
