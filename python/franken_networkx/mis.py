"""FrankenNetworkX maximal-independent-set algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

from networkx.utils import create_py_random_state as _create_py_random_state

_nx_mis = _importlib.import_module("networkx.algorithms.mis")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_mis, "__all__", ("maximal_independent_set",)))


def maximal_independent_set(G, nodes=None, seed=None, *, backend=None, **backend_kwargs):
    """Return a maximal independent set with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "maximal_independent_set", backend, backend_kwargs
    )
    upstream_impl = getattr(
        _nx_mis.maximal_independent_set,
        "orig_func",
        _nx_mis.maximal_independent_set,
    )
    return upstream_impl(G, nodes=nodes, seed=_create_py_random_state(seed))


def __getattr__(name):
    try:
        return getattr(_nx_mis, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_mis) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
