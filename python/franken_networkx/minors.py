"""FrankenNetworkX minors submodule.

Re-exports the upstream ``networkx.algorithms.minors`` surface so
existing ``franken_networkx.minors.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``quotient_graph`` — returns fnx.Graph/fnx.DiGraph
- ``contracted_nodes`` — returns fnx graph
- ``contracted_edge`` — returns fnx graph
- ``identified_nodes`` — returns fnx graph
"""

from __future__ import annotations

from networkx.algorithms.minors import *  # noqa: F401,F403
import networkx.algorithms.minors as _nx_minors

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_minors,
        "__all__",
        (
            "contracted_edge",
            "contracted_nodes",
            "equivalence_classes",
            "identified_nodes",
            "quotient_graph",
        ),
    )
)

# br-r37-c1-2qsqf: ``from networkx.algorithms.minors import *`` above left
# ``equivalence_classes`` bound to networkx's implementation, so
# ``fnx.minors.equivalence_classes`` silently resolved to nx's instead of fnx's
# native version. Route it to the fnx top-level function via a call-time closure
# wrapper (import-order robust).
def _make_fnx_minors_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.minors.{_fn_name}`` for semantics."
    )
    return _routed


equivalence_classes = _make_fnx_minors_router("equivalence_classes")


def _convert_contraction_result(nx_result, *, copy):
    if not copy:
        return nx_result
    return _from_nx_graph(nx_result)


def quotient_graph(
    G,
    partition,
    edge_relation=None,
    node_data=None,
    edge_data=None,
    weight="weight",
    relabel=False,
    create_using=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Return the quotient graph of G under the specified equivalence relation.

    Wraps ``networkx.algorithms.minors.quotient_graph`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("quotient_graph", backend, backend_kwargs)
    nx_result = _nx_minors.quotient_graph(
        G,
        partition,
        edge_relation=edge_relation,
        node_data=node_data,
        edge_data=edge_data,
        weight=weight,
        relabel=relabel,
        create_using=create_using,
    )
    return _from_nx_graph(nx_result, create_using=create_using)


def contracted_nodes(G, u, v, self_loops=True, copy=True, *, store_contraction_as="contraction", backend=None, **backend_kwargs):
    """Return the graph with nodes u and v contracted.

    Wraps ``networkx.algorithms.minors.contracted_nodes``. ``copy=False``
    preserves NetworkX's in-place return identity; copy-producing calls convert
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("contracted_nodes", backend, backend_kwargs)
    nx_result = _nx_minors.contracted_nodes(G, u, v, self_loops=self_loops, copy=copy, store_contraction_as=store_contraction_as)
    return _convert_contraction_result(nx_result, copy=copy)


def contracted_edge(G, edge, self_loops=True, copy=True, *, store_contraction_as="contraction", backend=None, **backend_kwargs):
    """Return the graph with the specified edge contracted.

    Wraps ``networkx.algorithms.minors.contracted_edge``. ``copy=False``
    preserves NetworkX's in-place return identity; copy-producing calls convert
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("contracted_edge", backend, backend_kwargs)
    nx_result = _nx_minors.contracted_edge(G, edge, self_loops=self_loops, copy=copy, store_contraction_as=store_contraction_as)
    return _convert_contraction_result(nx_result, copy=copy)


def identified_nodes(G, u, v, self_loops=True, copy=True, *, store_contraction_as="contraction", backend=None, **backend_kwargs):
    """Return the graph with nodes u and v identified (contracted).

    Wraps ``networkx.algorithms.minors.identified_nodes``. ``copy=False``
    preserves NetworkX's in-place return identity; copy-producing calls convert
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("identified_nodes", backend, backend_kwargs)
    nx_result = _nx_minors.identified_nodes(G, u, v, self_loops=self_loops, copy=copy, store_contraction_as=store_contraction_as)
    return _convert_contraction_result(nx_result, copy=copy)
