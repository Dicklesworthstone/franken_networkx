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
