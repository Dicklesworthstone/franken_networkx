"""FrankenNetworkX operators submodule.

Re-exports the upstream ``networkx.algorithms.operators`` surface so
existing ``franken_networkx.operators.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides (product functions):
- ``cartesian_product`` — returns fnx graph
- ``tensor_product`` — returns fnx graph
- ``lexicographic_product`` — returns fnx graph
- ``strong_product`` — returns fnx graph
- ``modular_product`` — returns fnx graph
- ``rooted_product`` — returns fnx graph
- ``corona_product`` — returns fnx graph
- ``power`` — returns fnx graph
- ``union_all`` — returns fnx graph
- ``intersection_all`` — returns fnx graph
- ``compose_all`` — returns fnx graph
- ``disjoint_union_all`` — returns fnx graph
"""

from __future__ import annotations

from networkx.algorithms.operators import *  # noqa: F401,F403
import networkx.algorithms.operators.product as _nx_product
import networkx.algorithms.operators.all as _nx_all

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def cartesian_product(G, H, *, backend=None, **backend_kwargs):
    """Return the Cartesian product of G and H.

    Wraps ``networkx.algorithms.operators.cartesian_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("cartesian_product", backend, backend_kwargs)
    nx_result = _nx_product.cartesian_product(G, H)
    return _from_nx_graph(nx_result)


def tensor_product(G, H, *, backend=None, **backend_kwargs):
    """Return the tensor product of G and H.

    Wraps ``networkx.algorithms.operators.tensor_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("tensor_product", backend, backend_kwargs)
    nx_result = _nx_product.tensor_product(G, H)
    return _from_nx_graph(nx_result)


def lexicographic_product(G, H, *, backend=None, **backend_kwargs):
    """Return the lexicographic product of G and H.

    Wraps ``networkx.algorithms.operators.lexicographic_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("lexicographic_product", backend, backend_kwargs)
    nx_result = _nx_product.lexicographic_product(G, H)
    return _from_nx_graph(nx_result)


def strong_product(G, H, *, backend=None, **backend_kwargs):
    """Return the strong product of G and H.

    Wraps ``networkx.algorithms.operators.strong_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("strong_product", backend, backend_kwargs)
    nx_result = _nx_product.strong_product(G, H)
    return _from_nx_graph(nx_result)


def modular_product(G, H, *, backend=None, **backend_kwargs):
    """Return the modular product of G and H.

    Wraps ``networkx.algorithms.operators.modular_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("modular_product", backend, backend_kwargs)
    nx_result = _nx_product.modular_product(G, H)
    return _from_nx_graph(nx_result)


def rooted_product(G, H, root, *, backend=None, **backend_kwargs):
    """Return the rooted product of G and H rooted at root in H.

    Wraps ``networkx.algorithms.operators.rooted_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("rooted_product", backend, backend_kwargs)
    nx_result = _nx_product.rooted_product(G, H, root)
    return _from_nx_graph(nx_result)


def corona_product(G, H, *, backend=None, **backend_kwargs):
    """Return the corona product of G and H.

    Wraps ``networkx.algorithms.operators.corona_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("corona_product", backend, backend_kwargs)
    nx_result = _nx_product.corona_product(G, H)
    return _from_nx_graph(nx_result)


def power(G, k, *, backend=None, **backend_kwargs):
    """Return the graph G to the power k.

    Wraps ``networkx.algorithms.operators.power`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("power", backend, backend_kwargs)
    nx_result = _nx_product.power(G, k)
    return _from_nx_graph(nx_result)


def union_all(graphs, rename=(), *, backend=None, **backend_kwargs):
    """Return the union of all graphs.

    Wraps ``networkx.algorithms.operators.union_all`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("union_all", backend, backend_kwargs)
    nx_result = _nx_all.union_all(graphs, rename=rename)
    return _from_nx_graph(nx_result)


def intersection_all(graphs, *, backend=None, **backend_kwargs):
    """Return the intersection of all graphs.

    Wraps ``networkx.algorithms.operators.intersection_all`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("intersection_all", backend, backend_kwargs)
    nx_result = _nx_all.intersection_all(graphs)
    return _from_nx_graph(nx_result)


def compose_all(graphs, *, backend=None, **backend_kwargs):
    """Return the composition of all graphs.

    Wraps ``networkx.algorithms.operators.compose_all`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("compose_all", backend, backend_kwargs)
    nx_result = _nx_all.compose_all(graphs)
    return _from_nx_graph(nx_result)


def disjoint_union_all(graphs, *, backend=None, **backend_kwargs):
    """Return the disjoint union of all graphs.

    Wraps ``networkx.algorithms.operators.disjoint_union_all`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("disjoint_union_all", backend, backend_kwargs)
    nx_result = _nx_all.disjoint_union_all(graphs)
    return _from_nx_graph(nx_result)
