"""Phase B certification: graph transforms (mycielskian, contracted_edge,
moral_graph), number_of_walks, threshold recognition, reaching
centrality, and distance-regularity / intersection_array. Zero
divergences.
"""
import random

import networkx as nx
import networkx.algorithms.threshold as nxth

import franken_networkx as fnx


def _EE(g):
    return sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in g.edges())


def _mk():
    R = random.Random(79)
    ue = [(u, v) for u, v in ((R.randrange(10), R.randrange(10)) for _ in range(28)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def _mkd():
    R = random.Random(79)
    [(R.randrange(10), R.randrange(10)) for _ in range(28)]  # align with _mk's stream then diverge
    de = [(u, v) for u, v in ((R.randrange(8), R.randrange(8)) for _ in range(15)) if u < v]
    return fnx.DiGraph(de), nx.DiGraph(de)


def test_transforms():
    gf, gn = _mk()
    assert _EE(nx.mycielskian(gf)) == _EE(nx.mycielskian(gn))
    e0 = sorted(gn.edges())[0]
    assert _EE(nx.contracted_edge(gf, e0, self_loops=False)) == _EE(
        nx.contracted_edge(gn, e0, self_loops=False)
    )
    df, dn = _mkd()
    assert _EE(nx.moral_graph(df)) == _EE(nx.moral_graph(dn))


def test_number_of_walks():
    gf, gn = _mk()
    a = {repr(k): {repr(k2): v2 for k2, v2 in v.items()} for k, v in nx.number_of_walks(gf, 3).items()}
    b = {repr(k): {repr(k2): v2 for k2, v2 in v.items()} for k, v in nx.number_of_walks(gn, 3).items()}
    assert a == b


def test_threshold_and_reaching():
    gf, gn = _mk()
    assert nxth.is_threshold_graph(gf) == nxth.is_threshold_graph(gn)
    df, dn = _mkd()
    assert round(nx.global_reaching_centrality(df), 9) == round(nx.global_reaching_centrality(dn), 9)
    assert round(nx.local_reaching_centrality(df, 0), 9) == round(nx.local_reaching_centrality(dn, 0), 9)


def test_distance_regular():
    gf, gn = _mk()
    assert nx.is_distance_regular(gf) == nx.is_distance_regular(gn)
    pf, pn = fnx.petersen_graph(), nx.petersen_graph()
    assert nx.is_distance_regular(pf) == nx.is_distance_regular(pn) is True
    assert nx.intersection_array(pf) == nx.intersection_array(pn)
