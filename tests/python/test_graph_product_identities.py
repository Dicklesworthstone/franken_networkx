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
    # br-r37-c1-fwrzb: the nx factors are built by adding NODES first and then
    # edges, in fnx's own order. They used to be constructed as
    # ``nx.Graph(list(g.edges()))``, which discovers nodes in edge order — for
    # 5 of these 20 seeds that produced a factor whose node order differed from
    # fnx's, so the two libraries were being handed DIFFERENT graphs. The
    # `_edges` comparison below sorts, so it could not see the difference. This
    # is the same trap test_exact_path_tiebreak_parity documents in its module
    # docstring: an edge-list-constructed nx graph permutes iteration order.
    r = random.Random(seed)
    g = fnx.path_graph(r.randint(2, 4)) if r.random() < 0.5 else fnx.cycle_graph(r.randint(3, 5))
    h = fnx.path_graph(r.randint(2, 4)) if r.random() < 0.5 else fnx.star_graph(r.randint(2, 4))
    ng = nx.Graph(); ng.add_nodes_from(g.nodes()); ng.add_edges_from(g.edges())
    nh = nx.Graph(); nh.add_nodes_from(h.nodes()); nh.add_edges_from(h.edges())
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
    # br-r37-c1-fwrzb: this asserted only equal node/edge COUNTS and called that
    # "the cheap check" — any two graphs of the same size pass it, including
    # ones that are not isomorphic at all. The property named in the test's own
    # title is now actually checked.
    g, h = fnx.path_graph(3), fnx.cycle_graph(4)
    gh = fnx.cartesian_product(g, h)
    hg = fnx.cartesian_product(h, g)
    assert gh.number_of_nodes() == hg.number_of_nodes()
    assert gh.number_of_edges() == hg.number_of_edges()
    assert fnx.is_isomorphic(gh, hg)


@pytest.mark.parametrize("seed", range(20))
def test_product_iteration_order_parity(seed):
    """br-r37-c1-fwrzb: ``_edges`` sorts tuples of sorted str endpoints, so it
    is blind to node identity and to iteration order — the property
    br-r37-c1-28lwc found diverging in three of these four products. That is
    fixed, so the order is locked here: this test is the regression guard for
    28lwc, and it fails on the pre-fix kernels.
    """
    g, h, ng, nh = _factors(seed)
    for name in (
        "cartesian_product",
        "tensor_product",
        "strong_product",
        "lexicographic_product",
    ):
        got = getattr(fnx, name)(g, h)
        want = getattr(nx, name)(ng, nh)
        assert list(got.nodes()) == list(want.nodes()), name
        assert list(got.edges()) == list(want.edges()), name
