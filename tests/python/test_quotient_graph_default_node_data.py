"""br-r37-c1-ja61l: regression tests for quotient_graph default node-data."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_quotient_graph_default_node_data_matches_nx():
    """When node_data is not provided, both fnx and nx attach
    graph/nnodes/nedges/density to each block node."""
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    rf = fnx.quotient_graph(fg, [{0, 1}, {2, 3}])
    rn = nx.quotient_graph(ng, [{0, 1}, {2, 3}])
    # Both should have the same block-node keys
    assert set(rf.nodes()) == set(rn.nodes())
    # And matching default attrs (graph/nnodes/nedges/density)
    for node in rf.nodes():
        rf_attrs = rf.nodes[node]
        rn_attrs = rn.nodes[node]
        # graph attribute is a subgraph; compare node sets
        if "graph" in rf_attrs and "graph" in rn_attrs:
            assert set(rf_attrs["graph"].nodes()) == set(rn_attrs["graph"].nodes())
        assert rf_attrs.get("nnodes") == rn_attrs.get("nnodes")
        assert rf_attrs.get("nedges") == rn_attrs.get("nedges")
        assert rf_attrs.get("density") == pytest.approx(rn_attrs.get("density"))


def test_quotient_graph_custom_node_data_unchanged():
    """When node_data IS provided, fnx uses it (default attrs NOT applied)."""
    g = fnx.path_graph(4)
    rf = fnx.quotient_graph(g, [{0, 1}, {2, 3}], node_data=lambda b: {"size": len(b)})
    for node in rf.nodes():
        attrs = rf.nodes[node]
        assert attrs == {"size": len(node)}  # custom data only, no defaults


def test_quotient_graph_default_attrs_present():
    g = fnx.path_graph(3)
    rf = fnx.quotient_graph(g, [{0, 1, 2}])
    block = next(iter(rf.nodes()))
    attrs = rf.nodes[block]
    assert set(attrs.keys()) >= {"graph", "nnodes", "nedges", "density"}
    assert attrs["nnodes"] == 3
    assert attrs["nedges"] == 2
