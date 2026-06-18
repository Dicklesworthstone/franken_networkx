"""Graph product identities: closed-form counts + networkx parity.

Graph products obey closed-form size identities that are a ground-truth oracle
independent of any reference implementation:
  - |V(G * H)| = |V(G)| * |V(H)|  (all products)
  - cartesian:     |E| = |E(G)||V(H)| + |E(H)||V(G)|
  - tensor:        |E| = 2|E(G)||E(H)|
  - strong:        |E| = cartesian + tensor
  - lexicographic: |E| = |E(G)||V(H)|^2 + |E(H)||V(G)|
This checks the identities AND exact structure parity with networkx.

No mocks: real fnx and real networkx on small named-graph factors.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _edges(g):
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in g.edges())


def _factors(seed):
    r = random.Random(seed)
    g = fnx.path_graph(r.randint(2, 4)) if r.random() < 0.5 else fnx.cycle_graph(r.randint(3, 5))
    h = fnx.path_graph(r.randint(2, 4)) if r.random() < 0.5 else fnx.star_graph(r.randint(2, 4))
    ng = nx.Graph(list(g.edges())); ng.add_nodes_from(g.nodes())
    nh = nx.Graph(list(h.edges())); nh.add_nodes_from(h.nodes())
    return g, h, ng, nh


@pytest.mark.parametrize("seed", range(20))
def test_cartesian_tensor_strong_identities(seed):
    g, h, ng, nh = _factors(seed)
    v1, v2 = g.number_of_nodes(), h.number_of_nodes()
    e1, e2 = g.number_of_edges(), h.number_of_edges()

    cart = fnx.cartesian_product(g, h)
    assert cart.number_of_nodes() == v1 * v2
    assert cart.number_of_edges() == e1 * v2 + e2 * v1
    assert _edges(cart) == _edges(nx.cartesian_product(ng, nh))

    tens = fnx.tensor_product(g, h)
    assert tens.number_of_nodes() == v1 * v2
    assert tens.number_of_edges() == 2 * e1 * e2
    assert _edges(tens) == _edges(nx.tensor_product(ng, nh))

    strong = fnx.strong_product(g, h)
    assert strong.number_of_nodes() == v1 * v2
    assert strong.number_of_edges() == e1 * v2 + e2 * v1 + 2 * e1 * e2
    assert _edges(strong) == _edges(nx.strong_product(ng, nh))


@pytest.mark.parametrize("seed", range(20))
def test_lexicographic_identity(seed):
    g, h, ng, nh = _factors(seed)
    v1, v2 = g.number_of_nodes(), h.number_of_nodes()
    e1, e2 = g.number_of_edges(), h.number_of_edges()

    lex = fnx.lexicographic_product(g, h)
    assert lex.number_of_nodes() == v1 * v2
    assert lex.number_of_edges() == e1 * v2 * v2 + e2 * v1
    assert _edges(lex) == _edges(nx.lexicographic_product(ng, nh))


def test_cartesian_product_is_commutative_up_to_iso():
    # G x H and H x G are isomorphic (same node/edge counts is the cheap check).
    g, h = fnx.path_graph(3), fnx.cycle_graph(4)
    gh = fnx.cartesian_product(g, h)
    hg = fnx.cartesian_product(h, g)
    assert gh.number_of_nodes() == hg.number_of_nodes()
    assert gh.number_of_edges() == hg.number_of_edges()
