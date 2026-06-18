"""FrankenNetworkX components submodule.

Re-exports the upstream ``networkx.algorithms.components`` surface so
existing ``franken_networkx.components.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``condensation`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.components import *  # noqa: F401,F403
import networkx.algorithms.components as _nx_components

import franken_networkx as _fnx

__all__ = list(
    getattr(_nx_components, "__all__", ())
    or [name for name in dir(_nx_components) if not name.startswith("_")]
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.components import *`` above left
# these connectivity predicates / component listers bound to networkx's
# implementations, so ``franken_networkx.components.connected_components`` etc.
# silently resolved to nx's (slower; ``is_connected`` family loses fnx's native
# CSR-BFS, and component listers return nx graph node sets). Route each to the
# fnx top-level native version. These are closure wrappers (not an import-time
# alias loop) so they reference ``_fnx.<fn>`` at CALL time — robust against the
# order in which franken_networkx defines these names during package init.
_FNX_NATIVE_COMPONENT_NAMES = (
    "articulation_points",
    "attracting_components",
    "biconnected_component_edges",
    "biconnected_components",
    "connected_components",
    "is_attracting_component",
    "is_biconnected",
    "is_connected",
    "is_semiconnected",
    "is_strongly_connected",
    "is_weakly_connected",
    "kosaraju_strongly_connected_components",
    "node_connected_component",
    "number_attracting_components",
    "number_connected_components",
    "number_strongly_connected_components",
    "number_weakly_connected_components",
    "strongly_connected_components",
    "weakly_connected_components",
)


def _make_fnx_component_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.components.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_COMPONENT_NAMES:
    globals()[_name] = _make_fnx_component_router(_name)


def condensation(G, scc=None, *, backend=None, **backend_kwargs):
    """Return the condensation of G.

    Returns the same fnx-native graph as ``franken_networkx.condensation``.
    """
    _fnx._validate_backend_dispatch_keywords("condensation", backend, backend_kwargs)
    return _fnx.condensation(G, scc=scc)
