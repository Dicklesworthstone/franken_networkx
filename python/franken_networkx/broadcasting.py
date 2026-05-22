"""FrankenNetworkX broadcasting submodule.

Re-exports the upstream ``networkx.algorithms.broadcasting`` surface so
existing ``franken_networkx.broadcasting.*`` call sites keep working.

Current functions:
- ``tree_broadcast_center`` — returns (time, centers) tuple
- ``tree_broadcast_time`` — returns broadcast time from node
"""

from __future__ import annotations

from networkx.algorithms.broadcasting import *  # noqa: F401,F403
import networkx.algorithms.broadcasting as _nx_broadcasting

import franken_networkx as _fnx


def tree_broadcast_center(G, *, backend=None, **backend_kwargs):
    """Return the tree broadcast center.

    Wraps ``networkx.algorithms.broadcasting.tree_broadcast_center``.
    Returns tuple (broadcast_time, set of center nodes).
    """
    _fnx._validate_backend_dispatch_keywords("tree_broadcast_center", backend, backend_kwargs)
    return _nx_broadcasting.tree_broadcast_center(G)


def tree_broadcast_time(G, node=None, *, backend=None, **backend_kwargs):
    """Return the broadcast time of a tree from the given node.

    Wraps ``networkx.algorithms.broadcasting.tree_broadcast_time``.
    Returns integer broadcast time.
    """
    _fnx._validate_backend_dispatch_keywords("tree_broadcast_time", backend, backend_kwargs)
    return _nx_broadcasting.tree_broadcast_time(G, node=node)
