"""FrankenNetworkX structural holes algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_structuralholes = _importlib.import_module("networkx.algorithms.structuralholes")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_structuralholes,
        "__all__",
        (
            "constraint",
            "local_constraint",
            "effective_size",
        ),
    )
)


def constraint(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the constraint on nodes in *G*."""
    _fnx._validate_backend_dispatch_keywords("constraint", backend, backend_kwargs)
    return _fnx.constraint(G, nodes=nodes, weight=weight)


def local_constraint(G, u, v, weight=None, *, backend=None, **backend_kwargs):
    """Return the local constraint on edge ``(u, v)``."""
    _fnx._validate_backend_dispatch_keywords(
        "local_constraint", backend, backend_kwargs
    )
    return _fnx.local_constraint(G, u, v, weight=weight)


def effective_size(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the effective size for nodes in *G*."""
    _fnx._validate_backend_dispatch_keywords("effective_size", backend, backend_kwargs)
    return _fnx.effective_size(G, nodes=nodes, weight=weight)


def __getattr__(name):
    try:
        return getattr(_nx_structuralholes, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_structuralholes) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
