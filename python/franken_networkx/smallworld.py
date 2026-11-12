"""FrankenNetworkX smallworld submodule.

Re-exports the upstream ``networkx.algorithms.smallworld`` surface so
existing ``franken_networkx.smallworld.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``random_reference`` — returns fnx.Graph
- ``lattice_reference`` — returns fnx.Graph
- ``sigma`` — fnx-native wrapper
- ``omega`` — fnx-native wrapper
"""

from __future__ import annotations

from networkx.algorithms.smallworld import *  # noqa: F401,F403
import networkx.algorithms.smallworld as _nx_smallworld

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_smallworld,
        "__all__",
        ("random_reference", "lattice_reference", "sigma", "omega"),
    )
)


def random_reference(G, niter=1, connectivity=True, seed=None, *, backend=None, **backend_kwargs):
    """Compute a random graph by swapping edges of a given graph.

    Routes to ``franken_networkx.random_reference`` for fnx-native parity.
    """
    _fnx._validate_backend_dispatch_keywords("random_reference", backend, backend_kwargs)
    return _fnx.random_reference(
        G,
        niter=niter,
        connectivity=connectivity,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def lattice_reference(G, niter=5, D=None, connectivity=True, seed=None, *, backend=None, **backend_kwargs):
    """Latticize the given graph by swapping edges.

    Routes to ``franken_networkx.lattice_reference`` for fnx-native parity.
    """
    _fnx._validate_backend_dispatch_keywords("lattice_reference", backend, backend_kwargs)
    return _fnx.lattice_reference(
        G,
        niter=niter,
        D=D,
        connectivity=connectivity,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def sigma(G, niter=100, nrand=10, seed=None, *, backend=None, **backend_kwargs):
    """Returns the small-world coefficient sigma of graph ``G``."""
    _fnx._validate_backend_dispatch_keywords("sigma", backend, backend_kwargs)
    return _fnx.sigma(
        G,
        niter=niter,
        nrand=nrand,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def omega(G, niter=5, nrand=10, seed=None, *, backend=None, **backend_kwargs):
    """Returns the small-world coefficient omega of graph ``G``."""
    _fnx._validate_backend_dispatch_keywords("omega", backend, backend_kwargs)
    return _fnx.omega(
        G,
        niter=niter,
        nrand=nrand,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )
