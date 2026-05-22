"""FrankenNetworkX simple path algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_simple_paths = _importlib.import_module("networkx.algorithms.simple_paths")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_simple_paths,
        "__all__",
        (
            "all_simple_paths",
            "is_simple_path",
            "shortest_simple_paths",
            "all_simple_edge_paths",
        ),
    )
)


def all_simple_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    """Generate all simple paths from *source* to *target*."""
    _fnx._validate_backend_dispatch_keywords(
        "all_simple_paths", backend, backend_kwargs
    )
    return _fnx.all_simple_paths(G, source, target, cutoff=cutoff)


def is_simple_path(G, nodes, *, backend=None, **backend_kwargs):
    """Return True if *nodes* forms a simple path in *G*."""
    _fnx._validate_backend_dispatch_keywords("is_simple_path", backend, backend_kwargs)
    return _fnx.is_simple_path(G, nodes)


def shortest_simple_paths(
    G, source, target, weight=None, *, backend=None, **backend_kwargs
):
    """Generate simple paths from *source* to *target* by increasing length."""
    _fnx._validate_backend_dispatch_keywords(
        "shortest_simple_paths", backend, backend_kwargs
    )
    return _fnx.shortest_simple_paths(G, source, target, weight=weight)


def all_simple_edge_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    """Generate edge paths for all simple paths from *source* to *target*."""
    _fnx._validate_backend_dispatch_keywords(
        "all_simple_edge_paths", backend, backend_kwargs
    )
    return _fnx.all_simple_edge_paths(G, source, target, cutoff=cutoff)


def __getattr__(name):
    try:
        return getattr(_nx_simple_paths, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_simple_paths) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
