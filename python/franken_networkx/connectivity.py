"""FrankenNetworkX connectivity submodule.

Re-exports the upstream ``networkx.algorithms.connectivity`` surface so
existing ``franken_networkx.connectivity.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``build_auxiliary_node_connectivity`` — returns fnx.DiGraph
- ``build_auxiliary_edge_connectivity`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.connectivity import *  # noqa: F401,F403
import networkx.algorithms.connectivity as _nx_connectivity

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(_nx_connectivity, "__all__", ())
    or [name for name in dir(_nx_connectivity) if not name.startswith("_")]
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.connectivity import *`` above left
# the connectivity/cut/disjoint-path functions bound to networkx's
# implementations, so ``fnx.connectivity.node_connectivity`` etc. silently
# resolved to nx's instead of fnx's native versions (node_connectivity even
# carries the br-r37-c1-cqlms/ebd8d local-connectivity fixes). Route each to the
# fnx top-level function via call-time closure wrappers (robust against the
# package-init order in which fnx defines them).
_FNX_NATIVE_CONNECTIVITY_NAMES = (
    "all_node_cuts",
    "all_pairs_node_connectivity",
    "average_node_connectivity",
    "edge_connectivity",
    "edge_disjoint_paths",
    "is_k_edge_connected",
    "k_components",
    "k_edge_augmentation",
    "k_edge_components",
    "k_edge_subgraphs",
    "minimum_edge_cut",
    "minimum_node_cut",
    "node_connectivity",
    "node_disjoint_paths",
    "stoer_wagner",
)


def _make_fnx_connectivity_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.connectivity.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CONNECTIVITY_NAMES:
    globals()[_name] = _make_fnx_connectivity_router(_name)


def build_auxiliary_node_connectivity(G):
    """Return auxiliary digraph for computing node connectivity.

    Wraps ``networkx.algorithms.connectivity.build_auxiliary_node_connectivity``
    and converts the result to an fnx.DiGraph for drop-in compatibility.
    """
    nx_result = _nx_connectivity.build_auxiliary_node_connectivity(G)
    return _from_nx_graph(nx_result)


def build_auxiliary_edge_connectivity(G):
    """Return auxiliary digraph for computing edge connectivity.

    Wraps ``networkx.algorithms.connectivity.build_auxiliary_edge_connectivity``
    and converts the result to an fnx.DiGraph for drop-in compatibility.
    """
    nx_result = _nx_connectivity.build_auxiliary_edge_connectivity(G)
    return _from_nx_graph(nx_result)
