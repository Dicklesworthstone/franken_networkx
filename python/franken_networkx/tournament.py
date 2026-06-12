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


def is_reachable(G, s, t, *, backend=None, **backend_kwargs):
    """Decide whether there is a path from ``s`` to ``t`` in the tournament.

    br-treachsnap: ``networkx.tournament.is_reachable`` is an O(V^3) closed-set
    scan that reads ``G._adj`` / ``G._pred`` thousands of times. Run on an fnx
    graph (via the ``import *`` re-export) it hammers fnx's adjacency accessors —
    3.9x slower than nx. Snapshot the successor/predecessor adjacency into plain
    ``set`` dicts ONCE, then run nx's EXACT algorithm on them. The result is a
    deterministic boolean, so it stays byte-identical to nx with no per-access
    accessor tax and no fnx->nx conversion.
    """
    _fnx._validate_backend_dispatch_keywords("is_reachable", backend, backend_kwargs)
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")

    nodes = list(G)
    succ = {u: set(G.successors(u)) for u in nodes}
    pred = {u: set(G.predecessors(u)) for u in nodes}

    def two_neighborhood(v):
        v_adj = succ[v]
        return {
            x
            for x in nodes
            if x == v or x in v_adj or any(z in v_adj for z in pred[x])
        }

    def is_closed(separating_set):
        return all(
            u in separating_set or separating_set <= succ[u] for u in nodes
        )

    return not any(
        s in separating_set and t not in separating_set and is_closed(separating_set)
        for separating_set in (two_neighborhood(v) for v in nodes)
    )
