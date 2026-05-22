"""FrankenNetworkX similarity algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_similarity = _importlib.import_module("networkx.algorithms.similarity")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_similarity,
        "__all__",
        (
            "graph_edit_distance",
            "optimal_edit_paths",
            "optimize_graph_edit_distance",
            "optimize_edit_paths",
            "simrank_similarity",
            "panther_similarity",
            "panther_vector_similarity",
            "generate_random_paths",
        ),
    )
)


def graph_edit_distance(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    roots=None,
    upper_bound=None,
    timeout=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the graph edit distance between two graphs."""
    _fnx._validate_backend_dispatch_keywords(
        "graph_edit_distance", backend, backend_kwargs
    )
    return _fnx.graph_edit_distance(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        roots=roots,
        upper_bound=upper_bound,
        timeout=timeout,
    )


def optimal_edit_paths(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return all optimal edit paths and their edit distance."""
    _fnx._validate_backend_dispatch_keywords(
        "optimal_edit_paths", backend, backend_kwargs
    )
    return _fnx.optimal_edit_paths(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
    )


def optimize_graph_edit_distance(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Generate increasingly better graph edit distance estimates."""
    _fnx._validate_backend_dispatch_keywords(
        "optimize_graph_edit_distance", backend, backend_kwargs
    )
    return _fnx.optimize_graph_edit_distance(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
    )


def optimize_edit_paths(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    strictly_decreasing=True,
    roots=None,
    timeout=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Generate edit paths and costs by decreasing cost."""
    _fnx._validate_backend_dispatch_keywords(
        "optimize_edit_paths", backend, backend_kwargs
    )
    return _fnx.optimize_edit_paths(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
        strictly_decreasing=strictly_decreasing,
        roots=roots,
        timeout=timeout,
    )


def simrank_similarity(
    G,
    source=None,
    target=None,
    importance_factor=0.9,
    max_iterations=1000,
    tolerance=0.0001,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return SimRank similarity values."""
    _fnx._validate_backend_dispatch_keywords(
        "simrank_similarity", backend, backend_kwargs
    )
    return _fnx.simrank_similarity(
        G,
        source=source,
        target=target,
        importance_factor=importance_factor,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )


def panther_similarity(
    G,
    source,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return Panther similarity scores from *source*."""
    _fnx._validate_backend_dispatch_keywords(
        "panther_similarity", backend, backend_kwargs
    )
    return _fnx.panther_similarity(
        G,
        source,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
    )


def panther_vector_similarity(
    G,
    source,
    *,
    D=10,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
    backend=None,
    **backend_kwargs,
):
    """Return Panther++ vector similarity scores from *source*."""
    _fnx._validate_backend_dispatch_keywords(
        "panther_vector_similarity", backend, backend_kwargs
    )
    return _fnx.panther_vector_similarity(
        G,
        source,
        D=D,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
    )


def generate_random_paths(
    G,
    sample_size,
    path_length=5,
    index_map=None,
    weight="weight",
    seed=None,
    *,
    source=None,
    backend=None,
    **backend_kwargs,
):
    """Generate random paths from *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "generate_random_paths", backend, backend_kwargs
    )
    return _fnx.generate_random_paths(
        G,
        sample_size,
        path_length=path_length,
        index_map=index_map,
        weight=weight,
        seed=seed,
        source=source,
    )


def __getattr__(name):
    try:
        return getattr(_nx_similarity, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_similarity) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
