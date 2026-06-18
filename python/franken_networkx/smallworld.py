"""FrankenNetworkX smallworld submodule.

Re-exports the upstream ``networkx.algorithms.smallworld`` surface so
existing ``franken_networkx.smallworld.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``random_reference`` — returns fnx.Graph
- ``lattice_reference`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.smallworld import *  # noqa: F401,F403
import networkx.algorithms.smallworld as _nx_smallworld

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_smallworld,
        "__all__",
        ("random_reference", "lattice_reference", "sigma", "omega"),
    )
)


def random_reference(G, niter=1, connectivity=True, seed=None, *, backend=None, **backend_kwargs):
    """Compute a random graph by swapping edges of a given graph.

    Wraps ``networkx.algorithms.smallworld.random_reference`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("random_reference", backend, backend_kwargs)
    nx_result = _nx_smallworld.random_reference(G, niter=niter, connectivity=connectivity, seed=seed)
    return _from_nx_graph(nx_result)


def lattice_reference(G, niter=5, D=None, connectivity=True, seed=None, *, backend=None, **backend_kwargs):
    """Latticize the given graph by swapping edges.

    Wraps ``networkx.algorithms.smallworld.lattice_reference`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("lattice_reference", backend, backend_kwargs)
    nx_result = _nx_smallworld.lattice_reference(G, niter=niter, D=D, connectivity=connectivity, seed=seed)
    return _from_nx_graph(nx_result)
