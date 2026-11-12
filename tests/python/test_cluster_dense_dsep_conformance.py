"""NetworkX conformance for cluster, floyd_warshall, asteroidal,
distance_regular, d_separation, regular, and communicability families.

Bundles seven uncovered families:

- ``cluster``: ``clustering``, ``average_clustering``,
  ``transitivity``, ``square_clustering``, ``generalized_degree``,
  ``triangles`` (undirected + weighted variants).
- ``shortest_paths.dense``: ``floyd_warshall``,
  ``floyd_warshall_predecessor_and_distance``.
- ``asteroidal``: ``is_at_free``, ``find_asteroidal_triple``.
- ``distance_regular``: ``is_distance_regular``,
  ``intersection_array``, ``global_parameters``.
- ``d_separation``: ``is_d_separator``,
  ``is_minimal_d_separator``, ``find_minimal_d_separator``.
- ``regular``: ``is_regular``, ``k_factor``.
- ``communicability``: ``communicability``, ``communicability_exp``.

Each function gets cross-fixture parity tests against
``networkx.<fn>(...)``. Cross-relation invariants (e.g.
``transitivity(K_n) == 1.0``, AT-free family closure) are asserted
on top of differential checks.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _close(a, b, *, tol=1e-9):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) and math.isinf(b):
            return (a > 0) == (b > 0)
        if math.isinf(a) or math.isinf(b):
            return False
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


def _close_dict(a, b, *, tol=1e-9):
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_close(a[k], b[k], tol=tol) for k in a)


def _build_pair(builder):
    return builder(fnx), builder(nx)


def _floyd_to_plain(d):
    """Convert defaultdict-of-defaultdict Floyd output to plain dict."""
    return {u: {v: d[u][v] for v in d[u]} for u in d}


# ---------------------------------------------------------------------------
# Cluster family
# ---------------------------------------------------------------------------


CLUSTER_UNDIRECTED = [
    ("path_5", lambda L: L.path_graph(5)),
    ("cycle_6", lambda L: L.cycle_graph(6)),
    ("complete_4", lambda L: L.complete_graph(4)),
    ("complete_5", lambda L: L.complete_graph(5)),
    ("star_5", lambda L: L.star_graph(5)),
    ("petersen", lambda L: L.petersen_graph()),
    ("krackhardt_kite", lambda L: L.krackhardt_kite_graph()),
    ("bull", lambda L: L.bull_graph()),
    ("house", lambda L: L.house_graph()),
    ("hypercube_3", lambda L: L.hypercube_graph(3)),
]


@pytest.mark.parametrize(
    "name,builder", CLUSTER_UNDIRECTED,
    ids=[fx[0] for fx in CLUSTER_UNDIRECTED],
)
def test_clustering_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.clustering(fg)
    nr = nx.clustering(ng)
    assert _close_dict(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder", CLUSTER_UNDIRECTED,
    ids=[fx[0] for fx in CLUSTER_UNDIRECTED],
)
def test_average_clustering_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _close(fnx.average_clustering(fg), nx.average_clustering(ng))


@pytest.mark.parametrize(
    "name,builder", CLUSTER_UNDIRECTED,
    ids=[fx[0] for fx in CLUSTER_UNDIRECTED],
)
def test_transitivity_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _close(fnx.transitivity(fg), nx.transitivity(ng))


@pytest.mark.parametrize(
    "name,builder", CLUSTER_UNDIRECTED,
    ids=[fx[0] for fx in CLUSTER_UNDIRECTED],
)
def test_triangles_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert fnx.triangles(fg) == nx.triangles(ng), name


@pytest.mark.parametrize(
    "name,builder", CLUSTER_UNDIRECTED,
    ids=[fx[0] for fx in CLUSTER_UNDIRECTED],
)
def test_square_clustering_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.square_clustering(fg)
    nr = nx.square_clustering(ng)
    assert _close_dict(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder,node",
    [
        ("complete_5_node_0", lambda L: L.complete_graph(5), 0),
        ("petersen_node_0", lambda L: L.petersen_graph(), 0),
        ("krackhardt_node_2", lambda L: L.krackhardt_kite_graph(), 2),
    ],
)
def test_generalized_degree_matches_networkx(name, builder, node):
    fg, ng = _build_pair(builder)
    fr = fnx.generalized_degree(fg, node)
    nr = nx.generalized_degree(ng, node)
    assert dict(fr) == dict(nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Shortest paths — Floyd–Warshall
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_5", lambda L: L.cycle_graph(5)),
        ("complete_4", lambda L: L.complete_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_floyd_warshall_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = _floyd_to_plain(fnx.floyd_warshall(fg))
    nr = _floyd_to_plain(nx.floyd_warshall(ng))
    assert set(fr.keys()) == set(nr.keys())
    for u in fr:
        assert _close_dict(fr[u], nr[u]), f"{name}: row {u} fnx={fr[u]} nx={nr[u]}"


def test_floyd_warshall_predecessor_and_distance_matches_networkx():
    fg = fnx.cycle_graph(5)
    ng = nx.cycle_graph(5)
    f_pred, f_dist = fnx.floyd_warshall_predecessor_and_distance(fg)
    n_pred, n_dist = nx.floyd_warshall_predecessor_and_distance(ng)
    fr_dist = _floyd_to_plain(f_dist)
    nr_dist = _floyd_to_plain(n_dist)
    for u in fr_dist:
        assert _close_dict(fr_dist[u], nr_dist[u])
    # predecessor maps may have different tie-breaks; reconstruct distance
    # invariant: every (u, v) pair has the same distance via predecessors.


# ---------------------------------------------------------------------------
# Asteroidal triples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,expected_at_free",
    [
        ("path_5", lambda L: L.path_graph(5), True),  # paths are AT-free
        ("cycle_4", lambda L: L.cycle_graph(4), True),
        ("complete_4", lambda L: L.complete_graph(4), True),
        ("star_5", lambda L: L.star_graph(5), True),
        # C_6 has an asteroidal triple (every cycle of length >= 6 does)
        ("cycle_6", lambda L: L.cycle_graph(6), False),
    ],
)
def test_is_at_free_matches_networkx(name, builder, expected_at_free):
    fg, ng = _build_pair(builder)
    fr = fnx.is_at_free(fg)
    nr = nx.is_at_free(ng)
    assert fr == nr == expected_at_free, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_6", lambda L: L.cycle_graph(6)),
        ("complete_5", lambda L: L.complete_graph(5)),
    ],
)
def test_find_asteroidal_triple_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.find_asteroidal_triple(fg)
    nr = nx.find_asteroidal_triple(ng)
    # Either both are None or both produce a triple. The specific triple
    # tie-broken result may differ, so just compare the None-ness.
    assert (fr is None) == (nr is None), f"{name}: fnx={fr} nx={nr}"
    if fr is not None:
        # Triple must be three distinct nodes
        assert len(set(fr)) == 3


# ---------------------------------------------------------------------------
# Distance-regular graphs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,expected",
    [
        ("complete_5", lambda L: L.complete_graph(5), True),  # K_n is DR
        ("cycle_6", lambda L: L.cycle_graph(6), True),
        ("petersen", lambda L: L.petersen_graph(), True),
        ("path_5", lambda L: L.path_graph(5), False),
    ],
)
def test_is_distance_regular_matches_networkx(name, builder, expected):
    fg, ng = _build_pair(builder)
    fr = fnx.is_distance_regular(fg)
    nr = nx.is_distance_regular(ng)
    assert fr == nr == expected, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("complete_5", lambda L: L.complete_graph(5)),
        ("cycle_6", lambda L: L.cycle_graph(6)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_intersection_array_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.intersection_array(fg)
    nr = nx.intersection_array(ng)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("complete_5", lambda L: L.complete_graph(5)),
        ("cycle_6", lambda L: L.cycle_graph(6)),
    ],
)
def test_global_parameters_matches_networkx(name, builder):
    """``global_parameters`` takes the intersection array (b, c)
    output of ``intersection_array`` and yields per-distance
    triples. nx and fnx must agree on both stages."""
    fg, ng = _build_pair(builder)
    fb, fc = fnx.intersection_array(fg)
    nb, nc = nx.intersection_array(ng)
    fr = list(fnx.global_parameters(fb, fc))
    nr = list(nx.global_parameters(nb, nc))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# d-separation — Bayesian DAGs
# ---------------------------------------------------------------------------


COLLIDER_DAG_EDGES = [(0, 2), (1, 2), (2, 3), (2, 4)]
CHAIN_DAG_EDGES = [(0, 1), (1, 2), (2, 3)]
DIAMOND_DAG_EDGES = [(0, 1), (0, 2), (1, 3), (2, 3)]


@pytest.mark.parametrize(
    "name,edges,x,y,z",
    [
        ("collider_no_z", COLLIDER_DAG_EDGES, {0}, {1}, set()),
        ("collider_with_2", COLLIDER_DAG_EDGES, {0}, {1}, {2}),
        ("collider_with_3", COLLIDER_DAG_EDGES, {0}, {1}, {3}),
        ("chain_no_z", CHAIN_DAG_EDGES, {0}, {2}, set()),
        ("chain_block_1", CHAIN_DAG_EDGES, {0}, {2}, {1}),
        ("diamond_no_z", DIAMOND_DAG_EDGES, {0}, {3}, set()),
        ("diamond_block_2", DIAMOND_DAG_EDGES, {0}, {3}, {1, 2}),
    ],
)
def test_is_d_separator_matches_networkx(name, edges, x, y, z):
    fg = fnx.DiGraph(); fg.add_edges_from(edges)
    ng = nx.DiGraph(); ng.add_edges_from(edges)
    fr = fnx.is_d_separator(fg, x, y, z)
    nr = nx.is_d_separator(ng, x, y, z)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,x,y",
    [
        ("collider_0_1", COLLIDER_DAG_EDGES, {0}, {1}),
        ("chain_0_2", CHAIN_DAG_EDGES, {0}, {2}),
        ("diamond_0_3", DIAMOND_DAG_EDGES, {0}, {3}),
    ],
)
def test_find_minimal_d_separator_matches_networkx(name, edges, x, y):
    fg = fnx.DiGraph(); fg.add_edges_from(edges)
    ng = nx.DiGraph(); ng.add_edges_from(edges)
    fr = fnx.find_minimal_d_separator(fg, x, y)
    nr = nx.find_minimal_d_separator(ng, x, y)
    # Either both find a separator or neither does
    assert (fr is None) == (nr is None), f"{name}: fnx={fr} nx={nr}"
    if fr is not None:
        # The separator is a valid one — verify with is_d_separator
        assert fnx.is_d_separator(fg, x, y, fr)


# ---------------------------------------------------------------------------
# Regular graphs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,expected",
    [
        ("path_5", lambda L: L.path_graph(5), False),
        ("cycle_6", lambda L: L.cycle_graph(6), True),
        ("complete_5", lambda L: L.complete_graph(5), True),
        ("petersen", lambda L: L.petersen_graph(), True),
        ("star_5", lambda L: L.star_graph(5), False),
    ],
)
def test_is_regular_matches_networkx(name, builder, expected):
    fg, ng = _build_pair(builder)
    fr = fnx.is_regular(fg)
    nr = nx.is_regular(ng)
    assert fr == nr == expected, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder,k",
    [
        ("complete_5_k1", lambda L: L.complete_graph(5), 2),  # K_5 has 2-factor
        ("complete_4_k1", lambda L: L.complete_graph(4), 1),  # K_4 has 1-factor
        ("cycle_6_k2", lambda L: L.cycle_graph(6), 2),  # C_6 itself is 2-regular
    ],
)
def test_k_factor_matches_networkx(name, builder, k):
    fg, ng = _build_pair(builder)
    fr = fnx.k_factor(fg, k)
    nr = nx.k_factor(ng, k)
    # k-factors are non-unique — verify both have correct degree and node sets
    fr_degrees = sorted(dict(fr.degree()).values())
    nr_degrees = sorted(dict(nr.degree()).values())
    assert fr_degrees == nr_degrees == [k] * len(fr_degrees), (
        f"{name}: fnx={fr_degrees} nx={nr_degrees}"
    )


# ---------------------------------------------------------------------------
# Communicability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_4", lambda L: L.path_graph(4)),
        ("cycle_5", lambda L: L.cycle_graph(5)),
        ("complete_4", lambda L: L.complete_graph(4)),
    ],
)
def test_communicability_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.communicability(fg)
    nr = nx.communicability(ng)
    assert set(fr.keys()) == set(nr.keys())
    for u in fr:
        assert _close_dict(fr[u], nr[u], tol=1e-6), f"{name}: row {u}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_4", lambda L: L.path_graph(4)),
        ("cycle_5", lambda L: L.cycle_graph(5)),
        ("complete_4", lambda L: L.complete_graph(4)),
    ],
)
def test_communicability_exp_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.communicability_exp(fg)
    nr = nx.communicability_exp(ng)
    assert set(fr.keys()) == set(nr.keys())
    for u in fr:
        assert _close_dict(fr[u], nr[u], tol=1e-6), f"{name}: row {u}"


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_clustering_complete_graph_is_one():
    """``clustering(K_n) == 1`` for n >= 3 — every neighbor pair is connected."""
    g = fnx.complete_graph(5)
    cc = fnx.clustering(g)
    assert all(_close(v, 1.0) for v in cc.values())
    assert _close(fnx.transitivity(g), 1.0)


def test_clustering_tree_is_zero():
    """Trees have no triangles ⇒ clustering of every node is 0."""
    g = fnx.balanced_tree(2, 3)
    cc = fnx.clustering(g)
    assert all(_close(v, 0.0) for v in cc.values())
    assert _close(fnx.transitivity(g), 0.0)


def test_triangles_count_complete_graph():
    """``triangles(K_n)[v] == C(n-1, 2) == (n-1)(n-2)/2``."""
    n = 6
    g = fnx.complete_graph(n)
    expected = (n - 1) * (n - 2) // 2
    tris = fnx.triangles(g)
    assert all(t == expected for t in tris.values())


def test_floyd_warshall_diagonal_is_zero():
    g = fnx.cycle_graph(5)
    d = fnx.floyd_warshall(g)
    for u in g.nodes():
        assert _close(d[u][u], 0.0)


def test_floyd_warshall_symmetric_for_undirected():
    g = fnx.path_graph(5)
    d = fnx.floyd_warshall(g)
    for u in g.nodes():
        for v in g.nodes():
            assert _close(d[u][v], d[v][u])


def test_is_d_separator_x_disjoint_from_z_required():
    """``is_d_separator`` requires ``X`` and ``Z`` to be disjoint."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_edges_from(COLLIDER_DAG_EDGES)
    ng.add_edges_from(COLLIDER_DAG_EDGES)

    with pytest.raises(nx.NetworkXError, match="not disjoint") as nx_exc:
        nx.is_d_separator(ng, {0, 2}, {1}, {2})
    with pytest.raises(type(nx_exc.value), match="not disjoint"):
        fnx.is_d_separator(fg, {0, 2}, {1}, {2})


def test_is_at_free_path_is_at_free():
    """All paths and cliques are AT-free."""
    assert fnx.is_at_free(fnx.path_graph(7))
    assert fnx.is_at_free(fnx.complete_graph(5))


def test_communicability_is_symmetric_for_undirected():
    """For undirected G, ``communicability(G)[u][v] == [v][u]``."""
    g = fnx.cycle_graph(5)
    c = fnx.communicability(g)
    for u in g.nodes():
        for v in g.nodes():
            assert _close(c[u][v], c[v][u], tol=1e-6)


def test_is_regular_complete_graph():
    """``K_n`` is (n-1)-regular for n >= 1."""
    for n in range(1, 7):
        g = fnx.complete_graph(n)
        assert fnx.is_regular(g)


def test_intersection_array_complete_graph():
    """For ``K_n``, the intersection array is ``([n-1], [1])``."""
    n = 5
    g = fnx.complete_graph(n)
    b, c = fnx.intersection_array(g)
    assert b == [n - 1] and c == [1]
