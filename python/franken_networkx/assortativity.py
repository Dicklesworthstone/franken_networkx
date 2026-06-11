"""FrankenNetworkX assortativity submodule.

Mirrors ``networkx.algorithms.assortativity`` but routes every function that
networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-asrt (follow-up to br-r37-c1-1s6cb / centrality): previously
``franken_networkx.algorithms.assortativity`` (and ``fnx.assortativity``) were
aliased verbatim to networkx's module. Several functions did NOT reach the fnx
backend via nx's dispatch, so they ran nx's pure-Python code against the fnx
graph's adjacency / degree views — e.g. ``degree_pearson_correlation_coefficient``
(52ms vs the native 9ms = 5.8x), ``attribute_assortativity_coefficient`` (6.6x),
``degree_mixing_matrix`` (7.2x), ``attribute_mixing_matrix`` (4x).

networkx aliases these to the top level, so binding each such name to the
``franken_networkx`` top-level (optimized, parity-tested) implementation is the
correct drop-in behaviour and makes ``fnx.algorithms.assortativity.X is fnx.X``
exactly as ``nx...assortativity.X is nx.X``. The mixing matrices are
order-sensitive; fnx's top-level versions are byte-exact with nx (verified over
150 adversarial barabasi/powerlaw/watts graphs, incl. ``normalized=False``).

The ``getattr(networkx, name) is <submodule fn>`` guard ensures we only
substitute names networkx itself re-exports at top level, leaving any submodule
name that collides with a different top-level function untouched.
"""

import networkx as _nx
import networkx.algorithms.assortativity as _nxa
from networkx.algorithms.assortativity import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxa, "__all__", [n for n in dir(_nxa) if not n.startswith("_")]
)


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx names to fnx's optimized implementations."""
    routed = []
    for name in dir(_nxa):
        if name.startswith("_"):
            continue
        nval = getattr(_nxa, name)
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
