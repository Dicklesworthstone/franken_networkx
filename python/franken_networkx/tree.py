"""FrankenNetworkX tree submodule.

Re-exports the upstream ``networkx.algorithms.tree`` surface so
existing ``franken_networkx.tree.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``from_prufer_sequence`` — returns fnx.Graph
- ``from_nested_tuple`` — returns fnx.Graph
- ``junction_tree`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.tree import *  # noqa: F401,F403
import networkx.algorithms.tree as _nx_tree

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def from_prufer_sequence(sequence, *, backend=None, **backend_kwargs):
    """Return the tree corresponding to the given Prüfer sequence.

    Wraps ``networkx.algorithms.tree.from_prufer_sequence`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("from_prufer_sequence", backend, backend_kwargs)
    nx_result = _nx_tree.from_prufer_sequence(sequence)
    return _from_nx_graph(nx_result)


def from_nested_tuple(sequence, sensible_relabeling=False, *, backend=None, **backend_kwargs):
    """Return the rooted tree corresponding to the given nested tuple.

    Wraps ``networkx.algorithms.tree.from_nested_tuple`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("from_nested_tuple", backend, backend_kwargs)
    nx_result = _nx_tree.from_nested_tuple(sequence, sensible_relabeling=sensible_relabeling)
    return _from_nx_graph(nx_result)


def junction_tree(G, *, backend=None, **backend_kwargs):
    """Return a junction tree of a given graph.

    Wraps ``networkx.algorithms.tree.junction_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("junction_tree", backend, backend_kwargs)
    nx_result = _nx_tree.junction_tree(G)
    return _from_nx_graph(nx_result)
