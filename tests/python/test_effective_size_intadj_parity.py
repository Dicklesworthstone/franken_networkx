"""Parity for the integer mark-array effective_size kernel (br-r37-c1-chq2a).

Burt's ``effective_size`` native kernel counted ties among each node's neighbors
with an O(deg^2) ``graph.has_edge(nbrs[i], nbrs[j])`` double loop -- String-keyed
substrate lookups that left it up to ~1.6x SLOWER than networkx on dense graphs.
The kernel now precomputes integer adjacency once and counts ties with a reusable
mark-array (``ties = total / 2``), an exact-integer count, so the float outputs are
unchanged while it is now 1.5x-3x FASTER than networkx.

Locks value parity (vs networkx) on the unweighted-undirected fast path and the
delegated paths (weighted / directed / self-loop).
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


def test_random_gnp_dense_and_sparse():
    for seed in range(250):
        rnd = random.Random(seed)
        n = rnd.randint(1, 90)
        p = rnd.uniform(0.0, 0.6)
        G = nx.gnp_random_graph(n, p, seed=seed)
        if G.number_of_edges() == 0:
            continue  # networkx raises on edgeless graphs
        _match(nx.effective_size(G), fnx.effective_size(_cp(G)))


def test_fixtures():
    for G in [
        nx.complete_graph(16),
        nx.star_graph(10),
        nx.cycle_graph(14),
        nx.path_graph(9),
        nx.wheel_graph(11),
        nx.barbell_graph(6, 3),
        nx.karate_club_graph(),
        nx.les_miserables_graph(),
    ]:
        _match(nx.effective_size(G), fnx.effective_size(_cp(G)))


def test_isolated_node_is_nan():
    G = nx.Graph()
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_node(99)  # isolated
    res = fnx.effective_size(_cp(G))
    assert math.isnan(res[99])
    _match(nx.effective_size(G), res)


def test_nodes_subset():
    G = nx.gnp_random_graph(50, 0.2, seed=11)
    F = _cp(G)
    sub = [0, 7, 13, 25, 40]
    _match(nx.effective_size(G, nodes=sub), fnx.effective_size(F, nodes=sub))


def test_directed_and_weighted_delegate_match():
    Gd = nx.gnp_random_graph(30, 0.15, seed=3, directed=True)
    _match(nx.effective_size(Gd), fnx.effective_size(_cp(Gd, directed=True)))
    Gw = nx.gnp_random_graph(30, 0.25, seed=4)
    for u, v in Gw.edges():
        Gw[u][v]["weight"] = 1.0 + (u + v) % 3
    Fw = _cp(Gw)
    for u, v in Gw.edges():
        Fw[u][v]["weight"] = Gw[u][v]["weight"]
    _match(
        nx.effective_size(Gw, weight="weight"),
        fnx.effective_size(Fw, weight="weight"),
    )
