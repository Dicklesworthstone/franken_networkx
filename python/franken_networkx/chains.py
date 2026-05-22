"""FrankenNetworkX chains submodule.

Re-exports the upstream ``networkx.algorithms.chains`` surface for
direct module import parity, while binding implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_chains = _importlib.import_module("networkx.algorithms.chains")

import franken_networkx as _fnx

chain_decomposition = _fnx.chain_decomposition

__all__ = list(getattr(_nx_chains, "__all__", ("chain_decomposition",)))


def __getattr__(name):
    try:
        return getattr(_nx_chains, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_chains) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
