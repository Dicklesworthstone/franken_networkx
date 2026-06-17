"""FrankenNetworkX matching algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_matching = _importlib.import_module("networkx.algorithms.matching")

import franken_networkx as _fnx

_DIRECT_MAX_WEIGHT_MATCHING_NODE_LIMIT = 12

__all__ = list(
    getattr(
        _nx_matching,
        "__all__",
        (
            "is_matching",
            "is_maximal_matching",
            "is_perfect_matching",
            "max_weight_matching",
            "min_weight_matching",
            "maximal_matching",
        ),
    )
)


def _upstream_body(name):
    function = getattr(_nx_matching, name)
    return getattr(function, "orig_func", function)


def _is_simple_fnx_graph(G):
    return isinstance(G, _fnx.Graph)


def is_matching(G, matching, *, backend=None, **backend_kwargs):
    """Return True if *matching* is a valid matching of *G*."""
    _fnx._validate_backend_dispatch_keywords("is_matching", backend, backend_kwargs)
    return _fnx.is_matching(G, matching)


def is_maximal_matching(G, matching, *, backend=None, **backend_kwargs):
    """Return True if *matching* is a maximal matching of *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "is_maximal_matching", backend, backend_kwargs
    )
    return _fnx.is_maximal_matching(G, matching)


def is_perfect_matching(G, matching, *, backend=None, **backend_kwargs):
    """Return True if *matching* is a perfect matching of *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "is_perfect_matching", backend, backend_kwargs
    )
    return _fnx.is_perfect_matching(G, matching)


def max_weight_matching(
    G, maxcardinality=False, weight="weight", *, backend=None, **backend_kwargs
):
    """Compute a maximum-weight matching of *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "max_weight_matching", backend, backend_kwargs
    )
    if _is_simple_fnx_graph(G) and len(G) <= _DIRECT_MAX_WEIGHT_MATCHING_NODE_LIMIT:
        return _upstream_body("max_weight_matching")(
            G,
            maxcardinality=maxcardinality,
            weight=weight,
        )
    return _fnx.max_weight_matching(
        G, maxcardinality=maxcardinality, weight=weight
    )


def min_weight_matching(G, weight="weight", *, backend=None, **backend_kwargs):
    """Compute a minimum-weight maximal matching of *G*."""
    _fnx._validate_backend_dispatch_keywords(
        "min_weight_matching", backend, backend_kwargs
    )
    if _is_simple_fnx_graph(G):
        return _upstream_body("min_weight_matching")(G, weight=weight)
    return _fnx.min_weight_matching(G, weight=weight)


def maximal_matching(G, *, backend=None, **backend_kwargs):
    """Find a maximal cardinality matching in *G*."""
    _fnx._validate_backend_dispatch_keywords("maximal_matching", backend, backend_kwargs)
    return _fnx.maximal_matching(G)


def __getattr__(name):
    try:
        return getattr(_nx_matching, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_matching) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
