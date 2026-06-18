"""FrankenNetworkX planarity submodule.

Re-exports the upstream ``networkx.algorithms.planarity`` surface so
existing ``franken_networkx.planarity.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``get_counterexample`` — returns fnx.Graph
- ``get_counterexample_recursive`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.planarity import *  # noqa: F401,F403
import networkx.algorithms.planarity as _nx_planarity

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

# br-r37-c1-56nd2: nx's ``planarity.__all__`` only star-exports
# ``check_planarity``, ``is_planar`` and ``PlanarEmbedding``.
# ``check_planarity_recursive`` is a module-level public function but is
# absent from ``__all__``, so ``import *`` above does not pick it up.
# Re-export it explicitly for ``fnx.algorithms.planarity`` parity — the
# upstream function already handles backend dispatch and returns an
# ``nx.PlanarEmbedding`` certificate, so no native wrapper is needed
# (this mirrors how ``check_planarity`` is surfaced via the star import).
check_planarity_recursive = _nx_planarity.check_planarity_recursive

__all__ = list(
    getattr(
        _nx_planarity,
        "__all__",
        ("check_planarity", "is_planar", "PlanarEmbedding"),
    )
)


def get_counterexample(G, *, backend=None, **backend_kwargs):
    """Obtains a Kuratowski subgraph.

    Wraps ``networkx.algorithms.planarity.get_counterexample`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("get_counterexample", backend, backend_kwargs)
    nx_result = _nx_planarity.get_counterexample(G)
    return _from_nx_graph(nx_result)


def get_counterexample_recursive(G, *, backend=None, **backend_kwargs):
    """Recursive version of get_counterexample.

    Wraps ``networkx.algorithms.planarity.get_counterexample_recursive`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("get_counterexample_recursive", backend, backend_kwargs)
    nx_result = _nx_planarity.get_counterexample_recursive(G)
    return _from_nx_graph(nx_result)
