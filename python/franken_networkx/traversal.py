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


def bfs_tree(G, source, reverse=False, depth_limit=None, sort_neighbors=None, *, backend=None, **backend_kwargs):
    """Return an oriented tree constructed from a breadth-first search.

    Wraps ``networkx.algorithms.traversal.bfs_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("bfs_tree", backend, backend_kwargs)
    nx_result = _nx_traversal.bfs_tree(
        G, source, reverse=reverse, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    )
    return _from_nx_graph(nx_result)


def dfs_tree(G, source=None, depth_limit=None, *, sort_neighbors=None, backend=None, **backend_kwargs):
    """Return an oriented tree constructed from a depth-first search.

    Wraps ``networkx.algorithms.traversal.dfs_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("dfs_tree", backend, backend_kwargs)
    nx_result = _nx_traversal.dfs_tree(
        G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    )
    return _from_nx_graph(nx_result)
