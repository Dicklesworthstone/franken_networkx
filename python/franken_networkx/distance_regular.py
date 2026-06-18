"""FrankenNetworkX distance-regular algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_distance_regular = _importlib.import_module("networkx.algorithms.distance_regular")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_distance_regular,
        "__all__",
        (
            "is_distance_regular",
            "is_strongly_regular",
            "intersection_array",
            "global_parameters",
        ),
    )
)


def is_distance_regular(G, *, backend=None, **backend_kwargs):
    """Returns True if the graph is distance regular, False otherwise."""
    _fnx._validate_backend_dispatch_keywords(
        "is_distance_regular", backend, backend_kwargs
    )
    return _fnx.is_distance_regular(G)


def is_strongly_regular(G, *, backend=None, **backend_kwargs):
    """Check if *G* is strongly regular."""
    _fnx._validate_backend_dispatch_keywords(
        "is_strongly_regular", backend, backend_kwargs
    )
    return _fnx.is_strongly_regular(G)


def intersection_array(G, *, backend=None, **backend_kwargs):
    """Return the intersection array of a distance-regular graph."""
    _fnx._validate_backend_dispatch_keywords(
        "intersection_array", backend, backend_kwargs
    )
    return _fnx.intersection_array(G)


def global_parameters(b, c):
    """Return global-parameter triples from an intersection array."""
    return _fnx.global_parameters(b, c)


def diameter(
    G, e=None, usebounds=False, weight=None, *, backend=None, **backend_kwargs
):
    """Return the diameter through the fnx top-level parity wrapper."""
    _fnx._validate_backend_dispatch_keywords("diameter", backend, backend_kwargs)
    return _fnx.diameter(G, e=e, usebounds=usebounds, weight=weight)


def __getattr__(name):
    try:
        return getattr(_nx_distance_regular, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_distance_regular) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
