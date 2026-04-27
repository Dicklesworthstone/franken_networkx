"""Parity for resistance_distance / betweenness_centrality_subset
unhashable inputs and astar_path_length combined-message wording.

Bead br-r37-c1-tm1tq (eighth follow-up to the unhashable-node series).

Three drifts found in the post-omjmu probe:

  resistance_distance(nodeA=unhashable)        fnx: TypeError    nx: NetworkXError
  resistance_distance(nodeB=unhashable)        fnx: TypeError    nx: NetworkXError
  betweenness_centrality_subset(sources=...)   fnx: <silent ok>  nx: TypeError
  astar_path_length missing-node message       fnx: 'Target ...'  nx: 'Either source ... or target ...'

resistance_distance was OVER-strict — fnx hashed the node by
indexing into a dict, raising TypeError; nx pre-checks ``not in G``
(silent-False on unhashable) and raises NetworkXError.
betweenness_centrality_subset was UNDER-strict — fnx silently
ignored unhashable members in sources/targets.  astar_path_length
was a message-shape drift (combined vs. per-side wording).
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# resistance_distance — NetworkXError on unhashable node, not TypeError
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_resistance_distance_unhashable_nodeA_raises_networkxerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"Node A is not in graph G"):
        fnx.resistance_distance(G, val, 1)
    with pytest.raises(nx.NetworkXError, match=r"Node A is not in graph G"):
        nx.resistance_distance(GX, val, 1)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_resistance_distance_unhashable_nodeB_raises_networkxerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"Node B is not in graph G"):
        fnx.resistance_distance(G, 1, val)
    with pytest.raises(nx.NetworkXError, match=r"Node B is not in graph G"):
        nx.resistance_distance(GX, 1, val)


@needs_nx
def test_resistance_distance_missing_hashable_nodeA_networkxerror():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"Node A is not in graph G"):
        fnx.resistance_distance(G, 99, 1)
    with pytest.raises(nx.NetworkXError, match=r"Node A is not in graph G"):
        nx.resistance_distance(GX, 99, 1)


# ---------------------------------------------------------------------------
# betweenness_centrality_subset — TypeError on unhashable in sources/targets
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_betweenness_centrality_subset_unhashable_sources_typeerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.betweenness_centrality_subset(G, [val], [1])
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.betweenness_centrality_subset(GX, [val], [1])


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_betweenness_centrality_subset_unhashable_targets_typeerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.betweenness_centrality_subset(G, [1], [val])
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.betweenness_centrality_subset(GX, [1], [val])


# ---------------------------------------------------------------------------
# astar_path_length — combined-message wording on missing nodes
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_astar_path_length_unhashable_target_combined_message(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        fnx.astar_path_length(G, 1, val)
    with pytest.raises(nx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        nx.astar_path_length(GX, 1, val)


@needs_nx
def test_astar_path_length_missing_hashable_target_combined_message():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        fnx.astar_path_length(G, 1, 99)
    with pytest.raises(nx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        nx.astar_path_length(GX, 1, 99)


@needs_nx
def test_astar_path_length_missing_hashable_source_combined_message():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        fnx.astar_path_length(G, 99, 1)
    with pytest.raises(nx.NodeNotFound, match=r"Either source .* or target .* is not in G"):
        nx.astar_path_length(GX, 99, 1)


# ---------------------------------------------------------------------------
# Regressions — hashable inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_resistance_distance_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (1, 3)])
    GX = nx.Graph([(1, 2), (2, 3), (1, 3)])
    f = fnx.resistance_distance(G, 1, 3)
    n = nx.resistance_distance(GX, 1, 3)
    assert abs(f - n) < 1e-9


@needs_nx
def test_betweenness_centrality_subset_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    f = fnx.betweenness_centrality_subset(G, [1], [4])
    n = nx.betweenness_centrality_subset(GX, [1], [4])
    assert {k: round(v, 9) for k, v in f.items()} == {k: round(v, 9) for k, v in n.items()}


@needs_nx
def test_astar_path_length_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert fnx.astar_path_length(G, 1, 4) == nx.astar_path_length(GX, 1, 4)
