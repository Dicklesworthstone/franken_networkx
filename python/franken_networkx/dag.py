"""FrankenNetworkX dag submodule.

Re-exports the upstream ``networkx.algorithms.dag`` surface so
existing ``franken_networkx.dag.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``dag_to_branching`` — returns fnx.DiGraph
"""

from __future__ import annotations

from itertools import combinations as _combinations

from networkx.algorithms.dag import *  # noqa: F401,F403
import networkx.algorithms.dag as _nx_dag

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


# br-r37-c1-tcnoconv: transitive_closure / transitive_reduction are NOT fnx
# backends, so ``nx.transitive_closure(fnx_G)`` runs nx's raw algorithm over the
# fnx graph — which starts from ``TC = G.copy()`` and so already returns an fnx
# graph, byte-identical to nx-on-an-nx-graph (verified 1500/1500 each, incl
# reflexive variants and node/edge attrs). The prior unconditional _from_nx_graph
# was a pure redundant O(V+E) re-conversion. Skip it when the result is already an
# fnx graph; a genuine nx-typed input still yields an nx result -> convert.
# (transitive_closure_dag / dag_to_branching return nx graphs and keep converting.)
def _fnx_result_or_convert(nx_result):
    if isinstance(
        nx_result, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ):
        return nx_result
    return _from_nx_graph(nx_result)


# br-r37-c1-4gmg2: has_cycle, colliders and v_structures are module-level
# public functions of networkx.algorithms.dag but are absent from
# dag.__all__, so the star import above does not pick them up.  Re-export
# them explicitly for fnx.algorithms.dag parity (same root cause as
# check_planarity_recursive, br-r37-c1-56nd2).  nx's implementations
# already accept fnx graph types, handle backend dispatch, and raise the
# correct NetworkXError / NetworkXNotImplemented on undirected input, so
# no native wrapper is needed.
def has_cycle(G, *, backend=None, **backend_kwargs):
    """Return whether directed graph ``G`` contains a cycle.

    br-hascycle: the wildcard import + explicit re-export left this bound to
    NetworkX's implementation, which on a fnx graph runs over the per-access
    substrate (0.017x nx cyclic / 0.13x DAG). ``has_cycle(G)`` is exactly
    ``not is_directed_acyclic_graph(G)``, and fnx's native is_dag uses Kahn's
    integer-CSR kernel that naturally terminates on the first stalled peel
    (fast on BOTH acyclic and cyclic inputs: ~34x nx cyclic, ~68x nx DAG,
    value-identical including self-loops, parallel edges, and the empty graph).
    Undirected input (nx raises ``NetworkXNotImplemented``) and backend dispatch
    fall back to NetworkX verbatim.
    """
    if G.is_directed() and backend is None and not backend_kwargs:
        return not _fnx.is_directed_acyclic_graph(G)
    return _nx_dag.has_cycle(G, backend=backend, **backend_kwargs)


# br-r37-c1-5fije: nx's colliders/v_structures call ``G.predecessors(node)``
# once per node, so on an fnx graph they pay O(V) boundary crossings, each
# re-materialising predecessor node-key PyObjects. Measured against live nx
# 3.6.1 on a 2000-node DAG: 0.0710x and 0.0888x, both admissible. The algorithm
# is identical — the graph interface is the whole gap.
#
# ``_native_predecessor_keys_bulk`` returns every node's predecessor row in ONE
# crossing, in ``nodes_ordered()`` order with the z6uka per-cell display-key
# override applied, i.e. exactly what ``G.nodes`` and ``pred[v][u]`` yield.
#
# A cheaper reconstruction from ``G.edges()`` was tried and FAILS PARITY: a
# predecessor row is in the insertion order of the edges INTO that node, while
# ``edges()`` walks the successor structure and emits grouped by source. Both
# functions are generators whose tuple order is observable, so the rows must
# come from the graph's own predecessor structure.
def _bulk_predecessor_rows(G):
    """[(node, [preds])] via one native crossing, or None if unavailable."""
    bulk = getattr(G, "_native_predecessor_keys_bulk", None)
    return None if bulk is None else bulk()


def _colliders_fast(rows):
    for node, parents in rows:
        if len(parents) > 1:
            for p1, p2 in _combinations(parents, 2):
                yield (p1, node, p2)


def _v_structures_fast(G, rows):
    for node, parents in rows:
        if len(parents) > 1:
            for p1, p2 in _combinations(parents, 2):
                if not (G.has_edge(p1, p2) or G.has_edge(p2, p1)):
                    yield (p1, node, p2)


# Deliberately NOT generator functions: nx raises NetworkXNotImplemented on
# undirected input when the function is CALLED, and a ``yield`` in this body
# would defer that to the first ``next()`` — an observable contract change. The
# fallback is therefore returned eagerly, matching ``has_cycle`` above.
def colliders(G, *, backend=None, **backend_kwargs):
    """Yield the collider 3-tuples of ``G``.

    See ``networkx.algorithms.dag.colliders``. Directed fnx graphs take a
    single-crossing predecessor bulk; every other input falls back to NetworkX
    verbatim, including backend dispatch and the undirected error contract.
    """
    if G.is_directed() and backend is None and not backend_kwargs:
        rows = _bulk_predecessor_rows(G)
        if rows is not None:
            return _colliders_fast(rows)
    return _nx_dag.colliders(G, backend=backend, **backend_kwargs)


def v_structures(G, *, backend=None, **backend_kwargs):
    """Yield the v-structure 3-tuples of ``G``.

    See ``networkx.algorithms.dag.v_structures``. Same routing as
    ``colliders``; the non-adjacency test stays on ``G.has_edge`` so the
    contract is nx's exactly.
    """
    if G.is_directed() and backend is None and not backend_kwargs:
        rows = _bulk_predecessor_rows(G)
        if rows is not None:
            return _v_structures_fast(G, rows)
    return _nx_dag.v_structures(G, backend=backend, **backend_kwargs)

# br-r37-c1-ukwgj: root_to_leaf_paths is dispatchable but absent from
# dag.__all__, so the star import skips it.  Re-export for parity.
root_to_leaf_paths = _nx_dag.root_to_leaf_paths

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
    """Return a branching representing the DAG.

    Wraps ``networkx.algorithms.dag.dag_to_branching`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("dag_to_branching", backend, backend_kwargs)
    nx_result = _nx_dag.dag_to_branching(G)
    return _from_nx_graph(nx_result)


def transitive_closure(G, reflexive=False, *, backend=None, **backend_kwargs):
    """Return the transitive closure of a DAG.

    Wraps ``networkx.algorithms.dag.transitive_closure`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("transitive_closure", backend, backend_kwargs)
    nx_result = _nx_dag.transitive_closure(G, reflexive=reflexive)
    return _fnx_result_or_convert(nx_result)


def transitive_closure_dag(G, topo_order=None, *, backend=None, **backend_kwargs):
    """Return the transitive closure of a DAG (optimized version).

    Wraps ``networkx.algorithms.dag.transitive_closure_dag`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("transitive_closure_dag", backend, backend_kwargs)
    nx_result = _nx_dag.transitive_closure_dag(G, topo_order=topo_order)
    return _from_nx_graph(nx_result)


def transitive_reduction(G, *, backend=None, **backend_kwargs):
    """Return the transitive reduction of a DAG.

    Wraps ``networkx.algorithms.dag.transitive_reduction`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("transitive_reduction", backend, backend_kwargs)
    nx_result = _nx_dag.transitive_reduction(G)
    return _fnx_result_or_convert(nx_result)
