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

import inspect as _inspect

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
    _target = getattr(_nx_connectivity, _fn_name, None) or getattr(_fnx, _fn_name, None)
    if _target is not None:
        try:
            _routed.__signature__ = _inspect.signature(_target)
        except (ValueError, TypeError):
            pass
    return _routed


for _name in _FNX_NATIVE_CONNECTIVITY_NAMES:
    globals()[_name] = _make_fnx_connectivity_router(_name)


def edge_connectivity(
    G, s=None, t=None, flow_func=None, cutoff=None, *, backend=None, **backend_kwargs
):
    return _fnx.edge_connectivity(
        G,
        s=s,
        t=t,
        flow_func=flow_func,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


def node_connectivity(G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs):
    return _fnx.node_connectivity(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def minimum_edge_cut(G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs):
    return _fnx.minimum_edge_cut(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def minimum_node_cut(G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs):
    return _fnx.minimum_node_cut(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def local_node_connectivity(
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
    """Local node connectivity kappa(source, target)."""
    _fnx._validate_backend_dispatch_keywords(
        "local_node_connectivity", backend, backend_kwargs
    )
    if (
        flow_func is None
        and auxiliary is None
        and residual is None
        and cutoff is None
        and s != t
        and s in G
        and t in G
    ):
        return _fnx.node_connectivity(G, s, t)
    if flow_func is None:
        # networkx's default flow function; neither networkx nor fnx exports
        # edmonds_karp at top level (br-r37-c1-7jhpr).
        from franken_networkx.flow import edmonds_karp

        flow_func = edmonds_karp
    H = build_auxiliary_node_connectivity(G) if auxiliary is None else auxiliary
    mapping = H.graph.get("mapping", None)
    if mapping is None:
        raise _fnx.NetworkXError("Invalid auxiliary digraph.")
    kwargs = {"flow_func": flow_func, "residual": residual}
    if getattr(flow_func, "__name__", None) != "preflow_push":
        kwargs["cutoff"] = cutoff
    if getattr(flow_func, "__name__", None) == "shortest_augmenting_path":
        kwargs["two_phase"] = True
    return _fnx.maximum_flow_value(H, f"{mapping[s]}B", f"{mapping[t]}A", **kwargs)


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
    """Local edge connectivity lambda(s, t)."""
    _fnx._validate_backend_dispatch_keywords(
        "local_edge_connectivity", backend, backend_kwargs
    )
    if (
        flow_func is None
        and auxiliary is None
        and residual is None
        and cutoff is None
        and s != t
        and s in G
        and t in G
    ):
        return _fnx.edge_connectivity(G, s, t)
    if flow_func is None:
        from franken_networkx.flow import edmonds_karp

        flow_func = edmonds_karp
    H = build_auxiliary_edge_connectivity(G) if auxiliary is None else auxiliary
    kwargs = {"flow_func": flow_func, "residual": residual}
    if getattr(flow_func, "__name__", None) != "preflow_push":
        kwargs["cutoff"] = cutoff
    if getattr(flow_func, "__name__", None) == "shortest_augmenting_path":
        kwargs["two_phase"] = True
    return _fnx.maximum_flow_value(H, s, t, **kwargs)


def is_locally_k_edge_connected(G, s, t, k, *, backend=None, **backend_kwargs):
    """Return whether ``s`` and ``t`` are locally k-edge-connected."""
    _fnx._validate_backend_dispatch_keywords(
        "is_locally_k_edge_connected", backend, backend_kwargs
    )
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if k < 1:
        raise ValueError(f"k must be positive, not {k}")
    if G.degree(s) < k or G.degree(t) < k:
        return False
    if k == 1:
        return _fnx.has_path(G, s, t)
    if s != t and s in G and t in G:
        return _fnx.edge_connectivity(G, s, t) >= k
    return local_edge_connectivity(G, s, t, cutoff=k) >= k


def build_auxiliary_node_connectivity(G, *, backend=None, **backend_kwargs):
    """Return auxiliary digraph for computing node connectivity.

    Directly constructs an fnx.DiGraph with byte-exact parity to NetworkX's
    build_auxiliary_node_connectivity without intermediate nx graph round-trips.
    """
    _fnx._validate_backend_dispatch_keywords(
        "build_auxiliary_node_connectivity", backend, backend_kwargs
    )
    directed = G.is_directed()
    mapping = {}
    H = _fnx.DiGraph()

    for i, node in enumerate(G):
        mapping[node] = i
        H.add_node(f"{i}A", id=node)
        H.add_node(f"{i}B", id=node)
        H.add_edge(f"{i}A", f"{i}B", capacity=1)

    edges = []
    for source, target in G.edges():
        edges.append((f"{mapping[source]}B", f"{mapping[target]}A"))
        if not directed:
            edges.append((f"{mapping[target]}B", f"{mapping[source]}A"))
    H.add_edges_from(edges, capacity=1)
    H.graph["mapping"] = mapping
    return H


def build_auxiliary_edge_connectivity(G, *, backend=None, **backend_kwargs):
    """Return auxiliary digraph for computing edge connectivity.

    Directly constructs an fnx.DiGraph with byte-exact parity to NetworkX's
    build_auxiliary_edge_connectivity without intermediate nx graph round-trips.
    """
    _fnx._validate_backend_dispatch_keywords(
        "build_auxiliary_edge_connectivity", backend, backend_kwargs
    )
    H = _fnx.DiGraph()
    H.add_nodes_from(G.nodes())
    if G.is_directed():
        H.add_edges_from(G.edges(), capacity=1)
    else:
        edges = []
        for source, target in G.edges():
            edges.extend([(source, target), (target, source)])
        H.add_edges_from(edges, capacity=1)
    return H


def bridge_components(G, *, backend=None, **backend_kwargs):
    """Find the bridge-connected components for the graph G."""
    _fnx._validate_backend_dispatch_keywords(
        "bridge_components", backend, backend_kwargs
    )
    return _fnx._bridge_components(G)


def minimum_st_edge_cut(
    G, s, t, flow_func=None, auxiliary=None, residual=None, *, backend=None, **backend_kwargs
):
    """Return the edges of the cut-set of a minimum (s, t)-cut."""
    _fnx._validate_backend_dispatch_keywords(
        "minimum_st_edge_cut", backend, backend_kwargs
    )
    H = build_auxiliary_edge_connectivity(G) if auxiliary is None else auxiliary
    if flow_func is None and residual is None:
        H_fnx = _fnx._coerce_arg_to_fnx_graph(H)
        _, (reachable, non_reachable) = _fnx._minimum_cut_raw(
            H_fnx, s, t, capacity="capacity", edmonds_karp=True
        )
    else:
        if flow_func is None:
            from franken_networkx.flow import edmonds_karp

            flow_func = edmonds_karp
        _, (reachable, non_reachable) = _fnx.minimum_cut(
            H, s, t, capacity="capacity", flow_func=flow_func, residual=residual
        )
    reachable = set(reachable)
    non_reachable = set(non_reachable)
    cutset = set()
    for u, nbrs in ((n, G[n]) for n in reachable):
        cutset.update((u, v) for v in nbrs if v in non_reachable)
    return cutset


def minimum_st_node_cut(
    G, s, t, flow_func=None, auxiliary=None, residual=None, *, backend=None, **backend_kwargs
):
    """Return a set of nodes of minimum cardinality that disconnect source from target in G."""
    _fnx._validate_backend_dispatch_keywords(
        "minimum_st_node_cut", backend, backend_kwargs
    )
    H = build_auxiliary_node_connectivity(G) if auxiliary is None else auxiliary
    mapping = H.graph.get("mapping", None)
    if mapping is None:
        raise _fnx.NetworkXError("Invalid auxiliary digraph.")
    if G.has_edge(s, t) or G.has_edge(t, s):
        return set()
    edge_cut = minimum_st_edge_cut(
        H,
        f"{mapping[s]}B",
        f"{mapping[t]}A",
        flow_func=flow_func,
        auxiliary=H,
        residual=residual,
    )
    node_cut = {H.nodes[node]["id"] for edge in edge_cut for node in edge}
    return node_cut - {s, t}


EdgeComponentAuxGraph = _fnx._EdgeComponentAuxGraph
general_k_edge_subgraphs = _fnx._general_k_edge_subgraphs

