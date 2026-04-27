"""Parity for second_order_centrality on empty / disconnected graphs.

Bead br-r37-c1-u7ry8. Pre-fix:
- ``fnx.second_order_centrality(empty)`` returned ``{}``;
  nx raises ``NetworkXException('Empty graph.')``.
- ``fnx.second_order_centrality(disconnected)`` returned a value dict
  (zeros or NaNs depending on shape); nx raises
  ``NetworkXException('Non connected graph.')``.

The single-isolated-node case is not affected — both fnx and nx
return ``{n: 0.0}``. Connected single- and multi-node graphs continue
to produce numerically-equivalent values via the Rust fast path
(unweighted) or the Python solver (weighted).
"""

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
def test_empty_graph_raises_networkxexception_empty_graph():
    with pytest.raises(fnx.NetworkXException, match=r"^Empty graph\.$"):
        fnx.second_order_centrality(fnx.Graph())
    with pytest.raises(nx.NetworkXException, match=r"^Empty graph\.$"):
        nx.second_order_centrality(nx.Graph())


@needs_nx
def test_disconnected_no_edges_raises_non_connected_graph():
    G = fnx.Graph()
    G.add_nodes_from([1, 2, 3])
    GX = nx.Graph()
    GX.add_nodes_from([1, 2, 3])
    with pytest.raises(fnx.NetworkXException, match=r"^Non connected graph\.$"):
        fnx.second_order_centrality(G)
    with pytest.raises(nx.NetworkXException, match=r"^Non connected graph\.$"):
        nx.second_order_centrality(GX)


@needs_nx
def test_disconnected_two_components_raises_non_connected_graph():
    G = fnx.Graph([(1, 2), (3, 4)])
    GX = nx.Graph([(1, 2), (3, 4)])
    with pytest.raises(fnx.NetworkXException, match=r"^Non connected graph\.$"):
        fnx.second_order_centrality(G)
    with pytest.raises(nx.NetworkXException, match=r"^Non connected graph\.$"):
        nx.second_order_centrality(GX)


@needs_nx
def test_single_isolated_node_returns_zero():
    """Single-node graphs are NOT considered disconnected by either
    library and both return ``{node: 0.0}``."""
    G = fnx.Graph()
    G.add_node(0)
    GX = nx.Graph()
    GX.add_node(0)
    assert fnx.second_order_centrality(G) == nx.second_order_centrality(GX) == {0: 0.0}


@needs_nx
def test_connected_path_graph_unchanged_after_fix():
    """Regression guard — the connected-graph happy path must continue
    to yield numerically-equivalent values to nx (Rust fast path)."""
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert set(f.keys()) == set(n.keys())
    for k in f:
        assert abs(f[k] - n[k]) < 1e-6, (k, f[k], n[k])


@needs_nx
def test_connected_weighted_graph_unchanged_after_fix():
    """Regression guard for the Python (weighted) branch."""
    edges = [(1, 2, {"weight": 1.5}), (2, 3, {"weight": 2.0})]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    for k in f:
        assert abs(f[k] - n[k]) < 1e-6


@needs_nx
def test_directed_raises_not_implemented():
    """Pre-existing parity (unchanged). Both fnx and nx raise
    NetworkXNotImplemented for directed inputs."""
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.second_order_centrality(fnx.DiGraph([(1, 2)]))
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.second_order_centrality(nx.DiGraph([(1, 2)]))


@needs_nx
def test_empty_caught_by_nx_class():
    """Drop-in: a fnx-raised NetworkXException must be catchable via
    ``except nx.NetworkXException`` (fnx exception hierarchy is
    registered as a subclass of nx)."""
    try:
        fnx.second_order_centrality(fnx.Graph())
    except nx.NetworkXException:
        return
    pytest.fail("fnx.second_order_centrality should raise on empty graph")
