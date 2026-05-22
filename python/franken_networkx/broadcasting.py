"""FrankenNetworkX broadcasting algorithm submodule.

Re-exports the upstream ``networkx.algorithms.broadcasting`` public surface
for direct module import parity, while delegating implemented functions to
the existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_broadcasting = _importlib.import_module("networkx.algorithms.broadcasting")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_broadcasting,
        "__all__",
        ("tree_broadcast_center", "tree_broadcast_time"),
    )
)


def tree_broadcast_center(G, *, backend=None, **backend_kwargs):
    """Return the broadcast center of a tree with the upstream signature."""
    _fnx._validate_backend_dispatch_keywords(
        "tree_broadcast_center", backend, backend_kwargs
    )
    return _fnx.tree_broadcast_center(G)


def tree_broadcast_time(G, node=None, *, backend=None, **backend_kwargs):
    """Return the minimum broadcast time with the upstream signature."""
    _fnx._validate_backend_dispatch_keywords(
        "tree_broadcast_time", backend, backend_kwargs
    )
    return _fnx.tree_broadcast_time(G, node=node)


def __getattr__(name):
    try:
        return getattr(_nx_broadcasting, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_broadcasting) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
