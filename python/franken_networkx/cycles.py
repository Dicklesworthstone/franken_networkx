"""FrankenNetworkX cycle algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_cycles = _importlib.import_module("networkx.algorithms.cycles")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_cycles,
        "__all__",
        (
            "cycle_basis",
            "simple_cycles",
            "recursive_simple_cycles",
            "find_cycle",
            "minimum_cycle_basis",
            "chordless_cycles",
            "girth",
        ),
    )
)


def cycle_basis(G, root=None, *, backend=None, **backend_kwargs):
    """Return a list of cycles forming a basis for *G*."""
    _fnx._validate_backend_dispatch_keywords("cycle_basis", backend, backend_kwargs)
    return _fnx.cycle_basis(G, root=root)


def simple_cycles(G, length_bound=None, *, backend=None, **backend_kwargs):
    """Yield simple cycles of *G*."""
    _fnx._validate_backend_dispatch_keywords("simple_cycles", backend, backend_kwargs)
    return _fnx.simple_cycles(G, length_bound=length_bound)


def recursive_simple_cycles(G, *, backend=None, **backend_kwargs):
    """Return simple cycles of a directed graph using recursive DFS."""
    _fnx._validate_backend_dispatch_keywords(
        "recursive_simple_cycles", backend, backend_kwargs
    )
    return _fnx.recursive_simple_cycles(G)


def find_cycle(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    """Return a cycle found in *G*."""
    _fnx._validate_backend_dispatch_keywords("find_cycle", backend, backend_kwargs)
    return _fnx.find_cycle(G, source=source, orientation=orientation)


def minimum_cycle_basis(G, weight=None, *, backend=None, **backend_kwargs):
    """Return a minimum weight cycle basis for *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "minimum_cycle_basis", backend, backend_kwargs
    )
    return _fnx.minimum_cycle_basis(G, weight=weight)


def chordless_cycles(G, length_bound=None, *, backend=None, **backend_kwargs):
    """Yield chordless cycles of *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "chordless_cycles", backend, backend_kwargs
    )
    return _fnx.chordless_cycles(G, length_bound=length_bound)


def girth(G, *, backend=None, **backend_kwargs):
    """Return the length of the shortest cycle in *G*."""
    _fnx._validate_backend_dispatch_keywords("girth", backend, backend_kwargs)
    return _fnx.girth(G)


def __getattr__(name):
    try:
        return getattr(_nx_cycles, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_cycles) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
