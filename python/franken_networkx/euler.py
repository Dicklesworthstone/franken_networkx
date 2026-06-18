"""FrankenNetworkX euler submodule.

Re-exports the upstream ``networkx.algorithms.euler`` surface so
existing ``franken_networkx.euler.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``eulerize`` — returns fnx.MultiGraph
"""

from __future__ import annotations

from networkx.algorithms.euler import *  # noqa: F401,F403
import networkx.algorithms.euler as _nx_euler

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_euler,
        "__all__",
        (
            "is_eulerian",
            "eulerian_circuit",
            "eulerize",
            "is_semieulerian",
            "has_eulerian_path",
            "eulerian_path",
        ),
    )
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.euler import *`` above left these
# Eulerian functions bound to networkx's implementations, so ``fnx.euler.is_eulerian``
# etc. silently resolved to nx's instead of fnx's native versions. Route them to
# the fnx top-level functions via call-time closure wrappers (import-order robust).
_FNX_NATIVE_EULER_NAMES = (
    "is_eulerian",
    "eulerian_circuit",
    "is_semieulerian",
    "has_eulerian_path",
    "eulerian_path",
)


def _make_fnx_euler_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.euler.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_EULER_NAMES:
    globals()[_name] = _make_fnx_euler_router(_name)


def eulerize(G, *, backend=None, **backend_kwargs):
    """Transform a graph into an Eulerian graph.

    Wraps ``networkx.algorithms.euler.eulerize`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("eulerize", backend, backend_kwargs)
    nx_result = _nx_euler.eulerize(G)
    return _from_nx_graph(nx_result)
