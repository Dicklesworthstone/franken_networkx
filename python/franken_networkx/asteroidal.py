"""FrankenNetworkX asteroidal submodule.

Re-exports the upstream ``networkx.algorithms.asteroidal`` surface for
direct module import parity, while binding implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_asteroidal = _importlib.import_module("networkx.algorithms.asteroidal")

import franken_networkx as _fnx

is_at_free = _fnx.is_at_free
find_asteroidal_triple = _fnx.find_asteroidal_triple

__all__ = list(
    getattr(_nx_asteroidal, "__all__", ("is_at_free", "find_asteroidal_triple"))
)


def __getattr__(name):
    try:
        return getattr(_nx_asteroidal, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_asteroidal) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
