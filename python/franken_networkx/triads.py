"""FrankenNetworkX triads submodule.

Re-exports the upstream ``networkx.algorithms.triads`` surface so
existing ``franken_networkx.triads.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``triadic_census`` — fnx-native census
- ``is_triad`` — fnx-native predicate
- ``all_triads`` — yields fnx.DiGraph
- ``triads_by_type`` — fnx-native grouping
- ``triad_type`` — fnx-native classifier
"""

from __future__ import annotations

from networkx.algorithms.triads import *  # noqa: F401,F403
import networkx.algorithms.triads as _nx_triads

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_triads,
        "__all__",
        ("triadic_census", "is_triad", "all_triads", "triads_by_type", "triad_type"),
    )
)


def triadic_census(G, nodelist=None, *, backend=None, **backend_kwargs):
    """Determine the triadic census of a directed graph."""
    _fnx._validate_backend_dispatch_keywords("triadic_census", backend, backend_kwargs)
    return _fnx.triadic_census(
        G,
        nodelist=nodelist,
        backend=backend,
        **backend_kwargs,
    )


def is_triad(G, *, backend=None, **backend_kwargs):
    """Returns True if graph ``G`` is a triad."""
    _fnx._validate_backend_dispatch_keywords("is_triad", backend, backend_kwargs)
    return _fnx.is_triad(G, backend=backend, **backend_kwargs)


def all_triads(G, *, backend=None, **backend_kwargs):
    """Generate all possible triads in G.

    Routes to ``franken_networkx.all_triads`` for fnx-native parity.
    """
    _fnx._validate_backend_dispatch_keywords("all_triads", backend, backend_kwargs)
    yield from _fnx.all_triads(G, backend=backend, **backend_kwargs)


def triads_by_type(G, *, backend=None, **backend_kwargs):
    """Returns a dict mapping triad type to triad subgraphs."""
    _fnx._validate_backend_dispatch_keywords("triads_by_type", backend, backend_kwargs)
    return _fnx.triads_by_type(G, backend=backend, **backend_kwargs)


def triad_type(G, *, backend=None, **backend_kwargs):
    """Returns the sociological triad type for a 3-node DiGraph."""
    _fnx._validate_backend_dispatch_keywords("triad_type", backend, backend_kwargs)
    return _fnx.triad_type(G, backend=backend, **backend_kwargs)
