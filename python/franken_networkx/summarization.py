"""FrankenNetworkX summarization submodule.

Re-exports the upstream ``networkx.algorithms.summarization`` surface so
existing ``franken_networkx.summarization.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``dedensify`` — returns (fnx.Graph, set)
- ``snap_aggregation`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.summarization import *  # noqa: F401,F403
import networkx.algorithms.summarization as _nx_summarization

import franken_networkx as _fnx
from franken_networkx.readwrite import _from_nx_graph

__all__ = list(
    getattr(
        _nx_summarization,
        "__all__",
        ("dedensify", "snap_aggregation"),
    )
)


def dedensify(G, threshold, prefix=None, copy=True, *, backend=None, **backend_kwargs):
    """Compresses neighborhoods around high-degree nodes.

    Wraps ``networkx.algorithms.summarization.dedensify`` and converts
    copy-producing results to fnx graph types for drop-in compatibility.
    ``copy=False`` preserves NetworkX's in-place return identity.

    Returns
    -------
    graph : fnx.Graph
        The dedensified graph.
    set
        Set of nodes that were compressed.
    """
    _fnx._validate_backend_dispatch_keywords("dedensify", backend, backend_kwargs)
    if isinstance(
        G, (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
    ):
        return _fnx.dedensify(G, threshold, prefix=prefix, copy=copy)

    nx_graph, contractions = _nx_summarization.dedensify(
        G, threshold, prefix=prefix, copy=copy
    )
    if not copy:
        return nx_graph, contractions
    return _from_nx_graph(nx_graph), contractions


def snap_aggregation(
    G,
    node_attributes,
    edge_attributes=(),
    prefix="Supernode-",
    supernode_attribute="group",
    superedge_attribute="types",
    *,
    backend=None,
    **backend_kwargs,
):
    """Creates a summary graph based on attributes and connectivity.

    Wraps ``networkx.algorithms.summarization.snap_aggregation`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("snap_aggregation", backend, backend_kwargs)
    nx_result = _nx_summarization.snap_aggregation(
        G,
        node_attributes,
        edge_attributes=edge_attributes,
        prefix=prefix,
        supernode_attribute=supernode_attribute,
        superedge_attribute=superedge_attribute,
    )
    return _from_nx_graph(nx_result)
