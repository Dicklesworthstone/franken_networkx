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


def center(G):
    """Return the center of an undirected tree using fnx's center wrapper."""
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    try:
        is_tree = _fnx.is_tree(G)
    except _fnx.NetworkXPointlessConcept:
        is_tree = False
    if not is_tree:
        raise _fnx.NotATree("input graph is not a tree")
    return _fnx.center(G)


def from_prufer_sequence(sequence, *, backend=None, **backend_kwargs):
    """Return the tree corresponding to the given Prüfer sequence.

    br-r37-c1-prufernative: decode the Prüfer sequence DIRECTLY into an fnx Graph
    instead of building an intermediate networkx graph (per-edge ``add_edge``) and
    then paying ``_from_nx_graph`` (the O(V+E) fnx<-nx conversion + adjacency-row
    alignment). The decode replicates networkx's exact algorithm
    (``networkx.algorithms.tree.coding.from_prufer_sequence``) verbatim — same
    remaining-degree counter, same smallest-available-leaf scan, same final
    two-orphan join, same ``v`` range validation — so node labels (0..n-1),
    edge order and the NetworkXError contract are byte-identical; only the
    construction is fnx-native (one ``add_nodes_from`` + one ``add_edges_from``).
    """
    from collections import Counter
    from itertools import chain

    _fnx._validate_backend_dispatch_keywords(
        "from_prufer_sequence", backend, backend_kwargs
    )
    n = len(sequence) + 2
    degree = Counter(chain(sequence, range(n)))
    edges = []
    not_orphaned = set()
    index = u = next(k for k in range(n) if degree[k] == 1)
    for v in sequence:
        if v < 0 or v > n - 1:
            raise _fnx.NetworkXError(
                f"Invalid Prufer sequence: Values must be between 0 and {n - 1}, got {v}"
            )
        edges.append((u, v))
        not_orphaned.add(u)
        degree[v] -= 1
        if v < index and degree[v] == 1:
            u = v
        else:
            index = u = next(k for k in range(index + 1, n) if degree[k] == 1)
    orphans = set(range(n)) - not_orphaned
    u, v = orphans
    edges.append((u, v))

    G = _fnx.Graph()
    G.add_nodes_from(range(n))
    G.add_edges_from(edges)
    return G


def from_nested_tuple(sequence, sensible_relabeling=False, *, backend=None, **backend_kwargs):
    """Return the rooted tree corresponding to the given nested tuple.

    br-r37-c1-04z53: build the fnx Graph directly instead of constructing a
    NetworkX Graph and then converting it back through ``_from_nx_graph``.
    This mirrors NetworkX's recursive ``join_trees`` label assignment: child
    subtrees are relabeled into contiguous ranges starting at 1 and the local
    root node 0 is appended last. The optional sensible relabeling then applies
    NetworkX's BFS-order mapping to that exact node/edge stream.
    """
    _fnx._validate_backend_dispatch_keywords("from_nested_tuple", backend, backend_kwargs)

    def _make_tree(subtree):
        if len(subtree) == 0:
            return [0], []

        child_parts = [_make_tree(child) for child in subtree]
        nodes = []
        edges = []
        child_roots = []
        next_label = 1
        for child_nodes, child_edges in child_parts:
            labels = {
                old_label: next_label + index
                for index, old_label in enumerate(child_nodes)
            }
            child_roots.append(labels[0])
            nodes.extend(labels[node] for node in child_nodes)
            edges.extend((labels[u], labels[v]) for u, v in child_edges)
            next_label += len(child_nodes)

        nodes.append(0)
        edges.extend((0, root) for root in child_roots)
        return nodes, edges

    nodes, edges = _make_tree(sequence)
    if sensible_relabeling:
        adjacency = {node: [] for node in nodes}
        for u, v in edges:
            adjacency[u].append(v)
            adjacency[v].append(u)

        labels = {0: 0}
        queue = [0]
        for u in queue:
            for v in adjacency[u]:
                if v not in labels:
                    labels[v] = len(labels)
                    queue.append(v)

        nodes = [labels[node] for node in nodes]
        edges = [(labels[u], labels[v]) for u, v in edges]

    graph = _fnx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


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

    Route through the fnx top-level implementation so the submodule does not
    rebuild a NetworkX graph and convert it back into fnx storage.
    """
    _fnx._validate_backend_dispatch_keywords("minimum_spanning_tree", backend, backend_kwargs)
    return _fnx.minimum_spanning_tree(
        G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan
    )


def maximum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False, *, backend=None, **backend_kwargs):
    """Return a maximum spanning tree of an undirected graph.

    Route through the fnx top-level implementation so the submodule does not
    rebuild a NetworkX graph and convert it back into fnx storage.
    """
    _fnx._validate_backend_dispatch_keywords("maximum_spanning_tree", backend, backend_kwargs)
    return _fnx.maximum_spanning_tree(
        G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan
    )
