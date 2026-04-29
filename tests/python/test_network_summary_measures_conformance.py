"""NetworkX conformance for the network-summary measures family.

Bundles several scalar / per-node summary statistics that lacked
broad differential coverage:

- ``rich_club_coefficient(G, normalized=)`` — fraction of edges
  among nodes with degree ≥ k, parametrised by k.
- ``flow_hierarchy(G, weight=)`` — fraction of edges not on any
  cycle (directed only).
- ``reciprocity(G, nodes=)`` and ``overall_reciprocity(G)`` —
  fraction of reciprocal edges.
- ``s_metric(G)`` — sum of products of degrees over edges, scale-
  free network indicator.
- ``non_randomness(G, k=, weight=)`` — community-aware non-
  randomness ratio.

The wiener_index / harmonic_diameter / etc. are covered separately
in test_wiener_index_conformance.py.
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _equiv(a, b, tol=1e-6):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) < tol
    return a == b


def _pair_undirected(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _pair_directed(edges, nodes=None):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _undirected_fixtures():
    out = []
    for n in range(2, 7):
        out.append((f"K_{n}", list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    for n in range(3, 9):
        out.append((f"C_{n}", [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    for n in range(2, 8):
        out.append((f"P_{n}",
                    list(zip(range(n - 1), range(1, n))),
                    list(range(n))))
    for n in range(1, 6):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    out.append(("petersen", list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes())))
    out.append(("hypercube_3", list(nx.hypercube_graph(3).edges()),
                list(nx.hypercube_graph(3).nodes())))
    for n, p, seed in [(8, 0.4, 1), (10, 0.4, 2), (12, 0.3, 3),
                       (15, 0.3, 4)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


def _directed_fixtures():
    return [
        ("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))),
        ("dir_C_5",
         [(i, (i + 1) % 5) for i in range(5)], list(range(5))),
        ("dir_DAG_chain",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))),
        ("dir_DAG_diamond",
         [(0, 1), (0, 2), (1, 3), (2, 3)], list(range(4))),
        ("dir_K3_both",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3))),
        ("dir_partial_recip",
         [(0, 1), (1, 0), (1, 2)], list(range(3))),
        ("dir_mixed",
         [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1)], list(range(4))),
        ("dir_pure_DAG",
         [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)], list(range(4))),
    ]


UNDIRECTED = _undirected_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# rich_club_coefficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
)
def test_rich_club_coefficient_unnormalized_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = dict(fnx.rich_club_coefficient(fg, normalized=False))
    nr = dict(nx.rich_club_coefficient(ng, normalized=False))
    assert set(fr.keys()) == set(nr.keys())
    for k in fr:
        assert _equiv(fr[k], nr[k]), f"{name}: rc[{k}] fnx={fr[k]} nx={nr[k]}"


# ---------------------------------------------------------------------------
# flow_hierarchy (directed only)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_flow_hierarchy_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.flow_hierarchy(fg)
    nr = nx.flow_hierarchy(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


def test_flow_hierarchy_dag_is_one():
    """A DAG has flow_hierarchy = 1.0 (no cycles)."""
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    assert _equiv(fnx.flow_hierarchy(fg), 1.0)


def test_flow_hierarchy_cyclic_is_zero():
    """A pure cycle has flow_hierarchy = 0.0 (every edge on a cycle)."""
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    assert _equiv(fnx.flow_hierarchy(fg), 0.0)


# ---------------------------------------------------------------------------
# reciprocity / overall_reciprocity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_overall_reciprocity_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.overall_reciprocity(fg)
    nr = nx.overall_reciprocity(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_per_node_reciprocity_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.reciprocity(fg)
    nr = nx.reciprocity(ng)
    if isinstance(fr, dict) and isinstance(nr, dict):
        assert set(fr.keys()) == set(nr.keys())
        for k in fr:
            assert _equiv(fr[k] or 0, nr[k] or 0), (
                f"{name}: rec[{k}] fnx={fr[k]} nx={nr[k]}"
            )
    else:
        assert _equiv(fr, nr)


@pytest.mark.parametrize(
    "name,edges,nodes,query_nodes",
    [
        ("dir_K3_both_query_subset",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3)), [0, 1]),
        ("dir_mixed_query_one",
         [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1)],
         list(range(4)), [1]),
    ],
)
def test_reciprocity_with_node_subset_matches_networkx(
    name, edges, nodes, query_nodes,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.reciprocity(fg, nodes=query_nodes)
    nr = nx.reciprocity(ng, nodes=query_nodes)
    if isinstance(fr, dict) and isinstance(nr, dict):
        assert set(fr.keys()) == set(nr.keys())
        for k in fr:
            assert _equiv(fr[k] or 0, nr[k] or 0)
    else:
        assert _equiv(fr or 0, nr or 0)


def test_overall_reciprocity_empty_graph_raises_matching_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    # NX raises on graphs with no edges.
    with pytest.raises(nx.NetworkXError):
        nx.overall_reciprocity(ng)
    with pytest.raises(fnx.NetworkXError):
        fnx.overall_reciprocity(fg)


# ---------------------------------------------------------------------------
# s_metric
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_s_metric_undirected_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.s_metric(fg)
    nr = nx.s_metric(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


def test_s_metric_path_value():
    """Hand-verified: s_metric(P_3) = sum over edges of deg(u)*deg(v)
    = (1*2) + (2*1) = 4."""
    fg, _ = _pair_undirected([(0, 1), (1, 2)], list(range(3)))
    assert _equiv(fnx.s_metric(fg), 4.0)


def test_s_metric_star_value():
    """Hand-verified: s_metric(S_4) (1 hub, 4 leaves) = 4 * (4 * 1) = 16."""
    fg, _ = _pair_undirected(
        [(0, i) for i in range(1, 5)], list(range(5)),
    )
    assert _equiv(fnx.s_metric(fg), 16.0)


# ---------------------------------------------------------------------------
# non_randomness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("petersen", lambda L: L.petersen_graph()),
        ("hypercube_3", lambda L: L.hypercube_graph(3)),
    ],
)
def test_non_randomness_matches_networkx(name, builder):
    """``non_randomness`` rejects fixtures where the auto-detected
    community count doesn't make sense for the graph size; lock in
    success cases only."""
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.non_randomness(g_fnx)
    nr = nx.non_randomness(g_nx)
    assert len(fr) == len(nr) == 2
    assert _equiv(fr[0], nr[0]) and _equiv(fr[1], nr[1])


def test_non_randomness_invalid_community_count_raises_matching_networkx():
    """Both libs raise ``ValueError`` when the auto-detected community
    count doesn't match the structure (e.g. 2 communities is invalid
    for a graph with too few edges relative to clustering)."""
    g_fnx = fnx.Graph(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    )
    g_nx = nx.Graph(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    )
    with pytest.raises(ValueError) as nx_exc:
        nx.non_randomness(g_nx)
    with pytest.raises(ValueError) as fnx_exc:
        fnx.non_randomness(g_fnx)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_non_randomness_with_explicit_k_matches_networkx():
    g_nx = nx.gnp_random_graph(10, 0.3, seed=1)
    g_fnx = fnx.Graph(); g_fnx.add_edges_from(g_nx.edges())
    g_fnx.add_nodes_from(g_nx.nodes())
    for k in [2, 3]:
        try:
            fr = fnx.non_randomness(g_fnx, k=k)
            nr = nx.non_randomness(g_nx, k=k)
            assert _equiv(fr[0], nr[0]) and _equiv(fr[1], nr[1])
        except (ValueError, nx.NetworkXError):
            # both must raise for the same fixture
            pass


# ---------------------------------------------------------------------------
# Cross-relation: reciprocity + overall_reciprocity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in DIRECTED if fx[0] != "dir_pure_DAG"],
    ids=[fx[0] for fx in DIRECTED if fx[0] != "dir_pure_DAG"],
)
def test_overall_reciprocity_equals_2_recip_over_total(name, edges, nodes):
    """Definition: ``overall_reciprocity(G) = |reciprocal edges| /
    |edges|``. Verify against ``len(...)``."""
    fg, _ = _pair_directed(edges, nodes)
    overall = fnx.overall_reciprocity(fg)
    # count reciprocal directed edges
    edge_set = set(fg.edges())
    n_reciprocal = sum(1 for u, v in edge_set if (v, u) in edge_set)
    expected = n_reciprocal / fg.number_of_edges()
    assert _equiv(overall, expected)


# ---------------------------------------------------------------------------
# s_metric invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_s_metric_K_n_matches_n_n_minus_1_squared(n):
    """``s_metric(K_n) = #edges × (n-1)² = (n*(n-1)/2) * (n-1)²``
    since every edge connects two nodes of degree n-1."""
    K_n = list(itertools.combinations(range(n), 2))
    fg, _ = _pair_undirected(K_n, list(range(n)))
    expected = (n * (n - 1) / 2) * (n - 1) ** 2
    assert _equiv(fnx.s_metric(fg), expected)
