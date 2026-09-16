"""FrankenNetworkX time_dependent algorithm submodule.

Mirrors ``networkx.algorithms.time_dependent`` but routes functions that
networkx re-exports at top level or in algorithms to FrankenNetworkX's
optimized implementations.
"""

from __future__ import annotations

import importlib as _importlib

_nx_time_dependent = _importlib.import_module("networkx.algorithms.time_dependent")

import franken_networkx as _fnx

cd_index = _fnx.cd_index

__all__ = list(getattr(_nx_time_dependent, "__all__", ("cd_index",)))


def __getattr__(name):
    try:
        return getattr(_nx_time_dependent, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_time_dependent) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
