"""FrankenNetworkX dag submodule.

Re-exports the upstream ``networkx.algorithms.dag`` surface so
existing ``franken_networkx.dag.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``dag_to_branching`` — returns fnx.DiGraph
"""

from __future__ import annotations

from itertools import combinations as _combinations, product as _product

from networkx.algorithms.dag import *  # noqa: F401,F403
import networkx.algorithms.dag as _nx_dag

import franken_networkx as _fnx


def has_cycle(G, *, backend=None, **backend_kwargs):
    """Return whether directed graph ``G`` contains a cycle."""
    _fnx._validate_backend_dispatch_keywords("has_cycle", backend, backend_kwargs)
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    return not _fnx.is_directed_acyclic_graph(G)


def _bulk_predecessor_rows(G):
    """[(node, [preds])] via one native crossing, or None if unavailable."""
    bulk = getattr(G, "_native_predecessor_keys_bulk", None)
    return None if bulk is None else bulk()


def _colliders_fast(rows):
    for node, parents in rows:
        if len(parents) > 1:
            for p1, p2 in _combinations(parents, 2):
                yield (p1, node, p2)


def _colliders_generic(G):
    for node in G.nodes:
        for p1, p2 in _combinations(G.predecessors(node), 2):
            yield (p1, node, p2)


def _v_structures_fast(G, rows):
    for node, parents in rows:
        if len(parents) > 1:
            for p1, p2 in _combinations(parents, 2):
                if not (G.has_edge(p1, p2) or G.has_edge(p2, p1)):
                    yield (p1, node, p2)


def _v_structures_generic(G):
    for p1, c, p2 in _colliders_generic(G):
        if not (G.has_edge(p1, p2) or G.has_edge(p2, p1)):
            yield (p1, c, p2)


# Deliberately NOT generator functions: nx raises NetworkXNotImplemented on
# undirected input when the function is CALLED, and a ``yield`` in this body
# would defer that to the first ``next()`` — an observable contract change.
def colliders(G, *, backend=None, **backend_kwargs):
    """Yield the collider 3-tuples of ``G``."""
    _fnx._validate_backend_dispatch_keywords("colliders", backend, backend_kwargs)
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    rows = _bulk_predecessor_rows(G)
    if rows is not None:
        return _colliders_fast(rows)
    return _colliders_generic(G)


def v_structures(G, *, backend=None, **backend_kwargs):
    """Yield the v-structure 3-tuples of ``G``."""
    _fnx._validate_backend_dispatch_keywords("v_structures", backend, backend_kwargs)
    if not G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for undirected type")
    rows = _bulk_predecessor_rows(G)
    if rows is not None:
        return _v_structures_fast(G, rows)
    return _v_structures_generic(G)


def root_to_leaf_paths(G, *, backend=None, **backend_kwargs):
    """Yield root-to-leaf paths in a directed acyclic graph."""
    _fnx._validate_backend_dispatch_keywords(
        "root_to_leaf_paths", backend, backend_kwargs
    )

    def _gen():
        roots = (v for v, d in G.in_degree() if d == 0)
        leaves = (v for v, d in G.out_degree() if d == 0)
        for root, leaf in _product(roots, leaves):
            yield from _fnx.all_simple_paths(G, root, leaf)

    return _gen()

def descendants(G, source, *, backend=None, **backend_kwargs):
    """Return descendants through FrankenNetworkX's native implementation."""
    return _fnx.descendants(G, source, backend=backend, **backend_kwargs)


def ancestors(G, source, *, backend=None, **backend_kwargs):
    """Return ancestors through FrankenNetworkX's native implementation."""
    return _fnx.ancestors(G, source, backend=backend, **backend_kwargs)


def topological_sort(G, *, backend=None, **backend_kwargs):
    """Yield a native topological ordering."""
    return _fnx.topological_sort(G, backend=backend, **backend_kwargs)


def lexicographical_topological_sort(G, key=None, *, backend=None, **backend_kwargs):
    """Yield a native lexicographical topological ordering."""
    return _fnx.lexicographical_topological_sort(
        G, key=key, backend=backend, **backend_kwargs
    )


def all_topological_sorts(G, *, backend=None, **backend_kwargs):
    """Yield all native topological orderings."""
    return _fnx.all_topological_sorts(G, backend=backend, **backend_kwargs)


def topological_generations(G, *, backend=None, **backend_kwargs):
    """Yield native topological generations."""
    return _fnx.topological_generations(G, backend=backend, **backend_kwargs)


def is_directed_acyclic_graph(G, *, backend=None, **backend_kwargs):
    """Return whether ``G`` is acyclic using the native predicate."""
    return _fnx.is_directed_acyclic_graph(G, backend=backend, **backend_kwargs)


def is_aperiodic(G, *, backend=None, **backend_kwargs):
    """Return whether ``G`` is aperiodic using the native predicate."""
    return _fnx.is_aperiodic(G, backend=backend, **backend_kwargs)


def antichains(G, topo_order=None, *, backend=None, **backend_kwargs):
    """Yield antichains through FrankenNetworkX's native implementation."""
    return _fnx.antichains(
        G, topo_order=topo_order, backend=backend, **backend_kwargs
    )


def dag_longest_path(
    G, weight="weight", default_weight=1, topo_order=None, *, backend=None, **backend_kwargs
):
    """Return a native longest path in a DAG."""
    return _fnx.dag_longest_path(
        G,
        weight=weight,
        default_weight=default_weight,
        topo_order=topo_order,
        backend=backend,
        **backend_kwargs,
    )


def dag_longest_path_length(
    G, weight="weight", default_weight=1, *, backend=None, **backend_kwargs
):
    """Return a native longest-path length in a DAG."""
    return _fnx.dag_longest_path_length(
        G,
        weight=weight,
        default_weight=default_weight,
        backend=backend,
        **backend_kwargs,
    )

__all__ = list(
    getattr(
        _nx_dag,
        "__all__",
        (
            "descendants",
            "ancestors",
            "topological_sort",
            "lexicographical_topological_sort",
            "all_topological_sorts",
            "topological_generations",
            "is_directed_acyclic_graph",
            "is_aperiodic",
            "transitive_closure",
            "transitive_closure_dag",
            "transitive_reduction",
            "antichains",
            "dag_longest_path",
            "dag_longest_path_length",
            "dag_to_branching",
        ),
    )
)


def dag_to_branching(G, *, backend=None, **backend_kwargs):
    """Return a branching representing the DAG."""
    return _fnx.dag_to_branching(G, backend=backend, **backend_kwargs)


def transitive_closure(G, reflexive=False, *, backend=None, **backend_kwargs):
    """Return the transitive closure of a DAG."""
    return _fnx.transitive_closure(G, reflexive=reflexive, backend=backend, **backend_kwargs)


def transitive_closure_dag(G, topo_order=None, *, backend=None, **backend_kwargs):
    """Return the transitive closure of a DAG (optimized version)."""
    return _fnx.transitive_closure_dag(G, topo_order=topo_order, backend=backend, **backend_kwargs)


def transitive_reduction(G, *, backend=None, **backend_kwargs):
    """Return the transitive reduction of a DAG."""
    return _fnx.transitive_reduction(G, backend=backend, **backend_kwargs)
