"""FrankenNetworkX tournament submodule.

Re-exports the upstream ``networkx.algorithms.tournament`` surface so
existing ``franken_networkx.tournament.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``random_tournament`` — returns fnx.DiGraph
"""

from __future__ import annotations

from itertools import combinations as _combinations

from networkx.algorithms.tournament import *  # noqa: F401,F403
import networkx.algorithms.tournament as _nx_tournament

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(_nx_tournament, "__all__", ())
    or [name for name in dir(_nx_tournament) if not name.startswith("_")]
)


def score_sequence(G, *, backend=None, **backend_kwargs):
    """Return the sorted list of out-degrees of the tournament's nodes.

    br-tscoreseq: the ``import *`` re-export bound nx's ``@_dispatchable``
    ``score_sequence``; called on an fnx graph it routed through nx's backend-
    dispatch machinery (~2.5 ms of pure overhead for what is just
    ``sorted(out-degrees)``) — 280x slower than nx. Compute it directly here,
    bypassing the dispatcher. Byte-identical (a sorted list of ints).
    """
    _fnx._validate_backend_dispatch_keywords("score_sequence", backend, backend_kwargs)
    # nx stacks @not_implemented_for("undirected") over ("multigraph"); for a
    # MultiGraph the multigraph check fires first, so test multigraph before
    # undirected to match nx's exception message exactly.
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    return sorted(d for _v, d in G.out_degree())


def hamiltonian_path(G, *, backend=None, **backend_kwargs):
    """Return a Hamiltonian path in the tournament ``G`` (br-r37-c1-tourham, cc).

    The ``import *`` re-export ran nx's recursive algorithm — remove a node, recurse on
    ``G.subgraph(rest)``, re-insert — which builds ``len(G)`` nested subgraph views over the
    slow fnx adjacency (0.63x at n=80). Build the same path iteratively on a one-shot
    adjacency snapshot: seed with the last node, then insert each earlier node before the
    first path node that beats it. Same insertion order and positions as nx's recursion, so
    the produced path is byte-identical.
    """
    _fnx._validate_backend_dispatch_keywords("hamiltonian_path", backend, backend_kwargs)
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    nodes = list(G)
    if not nodes:
        return []
    # out-adjacency snapshot: ``v in adj[u]`` iff u -> v (u beats v).
    adj = {n: set(G.successors(n)) for n in nodes}
    hampath = [nodes[-1]]
    for v in reversed(nodes[:-1]):
        # nx inserts v before the first path node it BEATS (``v not in G[u]`` ==> v -> u),
        # giving ...prev -> v -> u...; default to the end if v beats nothing remaining.
        index = next(
            (i for i, u in enumerate(hampath) if v not in adj[u]), len(hampath)
        )
        hampath.insert(index, v)
    return hampath


def is_tournament(G, *, backend=None, **backend_kwargs):
    """Return ``True`` iff ``G`` is a tournament.

    br-tistourn: same dispatcher overhead as ``score_sequence`` plus nx's
    O(V^2) all-pairs edge check reading the slow fnx adjacency view per pair
    (6x slower than nx). Snapshot the successor adjacency into plain ``set``
    dicts once, then run nx's exact XOR-over-pairs test. Deterministic boolean,
    byte-identical to nx.
    """
    _fnx._validate_backend_dispatch_keywords("is_tournament", backend, backend_kwargs)
    # nx stacks @not_implemented_for("undirected") over ("multigraph"); for a
    # MultiGraph the multigraph check fires first, so test multigraph before
    # undirected to match nx's exception message exactly.
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    nodes = list(G)
    succ = {u: set(G.successors(u)) for u in nodes}
    if any(u in succ[u] for u in nodes):  # self-loop -> not a tournament
        return False
    return all((v in succ[u]) ^ (u in succ[v]) for u, v in _combinations(nodes, 2))


def random_tournament(n, seed=None, *, backend=None, **backend_kwargs):
    """Return a random tournament graph on n nodes.

    Wraps ``networkx.algorithms.tournament.random_tournament`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("random_tournament", backend, backend_kwargs)
    # br-r37-c1-tournrandgen: de-delegate via the create_py_random_state RNG-
    # reproduction lever. nx flips one coin per distinct pair in combinations(range
    # (n), 2) order, orienting u->v if r<0.5 else v->u, and builds nx.DiGraph(edges)
    # (node order = edge appearance). Reproduce the exact draw sequence + edge
    # construction directly instead of nx build + _from_nx_graph.
    from itertools import combinations as _combinations
    from networkx.utils import create_py_random_state

    rng = create_py_random_state(seed)
    coins = (rng.random() for _ in range((n * (n - 1)) // 2))
    pairs = _combinations(range(n), 2)
    edges = [(u, v) if r < 0.5 else (v, u) for (u, v), r in zip(pairs, coins)]
    G = _fnx.DiGraph()
    G.add_edges_from(edges)
    return G


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
    # nx stacks @not_implemented_for("undirected") over ("multigraph"); for a
    # MultiGraph the multigraph check fires first, so test multigraph before
    # undirected to match nx's exception message exactly.
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")

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


def is_strongly_connected(G, *, backend=None, **backend_kwargs):
    """Decide whether the given tournament is strongly connected.

    br-tscsnap: ``networkx.tournament.is_strongly_connected`` is
    ``all(is_reachable(G, u, v) for u in G for v in G)`` — O(V^2) tournament
    reachability calls (the docstring itself notes the "theoretically efficient"
    bound needs parallelism it does not implement). Run on an fnx graph it is
    catastrophically slow. For a tournament this predicate is *exactly* general
    strong connectivity, so route to fnx's native
    :func:`~franken_networkx.is_strongly_connected` (index-CSR forward+reverse
    reachability, O(V+E)). Value-identical for tournaments; the empty graph is
    ``True`` here (``all`` over no pairs) while the generic kernel raises
    ``NetworkXPointlessConcept``, so special-case it. Undirected / multigraph
    raise to match nx's stacked ``not_implemented_for`` exactly.
    """
    _fnx._validate_backend_dispatch_keywords(
        "is_strongly_connected", backend, backend_kwargs
    )
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    if len(G) == 0:
        return True
    return _fnx.is_strongly_connected(G)
