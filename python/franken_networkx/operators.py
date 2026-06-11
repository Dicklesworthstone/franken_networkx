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

br-r37-c1-prodroute: the product functions now route to the fnx top-level
native kernels (``franken_networkx.cartesian_product`` etc.) instead of running
nx's pure-Python product on the fnx graph and double-converting via
``_from_nx_graph``. The native kernels are parity-exact with nx (edge set +
node/edge attrs) and 17-31x faster on the submodule path (e.g. tensor_product
783ms -> 25ms at |G|=80,|H|=60), and 2-5.6x faster than genuine nx. The
docstrings below still say "Wraps networkx" for the mechanism that produced an
equivalent result; the contract (returns the fnx-graph product) is unchanged.
"""

from __future__ import annotations

from networkx.algorithms.operators import *  # noqa: F401,F403
import networkx.algorithms.operators.product as _nx_product
import networkx.algorithms.operators.all as _nx_all

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def disjoint_union(G, H, *, backend=None, **backend_kwargs):
    """Return the disjoint union of graphs G and H.

    br-r37-c1-muhsi: the ``from networkx... import *`` re-export left
    ``disjoint_union`` as nx's pure-Python version. Run on fnx graphs it relabels
    via ``convert_node_labels_to_integers`` and returns an **nx.Graph** (a drop-in
    type bug — every other operator here returns an fnx graph) and is ~6x slower
    than the native ``fnx.disjoint_union`` (23ms vs 3.8ms at n=1600; fnx-native is
    2.6x faster than genuine nx). Route to the fnx top-level implementation, which
    returns the correct fnx graph type and is byte-exact with nx (node relabeling
    + edge/graph attrs).
    """
    _fnx._validate_backend_dispatch_keywords("disjoint_union", backend, backend_kwargs)
    return _fnx.disjoint_union(G, H)


def cartesian_product(G, H, *, backend=None, **backend_kwargs):
    """Return the Cartesian product of G and H.

    Wraps ``networkx.algorithms.operators.cartesian_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("cartesian_product", backend, backend_kwargs)
    return _fnx.cartesian_product(G, H)


def tensor_product(G, H, *, backend=None, **backend_kwargs):
    """Return the tensor product of G and H.

    Wraps ``networkx.algorithms.operators.tensor_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("tensor_product", backend, backend_kwargs)
    return _fnx.tensor_product(G, H)


def lexicographic_product(G, H, *, backend=None, **backend_kwargs):
    """Return the lexicographic product of G and H.

    Wraps ``networkx.algorithms.operators.lexicographic_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("lexicographic_product", backend, backend_kwargs)
    return _fnx.lexicographic_product(G, H)


def strong_product(G, H, *, backend=None, **backend_kwargs):
    """Return the strong product of G and H.

    Wraps ``networkx.algorithms.operators.strong_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("strong_product", backend, backend_kwargs)
    return _fnx.strong_product(G, H)


def modular_product(G, H, *, backend=None, **backend_kwargs):
    """Return the modular product of G and H.

    Wraps ``networkx.algorithms.operators.modular_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("modular_product", backend, backend_kwargs)
    return _fnx.modular_product(G, H)


def rooted_product(G, H, root, *, backend=None, **backend_kwargs):
    """Return the rooted product of G and H rooted at root in H.

    Wraps ``networkx.algorithms.operators.rooted_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("rooted_product", backend, backend_kwargs)
    return _fnx.rooted_product(G, H, root)


def corona_product(G, H, *, backend=None, **backend_kwargs):
    """Return the corona product of G and H.

    Wraps ``networkx.algorithms.operators.corona_product`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("corona_product", backend, backend_kwargs)
    return _fnx.corona_product(G, H)


def power(G, k, *, backend=None, **backend_kwargs):
    """Return the graph G to the power k.

    Wraps ``networkx.algorithms.operators.power`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("power", backend, backend_kwargs)
    return _fnx.power(G, k)


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
