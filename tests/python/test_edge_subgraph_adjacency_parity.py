"""Parity coverage for Graph/DiGraph edge_subgraph adjacency() mapping.

Bead franken_networkx-xkpr: simple edge_subgraph views expose
.adjacency() as an iterator of (node, filtered-atlas-mapping) pairs
matching upstream (not bare node lists).
"""

from collections.abc import Mapping

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_edge_subgraph_adjacency_yields_mapping_pairs(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2, {"weight": 7}), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2, {"weight": 7}), (2, 3)])

    fh = fg.edge_subgraph([(1, 2)])
    nh = ng.edge_subgraph([(1, 2)])

    fnx_items = list(fh.adjacency())
    nx_items = list(nh.adjacency())

    # Each payload is a Mapping (AtlasView-like), not a bare list.
    for _, payload in fnx_items:
        assert isinstance(payload, Mapping)

    # Deep content matches upstream — identical node set, identical
    # neighbors with identical edge attrs.
    f_deep = [
        (n, {k: dict(v) for k, v in dict(nbrs).items()}) for n, nbrs in fnx_items
    ]
    n_deep = [
        (n, {k: dict(v) for k, v in dict(nbrs).items()}) for n, nbrs in nx_items
    ]
    assert f_deep == n_deep
