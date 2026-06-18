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

# br-r37-c1-2qsqf: ``from networkx.algorithms.clique import *`` above left these
# clique functions bound to networkx's implementations, so ``fnx.clique.find_cliques``
# etc. silently resolved to nx's instead of fnx's native versions. ``make_clique_bipartite``
# already overrides below; route the rest to the fnx top-level functions via
# call-time closure wrappers (import-order robust).
_FNX_NATIVE_CLIQUE_NAMES = (
    "find_cliques",
    "find_cliques_recursive",
    "make_max_clique_graph",
    "node_clique_number",
    "number_of_cliques",
    "enumerate_all_cliques",
    "max_weight_clique",
)


def _make_fnx_clique_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.clique.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CLIQUE_NAMES:
    globals()[_name] = _make_fnx_clique_router(_name)


def make_clique_bipartite(G, fpos=None, create_using=None, name=None, *, backend=None, **backend_kwargs):
    """Return the bipartite clique graph corresponding to G.

    Wraps ``networkx.algorithms.clique.make_clique_bipartite`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("make_clique_bipartite", backend, backend_kwargs)
    nx_result = _nx_clique.make_clique_bipartite(G, fpos=fpos, create_using=create_using, name=name)
    return _from_nx_graph(nx_result, create_using=create_using)
