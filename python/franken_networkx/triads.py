"""FrankenNetworkX triads submodule.

Re-exports the upstream ``networkx.algorithms.triads`` surface so
existing ``franken_networkx.triads.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``all_triads`` — yields fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.triads import *  # noqa: F401,F403
import networkx.algorithms.triads as _nx_triads

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_triads,
        "__all__",
        ("triadic_census", "is_triad", "all_triads", "triads_by_type", "triad_type"),
    )
)


def all_triads(G, *, backend=None, **backend_kwargs):
    """Generate all possible triads in G.

    Wraps ``networkx.algorithms.triads.all_triads`` and converts
    each yielded triad to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("all_triads", backend, backend_kwargs)
    for triad in _nx_triads.all_triads(G):
        yield _from_nx_graph(triad)
