"""degree_histogram consistency with the degree sequence.

The degree histogram is the frequency table of the degree sequence, so it
cross-checks degree_histogram against the degree view:
  - histogram[k] == number of nodes whose degree is exactly k;
  - sum(histogram) == number of nodes;
  - sum(k * histogram[k]) == 2|E|  (handshaking lemma, via the histogram);
  - K_n: every node has degree n-1, so histogram[n-1] == n.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(40))
def test_histogram_matches_degree_sequence(seed):
    r = random.Random(seed)
    n = r.randint(4, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    hist = fnx.degree_histogram(g)
    degs = [d for _, d in g.degree()]

    # Each bucket counts nodes of that exact degree.
    for k in range(len(hist)):
        assert hist[k] == sum(1 for d in degs if d == k)
    # The histogram covers every node.
    assert sum(hist) == n
    # Handshaking via the histogram: sum of k * count == 2|E|.
    assert sum(k * hist[k] for k in range(len(hist))) == 2 * g.number_of_edges()


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_histogram(n):
    hist = fnx.degree_histogram(fnx.complete_graph(n))
    # Every node has degree n-1.
    assert hist[n - 1] == n
    assert sum(hist) == n
    assert all(hist[k] == 0 for k in range(n - 1))


def test_path_and_star_histograms():
    # Path P_5: two endpoints (degree 1), three internal (degree 2).
    hist = fnx.degree_histogram(fnx.path_graph(5))
    assert hist[1] == 2
    assert hist[2] == 3
    # Star with 4 leaves: 4 leaves (degree 1), 1 center (degree 4).
    hist = fnx.degree_histogram(fnx.star_graph(4))
    assert hist[1] == 4
    assert hist[4] == 1


@pytest.mark.parametrize("seed", range(40))
def test_histogram_length_is_max_degree_plus_one(seed):
    """Every existing assertion is invariant under trailing zeros.

    The per-bucket check iterates `range(len(hist))`, so padding the histogram
    with extra empty buckets keeps it true; the sum and the handshaking total
    are unchanged as well. Only the length distinguishes them.
    """
    r = random.Random(seed)
    n = r.randint(4, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    hist = fnx.degree_histogram(g)
    assert len(hist) == max(d for _, d in g.degree()) + 1
    # The last bucket is therefore occupied: no trailing zero.
    assert hist[-1] > 0


def test_histogram_on_other_graph_types_and_degenerate_sizes():
    """The sweep builds simple undirected graphs with n >= 4 only."""
    # Directed: the histogram bins the TOTAL degree, in plus out.
    d = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])
    nd = nx.DiGraph([(0, 1), (1, 2), (0, 2)])
    assert fnx.degree_histogram(d) == nx.degree_histogram(nd) == [0, 0, 3]

    # Multigraph: parallel edges count once each toward the degree.
    m = fnx.MultiGraph(); m.add_edge(0, 1); m.add_edge(0, 1)
    nm = nx.MultiGraph(); nm.add_edge(0, 1); nm.add_edge(0, 1)
    assert fnx.degree_histogram(m) == nx.degree_histogram(nm) == [0, 0, 2]

    # The empty graph has no buckets at all; one isolated node occupies bucket 0.
    assert fnx.degree_histogram(fnx.empty_graph(0)) == nx.degree_histogram(nx.empty_graph(0)) == []
    assert fnx.degree_histogram(fnx.empty_graph(1)) == nx.degree_histogram(nx.empty_graph(1)) == [1]


def test_isolated_nodes_occupy_bucket_zero():
    """Guards bucket 0: it is exercised on only 6 of the 40 random draws."""
    g = fnx.Graph(); g.add_edges_from([(0, 1)]); g.add_nodes_from([8, 9])
    hist = fnx.degree_histogram(g)
    assert hist[0] == 2          # the two isolated nodes
    assert hist[1] == 2          # the two endpoints
    assert sum(hist) == g.number_of_nodes()
