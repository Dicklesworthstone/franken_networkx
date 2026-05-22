"""FrankenNetworkX d-separation algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_d_separation = _importlib.import_module("networkx.algorithms.d_separation")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_d_separation,
        "__all__",
        ("is_d_separator", "is_minimal_d_separator", "find_minimal_d_separator"),
    )
)


def is_d_separator(G, x, y, z, *, backend=None, **backend_kwargs):
    """Check whether node set *z* d-separates *x* from *y* in a DAG."""
    _fnx._validate_backend_dispatch_keywords(
        "is_d_separator", backend, backend_kwargs
    )
    return _fnx.is_d_separator(G, x, y, z)


def is_minimal_d_separator(
    G,
    x,
    y,
    z,
    *,
    included=None,
    restricted=None,
    backend=None,
    **backend_kwargs,
):
    """Check whether *z* is a minimal d-separator of *x* and *y*."""
    _fnx._validate_backend_dispatch_keywords(
        "is_minimal_d_separator", backend, backend_kwargs
    )
    return _fnx.is_minimal_d_separator(
        G, x, y, z, included=included, restricted=restricted
    )


def find_minimal_d_separator(
    G,
    x,
    y,
    *,
    included=None,
    restricted=None,
    backend=None,
    **backend_kwargs,
):
    """Find a minimal d-separating set between *x* and *y* in a DAG."""
    _fnx._validate_backend_dispatch_keywords(
        "find_minimal_d_separator", backend, backend_kwargs
    )
    return _fnx.find_minimal_d_separator(
        G, x, y, included=included, restricted=restricted
    )


def __getattr__(name):
    try:
        return getattr(_nx_d_separation, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_d_separation) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
