"""FrankenNetworkX clustering algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_cluster = _importlib.import_module("networkx.algorithms.cluster")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_cluster,
        "__all__",
        (
            "triangles",
            "all_triangles",
            "average_clustering",
            "clustering",
            "transitivity",
            "square_clustering",
            "generalized_degree",
        ),
    )
)


def triangles(G, nodes=None, *, backend=None, **backend_kwargs):
    """Compute the number of triangles."""
    _fnx._validate_backend_dispatch_keywords("triangles", backend, backend_kwargs)
    return _fnx.triangles(G, nodes=nodes)


def all_triangles(G, nbunch=None, *, backend=None, **backend_kwargs):
    """Yield unique triangles in an undirected graph."""
    _fnx._validate_backend_dispatch_keywords("all_triangles", backend, backend_kwargs)
    return _fnx.all_triangles(G, nbunch=nbunch)


def average_clustering(
    G, nodes=None, weight=None, count_zeros=True, *, backend=None, **backend_kwargs
):
    """Compute the average clustering coefficient for the graph."""
    _fnx._validate_backend_dispatch_keywords(
        "average_clustering", backend, backend_kwargs
    )
    return _fnx.average_clustering(
        G, nodes=nodes, weight=weight, count_zeros=count_zeros
    )


def clustering(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    """Compute the clustering coefficient for nodes."""
    _fnx._validate_backend_dispatch_keywords("clustering", backend, backend_kwargs)
    return _fnx.clustering(G, nodes=nodes, weight=weight)


def transitivity(G, *, backend=None, **backend_kwargs):
    """Compute graph transitivity."""
    _fnx._validate_backend_dispatch_keywords("transitivity", backend, backend_kwargs)
    return _fnx.transitivity(G)


def square_clustering(G, nodes=None, *, backend=None, **backend_kwargs):
    """Compute the squares clustering coefficient for nodes."""
    _fnx._validate_backend_dispatch_keywords(
        "square_clustering", backend, backend_kwargs
    )
    return _fnx.square_clustering(G, nodes=nodes)


def generalized_degree(G, nodes=None, *, backend=None, **backend_kwargs):
    """Return the generalized degree for each node."""
    _fnx._validate_backend_dispatch_keywords(
        "generalized_degree", backend, backend_kwargs
    )
    return _fnx.generalized_degree(G, nodes=nodes)


def __getattr__(name):
    try:
        return getattr(_nx_cluster, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_cluster) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
