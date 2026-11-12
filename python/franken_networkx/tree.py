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

import inspect as _inspect

import franken_networkx as _fnx
import networkx.algorithms.tree as _nx_tree
from franken_networkx.readwrite import _from_nx_graph
from networkx.algorithms.tree import *

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
    _target = getattr(_nx_tree, _fn_name, None) or getattr(_fnx, _fn_name, None)
    if _target is not None:
        try:
            _routed.__signature__ = _inspect.signature(_target)
        except (ValueError, TypeError):
            pass
    return _routed


for _name in _FNX_NATIVE_TREE_FUNCS:
    globals()[_name] = _make_fnx_tree_router(_name)

for _name in _FNX_NATIVE_TREE_CLASSES:
    if hasattr(_fnx, _name):
        globals()[_name] = getattr(_fnx, _name)


def is_arborescence(G, *, backend=None, **backend_kwargs):
    return _fnx.is_arborescence(G, backend=backend, **backend_kwargs)


def is_branching(G, *, backend=None, **backend_kwargs):
    return _fnx.is_branching(G, backend=backend, **backend_kwargs)


def is_forest(G, *, backend=None, **backend_kwargs):
    return _fnx.is_forest(G, backend=backend, **backend_kwargs)


def is_tree(G, *, backend=None, **backend_kwargs):
    return _fnx.is_tree(G, backend=backend, **backend_kwargs)


