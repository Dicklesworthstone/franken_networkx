"""Density + handshaking identities (density/degree/edges cross-checks).

Basic but foundational counting identities, cross-checking density and the
degree views against the edge count:
  - undirected density(G) = 2|E| / (n(n-1));  directed = |E| / (n(n-1));
  - density(K_n) = 1, density(empty) = 0;
  - handshaking lemma: sum of degrees = 2|E| (undirected);
  - directed: sum(in_degree) = sum(out_degree) = |E|.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_density_closed_forms(n):
    assert fnx.density(fnx.complete_graph(n)) == pytest.approx(1.0)
    e = fnx.empty_graph(n)
    assert fnx.density(e) == pytest.approx(0.0)


@pytest.mark.parametrize("seed", range(30))
def test_undirected_density_and_handshaking(seed):
    r = random.Random(seed)
    n = r.randint(3, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    E = g.number_of_edges()
    assert fnx.density(g) == pytest.approx(2 * E / (n * (n - 1)))
    # Handshaking lemma.
    assert sum(d for _, d in g.degree()) == 2 * E


@pytest.mark.parametrize("seed", range(30))
def test_directed_density_and_degree_sums(seed):
    r = random.Random(seed)
    n = r.randint(3, 9)
    arcs = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    d = fnx.DiGraph(); d.add_nodes_from(range(n)); d.add_edges_from(arcs)
    E = d.number_of_edges()
    assert fnx.density(d) == pytest.approx(E / (n * (n - 1)))
    # Every arc contributes one in-degree and one out-degree.
    assert sum(x for _, x in d.in_degree()) == E
    assert sum(x for _, x in d.out_degree()) == E
