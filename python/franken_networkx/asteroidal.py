"""FrankenNetworkX asteroidal submodule.

Re-exports the upstream ``networkx.algorithms.asteroidal`` surface for
direct module import parity, while binding implemented functions to the
existing fnx wrappers.
"""

from __future__ import annotations

import importlib as _importlib

_nx_asteroidal = _importlib.import_module("networkx.algorithms.asteroidal")

import franken_networkx as _fnx
from franken_networkx import utils as _fnx_utils

not_implemented_for = _fnx_utils.not_implemented_for
is_at_free = _fnx.is_at_free
find_asteroidal_triple = _fnx.find_asteroidal_triple


def create_component_structure(G, *, backend=None, **backend_kwargs):
    """Create component structure for G."""
    _fnx._validate_backend_dispatch_keywords(
        "create_component_structure", backend, backend_kwargs
    )
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    V = set(G.nodes)
    component_structure = {}
    for v in V:
        label = 0
        closed_neighborhood = set(G[v]).union({v})
        row_dict = {}
        for u in closed_neighborhood:
            row_dict[u] = 0

        G_reduced = G.subgraph(set(G.nodes) - closed_neighborhood)
        for cc in _fnx.connected_components(G_reduced):
            label += 1
            for u in cc:
                row_dict[u] = label

        component_structure[v] = row_dict

    return component_structure

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
