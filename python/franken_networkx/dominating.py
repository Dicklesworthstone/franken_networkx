"""FrankenNetworkX dominating-set algorithm submodule.

Re-exports the upstream ``networkx.algorithms.dominating`` public surface for
direct module import parity, while delegating functions through existing fnx
wrappers or the NetworkX parity fallback.
"""

from __future__ import annotations

import importlib as _importlib

_nx_dominating = _importlib.import_module("networkx.algorithms.dominating")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_dominating,
        "__all__",
        (
            "dominating_set",
            "is_dominating_set",
            "connected_dominating_set",
            "is_connected_dominating_set",
        ),
    )
)


def dominating_set(G, start_with=None, *, backend=None, **backend_kwargs):
    """Return a dominating set with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "dominating_set", backend, backend_kwargs
    )
    return _fnx.dominating_set(G, start_with=start_with)


def is_dominating_set(G, nbunch, *, backend=None, **backend_kwargs):
    """Return whether ``nbunch`` is a dominating set."""
    _fnx._validate_backend_dispatch_keywords(
        "is_dominating_set", backend, backend_kwargs
    )
    return _fnx.is_dominating_set(G, nbunch)


def connected_dominating_set(G, *, backend=None, **backend_kwargs):
    """Return a connected dominating set with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "connected_dominating_set", backend, backend_kwargs
    )
    return _fnx._call_networkx_for_parity("connected_dominating_set", G)


def is_connected_dominating_set(G, nbunch, *, backend=None, **backend_kwargs):
    """Return whether ``nbunch`` is a connected dominating set."""
    _fnx._validate_backend_dispatch_keywords(
        "is_connected_dominating_set", backend, backend_kwargs
    )
    return _fnx._call_networkx_for_parity("is_connected_dominating_set", G, nbunch)


def __getattr__(name):
    try:
        return getattr(_nx_dominating, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_dominating) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
