"""FrankenNetworkX chordal submodule.

Re-exports the upstream ``networkx.algorithms.chordal`` surface so
existing ``franken_networkx.chordal.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``complete_to_chordal_graph`` — returns (fnx.Graph, dict)
"""

from __future__ import annotations

from networkx.algorithms.chordal import *  # noqa: F401,F403
import networkx.algorithms.chordal as _nx_chordal

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_chordal,
        "__all__",
        (
            "is_chordal",
            "find_induced_nodes",
            "chordal_graph_cliques",
            "chordal_graph_treewidth",
            "NetworkXTreewidthBoundExceeded",
            "complete_to_chordal_graph",
        ),
    )
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.chordal import *`` above left these
# chordal functions and the NetworkXTreewidthBoundExceeded exception bound to
# networkx's objects, so ``fnx.chordal.is_chordal`` etc. silently resolved to
# nx's instead of fnx's native versions. ``complete_to_chordal_graph`` already
# overrides below; route the functions via call-time closure wrappers and the
# exception class via direct hasattr-guarded alias (a closure would break
# ``except fnx.chordal.NetworkXTreewidthBoundExceeded`` / isinstance).
_FNX_NATIVE_CHORDAL_FUNCS = (
    "is_chordal",
    "find_induced_nodes",
    "chordal_graph_cliques",
    "chordal_graph_treewidth",
)


def _make_fnx_chordal_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.chordal.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CHORDAL_FUNCS:
    globals()[_name] = _make_fnx_chordal_router(_name)

if hasattr(_fnx, "NetworkXTreewidthBoundExceeded"):
    NetworkXTreewidthBoundExceeded = _fnx.NetworkXTreewidthBoundExceeded


def complete_to_chordal_graph(G, *, backend=None, **backend_kwargs):
    """Return a chordal completion of G and the added fill-in edges.

    Routes through the fnx top-level implementation so the standalone chordal
    module path returns the same native graph type and alpha map as
    ``franken_networkx.complete_to_chordal_graph``.
    """
    return _fnx.complete_to_chordal_graph(
        G,
        backend=backend,
        **backend_kwargs,
    )
