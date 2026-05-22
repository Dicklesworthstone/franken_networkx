"""FrankenNetworkX polynomial algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_polynomials = _importlib.import_module("networkx.algorithms.polynomials")

import franken_networkx as _fnx

__all__ = list(
    getattr(_nx_polynomials, "__all__", ("tutte_polynomial", "chromatic_polynomial"))
)


def chromatic_polynomial(G, *, backend=None, **backend_kwargs):
    """Return the chromatic polynomial of a graph."""
    _fnx._validate_backend_dispatch_keywords(
        "chromatic_polynomial", backend, backend_kwargs
    )
    return _fnx.chromatic_polynomial(G)


def tutte_polynomial(G, *, backend=None, **backend_kwargs):
    """Return the Tutte polynomial of a graph."""
    _fnx._validate_backend_dispatch_keywords(
        "tutte_polynomial", backend, backend_kwargs
    )
    return _fnx.tutte_polynomial(G)


def __getattr__(name):
    try:
        return getattr(_nx_polynomials, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_polynomials) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
