"""FrankenNetworkX dominance algorithm submodule.

Re-exports the upstream ``networkx.algorithms.dominance`` public surface for
direct module import parity, while delegating implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_dominance = _importlib.import_module("networkx.algorithms.dominance")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_dominance,
        "__all__",
        ("immediate_dominators", "dominance_frontiers"),
    )
)


def immediate_dominators(G, start, *, backend=None, **backend_kwargs):
    """Return immediate dominators with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "immediate_dominators", backend, backend_kwargs
    )
    return _fnx.immediate_dominators(G, start)


def dominance_frontiers(G, start, *, backend=None, **backend_kwargs):
    """Return dominance frontiers with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "dominance_frontiers", backend, backend_kwargs
    )
    return _fnx.dominance_frontiers(G, start)


def __getattr__(name):
    try:
        return getattr(_nx_dominance, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_dominance) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
