"""FrankenNetworkX distance_measures submodule.

Mirrors ``networkx.algorithms.distance_measures`` but routes every function
that networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-muhsi (follow-up to br-r37-c1-1s6cb / centrality): previously
``franken_networkx.algorithms.distance_measures`` (and ``fnx.distance_measures``)
were aliased straight to networkx's module. Most distance functions
(center/diameter/eccentricity/...) already reached the fnx backend via nx's
dispatch, but ``harmonic_diameter`` did NOT — it ran nx's pure-Python all-pairs
sum against the fnx graph's adjacency views (730ms vs the native
``fnx.harmonic_diameter`` 96ms = 7.6x). Binding every name networkx aliases to
top level to the ``franken_networkx`` top-level implementation closes that gap
and makes the whole submodule consistently use fnx's tested surface
(center/diameter/radius/periphery/eccentricity/barycenter are 14-16x faster
than genuine nx; harmonic_diameter 7.4x; kemeny_constant 5x).
"""

import networkx as _nx
import networkx.algorithms.distance_measures as _nxd
from networkx.algorithms.distance_measures import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxd, "__all__", [n for n in dir(_nxd) if not n.startswith("_")]
)


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx names to fnx's optimized implementations."""
    routed = []
    for name in dir(_nxd):
        if name.startswith("_"):
            continue
        nval = getattr(_nxd, name)
        if not callable(nval):
            continue
        # Only names networkx itself aliases to top level are safe to swap.
        if getattr(_nx, name, None) is not nval:
            continue
        fval = getattr(_fnx, name, None)
        if fval is not None and fval is not nval:
            globals()[name] = fval
            routed.append(name)
    return routed


_routed_names = _route_to_fnx_toplevel()
