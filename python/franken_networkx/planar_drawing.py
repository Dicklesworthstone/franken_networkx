"""FrankenNetworkX planar_drawing algorithm submodule.

Mirrors ``networkx.algorithms.planar_drawing`` but routes functions that
networkx re-exports at top level or in algorithms to FrankenNetworkX's
optimized implementations.
"""

from __future__ import annotations

import importlib as _importlib

_nx_planar_drawing = _importlib.import_module("networkx.algorithms.planar_drawing")

import franken_networkx as _fnx

combinatorial_embedding_to_pos = _fnx.combinatorial_embedding_to_pos

__all__ = list(
    getattr(_nx_planar_drawing, "__all__", ("combinatorial_embedding_to_pos",))
)


def __getattr__(name):
    try:
        return getattr(_nx_planar_drawing, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_planar_drawing) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
