"""FrankenNetworkX traversal submodule.

Re-exports the upstream ``networkx.algorithms.traversal`` surface so
existing ``franken_networkx.traversal.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``bfs_tree`` — returns fnx.DiGraph
- ``dfs_tree`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.traversal import *  # noqa: F401,F403
import networkx.algorithms.traversal as _nx_traversal

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


# br-r37-c1-tcnoconv: ``nx.bfs_tree(fnx_G)`` / ``nx.dfs_tree(fnx_G)`` already
# resolve to an fnx-native DiGraph (fnx is a registered backend for these), so the
# subsequent ``_from_nx_graph`` was a pure redundant O(V+E) re-conversion of an
# already-fnx, already-nx-byte-exact tree (verified 2000/2000 each, order-sensitive:
# node order + BFS/DFS edge-discovery order + attrs, across directed/undirected,
# reverse and depth_limit variants). Skip it when the result is already an fnx graph;
# a genuine nx-typed input still yields an nx result -> convert.
def _fnx_result_or_convert(nx_result):
    if isinstance(
        nx_result, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ):
        return nx_result
    return _from_nx_graph(nx_result)


__all__ = list(
    getattr(_nx_traversal, "__all__", ())
    or [name for name in dir(_nx_traversal) if not name.startswith("_")]
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.traversal import *`` above left the
# BFS/DFS edge/node/predecessor/successor generators bound to networkx's
# implementations, so ``fnx.traversal.bfs_edges`` etc. silently resolved to nx's
# instead of fnx's native versions. ``bfs_tree``/``dfs_tree`` already override
# below; route the rest to the fnx top-level functions via call-time closure
# wrappers (robust against the package-init order in which fnx defines them).
_FNX_NATIVE_TRAVERSAL_NAMES = (
    "bfs_beam_edges",
    "bfs_edges",
    "bfs_labeled_edges",
    "bfs_layers",
    "bfs_predecessors",
    "bfs_successors",
    "descendants_at_distance",
    "dfs_edges",
    "dfs_labeled_edges",
    "dfs_postorder_nodes",
    "dfs_predecessors",
    "dfs_preorder_nodes",
    "dfs_successors",
    "edge_bfs",
    "edge_dfs",
    "generic_bfs_edges",
)


def _make_fnx_traversal_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.traversal.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_TRAVERSAL_NAMES:
    globals()[_name] = _make_fnx_traversal_router(_name)


def bfs_tree(G, source, reverse=False, depth_limit=None, sort_neighbors=None, *, backend=None, **backend_kwargs):
    """Return an oriented tree constructed from a breadth-first search.

    Wraps ``networkx.algorithms.traversal.bfs_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("bfs_tree", backend, backend_kwargs)
    nx_result = _nx_traversal.bfs_tree(
        G, source, reverse=reverse, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    )
    return _fnx_result_or_convert(nx_result)


def dfs_tree(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    """Return an oriented tree constructed from a depth-first search.

    Wraps ``networkx.algorithms.traversal.dfs_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("dfs_tree", backend, backend_kwargs)
    nx_result = _nx_traversal.dfs_tree(
        G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    )
    return _fnx_result_or_convert(nx_result)
