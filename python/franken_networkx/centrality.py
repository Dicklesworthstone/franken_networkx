"""FrankenNetworkX centrality submodule.

Mirrors ``networkx.algorithms.centrality`` but routes every function that
networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-1s6cb: previously ``franken_networkx.centrality`` /
``franken_networkx.algorithms.centrality`` were aliased straight to
``networkx.algorithms.centrality``. So ``fnx.algorithms.centrality.
betweenness_centrality(G)`` ran nx's pure-Python Brandes against the fnx
graph's adjacency *views* — measured 33x slower than the native
``fnx.betweenness_centrality`` (363ms vs 11ms at n=400, p=0.04).

networkx itself aliases every top-level centrality function to this submodule
(``nx.betweenness_centrality is nx.algorithms.centrality.betweenness_centrality``).
Mirroring that — binding each such name to the ``franken_networkx`` top-level
(optimized, parity-tested) function — is the correct drop-in behaviour and
makes ``fnx.algorithms.centrality.X is fnx.X`` exactly as
``nx.algorithms.centrality.X is nx.X``.

The ``getattr(networkx, name) is <submodule fn>`` guard ensures we only
substitute names networkx itself re-exports at top level, so any submodule
name that collides with a *different* top-level function is left untouched.
"""

import networkx as _nx
import networkx.algorithms.centrality as _nxc
from networkx.algorithms.centrality import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxc, "__all__", [n for n in dir(_nxc) if not n.startswith("_")]
)


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx centrality names to fnx's optimized ones."""
    routed = []
    for name in dir(_nxc):
        if name.startswith("_"):
            continue
        nval = getattr(_nxc, name)
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