def maximum_spanning_edges(
    G,
    algorithm="kruskal",
    weight="weight",
    keys=True,
    data=True,
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.maximum_spanning_edges(
        G,
        algorithm=algorithm,
        weight=weight,
        keys=keys,
        data=data,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def minimum_spanning_edges(
    G,
    algorithm="kruskal",
    weight="weight",
    keys=True,
    data=True,
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.minimum_spanning_edges(
        G,
        algorithm=algorithm,
        weight=weight,
        keys=keys,
        data=data,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def maximum_branching(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.maximum_branching(
        G, attr=attr, default=default, preserve_attrs=preserve_attrs,
        partition=partition, backend=backend, **backend_kwargs,
    )


def minimum_branching(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.minimum_branching(
        G, attr=attr, default=default, preserve_attrs=preserve_attrs,
        partition=partition, backend=backend, **backend_kwargs,
    )


def maximum_spanning_arborescence(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.maximum_spanning_arborescence(
        G, attr=attr, default=default, preserve_attrs=preserve_attrs,
        partition=partition, backend=backend, **backend_kwargs,
    )


def minimum_spanning_arborescence(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx.minimum_spanning_arborescence(
        G, attr=attr, default=default, preserve_attrs=preserve_attrs,
        partition=partition, backend=backend, **backend_kwargs,
    )


def to_nested_tuple(T, root, canonical_form=False, *, backend=None, **backend_kwargs):
    return _fnx.to_nested_tuple(
        T,
        root,
        canonical_form=canonical_form,
        backend=backend,
        **backend_kwargs,
    )


def to_prufer_sequence(T, *, backend=None, **backend_kwargs):
    return _fnx.to_prufer_sequence(T, backend=backend, **backend_kwargs)


def number_of_spanning_trees(G, *, root=None, weight=None, backend=None, **backend_kwargs):
    return _fnx.number_of_spanning_trees(
        G, root=root, weight=weight, backend=backend, **backend_kwargs
    )


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


def _subtree_sizes(G, root):
    sizes = {root: 1}
    stack = [root]
    for parent, child in _fnx.dfs_edges(G, root):
        while stack[-1] != parent:
            descendant = stack.pop()
            sizes[stack[-1]] += sizes[descendant]
        stack.append(child)
        sizes[child] = 1
    for i in range(len(stack) - 1, 0, -1):
        sizes[stack[i - 1]] += sizes[stack[i]]
    return sizes


def centroid(G, *, backend=None, **backend_kwargs):
    """Return the centroid of an unweighted tree."""
    _fnx._validate_backend_dispatch_keywords("centroid", backend, backend_kwargs)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if not _fnx.is_tree(G):
        raise _fnx.NotATree("provided graph is not a tree")
    prev, root = None, next(iter(G))
    sizes = _subtree_sizes(G, root)
    total_size = G.number_of_nodes()

    def _heaviest_child(prev_node, root_node):
        return max(
            (x for x in G.neighbors(root_node) if x != prev_node),
            key=sizes.get,
            default=None,
        )

    hc = _heaviest_child(prev, root)
    while max(total_size - sizes[root], sizes.get(hc, 0)) > total_size / 2:
        prev, root = root, hc
        hc = _heaviest_child(prev, root)

    return [root] + [
        x for x in G.neighbors(root) if x != prev and sizes[x] == total_size / 2
    ]


def branching_weight(G, attr="weight", default=1, *, backend=None, **backend_kwargs):
    """Return the total weight of a branching."""
    _fnx._validate_backend_dispatch_keywords(
        "branching_weight", backend, backend_kwargs
    )
    return sum(edge[2].get(attr, default) for edge in G.edges(data=True))


def minimal_branching(
    G,
    /,
    *,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    backend=None,
    **backend_kwargs,
):
    """Return a minimal branching from ``G``."""
    _fnx._validate_backend_dispatch_keywords(
        "minimal_branching", backend, backend_kwargs
    )
    return _fnx._minimal_branching_backend_impl(
        G,
        attr=attr,
        default=default,
        preserve_attrs=preserve_attrs,
        partition=partition,
    )


def greedy_branching(
    G, attr="weight", default=1, kind="max", seed=None, *, backend=None, **backend_kwargs
):
    """Return a branching obtained through a greedy algorithm."""
    import operator as _operator
    import string as _string

    _fnx._validate_backend_dispatch_keywords(
        "greedy_branching", backend, backend_kwargs
    )
    if kind not in {"max", "min"}:
        raise _fnx.NetworkXException("Unknown value for `kind`.")

    reverse = kind != "min"
    if attr is None:
        rng = _fnx._generator_random_state(seed)
        attr = "".join(rng.choice(_string.ascii_letters) for _ in range(15))

    edges = [(u, v, data.get(attr, default)) for (u, v, data) in G.edges(data=True)]
    try:
        edges.sort(key=_operator.itemgetter(2, 0, 1), reverse=reverse)
    except TypeError:
        edges.sort(key=_operator.itemgetter(2), reverse=reverse)

    B = _fnx.DiGraph()
    B.add_nodes_from(G)

    parent = {}
    weight_rank = {}

    def _find(x):
        if x not in parent:
            parent[x] = x
            weight_rank[x] = 1
            return x
        path = []
        root = parent[x]
        while root != x:
            path.append(x)
            x = root
            root = parent[x]
        for ancestor in path:
            parent[ancestor] = root
        return root

    def _union(x, y):
        rx, ry = _find(x), _find(y)
        if rx == ry:
            return
        if weight_rank[rx] < weight_rank[ry]:
            rx, ry = ry, rx
        weight_rank[rx] += weight_rank[ry]
        parent[ry] = rx

    for u, v, w in edges:
        if _find(u) == _find(v):
            continue
        if B.in_degree(v) == 1:
            continue
        data = {attr: w} if attr is not None else {}
        B.add_edge(u, v, **data)
        _union(u, v)

    return B


def from_prufer_sequence(sequence, *, backend=None, **backend_kwargs):
    """Return the tree corresponding to the given Prüfer sequence.

    br-r37-c1-prufernative: route to the native Rust decoder (_fnx.from_prufer_sequence),
    which uses _fnx.from_prufer_sequence_rust for a ~5.9x speedup vs NetworkX and byte-exact
    parity.
    """
    _fnx._validate_backend_dispatch_keywords(
        "from_prufer_sequence", backend, backend_kwargs
    )
    return _fnx.from_prufer_sequence(sequence)



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
    """Return a junction tree of a given graph."""
    return _fnx.junction_tree(G, backend=backend, **backend_kwargs)


def minimum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False, *, backend=None, **backend_kwargs):
    """Return a minimum spanning tree of an undirected graph.

    Wraps ``networkx.algorithms.tree.minimum_spanning_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("minimum_spanning_tree", backend, backend_kwargs)
    # br-r37-c1-treemst (cc): was nx-delegating (_nx_tree.minimum_spanning_tree +
    # _from_nx_graph = full fnx->nx->fnx round-trip, 0.36x vs nx). The top-level
    # fnx.minimum_spanning_tree has a byte-exact native Kruskal/Prim/Boruvka kernel
    # that returns an fnx graph directly -> 0.36x -> 0.66x (1.9x self), no round-trip.
    return _fnx.minimum_spanning_tree(G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan)


def maximum_spanning_tree(G, weight="weight", algorithm="kruskal", ignore_nan=False, *, backend=None, **backend_kwargs):
    """Return a maximum spanning tree of an undirected graph.

    Wraps ``networkx.algorithms.tree.maximum_spanning_tree`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("maximum_spanning_tree", backend, backend_kwargs)
    # br-r37-c1-treemst (cc): route to the native top-level (no nx round-trip), as
    # with minimum_spanning_tree.
    return _fnx.maximum_spanning_tree(G, weight=weight, algorithm=algorithm, ignore_nan=ignore_nan)
