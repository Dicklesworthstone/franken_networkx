"""FrankenNetworkX cut and expansion algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_cuts = _importlib.import_module("networkx.algorithms.cuts")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_cuts,
        "__all__",
        (
            "boundary_expansion",
            "conductance",
            "cut_size",
            "edge_expansion",
            "mixing_expansion",
            "node_expansion",
            "normalized_cut_size",
            "volume",
        ),
    )
)


def boundary_expansion(G, S, *, backend=None, **backend_kwargs):
    """Return the boundary expansion of set *S*."""
    _fnx._validate_backend_dispatch_keywords(
        "boundary_expansion", backend, backend_kwargs
    )
    return _fnx.boundary_expansion(G, S)


def conductance(G, S, T=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the conductance of set *S*."""
    _fnx._validate_backend_dispatch_keywords("conductance", backend, backend_kwargs)
    return _fnx.conductance(G, S, T=T, weight=weight)


def cut_size(G, S, T=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the size of the cut between *S* and *T*."""
    _fnx._validate_backend_dispatch_keywords("cut_size", backend, backend_kwargs)
    return _fnx.cut_size(G, S, T=T, weight=weight)


def edge_expansion(G, S, T=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the edge expansion of set *S*."""
    _fnx._validate_backend_dispatch_keywords("edge_expansion", backend, backend_kwargs)
    return _fnx.edge_expansion(G, S, T=T, weight=weight)


def mixing_expansion(G, S, T=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the mixing expansion of set *S*."""
    _fnx._validate_backend_dispatch_keywords(
        "mixing_expansion", backend, backend_kwargs
    )
    return _fnx.mixing_expansion(G, S, T=T, weight=weight)


def node_expansion(G, S, *, backend=None, **backend_kwargs):
    """Return the node expansion of set *S*."""
    _fnx._validate_backend_dispatch_keywords("node_expansion", backend, backend_kwargs)
    return _fnx.node_expansion(G, S)


def normalized_cut_size(G, S, T=None, weight=None, *, backend=None, **backend_kwargs):
    """Return the normalized cut size of set *S*."""
    _fnx._validate_backend_dispatch_keywords(
        "normalized_cut_size", backend, backend_kwargs
    )
    return _fnx.normalized_cut_size(G, S, T=T, weight=weight)


def volume(G, S, weight=None, *, backend=None, **backend_kwargs):
    """Return the volume of set *S*."""
    _fnx._validate_backend_dispatch_keywords("volume", backend, backend_kwargs)
    return _fnx.volume(G, S, weight=weight)


def __getattr__(name):
    try:
        return getattr(_nx_cuts, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_cuts) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
