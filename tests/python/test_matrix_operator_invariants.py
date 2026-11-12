"""Oracle-free linear-algebra and operator invariants.

Matrix identities:
* Laplacian == Degree - Adjacency
* undirected adjacency is symmetric with zero trace (no self-loops)
* oriented incidence ``B @ B.T == Laplacian``
* ``normalized_laplacian == I - D^-1/2 A D^-1/2``

Operator involutions:
* ``complement(complement(G)) == G``  (simple undirected)
* ``reverse(reverse(G)) == G``        (directed)
* ``to_undirected(to_directed(G)) == G``

br-r37-c1-is5fj
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _undirected(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    return g, n


def _edge_signature(G):
    if G.is_directed():
        return sorted((str(u), str(v)) for u, v in G.edges())
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in G.edges())


@pytest.mark.parametrize("seed", range(50))
def test_matrix_identities(seed):
    g, n = _undirected(seed)
    nodelist = list(g.nodes())
    A = np.asarray(fnx.adjacency_matrix(g, nodelist=nodelist).todense(), dtype=float)
    L = np.asarray(fnx.laplacian_matrix(g, nodelist=nodelist).todense(), dtype=float)
    D = np.diag(A.sum(axis=1))
    assert np.allclose(L, D - A)
    assert np.allclose(A, A.T)
    assert abs(np.trace(A)) < 1e-9
    B = np.asarray(
        fnx.incidence_matrix(g, nodelist=nodelist, oriented=True).todense(), dtype=float
    )
    assert np.allclose(B @ B.T, L)
    if min(A.sum(axis=1)) > 0:
        nl = np.asarray(
            fnx.normalized_laplacian_matrix(g, nodelist=nodelist).todense(), dtype=float
        )
        dinv = np.diag(1.0 / np.sqrt(A.sum(axis=1)))
        assert np.allclose(nl, np.eye(n) - dinv @ A @ dinv)


@pytest.mark.parametrize("seed", range(50))
def test_complement_involution(seed):
    g, _ = _undirected(seed)
    assert _edge_signature(fnx.complement(fnx.complement(g))) == _edge_signature(g)


@pytest.mark.parametrize("seed", range(50))
def test_reverse_involution(seed):
    rng = random.Random(seed + 100)
    n = rng.randint(4, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < 0.4:
                g.add_edge(u, v)
    assert _edge_signature(fnx.reverse(fnx.reverse(g))) == _edge_signature(g)


@pytest.mark.parametrize("seed", range(40))
def test_to_undirected_of_to_directed_is_identity(seed):
    g, _ = _undirected(seed)
    assert _edge_signature(fnx.to_undirected(fnx.to_directed(g))) == _edge_signature(g)
