"""Numerical parity on larger graphs (precision at scale).

Small graphs can hide numerical-precision and scaling divergences. This runs
the precision-sensitive metrics on larger random graphs (n=40-60) and checks
fnx stays within tight tolerance of networkx — catching accumulation/precision
bugs that n<15 tests miss.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_large(seed):
    r = random.Random(seed)
    n = r.randint(40, 60)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.18]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


def _maxdiff(fd, nd):
    return max(abs(fd[k] - nd[k]) for k in fd)


@pytest.mark.parametrize("seed", range(10))
def test_large_graph_centrality_precision(seed):
    fg, ng, n = _identical_large(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _maxdiff(fnx.betweenness_centrality(fg), nx.betweenness_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.closeness_centrality(fg), nx.closeness_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.harmonic_centrality(fg), nx.harmonic_centrality(ng)) < 1e-6
    assert _maxdiff(fnx.pagerank(fg), nx.pagerank(ng)) < 1e-6
    assert _maxdiff(
        fnx.eigenvector_centrality_numpy(fg), nx.eigenvector_centrality_numpy(ng)
    ) < 1e-5
    assert _maxdiff(
        fnx.katz_centrality_numpy(fg), nx.katz_centrality_numpy(ng)
    ) < 1e-5


@pytest.mark.parametrize("seed", range(10))
def test_large_graph_scalar_precision(seed):
    fg, ng, n = _identical_large(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert abs(fnx.transitivity(fg) - nx.transitivity(ng)) < 1e-9
    assert abs(fnx.average_clustering(fg) - nx.average_clustering(ng)) < 1e-9
    assert abs(fnx.global_efficiency(fg) - nx.global_efficiency(ng)) < 1e-9
    assert fnx.diameter(fg) == nx.diameter(ng)
    assert _maxdiff(fnx.clustering(fg), nx.clustering(ng)) < 1e-9
    assert abs(fnx.estrada_index(fg) - nx.estrada_index(ng)) < 1e-3
