"""Phase B certification: matching predicates (is_matching /
is_maximal_matching / is_perfect_matching), max/min weight matching,
seeded small-world metrics (sigma/omega), k-edge-connectivity. Zero
divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _mk():
    R = random.Random(97)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(40)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_matching_predicates():
    gf, gn = _mk()
    mf, mn = nx.max_weight_matching(gf), nx.max_weight_matching(gn)
    assert {tuple(sorted((repr(a), repr(b)))) for a, b in mf} == {
        tuple(sorted((repr(a), repr(b)))) for a, b in mn
    }
    assert nx.is_matching(gf, mf) == nx.is_matching(gn, mn) is True
    assert nx.is_maximal_matching(gf, mf) == nx.is_maximal_matching(gn, mn)
    assert nx.is_perfect_matching(gf, mf) == nx.is_perfect_matching(gn, mn)
    assert len(nx.maximal_matching(gf)) == len(nx.maximal_matching(gn))


def test_weighted_matching():
    R = random.Random(97)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(40)) if u != v]
    wf, wn = fnx.Graph(), nx.Graph()
    for i, (u, v) in enumerate(ue):
        wf.add_edge(u, v, weight=1 + (i % 9))
        wn.add_edge(u, v, weight=1 + (i % 9))
    assert {tuple(sorted((repr(a), repr(b)))) for a, b in nx.max_weight_matching(wf)} == {
        tuple(sorted((repr(a), repr(b)))) for a, b in nx.max_weight_matching(wn)
    }
    assert len(nx.min_weight_matching(wf)) == len(nx.min_weight_matching(wn))


def test_smallworld_seeded():
    wf = fnx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    wn = nx.connected_watts_strogatz_graph(20, 4, 0.3, seed=1)
    assert round(nx.sigma(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.sigma(wn, niter=2, nrand=2, seed=1), 4
    )
    assert round(nx.omega(wf, niter=2, nrand=2, seed=1), 4) == round(
        nx.omega(wn, niter=2, nrand=2, seed=1), 4
    )


def test_k_edge_connectivity():
    gf, gn = _mk()
    assert nx.is_k_edge_connected(gf, 2) == nx.is_k_edge_connected(gn, 2)
    assert nx.is_connected(gf) == nx.is_connected(gn)
