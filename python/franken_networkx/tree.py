"""FrankenNetworkX tree submodule.

Re-exports the upstream ``networkx.algorithms.tree`` surface so
existing ``franken_networkx.tree.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``from_prufer_sequence`` — returns fnx.Graph
- ``from_nested_tuple`` — returns fnx.Graph
- ``junction_tree`` — returns fnx.Graph
- ``minimum_spanning_tree`` — returns fnx.Graph
- ``maximum_spanning_tree`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.tree import *  # noqa: F401,F403
import networkx.algorithms.tree as _nx_tree

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(_nx_tree, "__all__", ())
    or [name for name in dir(_nx_tree) if not name.startswith("_")]
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.tree import *`` above left the tree
# predicates / branching / spanning-tree functions (and the iterator/partition
# classes) bound to networkx's objects, so ``fnx.tree.is_tree`` etc. silently
# resolved to nx's instead of fnx's native versions. Route them to the fnx
# top-level objects: functions via call-time closure wrappers (import-order
# robust); classes via direct hasattr-guarded alias (call-wrappers would break
# isinstance / class semantics).
_FNX_NATIVE_TREE_FUNCS = (
    "is_arborescence",
    "is_branching",
    "is_forest",
    "is_tree",
    "join_trees",
    "maximum_branching",
    "maximum_spanning_arborescence",
    "maximum_spanning_edges",
    "minimum_branching",
    "minimum_spanning_arborescence",
    "minimum_spanning_edges",
    "number_of_spanning_trees",
    "partition_spanning_tree",
    "random_spanning_tree",
    "to_nested_tuple",
    "to_prufer_sequence",
)
_FNX_NATIVE_TREE_CLASSES = (
    "ArborescenceIterator",
    "EdgePartition",
    "SpanningTreeIterator",
)


def _make_fnx_tree_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.tree.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_TREE_FUNCS:
    globals()[_name] = _make_fnx_tree_router(_name)

for _name in _FNX_NATIVE_TREE_CLASSES:
    if hasattr(_fnx, _name):
        globals()[_name] = getattr(_fnx, _name)


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


def minimum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False, *, backend=None, **backend_kwargs):
    """Return a minimum spanning tree of an undirected graph.

    Wraps ``networkx.algorithms.tree.minimum_spanning_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("minimum_spanning_tree", backend, backend_kwargs)
    nx_result = _nx_tree.minimum_spanning_tree(G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan)
    return _from_nx_graph(nx_result)


def maximum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False, *, backend=None, **backend_kwargs):
    """Return a maximum spanning tree of an undirected graph.

    Wraps ``networkx.algorithms.tree.maximum_spanning_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("maximum_spanning_tree", backend, backend_kwargs)
    nx_result = _nx_tree.maximum_spanning_tree(G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan)
    return _from_nx_graph(nx_result)
