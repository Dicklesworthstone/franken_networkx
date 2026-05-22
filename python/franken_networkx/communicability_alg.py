"""FrankenNetworkX communicability algorithm submodule.

Re-exports the upstream ``networkx.algorithms.communicability_alg`` public
surface for direct module import parity, while binding implemented functions
to the existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_communicability_alg = _importlib.import_module(
    "networkx.algorithms.communicability_alg"
)

import franken_networkx as _fnx

communicability = _fnx.communicability
communicability_exp = _fnx.communicability_exp

__all__ = list(
    getattr(
        _nx_communicability_alg,
        "__all__",
        ("communicability", "communicability_exp"),
    )
)


def __getattr__(name):
    try:
        return getattr(_nx_communicability_alg, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_communicability_alg) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
