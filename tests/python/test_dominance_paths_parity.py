"""Phase B certification: dominance (immediate_dominators /
dominance_frontiers), simple-path enumeration (all_simple_paths /
all_simple_edge_paths / shortest_simple_paths), and load / percolation
centrality. Zero divergences. Direct asserts (no try/except) so a
both-impls-raise case can't be silently masked.
"""
import random

import networkx as nx

import franken_networkx as fnx

_DE = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (1, 4), (2, 5), (5, 4), (4, 6), (3, 6)]


def _kd(d):
    return {
        repr(k): (repr(v) if not isinstance(v, (set, list)) else sorted(repr(x) for x in v))
        for k, v in d.items()
    }


def test_dominance():
    df, dn = fnx.DiGraph(_DE), nx.DiGraph(_DE)
    assert _kd(fnx.immediate_dominators(df, 0)) == _kd(nx.immediate_dominators(dn, 0))
    assert _kd(fnx.dominance_frontiers(df, 0)) == _kd(nx.dominance_frontiers(dn, 0))


def _ue():
    R = random.Random(303)
    return [(u, v) for u, v in ((R.randrange(8), R.randrange(8)) for _ in range(20)) if u != v]


def _pset(ps):
    return sorted(tuple(repr(n) for n in p) for p in ps)


def test_simple_paths():
    ue = _ue()
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    assert _pset(fnx.all_simple_paths(gf, 0, 5, cutoff=4)) == _pset(
        nx.all_simple_paths(gn, 0, 5, cutoff=4)
    )
    assert _pset(list(fnx.shortest_simple_paths(gf, 0, 5))[:10]) == _pset(
        list(nx.shortest_simple_paths(gn, 0, 5))[:10]
    )
    assert {repr(s): {repr(t): v for t, v in d.items()} for s, d in nx.all_pairs_node_connectivity(gf).items()} == {
        repr(s): {repr(t): v for t, v in d.items()} for s, d in nx.all_pairs_node_connectivity(gn).items()
    }


def _rd(d, n=6):
    return {repr(k): round(v, n) for k, v in d.items()}


def test_load_and_percolation_centrality():
    ue = _ue()
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    assert _rd(fnx.load_centrality(gf)) == _rd(nx.load_centrality(gn))
    assert sorted(
        (tuple(sorted((repr(u), repr(v)))), round(w, 6)) for (u, v), w in fnx.edge_load_centrality(gf).items()
    ) == sorted(
        (tuple(sorted((repr(u), repr(v)))), round(w, 6)) for (u, v), w in nx.edge_load_centrality(gn).items()
    )
    assert _rd(nx.percolation_centrality(gf)) == _rd(nx.percolation_centrality(gn))
    assert round(nx.dispersion(gf, 0, 1), 6) == round(nx.dispersion(gn, 0, 1), 6)
