"""FrankenNetworkX reciprocity algorithm submodule."""

from __future__ import annotations

import importlib as _importlib
import inspect as _inspect
import sys as _sys
import types as _types

_nx_reciprocity = _importlib.import_module("networkx.algorithms.reciprocity")

import franken_networkx as _fnx

_fnx_reciprocity = _fnx.__dict__["reciprocity"]
_fnx_overall_reciprocity = _fnx.__dict__["overall_reciprocity"]

__all__ = list(
    getattr(_nx_reciprocity, "__all__", ("reciprocity", "overall_reciprocity"))
)


def overall_reciprocity(G, *, backend=None, **backend_kwargs):
    """Return the reciprocity for the whole graph."""
    _fnx._validate_backend_dispatch_keywords(
        "overall_reciprocity", backend, backend_kwargs
    )
    return _fnx_overall_reciprocity(G)


def reciprocity(G, nodes=None, *, backend=None, **backend_kwargs):
    """Return reciprocity for nodes in a directed graph."""
    _fnx._validate_backend_dispatch_keywords("reciprocity", backend, backend_kwargs)
    return _fnx_reciprocity(G, nodes=nodes)


def __getattr__(name):
    try:
        return getattr(_nx_reciprocity, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_reciprocity) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)


class _CallableReciprocityModule(_types.ModuleType):
    def __call__(self, G, nodes=None, *, backend=None, **backend_kwargs):
        return reciprocity(G, nodes=nodes, backend=backend, **backend_kwargs)


_module = _sys.modules[__name__]
_module.__class__ = _CallableReciprocityModule
_module.__signature__ = _inspect.signature(_nx_reciprocity.reciprocity)
