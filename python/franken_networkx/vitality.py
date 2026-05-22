"""FrankenNetworkX vitality algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_vitality = _importlib.import_module("networkx.algorithms.vitality")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_vitality, "__all__", ("closeness_vitality",)))


def closeness_vitality(
    G,
    node=None,
    weight=None,
    wiener_index=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return closeness vitality with the upstream module signature."""
    _fnx._validate_backend_dispatch_keywords(
        "closeness_vitality", backend, backend_kwargs
    )
    return _fnx.closeness_vitality(
        G,
        node=node,
        weight=weight,
        wiener_index=wiener_index,
    )


def __getattr__(name):
    try:
        return getattr(_nx_vitality, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_vitality) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
