"""Closed-form ground-truth centrality values on structured graphs.

Known centrality values from graph theory, asserted with NO networkx
oracle — they catch centrality bugs even if fnx and nx shared one, and pin
the symmetry/normalization behaviour exactly.

br-r37-c1-9e4mx
"""

from __future__ import annotations

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [4, 5, 6])
def test_star_graph_centralities(n):
    # star_graph(n): node 0 is the centre, nodes 1..n are leaves.
    g = fnx.star_graph(n)
    bc = fnx.betweenness_centrality(g, normalized=True)
    assert bc[0] == pytest.approx(1.0)            # every path crosses the centre
    assert all(bc[leaf] == pytest.approx(0.0) for leaf in range(1, n + 1))
    cc = fnx.closeness_centrality(g)
    assert cc[0] == pytest.approx(1.0)            # centre adjacent to all
    assert fnx.degree_centrality(g)[0] == pytest.approx(1.0)


@pytest.mark.parametrize("n", [4, 5, 6])
def test_complete_graph_centralities(n):
    g = fnx.complete_graph(n)
    # Every pair is adjacent -> no node lies between any other pair.
    assert all(abs(v) < 1e-9 for v in fnx.betweenness_centrality(g).values())
    # All nodes are mutually adjacent -> closeness 1.0 everywhere.
    assert all(v == pytest.approx(1.0) for v in fnx.closeness_centrality(g).values())
    # Vertex-transitive -> uniform eigenvector centrality.
    ev = fnx.eigenvector_centrality_numpy(g)
    assert max(ev.values()) - min(ev.values()) < 1e-6
    # Uniform pagerank.
    pr = fnx.pagerank(g)
    assert max(pr.values()) - min(pr.values()) < 1e-6


@pytest.mark.parametrize("n", [5, 6, 7])
def test_cycle_graph_is_centrality_symmetric(n):
    g = fnx.cycle_graph(n)
    # Vertex-transitive -> every node has identical betweenness / closeness.
    for centrality in (fnx.betweenness_centrality(g), fnx.closeness_centrality(g)):
        vals = list(centrality.values())
        assert max(vals) - min(vals) < 1e-9


def test_path_graph_centrality_ordering():
    g = fnx.path_graph(5)
    cc = fnx.closeness_centrality(g)
    # The middle node is closer to everything than the endpoints.
    assert cc[2] > cc[1] > cc[0]
    bc = fnx.betweenness_centrality(g, normalized=False)
    # Middle node lies on the most shortest paths.
    assert bc[2] > bc[1] > bc[0]
    assert bc[0] == pytest.approx(0.0)
