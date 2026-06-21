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


def local_node_connectivity(
    G,
    source,
    target,
    flow_func=None,
    auxiliary=None,
    residual=None,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Local node connectivity kappa(source, target).

    br-lncroute: the ``from networkx... import *`` above left this bound to
    NetworkX's flow-based implementation, so calling it on an fnx graph ran nx's
    Python max-flow over the per-access AtlasView substrate (~0.75x nx). For the
    default exact query, ``local_node_connectivity(G, s, t)`` is identically
    ``kappa(s, t) == node_connectivity(G, s, t)``, and fnx's native
    ``node_connectivity`` computes it via the fast max-flow substrate
    (~2.9x nx, value-identical over 60 random directed+undirected pairs plus
    complete / path / cycle / disconnected / dense-adjacent edge cases).

    Route only the default case (no custom ``flow_func`` / ``auxiliary`` /
    ``residual`` / ``cutoff`` / backend, distinct in-graph endpoints) to the
    native path; everything else — including the early-exit ``cutoff`` contract
    (returns ``min(true, cutoff)``) and the ``KeyError`` raised for a missing
    endpoint — falls back to NetworkX's implementation verbatim.
    """
    if (
        flow_func is None
        and auxiliary is None
        and residual is None
        and cutoff is None
        and backend is None
        and not backend_kwargs
        and source != target
        and source in G
        and target in G
    ):
        return _fnx.node_connectivity(G, source, target)
    return _nx_connectivity.local_node_connectivity(
        G,
        source,
        target,
        flow_func=flow_func,
        auxiliary=auxiliary,
        residual=residual,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


def local_edge_connectivity(
    G,
    s,
    t,
    flow_func=None,
    auxiliary=None,
    residual=None,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Local edge connectivity lambda(s, t).

    br-lncroute: sibling of :func:`local_node_connectivity`. Left bound to
    NetworkX's flow implementation by the wildcard import, so it ran nx's
    Python max-flow over the fnx per-access substrate (~0.71x nx). For the
    default exact query ``local_edge_connectivity(G, s, t) == lambda(s, t) ==
    edge_connectivity(G, s, t)``, and fnx's native ``edge_connectivity`` computes
    it via the fast value-only max-flow substrate (~17x nx, value-identical over
    60 directed+undirected pairs plus complete / path / disconnected edge cases).

    Routes only the default case (no custom ``flow_func`` / ``auxiliary`` /
    ``residual`` / ``cutoff`` / backend, distinct in-graph endpoints); the
    ``cutoff`` early-exit contract and missing-endpoint errors fall back to
    NetworkX verbatim.
    """
    if (
        flow_func is None
        and auxiliary is None
        and residual is None
        and cutoff is None
        and backend is None
        and not backend_kwargs
        and s != t
        and s in G
        and t in G
    ):
        return _fnx.edge_connectivity(G, s, t)
    return _nx_connectivity.local_edge_connectivity(
        G,
        s,
        t,
        flow_func=flow_func,
        auxiliary=auxiliary,
        residual=residual,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


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
