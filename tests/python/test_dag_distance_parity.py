"""Phase B certification: DAG-advanced (transitive reduction/closure,
antichains incl. enumeration order, longest-path) + Laplacian distance
measures (resistance, kemeny, effective resistance, wiener) + complement
/ isolates. Zero divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _mkdag(mod):
    R = random.Random(59)
    de = sorted({(u, v) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u < v})
    g = mod.DiGraph()
    for u, v in de:
        g.add_edge(u, v)
    return g


def _EE(g):
    return sorted((repr(u), repr(v)) for u, v in g.edges())


def test_transitive_reduction_and_closure():
    df, dn = _mkdag(fnx), _mkdag(nx)
    assert _EE(fnx.transitive_reduction(df)) == _EE(nx.transitive_reduction(dn))
    assert _EE(fnx.transitive_closure_dag(df)) == _EE(nx.transitive_closure_dag(dn))


def test_antichains_set_and_order():
    df, dn = _mkdag(fnx), _mkdag(nx)
    assert [[repr(x) for x in a] for a in fnx.antichains(df)] == [
        [repr(x) for x in a] for a in nx.antichains(dn)
    ]
    assert fnx.dag_longest_path_length(df) == nx.dag_longest_path_length(dn)


def _mk_connected():
    R = random.Random(59)
    ue = [(u, v) for u, v in ((R.randrange(10), R.randrange(10)) for _ in range(30)) if u != v]
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    if not nx.is_connected(gn):
        comp = list(nx.connected_components(gn))
        for i in range(len(comp) - 1):
            a, b = next(iter(comp[i])), next(iter(comp[i + 1]))
            gf.add_edge(a, b)
            gn.add_edge(a, b)
    return gf, gn


def test_laplacian_distance_measures():
    gf, gn = _mk_connected()
    assert round(fnx.resistance_distance(gf, 0, 1), 6) == round(nx.resistance_distance(gn, 0, 1), 6)
    assert round(nx.kemeny_constant(gf), 6) == round(nx.kemeny_constant(gn), 6)
    assert round(nx.effective_graph_resistance(gf), 6) == round(nx.effective_graph_resistance(gn), 6)
    assert round(fnx.global_efficiency(gf), 9) == round(nx.global_efficiency(gn), 9)
    assert fnx.wiener_index(gf) == nx.wiener_index(gn)


def test_complement_and_isolates():
    gf, gn = _mk_connected()
    assert _EE(fnx.complement(gf)) == _EE(nx.complement(gn))
    assert sorted(repr(x) for x in fnx.isolates(gf)) == sorted(repr(x) for x in nx.isolates(gn))
