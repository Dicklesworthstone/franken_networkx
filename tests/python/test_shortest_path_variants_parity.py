"""Phase B certification: shortest-path variants (astar, bidirectional,
johnson, floyd_warshall, all_pairs_bellman_ford) and disjoint paths.
Zero divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _mkw(mod, directed=False):
    R = random.Random(103)
    we = [(u, v, R.randrange(1, 9)) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u != v]
    g = (mod.DiGraph if directed else mod.Graph)()
    for u, v, w in we:
        g.add_edge(u, v, weight=w)
    return g


def _P(p):
    return [repr(n) for n in p]


def test_astar_and_bidirectional():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert _P(fnx.astar_path(gf, 0, 9)) == _P(nx.astar_path(gn, 0, 9))
    assert fnx.astar_path_length(gf, 0, 9) == nx.astar_path_length(gn, 0, 9)
    df, pf = fnx.bidirectional_dijkstra(gf, 0, 9)
    dn, pn = nx.bidirectional_dijkstra(gn, 0, 9)
    assert (df, _P(pf)) == (dn, _P(pn))
    assert _P(fnx.bidirectional_shortest_path(gf, 0, 9)) == _P(nx.bidirectional_shortest_path(gn, 0, 9))


def test_all_pairs_path_lengths():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert {repr(s): {repr(t): _P(p) for t, p in d.items()} for s, d in fnx.johnson(gf).items()} == {
        repr(s): {repr(t): _P(p) for t, p in d.items()} for s, d in nx.johnson(gn).items()
    }
    assert {repr(s): {repr(t): l for t, l in d.items()} for s, d in fnx.floyd_warshall(gf).items()} == {
        repr(s): {repr(t): l for t, l in d.items()} for s, d in nx.floyd_warshall(gn).items()
    }
    assert {repr(s): {repr(t): l for t, l in d.items()} for s, d in fnx.all_pairs_bellman_ford_path_length(gf)} == {
        repr(s): {repr(t): l for t, l in d.items()} for s, d in nx.all_pairs_bellman_ford_path_length(gn)
    }


def test_disjoint_paths():
    df, dn = _mkw(fnx, True), _mkw(nx, True)
    assert len(list(nx.node_disjoint_paths(df, 0, 9))) == len(list(nx.node_disjoint_paths(dn, 0, 9)))
    assert len(list(nx.edge_disjoint_paths(df, 0, 9))) == len(list(nx.edge_disjoint_paths(dn, 0, 9)))
    gf, gn = _mkw(fnx), _mkw(nx)
    assert fnx.has_path(gf, 0, 9) == nx.has_path(gn, 0, 9)
    assert fnx.shortest_path_length(gf, 0, 9, weight="weight") == nx.shortest_path_length(
        gn, 0, 9, weight="weight"
    )
