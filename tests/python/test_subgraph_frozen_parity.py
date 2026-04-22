"""Parity coverage for subgraph returning frozen views.

Bead franken_networkx-5e8p: subgraph must return a frozen view across
all four graph-family classes matching upstream NetworkX.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_subgraph_is_frozen(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3)])

    fs = fg.subgraph([0, 1, 2])
    ns = ng.subgraph([0, 1, 2])

    assert fnx.is_frozen(fs)
    assert nx.is_frozen(ns)
    with pytest.raises(fnx.NetworkXError):
        fs.add_node(99)
    # Node set matches upstream.
    assert set(fs.nodes()) == set(ns.nodes())
