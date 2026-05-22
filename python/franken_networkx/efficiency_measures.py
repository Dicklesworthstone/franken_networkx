"""FrankenNetworkX efficiency-measures algorithm submodule.

Re-exports the upstream ``networkx.algorithms.efficiency_measures`` public
surface for direct module import parity, while delegating implemented
functions to the existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_efficiency_measures = _importlib.import_module(
    "networkx.algorithms.efficiency_measures"
)

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_efficiency_measures,
        "__all__",
        ("efficiency", "local_efficiency", "global_efficiency"),
    )
)


def efficiency(G, u, v, *, backend=None, **backend_kwargs):
    """Return node-pair efficiency with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords("efficiency", backend, backend_kwargs)
    return _fnx.efficiency(G, u, v)


def local_efficiency(G, *, backend=None, **backend_kwargs):
    """Return local efficiency with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "local_efficiency", backend, backend_kwargs
    )
    return _fnx.local_efficiency(G)


def global_efficiency(G, *, backend=None, **backend_kwargs):
    """Return global efficiency with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "global_efficiency", backend, backend_kwargs
    )
    return _fnx.global_efficiency(G)


def __getattr__(name):
    try:
        return getattr(_nx_efficiency_measures, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_efficiency_measures) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
