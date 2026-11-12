"""Communicability closed form (matrix exponential of the adjacency matrix).

Communicability between u and v is the (u,v) entry of exp(A):
  communicability(G)[u][v] = (exp(A))[u][v] = sum_k (A^k)[u][v] / k!  (walk sum).
This cross-checks communicability against the matrix exponential and ties it to
subgraph_centrality (existing tests cover nx parity, not these identities):
  - communicability[u][v] == expm(A)[u][v];
  - the matrix is symmetric (undirected graph);
  - the diagonal equals subgraph_centrality: communicability[u][u] == sc[u].
Oracle-free, independent of networkx.

Unlike the other centrality families, there is no directed case to cover here:
communicability is defined for undirected graphs only, and both fnx and networkx
raise NetworkXNotImplemented on a digraph — pinned below as a contract rather
than assumed. What was missing instead is that each of these functions has a
SIBLING computing the same quantity a different way (communicability_exp,
subgraph_centrality_exp), and neither was cross-checked against its partner.

No mocks: real fnx (scipy for the matrix exponential ground truth).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")
expm = pytest.importorskip("scipy.linalg").expm


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(20))
def test_communicability_equals_matrix_exponential(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    E = expm(A)
    comm = fnx.communicability(g)
    for u in range(n):
        for v in range(n):
            assert comm[u][v] == pytest.approx(E[u][v], abs=1e-6)
            # Symmetry for an undirected graph.
            assert comm[u][v] == pytest.approx(comm[v][u], abs=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_communicability_diagonal_is_subgraph_centrality(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    comm = fnx.communicability(g)
    sc = fnx.subgraph_centrality(g)
    for u in range(n):
        assert comm[u][u] == pytest.approx(sc[u], abs=1e-5)


@pytest.mark.parametrize("seed", range(20))
def test_communicability_exp_agrees_with_communicability(seed):
    """Two implementations of the same quantity: series vs matrix exponential."""
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    series = fnx.communicability(g)
    exponential = fnx.communicability_exp(g)
    for u in range(n):
        for v in range(n):
            assert series[u][v] == pytest.approx(exponential[u][v], abs=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_subgraph_centrality_exp_agrees_with_subgraph_centrality(seed):
    g, _ = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    eigen = fnx.subgraph_centrality(g)
    exponential = fnx.subgraph_centrality_exp(g)
    for u in g:
        assert eigen[u] == pytest.approx(exponential[u], abs=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_estrada_index_is_the_sum_of_the_diagonal(seed):
    """Closes the chain: diagonal == subgraph_centrality, whose sum == Estrada.

    The Estrada tests reach the same number through the adjacency SPECTRUM, so
    this ties the walk-sum route to the spectral one.
    """
    g, _ = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    sc = fnx.subgraph_centrality(g)
    assert sum(sc.values()) == pytest.approx(fnx.estrada_index(g), abs=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_separate_components_cannot_communicate(seed):
    """No walk crosses between components, so those entries are exactly zero."""
    g, _ = _graph(seed)
    if g.number_of_edges() == 0 or fnx.is_connected(g):
        pytest.skip("connected or empty")
    components = [set(c) for c in fnx.connected_components(g)]
    pairs = [
        (u, v)
        for i, first in enumerate(components)
        for second in components[i + 1:]
        for u in first
        for v in second
    ]

    # The two routes differ in how clean the zero is, so each gets the assertion
    # that actually holds for it. communicability() goes through an eigen-
    # decomposition and leaves residue on one of the five disconnected draws
    # (measured worst 7.0e-16); communicability_exp() is exactly 0.0 on all five.
    series = fnx.communicability(g)
    assert all(abs(series[u][v]) < 1e-12 for u, v in pairs)

    exponential = fnx.communicability_exp(g)
    assert all(exponential[u][v] == 0.0 for u, v in pairs)


def test_directed_graphs_are_not_supported():
    """Communicability is undirected-only; the refusal is part of the contract."""
    d = fnx.DiGraph(); d.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.communicability(d)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.communicability_exp(d)
