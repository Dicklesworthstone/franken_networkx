"""FrankenNetworkX approximation submodule.

Re-exports the upstream ``networkx.algorithms.approximation`` surface so
existing ``franken_networkx.approximation.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``steiner_tree`` — returns fnx.Graph
- ``treewidth_min_degree`` — returns (int, fnx.Graph)
- ``treewidth_min_fill_in`` — returns (int, fnx.Graph)
- ``metric_closure`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.approximation import *  # noqa: F401,F403
import networkx.algorithms.approximation as _nx_approx

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(_nx_approx, "__all__", ())
    or [name for name in dir(_nx_approx) if not name.startswith("_")]
)


def steiner_tree(G, terminal_nodes, weight="weight", method=None, *, backend=None, **backend_kwargs):
    """Return an approximate minimum Steiner tree of G.

    Wraps ``networkx.algorithms.approximation.steiner_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("steiner_tree", backend, backend_kwargs)
    nx_result = _nx_approx.steiner_tree(
        G, terminal_nodes, weight=weight, method=method
    )
    return _from_nx_graph(nx_result)


def treewidth_min_degree(G, *, backend=None, **backend_kwargs):
    """Return a (treewidth, graph) tuple using the minimum degree heuristic.

    Wraps ``networkx.algorithms.approximation.treewidth_min_degree`` and
    converts the tree decomposition graph to an fnx graph type.
    """
    _fnx._validate_backend_dispatch_keywords("treewidth_min_degree", backend, backend_kwargs)
    treewidth, nx_decomp = _nx_approx.treewidth_min_degree(G)
    return treewidth, _from_nx_graph(nx_decomp)


def treewidth_min_fill_in(G, *, backend=None, **backend_kwargs):
    """Return a (treewidth, graph) tuple using the minimum fill-in heuristic.

    Wraps ``networkx.algorithms.approximation.treewidth_min_fill_in`` and
    converts the tree decomposition graph to an fnx graph type.
    """
    _fnx._validate_backend_dispatch_keywords("treewidth_min_fill_in", backend, backend_kwargs)
    treewidth, nx_decomp = _nx_approx.treewidth_min_fill_in(G)
    return treewidth, _from_nx_graph(nx_decomp)


def metric_closure(G, weight="weight", *, backend=None, **backend_kwargs):
    """Return the metric closure of a graph.

    Wraps ``networkx.algorithms.approximation.metric_closure`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("metric_closure", backend, backend_kwargs)
    nx_result = _nx_approx.metric_closure(G, weight=weight)
    return _from_nx_graph(nx_result)
