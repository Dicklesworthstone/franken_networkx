"""FrankenNetworkX walks algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_walks = _importlib.import_module("networkx.algorithms.walks")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_walks, "__all__", ("number_of_walks",)))


def number_of_walks(G, walk_length, *, backend=None, **backend_kwargs):
    """Count walks of a given length."""
    _fnx._validate_backend_dispatch_keywords(
        "number_of_walks", backend, backend_kwargs
    )
    return _fnx.number_of_walks(G, walk_length)


def __getattr__(name):
    try:
        return getattr(_nx_walks, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_walks) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
