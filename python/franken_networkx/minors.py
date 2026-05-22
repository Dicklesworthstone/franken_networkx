"""FrankenNetworkX minors submodule.

Re-exports the upstream ``networkx.algorithms.minors`` surface so
existing ``franken_networkx.minors.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``quotient_graph`` — returns fnx.Graph/fnx.DiGraph
"""

from __future__ import annotations

from networkx.algorithms.minors import *  # noqa: F401,F403
import networkx.algorithms.minors as _nx_minors

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph


def quotient_graph(
    G,
    partition,
    edge_relation=None,
    node_data=None,
    edge_data=None,
    relabel=True,
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
        relabel=relabel,
        create_using=create_using,
    )
    return _from_nx_graph(nx_result, create_using=create_using)
