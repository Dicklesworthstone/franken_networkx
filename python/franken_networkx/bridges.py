"""FrankenNetworkX bridges submodule.

Re-exports the upstream ``networkx.algorithms.bridges`` surface for
direct module import parity, while binding the main public functions to
the existing fnx wrappers.
"""

from __future__ import annotations

import inspect as _inspect
import importlib as _importlib
import sys as _sys
import types as _types

_nx_bridges = _importlib.import_module("networkx.algorithms.bridges")

import franken_networkx as _fnx

bridges = _fnx.bridges
has_bridges = _fnx.has_bridges
local_bridges = _fnx.local_bridges

__all__ = list(
    getattr(_nx_bridges, "__all__", ("bridges", "has_bridges", "local_bridges"))
)


class _CallableBridgesModule(_types.ModuleType):
    def __call__(self, G, root=None, *, backend=None, **backend_kwargs):
        return bridges(G, root=root, backend=backend, **backend_kwargs)

    def __dir__(self):
        return _module_dir()


def __getattr__(name):
    try:
        return getattr(_nx_bridges, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def _module_dir():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_bridges) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)


def __dir__():
    return _module_dir()


_module = _sys.modules[__name__]
_module.__class__ = _CallableBridgesModule
_module.__signature__ = _inspect.signature(bridges)
