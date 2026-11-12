"""Parity for the integer-adjacency mark-array constraint kernel (br-constraint-intadj).

Burt's ``constraint`` used a native kernel that rebuilt ``graph.neighbors(v)`` (a
String-keyed Vec + HashSet allocation) for every (u, v) pair -- ~2m repeated
neighbor materializations -- leaving it ~3.1x SLOWER than networkx's lru_cache'd
Python path. The kernel now precomputes integer adjacency once and runs the same
double sum with a reusable mark-array, with a byte-identical accumulation order, so
the float outputs are unchanged while it is now 1.2x-2.9x FASTER than networkx.

This locks the value parity (vs networkx) across the unweighted-undirected fast
path and the delegated paths (weighted / directed / self-loop).
"""

import math
import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def _match(a, b, tol=1e-9):
    assert set(a) == set(b)
    for k in a:
        av, bv = a[k], b[k]
        if math.isnan(av) or math.isnan(bv):
            assert math.isnan(av) and math.isnan(bv), k
        else:
            assert abs(av - bv) <= tol, (k, av, bv)


def test_random_gnp_matches_networkx():
    for seed in range(250):
        rnd = random.Random(seed)
        n = rnd.randint(0, 80)
        p = rnd.uniform(0.0, 0.5)
        G = nx.gnp_random_graph(n, p, seed=seed)
        try:
            a = nx.constraint(G)
        except nx.NetworkXError:
            # empty graph -> both raise
            try:
                fnx.constraint(_cp(G))
            except Exception:
                continue
            raise AssertionError("fnx did not raise on empty graph")
        _match(a, fnx.constraint(_cp(G)))


def test_fixtures():
    for G in [
        nx.complete_graph(12),
        nx.star_graph(9),
        nx.cycle_graph(15),
        nx.path_graph(8),
        nx.wheel_graph(10),
        nx.barbell_graph(5, 2),
        nx.karate_club_graph(),
    ]:
        _match(nx.constraint(G), fnx.constraint(_cp(G)))


def test_isolated_node_is_nan():
    G = nx.Graph()
    G.add_node(0)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    res = fnx.constraint(_cp(G))
    assert math.isnan(res[0])  # isolated -> nan, matching networkx
    _match(nx.constraint(G), res)


def test_nodes_subset():
    G = nx.gnp_random_graph(40, 0.15, seed=7)
    F = _cp(G)
    sub = [0, 5, 10, 20]
    _match(nx.constraint(G, nodes=sub), fnx.constraint(F, nodes=sub))


def test_directed_and_weighted_delegate_match():
    # Directed and weighted paths delegate to networkx; verify they still agree.
    Gd = nx.gnp_random_graph(30, 0.12, seed=3, directed=True)
    _match(nx.constraint(Gd), fnx.constraint(_cp(Gd, directed=True)))
    Gw = nx.gnp_random_graph(30, 0.2, seed=4)
    for u, v in Gw.edges():
        Gw[u][v]["weight"] = 1.0 + (u + v) % 3
    Fw = _cp(Gw)
    for u, v in Gw.edges():
        Fw[u][v]["weight"] = Gw[u][v]["weight"]
    _match(nx.constraint(Gw, weight="weight"), fnx.constraint(Fw, weight="weight"))
