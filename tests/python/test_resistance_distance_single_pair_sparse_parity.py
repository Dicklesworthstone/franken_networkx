"""Parity for the grounded-sparse-solve single-pair resistance_distance.

br-resdsparse: resistance_distance(G, nodeA, nodeB) with both endpoints (the
common single-scalar call) built the full dense O(n^3) Laplacian pseudo-inverse
and read four entries. The single effective resistance
``r(i,j) = (e_i - e_j)_red^T L_red^{-1} (e_i - e_j)_red`` now comes from one
grounded reduced-Laplacian sparse SPD solve -- O(nnz), exact to ~1e-14 vs the
pinv formula (n=300: 2.8s -> 2ms, ~1265x). The dict / all-pairs return shapes
need diag(L^+) so they keep the dense pinv; a non-finite sparse result falls
back to the dense path.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx):
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def _graphs():
    for seed in range(25):
        rnd = random.Random(seed)
        n = rnd.randint(3, 40)
        Gx = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
        weighted = seed % 2 == 0
        if weighted:
            for u, v in Gx.edges():
                Gx[u][v]["weight"] = rnd.uniform(0.5, 5.0)
        yield Gx, _cp(Gx), ("weight" if weighted else None)


def test_single_pair_matches_networkx():
    for Gx, Gf, wk in _graphs():
        nl = list(Gx.nodes())
        rnd = random.Random(hash(wk) & 0xFFFF)
        for invert in (True, False):
            for _ in range(6):
                a, b = rnd.choice(nl), rnd.choice(nl)
                ra = nx.resistance_distance(Gx, a, b, weight=wk, invert_weight=invert)
                rb = fnx.resistance_distance(Gf, a, b, weight=wk, invert_weight=invert)
                assert abs(ra - rb) < 1e-6, (a, b, wk, invert, ra, rb)


def test_single_pair_matches_dense_pinv_path():
    # The fast sparse path and the dense pinv fallback must agree (isomorphism).
    import franken_networkx as F

    orig = F._resistance_single_pair_sparse
    try:
        for Gx, Gf, wk in _graphs():
            nl = list(Gx.nodes())
            for _ in range(5):
                a, b = random.choice(nl), random.choice(nl)
                F._resistance_single_pair_sparse = orig
                fast = fnx.resistance_distance(Gf, a, b, weight=wk)
                F._resistance_single_pair_sparse = lambda *aa, **kk: None
                dense = fnx.resistance_distance(Gf, a, b, weight=wk)
                assert abs(fast - dense) < 1e-9, (a, b, wk, fast, dense)
    finally:
        F._resistance_single_pair_sparse = orig


def test_same_node_is_zero():
    Gf = _cp(nx.path_graph(6))
    assert fnx.resistance_distance(Gf, 3, 3) == 0.0


def test_dict_shapes_still_match():
    Gx = nx.connected_watts_strogatz_graph(40, 6, 0.3, seed=11)
    Gf = _cp(Gx)
    a = 0
    da = nx.resistance_distance(Gx, a, None)
    db = fnx.resistance_distance(Gf, a, None)
    assert set(da) == set(db)
    assert all(abs(da[k] - db[k]) < 1e-6 for k in da)
    full_x = nx.resistance_distance(Gx)
    full_f = fnx.resistance_distance(Gf)
    assert all(abs(full_x[u][v] - full_f[u][v]) < 1e-6 for u in full_x for v in full_x[u])


def test_directed_raises():
    try:
        fnx.resistance_distance(fnx.DiGraph([(0, 1), (1, 0)]), 0, 1)
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for directed")


def test_disconnected_raises():
    try:
        fnx.resistance_distance(fnx.Graph([(0, 1), (2, 3)]), 0, 1)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for disconnected graph")


def test_missing_node_raises():
    Gf = _cp(nx.path_graph(4))
    try:
        fnx.resistance_distance(Gf, 0, 99)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for missing node")
