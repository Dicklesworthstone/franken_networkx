"""Parity for the precomputed-adjacency dispersion fast path (br-r37-c1-dispadj).

The dict form of ``dispersion`` recomputed ``set(G.neighbors(x))`` from the
String-keyed substrate for every (node, nbr) pair and every common neighbour,
leaving fnx ~3x SLOWER than networkx. It now precomputes every adjacency set once
and reuses it; the set logic is identical and ``disp`` is an order-invariant
integer count, so the float outputs are unchanged while it is now ~1.2x FASTER.

Locks value parity (vs networkx) across the normalization parameters, the
single-node dict form, and the single-pair form.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def _match_dict_of_dicts(a, b, tol=1e-12):
    assert set(a) == set(b)
    for node in a:
        assert set(a[node]) == set(b[node]), node
        for nbr in a[node]:
            assert abs(a[node][nbr] - b[node][nbr]) <= tol, (node, nbr)


def test_random_param_variations():
    param_sets = [
        {},
        {"normalized": False},
        {"alpha": 1.5, "b": 0.5, "c": 1.0},
        {"normalized": True, "b": 1.0},
        {"alpha": 2.0, "c": 2.0},
    ]
    for seed in range(200):
        rnd = random.Random(seed)
        n = rnd.randint(2, 45)
        p = rnd.uniform(0.03, 0.55)
        G = nx.gnp_random_graph(n, p, seed=seed)
        F = _cp(G)
        for pr in param_sets:
            _match_dict_of_dicts(nx.dispersion(G, **pr), fnx.dispersion(F, **pr))


def test_single_node_form():
    G = nx.gnp_random_graph(40, 0.2, seed=5)
    F = _cp(G)
    for node in [0, 7, 20, 39]:
        a = nx.dispersion(G, u=node)
        b = fnx.dispersion(F, u=node)
        assert set(a) == set(b)
        for nbr in a:
            assert abs(a[nbr] - b[nbr]) <= 1e-12, (node, nbr)


def test_single_pair_form():
    G = nx.karate_club_graph()
    F = _cp(G)
    for u, v in list(G.edges())[:20]:
        assert abs(nx.dispersion(G, u, v) - fnx.dispersion(F, u, v)) <= 1e-12, (u, v)


def test_fixtures():
    for G in [
        nx.karate_club_graph(),
        nx.les_miserables_graph(),
        nx.complete_graph(9),
        nx.cycle_graph(11),
        nx.wheel_graph(10),
    ]:
        _match_dict_of_dicts(nx.dispersion(G), fnx.dispersion(_cp(G)))


def test_missing_node_keyerror():
    G = nx.path_graph(5)
    F = _cp(G)
    try:
        fnx.dispersion(F, u=999)
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for missing node")
