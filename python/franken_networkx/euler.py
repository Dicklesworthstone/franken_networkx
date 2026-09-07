"""FrankenNetworkX euler submodule.

Re-exports the upstream ``networkx.algorithms.euler`` surface so
existing ``franken_networkx.euler.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``eulerize`` — returns fnx.MultiGraph
"""

from __future__ import annotations

from networkx.algorithms.euler import *  # noqa: F401,F403
import networkx.algorithms.euler as _nx_euler

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_euler,
        "__all__",
        (
            "is_eulerian",
            "eulerian_circuit",
            "eulerize",
            "is_semieulerian",
            "has_eulerian_path",
            "eulerian_path",
        ),
    )
)

def is_eulerian(G, *, backend=None, **backend_kwargs):
    """Return whether ``G`` is Eulerian using FrankenNetworkX's implementation."""
    return _fnx.is_eulerian(G, backend=backend, **backend_kwargs)


def eulerian_circuit(G, source=None, keys=False, *, backend=None, **backend_kwargs):
    """Yield an Eulerian circuit through FrankenNetworkX's implementation."""
    return _fnx.eulerian_circuit(
        G, source=source, keys=keys, backend=backend, **backend_kwargs
    )


def is_semieulerian(G, *, backend=None, **backend_kwargs):
    """Return whether ``G`` is semi-Eulerian using FrankenNetworkX's implementation."""
    return _fnx.is_semieulerian(G, backend=backend, **backend_kwargs)


def has_eulerian_path(G, source=None, *, backend=None, **backend_kwargs):
    """Return whether ``G`` has an Eulerian path."""
    return _fnx.has_eulerian_path(
        G, source=source, backend=backend, **backend_kwargs
    )


def eulerian_path(G, source=None, keys=False, *, backend=None, **backend_kwargs):
    """Yield an Eulerian path through FrankenNetworkX's implementation."""
    return _fnx.eulerian_path(
        G, source=source, keys=keys, backend=backend, **backend_kwargs
    )


def eulerize(G, *, backend=None, **backend_kwargs):
    """Transform a graph into an Eulerian graph."""
    return _fnx.eulerize(G, backend=backend, **backend_kwargs)
