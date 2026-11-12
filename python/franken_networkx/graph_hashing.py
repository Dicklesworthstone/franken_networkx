"""FrankenNetworkX graph-hashing algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_graph_hashing = _importlib.import_module("networkx.algorithms.graph_hashing")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_graph_hashing,
        "__all__",
        ("weisfeiler_lehman_graph_hash", "weisfeiler_lehman_subgraph_hashes"),
    )
)


def weisfeiler_lehman_graph_hash(
    G,
    edge_attr=None,
    node_attr=None,
    iterations=3,
    digest_size=16,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the Weisfeiler-Lehman graph hash."""
    _fnx._validate_backend_dispatch_keywords(
        "weisfeiler_lehman_graph_hash", backend, backend_kwargs
    )
    return _fnx.weisfeiler_lehman_graph_hash(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        iterations=iterations,
        digest_size=digest_size,
    )


def weisfeiler_lehman_subgraph_hashes(
    G,
    edge_attr=None,
    node_attr=None,
    iterations=3,
    digest_size=16,
    include_initial_labels=False,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return Weisfeiler-Lehman subgraph hashes keyed by node."""
    _fnx._validate_backend_dispatch_keywords(
        "weisfeiler_lehman_subgraph_hashes", backend, backend_kwargs
    )
    return _fnx.weisfeiler_lehman_subgraph_hashes(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        iterations=iterations,
        digest_size=digest_size,
        include_initial_labels=include_initial_labels,
    )


def __getattr__(name):
    try:
        return getattr(_nx_graph_hashing, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_graph_hashing) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
