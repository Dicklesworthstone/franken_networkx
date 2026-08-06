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
# br-r37-c1-9hnq3: ``make_max_clique_graph`` is deliberately NOT in this tuple.
# The generic router below forwards ``*args, **kwargs``, which the coverage
# matrix classifies as PARTIAL coverage of the nx surface rather than present —
# `inspect.signature`, `help()` and keyword-only enforcement all degrade through
# it. It is spelled out below instead, like ``make_clique_bipartite``.
#
# The other six here have the same weakness and are left alone on purpose: they
# are already accounted for in the pinned coverage numbers, whereas
# ``make_max_clique_graph`` had regressed away from them. Converting the rest is
# a real improvement but a separate, wider change — filed, not smuggled in here.
_FNX_NATIVE_CLIQUE_NAMES = (
    "find_cliques",
    "find_cliques_recursive",
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
