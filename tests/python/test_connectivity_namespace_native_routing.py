"""``franken_networkx.connectivity`` routes to fnx-native connectivity fns.

``from networkx.algorithms.connectivity import *`` left node/edge
connectivity, cuts, disjoint paths, k-edge components and stoer_wagner
bound to networkx's implementations instead of fnx's native versions
(``node_connectivity`` even carries the br-r37-c1-cqlms / ebd8d local
connectivity fixes). These now route to the fnx top-level functions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import connectivity as fnx_conn

_NAMES = [
    "all_node_cuts", "all_pairs_node_connectivity", "average_node_connectivity",
    "edge_connectivity", "edge_disjoint_paths", "is_k_edge_connected",
    "k_components", "k_edge_augmentation", "k_edge_components", "k_edge_subgraphs",
    "minimum_edge_cut", "minimum_node_cut", "node_connectivity",
    "node_disjoint_paths", "stoer_wagner",
]


@pytest.mark.parametrize("name", _NAMES)
def test_connectivity_fn_is_not_networkx_version(name):
    fn = getattr(fnx_conn, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_connectivity_values_match_networkx():
    g = fnx.complete_graph(5)
    ng = nx.complete_graph(5)
    assert fnx_conn.node_connectivity(g) == nx.node_connectivity(ng)
    assert fnx_conn.edge_connectivity(g) == nx.edge_connectivity(ng)
    # The cqlms/ebd8d local-connectivity fixes flow through the namespace too:
    # adjacent pair in K5 has local node connectivity 4 (not 0).
    assert fnx_conn.node_connectivity(g, 0, 4) == 4
    assert fnx_conn.node_connectivity(g, 0, 4) == nx.node_connectivity(ng, 0, 4)
    assert fnx_conn.stoer_wagner(g)[0] == nx.stoer_wagner(ng)[0]
    assert len(list(fnx_conn.edge_disjoint_paths(g, 0, 4))) == (
        len(list(nx.edge_disjoint_paths(ng, 0, 4)))
    )
