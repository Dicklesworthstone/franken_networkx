"""FrankenNetworkX Wiener-index algorithm submodule.

Re-exports the upstream ``networkx.algorithms.wiener`` public surface for
direct module import parity, while binding implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_wiener = _importlib.import_module("networkx.algorithms.wiener")

import franken_networkx as _fnx

wiener_index = _fnx.wiener_index
schultz_index = _fnx.schultz_index
gutman_index = _fnx.gutman_index


def hyper_wiener_index(G, weight=None, *, backend=None, **backend_kwargs):
    """Return the hyper-Wiener index with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "hyper_wiener_index", backend, backend_kwargs
    )
    return _fnx.hyper_wiener_index(G, weight=weight)

__all__ = list(
    getattr(
        _nx_wiener,
        "__all__",
        (
            "wiener_index",
            "schultz_index",
            "gutman_index",
            "hyper_wiener_index",
        ),
    )
)


def __getattr__(name):
    try:
        return getattr(_nx_wiener, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_wiener) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
