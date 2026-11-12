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

def is_chordal(G, *, backend=None, **backend_kwargs):
    """Return whether ``G`` is chordal."""
    return _fnx.is_chordal(G, backend=backend, **backend_kwargs)


def find_induced_nodes(
    G,
    s,
    t,
    treewidth_bound=9223372036854775807,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the nodes of an induced cycle containing ``s`` and ``t``."""
    return _fnx.find_induced_nodes(
        G,
        s,
        t,
        treewidth_bound=treewidth_bound,
        backend=backend,
        **backend_kwargs,
    )


def chordal_graph_cliques(G, *, backend=None, **backend_kwargs):
    """Return the maximal cliques of a chordal graph."""
    return _fnx.chordal_graph_cliques(G, backend=backend, **backend_kwargs)


def chordal_graph_treewidth(G, *, backend=None, **backend_kwargs):
    """Return the treewidth of a chordal graph."""
    return _fnx.chordal_graph_treewidth(G, backend=backend, **backend_kwargs)

if hasattr(_fnx, "NetworkXTreewidthBoundExceeded"):
    NetworkXTreewidthBoundExceeded = _fnx.NetworkXTreewidthBoundExceeded


def complete_to_chordal_graph(G, *, backend=None, **backend_kwargs):
    """Return a chordal completion of G and the added fill-in edges.

    Routes through the fnx top-level implementation so the standalone chordal
    module path returns the same native graph type and alpha map as
    ``franken_networkx.complete_to_chordal_graph``.
    """
    return _fnx.complete_to_chordal_graph(
        G,
        backend=backend,
        **backend_kwargs,
    )
