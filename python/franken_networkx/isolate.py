"""FrankenNetworkX isolate algorithm submodule.

Re-exports the upstream ``networkx.algorithms.isolate`` public surface for
direct module import parity, while delegating implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_isolate = _importlib.import_module("networkx.algorithms.isolate")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_isolate,
        "__all__",
        ("is_isolate", "isolates", "number_of_isolates"),
    )
)


def is_isolate(G, n, *, backend=None, **backend_kwargs):
    """Return whether ``n`` is an isolate with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords("is_isolate", backend, backend_kwargs)
    return _fnx.is_isolate(G, n)


def isolates(G, *, backend=None, **backend_kwargs):
    """Yield isolates with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords("isolates", backend, backend_kwargs)
    return _fnx.isolates(G)


def number_of_isolates(G, *, backend=None, **backend_kwargs):
    """Return the isolate count with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "number_of_isolates", backend, backend_kwargs
    )
    return _fnx.number_of_isolates(G)


def __getattr__(name):
    try:
        return getattr(_nx_isolate, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_isolate) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
