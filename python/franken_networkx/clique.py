"""FrankenNetworkX clique submodule.

Re-exports the upstream ``networkx.algorithms.clique`` surface so
existing ``franken_networkx.clique.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``make_clique_bipartite`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.clique import *  # noqa: F401,F403
import networkx.algorithms.clique as _nx_clique

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_clique,
        "__all__",
        (
            "find_cliques",
            "find_cliques_recursive",
            "make_max_clique_graph",
            "make_clique_bipartite",
            "node_clique_number",
            "number_of_cliques",
            "enumerate_all_cliques",
            "max_weight_clique",
        ),
    )
)

def find_cliques(G, nodes=None, *, backend=None, **backend_kwargs):
    """Yield maximal cliques using FrankenNetworkX's native implementation."""
    return _fnx.find_cliques(G, nodes=nodes, backend=backend, **backend_kwargs)


def find_cliques_recursive(G, nodes=None, *, backend=None, **backend_kwargs):
    """Yield maximal cliques through the recursive native implementation."""
    return _fnx.find_cliques_recursive(G, nodes=nodes, backend=backend, **backend_kwargs)


def node_clique_number(
    G, nodes=None, cliques=None, separate_nodes=False, *, backend=None, **backend_kwargs
):
    """Return each requested node's largest maximal-clique size."""
    return _fnx.node_clique_number(
        G,
        nodes=nodes,
        cliques=cliques,
        separate_nodes=separate_nodes,
        backend=backend,
        **backend_kwargs,
    )


def number_of_cliques(G, nodes=None, cliques=None):
    """Return the number of maximal cliques containing each requested node."""
    return _fnx.number_of_cliques(G, nodes=nodes, cliques=cliques)


def enumerate_all_cliques(G, *, backend=None, **backend_kwargs):
    """Yield every clique using FrankenNetworkX's native implementation."""
    return _fnx.enumerate_all_cliques(G, backend=backend, **backend_kwargs)


def max_weight_clique(G, weight="weight", *, backend=None, **backend_kwargs):
    """Return a maximum-weight clique using FrankenNetworkX's implementation."""
    return _fnx.max_weight_clique(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def make_max_clique_graph(G, create_using=None, *, backend=None, **backend_kwargs):
    """Return the maximal clique graph of the given graph.

    Routes to ``franken_networkx.make_max_clique_graph`` (fnx-native) with nx's
    signature spelled out — see the note on ``_FNX_NATIVE_CLIQUE_NAMES``.
    """
    return _fnx.make_max_clique_graph(
        G, create_using=create_using, backend=backend, **backend_kwargs
    )


def make_clique_bipartite(G, fpos=None, create_using=None, name=None, *, backend=None, **backend_kwargs):
    """Return the bipartite clique graph corresponding to G.

    Wraps ``networkx.algorithms.clique.make_clique_bipartite`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("make_clique_bipartite", backend, backend_kwargs)
    nx_result = _nx_clique.make_clique_bipartite(G, fpos=fpos, create_using=create_using, name=name)
    return _from_nx_graph(nx_result, create_using=create_using)
