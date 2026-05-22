"""FrankenNetworkX s-metric algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_smetric = _importlib.import_module("networkx.algorithms.smetric")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_smetric, "__all__", ("s_metric",)))


def s_metric(G, *, backend=None, **backend_kwargs):
    """Return the graph s-metric with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords("s_metric", backend, backend_kwargs)
    return _fnx.s_metric(G)


def __getattr__(name):
    try:
        return getattr(_nx_smetric, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_smetric) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
