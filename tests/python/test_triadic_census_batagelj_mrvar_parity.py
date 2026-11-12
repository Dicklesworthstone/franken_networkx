"""Parity for the Batagelj-Mrvar O(m*d) triadic_census kernel.

br-triadbm: the Rust triadic_census kernel enumerated every node triple
(``for i: for j>i: for k>j``) -- O(n^3) -- making fnx ~6.4x SLOWER than networkx
on sparse directed graphs. It now uses the Batagelj-Mrvar subquadratic algorithm
(iterate connected triads via each ordered dyad's shared neighborhood, O(m*d)),
identical to networkx's method. Census counts are order-invariant, so the result
is bit-identical; fnx goes from 6.4x slower to ~14x FASTER than networkx, and the
gap grows with n (O(n^3) -> O(m)).
"""

import random

import networkx as nx

import franken_networkx as fnx

TYPES = [
    "003", "012", "102", "021D", "021U", "021C", "111D", "111U",
    "030T", "030C", "201", "120D", "120U", "120C", "210", "300",
]


def _cp(Gx):
    Gf = fnx.DiGraph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges())
    return Gf


def test_random_directed_graphs_match_networkx():
    for seed in range(120):
        rnd = random.Random(seed)
        n = rnd.randint(0, 45)
        p = rnd.uniform(0.0, 0.25)
        Gx = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        if seed % 3 == 0:  # inject mutual edges
            for u, v in list(Gx.edges()):
                if rnd.random() < 0.3:
                    Gx.add_edge(v, u)
        a = nx.triadic_census(Gx)
        b = fnx.triadic_census(_cp(Gx))
        assert {k: a[k] for k in TYPES} == {k: b[k] for k in TYPES}, (seed, n)


def test_census_sums_to_total_triads():
    Gx = nx.gnp_random_graph(60, 0.08, seed=1, directed=True)
    c = fnx.triadic_census(_cp(Gx))
    n = 60
    assert sum(c.values()) == n * (n - 1) * (n - 2) // 6


def test_all_sixteen_types_individually():
    cases = {
        "003": [],
        "012": [(0, 1)],
        "102": [(0, 1), (1, 0)],
        "021D": [(0, 1), (0, 2)],
        "021U": [(1, 0), (2, 0)],
        "021C": [(0, 1), (1, 2)],
        "111D": [(0, 1), (1, 0), (2, 0)],
        "111U": [(0, 1), (1, 0), (0, 2)],
        "030T": [(0, 1), (0, 2), (1, 2)],
        "030C": [(0, 1), (1, 2), (2, 0)],
        "201": [(0, 1), (1, 0), (0, 2), (2, 0)],
        "120D": [(0, 1), (1, 0), (2, 0), (2, 1)],
        "120U": [(0, 1), (1, 0), (0, 2), (1, 2)],
        "120C": [(0, 1), (1, 0), (0, 2), (2, 1)],
        "210": [(0, 1), (1, 0), (0, 2), (2, 0), (1, 2)],
        "300": [(0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)],
    }
    for expected, edges in cases.items():
        G = fnx.DiGraph()
        G.add_nodes_from([0, 1, 2])
        G.add_edges_from(edges)
        Gn = nx.DiGraph()
        Gn.add_nodes_from([0, 1, 2])
        Gn.add_edges_from(edges)
        c = fnx.triadic_census(G)
        assert c == nx.triadic_census(Gn), (expected, edges)
        assert c[expected] == 1, (expected, c)


def test_under_three_nodes_all_zero():
    for edges in ([], [(0, 1)], [(0, 1), (1, 0)]):
        G = fnx.DiGraph()
        G.add_edges_from(edges)
        c = fnx.triadic_census(G)
        assert sum(c.values()) == 0


def test_undirected_raises():
    try:
        fnx.triadic_census(fnx.Graph([(0, 1)]))
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for undirected")


def test_nodelist_form_still_matches():
    Gx = nx.gnp_random_graph(25, 0.12, seed=4, directed=True)
    Gf = _cp(Gx)
    nodelist = [0, 1, 2, 3, 4, 5]
    assert fnx.triadic_census(Gf, nodelist=nodelist) == nx.triadic_census(Gx, nodelist=nodelist)
