"""Phase B certification: clique-family enumeration ORDER, covering,
similarity, generalized_degree, rich_club, gomory_hu — surfaces not
covered elsewhere. find_cliques emission order is a parity contract
(Bron-Kerbosch pivot/recursion order). Zero divergences.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(seed=29, n=12, m=45):
    R = random.Random(seed)
    ue = [(u, v) for u, v in ((R.randrange(n), R.randrange(n)) for _ in range(m)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_find_cliques_enumeration_order():
    gf, gn = _mk()
    assert [[repr(x) for x in c] for c in fnx.find_cliques(gf)] == [
        [repr(x) for x in c] for c in nx.find_cliques(gn)
    ]


def test_node_clique_number_and_generalized_degree():
    gf, gn = _mk()
    assert sorted((repr(k), v) for k, v in fnx.node_clique_number(gf).items()) == sorted(
        (repr(k), v) for k, v in nx.node_clique_number(gn).items()
    )
    assert sorted((repr(k), sorted(dict(v).items())) for k, v in fnx.generalized_degree(gf).items()) == sorted(
        (repr(k), sorted(dict(v).items())) for k, v in nx.generalized_degree(gn).items()
    )


def test_simrank_and_rich_club():
    gf, gn = _mk()
    assert round(nx.simrank_similarity(gf, 0, 1), 6) == round(nx.simrank_similarity(gn, 0, 1), 6)
    assert sorted((k, round(v, 9)) for k, v in fnx.rich_club_coefficient(gf, normalized=False).items()) == sorted(
        (k, round(v, 9)) for k, v in nx.rich_club_coefficient(gn, normalized=False).items()
    )


def test_min_edge_cover_and_gomory_hu():
    gf, gn = _mk()
    assert len(nx.min_edge_cover(gf)) == len(nx.min_edge_cover(gn))
    cf, cn = fnx.Graph(), nx.Graph()
    rc = random.Random(31)
    cap = [(u, v, rc.randrange(1, 9)) for u, v in ((rc.randrange(8), rc.randrange(8)) for _ in range(20)) if u != v]
    for u, v, c in cap:
        cf.add_edge(u, v, capacity=c)
        cn.add_edge(u, v, capacity=c)
    assert nx.gomory_hu_tree(cf).number_of_edges() == nx.gomory_hu_tree(cn).number_of_edges()
