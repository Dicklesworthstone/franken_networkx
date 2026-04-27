"""Parity for eigenvector_centrality{,_numpy} on the empty graph.

Bead br-r37-c1-zvfcu. ``fnx.eigenvector_centrality(empty_graph)`` and
``fnx.eigenvector_centrality_numpy(empty_graph)`` silently returned
``{}``; nx raises ``NetworkXPointlessConcept('cannot compute centrality
for the null graph')``. Drop-in code that does
``pytest.raises(NetworkXPointlessConcept, ...)`` failed under fnx.

All other centralities (degree, in_degree, out_degree, closeness,
betweenness, harmonic, load, subgraph, communicability_betweenness,
information, current_flow_*, pagerank, hits, katz, katz_numpy) already
matched nx's empty-graph behavior — only the two eigenvector variants
were the remaining outliers.
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
def test_eigenvector_centrality_empty_raises_pointlessconcept():
    with pytest.raises(
        fnx.NetworkXPointlessConcept,
        match="cannot compute centrality for the null graph",
    ):
        fnx.eigenvector_centrality(fnx.Graph())
    with pytest.raises(
        nx.NetworkXPointlessConcept,
        match="cannot compute centrality for the null graph",
    ):
        nx.eigenvector_centrality(nx.Graph())


@needs_nx
def test_eigenvector_centrality_numpy_empty_raises_pointlessconcept():
    with pytest.raises(
        fnx.NetworkXPointlessConcept,
        match="cannot compute centrality for the null graph",
    ):
        fnx.eigenvector_centrality_numpy(fnx.Graph())
    with pytest.raises(
        nx.NetworkXPointlessConcept,
        match="cannot compute centrality for the null graph",
    ):
        nx.eigenvector_centrality_numpy(nx.Graph())


@needs_nx
def test_eigenvector_centrality_empty_caught_by_nx_class():
    """Drop-in: a fnx-raised NetworkXPointlessConcept must be catchable
    via ``except nx.NetworkXPointlessConcept`` since fnx's exception
    hierarchy is registered as a subclass of nx's."""
    try:
        fnx.eigenvector_centrality(fnx.Graph())
    except nx.NetworkXPointlessConcept:
        return
    pytest.fail("fnx.eigenvector_centrality should raise on empty graph")


@needs_nx
def test_eigenvector_centrality_non_empty_still_works():
    """Regression guard — the fix only adds an empty-graph guard;
    the non-empty path must still produce correct values."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1)])
    Gn = nx.Graph([(1, 2), (2, 3), (3, 1)])
    f = fnx.eigenvector_centrality(G)
    n = nx.eigenvector_centrality(Gn)
    assert set(f.keys()) == set(n.keys())
    for k in f:
        assert abs(f[k] - n[k]) < 1e-6, (k, f[k], n[k])


@needs_nx
def test_eigenvector_centrality_numpy_non_empty_still_works():
    G = fnx.Graph([(1, 2), (2, 3), (3, 1)])
    Gn = nx.Graph([(1, 2), (2, 3), (3, 1)])
    f = fnx.eigenvector_centrality_numpy(G)
    n = nx.eigenvector_centrality_numpy(Gn)
    assert set(f.keys()) == set(n.keys())
    for k in f:
        assert abs(f[k] - n[k]) < 1e-6, (k, f[k], n[k])
