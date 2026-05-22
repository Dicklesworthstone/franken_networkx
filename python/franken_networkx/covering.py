"""FrankenNetworkX covering algorithm submodule.

Re-exports the upstream ``networkx.algorithms.covering`` public surface for
direct module import parity, while delegating implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_covering = _importlib.import_module("networkx.algorithms.covering")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_covering, "__all__", ("min_edge_cover", "is_edge_cover")))


def min_edge_cover(G, matching_algorithm=None, *, backend=None, **backend_kwargs):
    """Return a minimum edge cover with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "min_edge_cover", backend, backend_kwargs
    )
    return _fnx.min_edge_cover(G, matching_algorithm=matching_algorithm)


def is_edge_cover(G, cover, *, backend=None, **backend_kwargs):
    """Return whether ``cover`` is an edge cover with the upstream signature."""
    _fnx._validate_backend_dispatch_keywords("is_edge_cover", backend, backend_kwargs)
    return _fnx.is_edge_cover(G, cover)


def __getattr__(name):
    try:
        return getattr(_nx_covering, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_covering) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
