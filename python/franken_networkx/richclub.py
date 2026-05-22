"""FrankenNetworkX rich-club algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_richclub = _importlib.import_module("networkx.algorithms.richclub")

import franken_networkx as _fnx

__all__ = list(getattr(_nx_richclub, "__all__", ("rich_club_coefficient",)))


def rich_club_coefficient(
    G,
    normalized=True,
    Q=100,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the rich-club coefficient of a graph."""
    _fnx._validate_backend_dispatch_keywords(
        "rich_club_coefficient", backend, backend_kwargs
    )
    return _fnx.rich_club_coefficient(G, normalized=normalized, Q=Q, seed=seed)


def __getattr__(name):
    try:
        return getattr(_nx_richclub, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_richclub) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
