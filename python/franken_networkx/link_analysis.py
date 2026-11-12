"""FrankenNetworkX link_analysis submodule.

Mirrors ``networkx.algorithms.link_analysis`` but routes every function that
networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-muhsi (follow-up to br-r37-c1-1s6cb / centrality): previously
``franken_networkx.algorithms.link_analysis`` was aliased verbatim to
networkx's module. ``pagerank`` / ``hits`` already reached the fnx backend via
nx dispatch (neutral), but ``google_matrix`` ran nx's pure-Python dense matrix
build against the fnx graph's adjacency views (~1.4x slower than the native
``fnx.google_matrix``). Binding every name networkx aliases to top level to the
``franken_networkx`` top-level implementation makes the submodule consistently
use fnx's tested surface — ``fnx.algorithms.link_analysis.X is fnx.X`` exactly
as ``nx...link_analysis.X is nx.X`` — with no regression (parity bit-exact for
pagerank/google_matrix, ~2e-18 for hits).
"""

import networkx as _nx
import networkx.algorithms.link_analysis as _nxla
from networkx.algorithms.link_analysis import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxla, "__all__", [n for n in dir(_nxla) if not n.startswith("_")]
)


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx names to fnx's optimized implementations."""
    routed = []
    for name in dir(_nxla):
        if name.startswith("_"):
            continue
        nval = getattr(_nxla, name)
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
