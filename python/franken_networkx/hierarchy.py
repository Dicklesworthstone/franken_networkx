"""FrankenNetworkX hierarchy algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_hierarchy = _importlib.import_module("networkx.algorithms.hierarchy")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_hierarchy, "__all__", ("flow_hierarchy",)))


def flow_hierarchy(G, weight=None, *, backend=None, **backend_kwargs):
    """Return flow hierarchy with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "flow_hierarchy", backend, backend_kwargs
    )
    return _fnx.flow_hierarchy(G, weight=weight)


def __getattr__(name):
    try:
        return getattr(_nx_hierarchy, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_hierarchy) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
