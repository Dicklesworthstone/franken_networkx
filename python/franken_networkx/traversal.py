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
def bfs_beam_edges(G, source, value, width=None, *, backend=None, **backend_kwargs):
    return _fnx.bfs_beam_edges(G, source, value, width=width, backend=backend, **backend_kwargs)


def bfs_edges(G, source, reverse=False, depth_limit=None, sort_neighbors=None, *, backend=None, **backend_kwargs):
    return _fnx.bfs_edges(G, source, reverse=reverse, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def bfs_labeled_edges(G, sources, *, backend=None, **backend_kwargs):
    return _fnx.bfs_labeled_edges(G, sources, backend=backend, **backend_kwargs)


def bfs_layers(G, sources, *, backend=None, **backend_kwargs):
    return _fnx.bfs_layers(G, sources, backend=backend, **backend_kwargs)


def bfs_predecessors(G, source, depth_limit=None, sort_neighbors=None, *, backend=None, **backend_kwargs):
    return _fnx.bfs_predecessors(G, source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def bfs_successors(G, source, depth_limit=None, sort_neighbors=None, *, backend=None, **backend_kwargs):
    return _fnx.bfs_successors(G, source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def descendants_at_distance(G, source, distance, *, backend=None, **backend_kwargs):
    return _fnx.descendants_at_distance(G, source, distance, backend=backend, **backend_kwargs)


def dfs_edges(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_edges(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def dfs_labeled_edges(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_labeled_edges(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def dfs_postorder_nodes(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_postorder_nodes(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def dfs_predecessors(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_predecessors(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def dfs_preorder_nodes(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_preorder_nodes(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def dfs_successors(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    return _fnx.dfs_successors(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors, backend=backend, **backend_kwargs)


def edge_bfs(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    return _fnx.edge_bfs(G, source=source, orientation=orientation, backend=backend, **backend_kwargs)


def edge_dfs(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    return _fnx.edge_dfs(G, source=source, orientation=orientation, backend=backend, **backend_kwargs)


def generic_bfs_edges(G, source, neighbors=None, depth_limit=None, *, backend=None, **backend_kwargs):
    return _fnx.generic_bfs_edges(G, source, neighbors=neighbors, depth_limit=depth_limit, backend=backend, **backend_kwargs)


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
