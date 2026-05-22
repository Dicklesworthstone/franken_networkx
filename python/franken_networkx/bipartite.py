"""FrankenNetworkX bipartite submodule.

Re-exports the upstream ``networkx.algorithms.bipartite`` surface so
existing ``franken_networkx.bipartite.*`` call sites keep working, but
overrides specific functions with fnx-native implementations as the
native port lands.

Current native overrides:

- ``collaboration_weighted_projected_graph`` — Newman's collaboration
  weighted projection (franken_networkx-f2e8).
"""

from __future__ import annotations

from networkx.algorithms.bipartite import *  # noqa: F401,F403
import networkx.algorithms.bipartite as _nx_bipartite

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def collaboration_weighted_projected_graph(B, nodes, *, backend=None, **backend_kwargs):
    r"""Native port of Newman's collaboration-weighted bipartite projection.

    Produces the same graph as
    ``networkx.bipartite.collaboration_weighted_projected_graph`` without
    delegating to NetworkX. Both undirected and directed bipartite graphs
    are supported; multigraph inputs are rejected matching upstream.

    Edge weight between ``u`` and ``v`` is the sum over shared neighbors
    ``k`` of ``1 / (deg_B(k) - 1)``, where ``deg_B(k)`` is the degree of
    ``k`` in the bipartite graph ``B``.

    br-r37-c1-bk-submod: backend dispatch surface match nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "collaboration_weighted_projected_graph", backend, backend_kwargs
    )
    if B.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")

    if B.is_directed():
        pred = B.pred
        G = _fnx.DiGraph()
    else:
        pred = B.adj
        G = _fnx.Graph()

    G.graph.update(B.graph)
    for node in nodes:
        G.add_node(node, **dict(B.nodes[node]))

    for u in nodes:
        unbrs = set(B[u])
        nbrs2 = {n for nbr in unbrs for n in B[nbr] if n != u}
        for v in nbrs2:
            vnbrs = set(pred[v])
            common_degree = (len(B[n]) for n in unbrs & vnbrs)
            weight = sum(1.0 / (deg - 1) for deg in common_degree if deg > 1)
            G.add_edge(u, v, weight=weight)
    return G


def projected_graph(B, nodes, multigraph=False, *, backend=None, **backend_kwargs):
    """Return the projection of B onto one of its node sets.

    Wraps ``networkx.algorithms.bipartite.projected_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.projected_graph(B, nodes, multigraph=multigraph)
    return _from_nx_graph(nx_result)


def weighted_projected_graph(B, nodes, ratio=False, *, backend=None, **backend_kwargs):
    """Return a weighted projection of B onto one of its node sets.

    Wraps ``networkx.algorithms.bipartite.weighted_projected_graph`` and
    converts the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "weighted_projected_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.weighted_projected_graph(B, nodes, ratio=ratio)
    return _from_nx_graph(nx_result)


def gnmk_random_graph(n, m, k, seed=None, directed=False, *, backend=None, **backend_kwargs):
    """Return a random bipartite graph G_{n,m,k}.

    Wraps ``networkx.algorithms.bipartite.gnmk_random_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords(
        "gnmk_random_graph", backend, backend_kwargs
    )
    nx_result = _nx_bipartite.gnmk_random_graph(n, m, k, seed=seed, directed=directed)
    return _from_nx_graph(nx_result)
