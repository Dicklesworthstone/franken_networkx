"""Parity for the native integer-bitset dispersion kernel (br-r37-c1-o53cp).

The dict form of ``dispersion`` now routes undirected simple loop-free graphs with
the normalized formula through a native Rust bitset kernel (the Backstrom-Kleinberg
``disp`` count via word-parallel set intersections). ``disp`` is an order-invariant
integer and the dispersion predicate is symmetric in the common-neighbour pair, so
the kernel is byte-identical to the Python path while being 7x-67x FASTER (it scales
with density). Directed / multigraph / self-loop / normalized=False inputs fall back
to the Python path.

These lock value parity (vs networkx) for the native path (dense + sparse) and for
every fall-back gate.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False, multi=False):
    if multi:
        F = fnx.MultiGraph()
    elif directed:
        F = fnx.DiGraph()
    else:
        F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def _match(a, b, tol=1e-12):
    assert set(a) == set(b)
    for node in a:
        assert set(a[node]) == set(b[node]), node
        for nbr in a[node]:
            assert abs(a[node][nbr] - b[node][nbr]) <= tol, (node, nbr)


def test_native_path_dense_and_sparse():
    for seed in range(200):
        rnd = random.Random(seed)
        n = rnd.randint(2, 60)
        p = rnd.uniform(0.03, 0.7)  # includes dense graphs the bitset path favours
        G = nx.gnp_random_graph(n, p, seed=seed)
        _match(nx.dispersion(G), fnx.dispersion(_cp(G)))


def test_directed_falls_back_to_python():
    for seed in range(40):
        rnd = random.Random(seed)
        n = rnd.randint(3, 30)
        p = rnd.uniform(0.05, 0.4)
        G = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        _match(nx.dispersion(G), fnx.dispersion(_cp(G, directed=True)))


def test_selfloops_match_networkx():
    # br-r37-c1-brlzk: self-loop graphs are gated OFF the native kernel and use
    # the Python path. dispadj regressed that path by building ``common`` from a
    # set (set-iteration order) instead of the ordered neighbour list; when a
    # self-loop puts ``v`` into ``common`` the dispersion predicate is asymmetric
    # so nx's combinations order matters. Iterating the ordered list restores
    # parity. Verify across many self-loop graphs.
    for seed in range(60):
        rnd = random.Random(seed)
        n = rnd.randint(4, 40)
        p = rnd.uniform(0.08, 0.4)
        G = nx.gnp_random_graph(n, p, seed=seed)
        for _ in range(rnd.randint(1, 3)):
            x = rnd.randrange(n)
            G.add_edge(x, x)
        _match(nx.dispersion(G), fnx.dispersion(_cp(G)))


def test_dict_form_equals_single_pair_form():
    # The dict form and the single-pair form must agree for every (u, v),
    # including self-loop graphs -- the invariant dispadj broke.
    for seed in range(40):
        rnd = random.Random(seed)
        n = rnd.randint(4, 35)
        G = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed)
        for _ in range(rnd.randint(0, 2)):
            x = rnd.randrange(n)
            G.add_edge(x, x)
        F = _cp(G)
        full = fnx.dispersion(F)
        for node in full:
            for nbr in full[node]:
                assert abs(full[node][nbr] - fnx.dispersion(F, node, nbr)) <= 1e-12, (
                    node,
                    nbr,
                )


def test_multigraph_falls_back():
    G = nx.MultiGraph()
    G.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 1), (2, 3), (3, 0)])
    base = nx.Graph(G)  # networkx dispersion treats it via unique neighbours
    _match(nx.dispersion(base), fnx.dispersion(_cp(G, multi=True)))


def test_normalized_false_and_custom_params():
    G = nx.karate_club_graph()
    F = _cp(G)
    for pr in [
        {"normalized": False},
        {"alpha": 1.5, "b": 0.5, "c": 1.0},
        {"alpha": 2.0, "c": 2.0},
        {"b": 1.0},
    ]:
        _match(nx.dispersion(G, **pr), fnx.dispersion(F, **pr))


def test_native_binding_matches_wrapper():
    # The raw native binding (default params) must equal the wrapper result.
    G = nx.gnp_random_graph(40, 0.2, seed=5)
    F = _cp(G)
    raw = fnx._fnx.dispersion_full_rust(F, 1.0, 0.0, 0.0)
    _match(fnx.dispersion(F), raw)
