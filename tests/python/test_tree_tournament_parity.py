"""Phase B certification: spanning-tree variants (kruskal/prim, min/max),
tournament predicates, prufer coding, arborescence, threshold. Zero
divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _mkw(mod):
    R = random.Random(202)
    we = [(u, v, R.randrange(1, 9)) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(45)) if u != v]
    g = mod.Graph()
    for u, v, w in we:
        g.add_edge(u, v, weight=w)
    return g


def _eset(es):
    return sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v, *_ in es)


def test_spanning_tree_variants():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert _eset(fnx.minimum_spanning_tree(gf).edges()) == _eset(nx.minimum_spanning_tree(gn).edges())
    assert _eset(fnx.maximum_spanning_tree(gf).edges()) == _eset(nx.maximum_spanning_tree(gn).edges())
    assert fnx.minimum_spanning_tree(gf).size(weight="weight") == nx.minimum_spanning_tree(gn).size(
        weight="weight"
    )
    assert _eset(fnx.minimum_spanning_edges(gf, algorithm="kruskal", data=False)) == _eset(
        nx.minimum_spanning_edges(gn, algorithm="kruskal", data=False)
    )
    assert sum(d["weight"] for *_, d in fnx.minimum_spanning_edges(gf, algorithm="prim")) == sum(
        d["weight"] for *_, d in nx.minimum_spanning_edges(gn, algorithm="prim")
    )


def test_tournament():
    R = random.Random(202)
    tt = [(i, j) if R.random() < 0.5 else (j, i) for i in range(8) for j in range(i + 1, 8)]
    tf, tn = fnx.DiGraph(tt), nx.DiGraph(tt)
    assert nx.tournament.is_tournament(tf) == nx.tournament.is_tournament(tn)
    assert nx.tournament.is_strongly_connected(tf) == nx.tournament.is_strongly_connected(tn)
    assert nx.tournament.score_sequence(tf) == nx.tournament.score_sequence(tn)


def test_tree_coding_and_predicates():
    t = nx.random_labeled_tree(10, seed=3)
    tef, ten = fnx.Graph(list(t.edges())), nx.Graph(list(t.edges()))
    assert fnx.to_prufer_sequence(tef) == nx.to_prufer_sequence(ten)
    assert fnx.is_tree(tef) == nx.is_tree(ten)
    assert nx.is_arborescence(fnx.DiGraph([(0, 1), (0, 2), (2, 3)])) == nx.is_arborescence(
        nx.DiGraph([(0, 1), (0, 2), (2, 3)])
    )
