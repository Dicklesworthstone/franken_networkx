"""FrankenNetworkX dag submodule.

Re-exports the upstream ``networkx.algorithms.dag`` surface so
existing ``franken_networkx.dag.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``dag_to_branching`` — returns fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.dag import *  # noqa: F401,F403
import networkx.algorithms.dag as _nx_dag

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

# br-r37-c1-4gmg2: has_cycle, colliders and v_structures are module-level
# public functions of networkx.algorithms.dag but are absent from
# dag.__all__, so the star import above does not pick them up.  Re-export
# them explicitly for fnx.algorithms.dag parity (same root cause as
# check_planarity_recursive, br-r37-c1-56nd2).  nx's implementations
# already accept fnx graph types, handle backend dispatch, and raise the
# correct NetworkXError / NetworkXNotImplemented on undirected input, so
# no native wrapper is needed.
has_cycle = _nx_dag.has_cycle
colliders = _nx_dag.colliders
v_structures = _nx_dag.v_structures

# br-r37-c1-ukwgj: root_to_leaf_paths is dispatchable but absent from
# dag.__all__, so the star import skips it.  Re-export for parity.
root_to_leaf_paths = _nx_dag.root_to_leaf_paths

# br-r37-c1-2qsqf: ``from networkx.algorithms.dag import *`` above left these DAG
# functions bound to networkx's implementations, so ``fnx.dag.topological_sort``
# (ancestors/descendants/is_directed_acyclic_graph/antichains/dag_longest_path/
# ...) silently resolved to nx's instead of fnx's native versions. Route each to
# the fnx top-level function via closure wrappers that reference ``_fnx.<fn>`` at
# CALL time (robust against the package-init order in which fnx defines them).
_FNX_NATIVE_DAG_NAMES = (
    "descendants",
    "ancestors",
    "topological_sort",
    "lexicographical_topological_sort",
    "all_topological_sorts",
    "topological_generations",
    "is_directed_acyclic_graph",
    "is_aperiodic",
    "antichains",
    "dag_longest_path",
    "dag_longest_path_length",
)


def _make_fnx_dag_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.dag.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_DAG_NAMES:
    globals()[_name] = _make_fnx_dag_router(_name)

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
    return _from_nx_graph(nx_result)


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
    return _from_nx_graph(nx_result)
