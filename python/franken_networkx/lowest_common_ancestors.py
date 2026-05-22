"""FrankenNetworkX lowest-common-ancestor algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_lca = _importlib.import_module("networkx.algorithms.lowest_common_ancestors")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_lca,
        "__all__",
        (
            "all_pairs_lowest_common_ancestor",
            "tree_all_pairs_lowest_common_ancestor",
            "lowest_common_ancestor",
        ),
    )
)


def all_pairs_lowest_common_ancestor(
    G, pairs=None, *, backend=None, **backend_kwargs
):
    """Return the lowest common ancestor of all pairs or provided pairs."""
    return _fnx.all_pairs_lowest_common_ancestor(
        G, pairs=pairs, backend=backend, **backend_kwargs
    )


def tree_all_pairs_lowest_common_ancestor(
    G, root=None, pairs=None, *, backend=None, **backend_kwargs
):
    """Yield lowest common ancestors for node pairs in a rooted tree."""
    return _fnx.tree_all_pairs_lowest_common_ancestor(
        G, root=root, pairs=pairs, backend=backend, **backend_kwargs
    )


def lowest_common_ancestor(
    G, node1, node2, default=None, *, backend=None, **backend_kwargs
):
    """Compute the lowest common ancestor of the given pair of nodes."""
    return _fnx.lowest_common_ancestor(
        G,
        node1,
        node2,
        default=default,
        backend=backend,
        **backend_kwargs,
    )


def __getattr__(name):
    try:
        return getattr(_nx_lca, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_lca) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
