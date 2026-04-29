"""NetworkX conformance for graph-metric algorithm families.

Bundles eleven small-but-important families with no current
conformance coverage:

- ``boundary``: ``edge_boundary``, ``node_boundary``
- ``cuts``: ``cut_size``, ``volume``, ``normalized_cut_size``,
  ``conductance``, ``edge_expansion``, ``mixing_expansion``,
  ``node_expansion``, ``boundary_expansion``
- ``isolate``: ``is_isolate``, ``isolates``, ``number_of_isolates``
- ``reciprocity``: ``reciprocity``, ``overall_reciprocity``
- ``richclub``: ``rich_club_coefficient`` (normalized=False — the
  randomized normalization mode is exercised separately by smallworld
  fixtures and is intentionally out-of-scope here)
- ``smetric``: ``s_metric``
- ``efficiency``: ``efficiency``, ``local_efficiency``,
  ``global_efficiency``
- ``hierarchy``: ``flow_hierarchy``
- ``non_randomness``: ``non_randomness``
- ``walks``: ``number_of_walks``
- ``kemeny``: ``kemeny_constant``

Each function gets cross-fixture parity tests; weighted and directed
variants are exercised where the function supports them. Cross-relation
invariants (e.g. ``volume(V) == 2*|E|`` undirected, ``is_isolate(v) iff
v in isolates(G)``) are asserted on top of the differential checks.
"""

from __future__ import annotations

import math

import pytest
import networkx as nx

import franken_networkx as fnx


def _equiv(a, b, tol=1e-6):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) and math.isinf(b):
            return (a > 0) == (b > 0)
        if math.isinf(a) or math.isinf(b):
            return False
        return abs(a - b) < tol
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_equiv(x, y, tol) for x, y in zip(a, b))
    return a == b


def _equiv_dict(a, b, tol=1e-6):
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_equiv(a[k], b[k], tol) for k in a)


def _build_pair(builder):
    """Build an ``(fnx, nx)`` graph pair from a builder lambda."""
    return builder(fnx), builder(nx)


# ---------------------------------------------------------------------------
# Fixture builders shared across families
# ---------------------------------------------------------------------------


UNDIRECTED_FIXTURES = [
    ("path_5", lambda L: L.path_graph(5)),
    ("path_8", lambda L: L.path_graph(8)),
    ("cycle_6", lambda L: L.cycle_graph(6)),
    ("complete_5", lambda L: L.complete_graph(5)),
    ("star_6", lambda L: L.star_graph(6)),
    ("petersen", lambda L: L.petersen_graph()),
    ("bull", lambda L: L.bull_graph()),
    ("diamond", lambda L: L.diamond_graph()),
    ("house", lambda L: L.house_graph()),
    ("krackhardt_kite", lambda L: L.krackhardt_kite_graph()),
]


DIRECTED_FIXTURES = [
    ("dir_cycle_4", lambda L: L.cycle_graph(4, create_using=L.DiGraph)),
    ("dir_path_5", lambda L: L.path_graph(5, create_using=L.DiGraph)),
    ("dir_balanced_tree",
     lambda L: L.balanced_tree(2, 3, create_using=L.DiGraph)),
]


def _digraph_with_some_reciprocal_edges(L):
    g = L.DiGraph()
    g.add_edges_from([(0, 1), (1, 0),  # reciprocal
                      (1, 2), (2, 3),  # one-way chain
                      (3, 1),          # cycle back
                      (4, 0),          # one-way to 0
                      (0, 4),          # reciprocates 4->0
                      ])
    return g


def _undirected_weighted(L):
    g = L.Graph()
    g.add_weighted_edges_from([
        (0, 1, 2.0), (1, 2, 3.0), (2, 3, 1.5),
        (0, 3, 5.0), (1, 3, 0.5), (3, 4, 2.0),
    ])
    return g


def _graph_with_isolates(L):
    g = L.Graph()
    g.add_nodes_from(range(8))
    g.add_edges_from([(0, 1), (1, 2), (3, 4)])  # 5,6,7 are isolates
    return g


# ---------------------------------------------------------------------------
# boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_edge_boundary_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    nodes = list(ng.nodes())
    if len(nodes) < 4:
        pytest.skip("too small")
    half = len(nodes) // 2
    S = set(nodes[:half])
    T = set(nodes[half:])
    fr = sorted(tuple(sorted(e)) for e in fnx.edge_boundary(fg, S, T))
    nr = sorted(tuple(sorted(e)) for e in nx.edge_boundary(ng, S, T))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_node_boundary_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    nodes = list(ng.nodes())
    if len(nodes) < 4:
        pytest.skip("too small")
    S = set(nodes[: len(nodes) // 2])
    fr = fnx.node_boundary(fg, S)
    nr = nx.node_boundary(ng, S)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_edge_boundary_weighted_data_matches_networkx():
    """``data=True`` returns edge attribute dicts."""
    fg = _undirected_weighted(fnx)
    ng = _undirected_weighted(nx)
    fr = sorted((tuple(sorted((u, v))), d.get("weight"))
                for u, v, d in fnx.edge_boundary(fg, {0, 1}, {2, 3, 4}, data=True))
    nr = sorted((tuple(sorted((u, v))), d.get("weight"))
                for u, v, d in nx.edge_boundary(ng, {0, 1}, {2, 3, 4}, data=True))
    assert fr == nr


# ---------------------------------------------------------------------------
# cuts — cut_size, volume, normalized_cut_size, conductance, expansions
# ---------------------------------------------------------------------------


CUT_FIXTURES = [
    ("path_6", [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
     {0, 1, 2}, {3, 4, 5}, list(range(6))),
    ("complete_5", [(u, v) for u in range(5) for v in range(u + 1, 5)],
     {0, 1}, {2, 3, 4}, list(range(5))),
    ("two_triangles_bridge",
     [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)],
     {0, 1, 2}, {3, 4, 5}, list(range(6))),
    ("disjoint",
     [(0, 1), (2, 3)],
     {0, 1}, {2, 3}, list(range(4))),
]


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    CUT_FIXTURES,
    ids=[fx[0] for fx in CUT_FIXTURES],
)
def test_cut_size_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert fg.size() == ng.size()
    assert _equiv(fnx.cut_size(fg, S, T), nx.cut_size(ng, S, T))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    CUT_FIXTURES,
    ids=[fx[0] for fx in CUT_FIXTURES],
)
def test_volume_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.volume(fg, S), nx.volume(ng, S))
    assert _equiv(fnx.volume(fg, T), nx.volume(ng, T))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    [fx for fx in CUT_FIXTURES if fx[0] != "disjoint"],
    ids=[fx[0] for fx in CUT_FIXTURES if fx[0] != "disjoint"],
)
def test_normalized_cut_size_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(
        fnx.normalized_cut_size(fg, S, T), nx.normalized_cut_size(ng, S, T)
    )


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    [fx for fx in CUT_FIXTURES if fx[0] != "disjoint"],
    ids=[fx[0] for fx in CUT_FIXTURES if fx[0] != "disjoint"],
)
def test_conductance_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.conductance(fg, S, T), nx.conductance(ng, S, T))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    CUT_FIXTURES,
    ids=[fx[0] for fx in CUT_FIXTURES],
)
def test_edge_expansion_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.edge_expansion(fg, S, T), nx.edge_expansion(ng, S, T))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    [fx for fx in CUT_FIXTURES if fx[0] != "disjoint"],
    ids=[fx[0] for fx in CUT_FIXTURES if fx[0] != "disjoint"],
)
def test_mixing_expansion_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.mixing_expansion(fg, S, T), nx.mixing_expansion(ng, S, T))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    CUT_FIXTURES,
    ids=[fx[0] for fx in CUT_FIXTURES],
)
def test_node_expansion_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.node_expansion(fg, S), nx.node_expansion(ng, S))


@pytest.mark.parametrize(
    "name,edges,S,T,nodes",
    CUT_FIXTURES,
    ids=[fx[0] for fx in CUT_FIXTURES],
)
def test_boundary_expansion_matches_networkx(name, edges, S, T, nodes):
    fg = fnx.Graph(); fg.add_nodes_from(nodes); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(nodes); ng.add_edges_from(edges)
    assert _equiv(fnx.boundary_expansion(fg, S), nx.boundary_expansion(ng, S))


def test_cut_volume_weighted_matches_networkx():
    fg = _undirected_weighted(fnx)
    ng = _undirected_weighted(nx)
    S = {0, 1}
    T = {2, 3, 4}
    assert _equiv(
        fnx.cut_size(fg, S, T, weight="weight"),
        nx.cut_size(ng, S, T, weight="weight"),
    )
    assert _equiv(
        fnx.volume(fg, S, weight="weight"),
        nx.volume(ng, S, weight="weight"),
    )
    assert _equiv(
        fnx.normalized_cut_size(fg, S, T, weight="weight"),
        nx.normalized_cut_size(ng, S, T, weight="weight"),
    )
    assert _equiv(
        fnx.conductance(fg, S, T, weight="weight"),
        nx.conductance(ng, S, T, weight="weight"),
    )


# ---------------------------------------------------------------------------
# isolate
# ---------------------------------------------------------------------------


def test_isolates_matches_networkx():
    fg = _graph_with_isolates(fnx)
    ng = _graph_with_isolates(nx)
    assert sorted(fnx.isolates(fg)) == sorted(nx.isolates(ng))
    assert fnx.number_of_isolates(fg) == nx.number_of_isolates(ng)
    for n in fg.nodes():
        assert fnx.is_isolate(fg, n) == nx.is_isolate(ng, n)


def test_isolates_directed_matches_networkx():
    """In digraphs, an isolate has zero in- AND out-edges."""
    fg = fnx.DiGraph()
    fg.add_nodes_from(range(6))
    fg.add_edges_from([(0, 1), (1, 2)])  # 3,4,5 are isolates
    ng = nx.DiGraph()
    ng.add_nodes_from(range(6))
    ng.add_edges_from([(0, 1), (1, 2)])
    assert sorted(fnx.isolates(fg)) == sorted(nx.isolates(ng))
    for n in fg.nodes():
        assert fnx.is_isolate(fg, n) == nx.is_isolate(ng, n)


# ---------------------------------------------------------------------------
# reciprocity
# ---------------------------------------------------------------------------


def test_overall_reciprocity_matches_networkx():
    fg = _digraph_with_some_reciprocal_edges(fnx)
    ng = _digraph_with_some_reciprocal_edges(nx)
    assert _equiv(fnx.overall_reciprocity(fg), nx.overall_reciprocity(ng))


def test_reciprocity_per_node_matches_networkx():
    fg = _digraph_with_some_reciprocal_edges(fnx)
    ng = _digraph_with_some_reciprocal_edges(nx)
    fr = fnx.reciprocity(fg, list(fg.nodes()))
    nr = nx.reciprocity(ng, list(ng.nodes()))
    assert _equiv_dict(fr, nr)


def test_reciprocity_for_undirected_raises():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)
    fnx_err = nx_err = None
    try:
        fnx.overall_reciprocity(fg)
    except Exception as e:
        fnx_err = type(e).__name__
    try:
        nx.overall_reciprocity(ng)
    except Exception as e:
        nx_err = type(e).__name__
    assert fnx_err == nx_err, f"fnx_err={fnx_err} nx_err={nx_err}"


# ---------------------------------------------------------------------------
# rich_club_coefficient (normalized=False)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_rich_club_coefficient_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    if ng.number_of_nodes() < 4:
        pytest.skip("too small")
    fr = fnx.rich_club_coefficient(fg, normalized=False)
    nr = nx.rich_club_coefficient(ng, normalized=False)
    assert _equiv_dict(fr, nr)


# ---------------------------------------------------------------------------
# s_metric
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_s_metric_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.s_metric(fg), nx.s_metric(ng))


# ---------------------------------------------------------------------------
# efficiency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_global_efficiency_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.global_efficiency(fg), nx.global_efficiency(ng))


@pytest.mark.parametrize("name,builder", UNDIRECTED_FIXTURES,
                         ids=[fx[0] for fx in UNDIRECTED_FIXTURES])
def test_local_efficiency_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.local_efficiency(fg), nx.local_efficiency(ng))


@pytest.mark.parametrize(
    "name,builder,u,v",
    [
        ("path_5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("path_5_mid", lambda L: L.path_graph(5), 1, 3),
        ("complete_5_pair", lambda L: L.complete_graph(5), 0, 4),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
    ],
)
def test_efficiency_pair_matches_networkx(name, builder, u, v):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.efficiency(fg, u, v), nx.efficiency(ng, u, v))


# ---------------------------------------------------------------------------
# flow_hierarchy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", DIRECTED_FIXTURES,
                         ids=[fx[0] for fx in DIRECTED_FIXTURES])
def test_flow_hierarchy_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.flow_hierarchy(fg), nx.flow_hierarchy(ng))


def test_flow_hierarchy_with_reciprocal_edges_matches_networkx():
    fg = _digraph_with_some_reciprocal_edges(fnx)
    ng = _digraph_with_some_reciprocal_edges(nx)
    assert _equiv(fnx.flow_hierarchy(fg), nx.flow_hierarchy(ng))


def test_flow_hierarchy_undirected_raises_matching():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    f_err = n_err = None
    try:
        fnx.flow_hierarchy(fg)
    except Exception as e:
        f_err = type(e).__name__
    try:
        nx.flow_hierarchy(ng)
    except Exception as e:
        n_err = type(e).__name__
    assert f_err == n_err


# ---------------------------------------------------------------------------
# non_randomness — needs k>=2 community count specified explicitly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,k",
    [
        # Connected, no self-loops, with 0 < p = 2km/(n(n-k)) < 1.
        ("path_6_k2", lambda L: L.path_graph(6), 2),       # n=6 m=5 p=20/24<1
        ("path_8_k2", lambda L: L.path_graph(8), 2),       # n=8 m=7 p<1
        ("cycle_8_k2", lambda L: L.cycle_graph(8), 2),     # n=8 m=8 p<1
        ("petersen_k2", lambda L: L.petersen_graph(), 2),  # n=10 m=15 p=60/80<1
    ],
)
def test_non_randomness_matches_networkx(name, builder, k):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.non_randomness(g_fnx, k=k)
    nr = nx.non_randomness(g_nx, k=k)
    # Returns a (non_randomness, relative_non_randomness) tuple.
    assert _equiv(fr, nr, tol=1e-5)


def test_non_randomness_invalid_k_matches_networkx_error():
    """fnx and nx share the same ``0 < p < 1`` validity check; both
    raise ValueError with the same wording when k is out of range."""
    g_fnx = fnx.petersen_graph()
    g_nx = nx.petersen_graph()
    fnx_err = nx_err = None
    try:
        fnx.non_randomness(g_fnx, k=3)
    except Exception as e:
        fnx_err = (type(e).__name__, str(e))
    try:
        nx.non_randomness(g_nx, k=3)
    except Exception as e:
        nx_err = (type(e).__name__, str(e))
    assert fnx_err == nx_err


# ---------------------------------------------------------------------------
# walks — number_of_walks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_4", lambda L: L.cycle_graph(4)),
        ("complete_4", lambda L: L.complete_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_number_of_walks_matches_networkx(name, builder, k):
    fg, ng = _build_pair(builder)
    fr = fnx.number_of_walks(fg, k)
    nr = nx.number_of_walks(ng, k)
    assert set(fr.keys()) == set(nr.keys())
    for u in fr:
        assert _equiv_dict(fr[u], nr[u])


def test_number_of_walks_directed_matches_networkx():
    fg = fnx.cycle_graph(4, create_using=fnx.DiGraph)
    ng = nx.cycle_graph(4, create_using=nx.DiGraph)
    for k in (1, 2, 3, 4):
        fr = fnx.number_of_walks(fg, k)
        nr = nx.number_of_walks(ng, k)
        for u in fr:
            assert _equiv_dict(fr[u], nr[u])


# ---------------------------------------------------------------------------
# kemeny_constant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_5", lambda L: L.cycle_graph(5)),
        ("complete_4", lambda L: L.complete_graph(4)),
        ("complete_5", lambda L: L.complete_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_kemeny_constant_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    assert _equiv(fnx.kemeny_constant(fg), nx.kemeny_constant(ng), tol=1e-6)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_isolates_invariants():
    """``is_isolate(v) iff v in isolates(G)``;
    ``number_of_isolates == len(isolates(G))``."""
    g = _graph_with_isolates(fnx)
    iso = set(fnx.isolates(g))
    for n in g.nodes():
        assert fnx.is_isolate(g, n) == (n in iso)
    assert fnx.number_of_isolates(g) == len(iso)


def test_volume_full_set_equals_two_m_undirected():
    """For undirected graphs, ``volume(G, V) == 2 * |E|``."""
    g = fnx.path_graph(8)
    V = set(g.nodes())
    assert _equiv(fnx.volume(g, V), 2.0 * g.number_of_edges())


def test_cut_size_symmetric_undirected():
    """For undirected graphs, ``cut_size(S, T) == cut_size(T, S)``."""
    g = fnx.cycle_graph(6)
    S = {0, 1, 2}
    T = {3, 4, 5}
    assert _equiv(fnx.cut_size(g, S, T), fnx.cut_size(g, T, S))


def test_edge_boundary_subset_of_global_boundary():
    """``edge_boundary(S, T) ⊆ edge_boundary(S, V\\S)`` for any T ⊆ V\\S."""
    g = fnx.cycle_graph(6)
    S = {0, 1, 2}
    T = {3, 4}  # strict subset of V\S
    eb_T = {tuple(sorted(e)) for e in fnx.edge_boundary(g, S, T)}
    eb_full = {tuple(sorted(e)) for e in fnx.edge_boundary(g, S)}
    assert eb_T.issubset(eb_full)


def test_s_metric_equals_sum_degree_products():
    """``s_metric(G) == sum_{(u,v) in E} deg(u)*deg(v)``."""
    g = fnx.house_graph()
    expected = sum(g.degree(u) * g.degree(v) for u, v in g.edges())
    assert _equiv(fnx.s_metric(g), float(expected))


def test_efficiency_pair_is_inverse_of_distance():
    """``efficiency(u, v) == 1 / d(u, v)`` for connected u != v."""
    g = fnx.path_graph(5)
    # d(0, 4) = 4 ⇒ efficiency = 1/4
    assert _equiv(fnx.efficiency(g, 0, 4), 0.25)
    assert _equiv(fnx.efficiency(g, 1, 3), 0.5)


def test_overall_reciprocity_within_zero_one():
    """``overall_reciprocity in [0, 1]`` for any digraph with edges."""
    g = _digraph_with_some_reciprocal_edges(fnx)
    r = fnx.overall_reciprocity(g)
    assert 0.0 <= r <= 1.0


def test_number_of_walks_k1_equals_adjacency():
    """``number_of_walks(G, 1)[u][v]`` is 1 if (u,v) in E else 0
    (for simple unweighted G)."""
    g = fnx.cycle_graph(4)
    walks = fnx.number_of_walks(g, 1)
    nodes = list(g.nodes())
    for u in nodes:
        for v in nodes:
            assert walks[u][v] == (1 if g.has_edge(u, v) else 0)


def test_global_efficiency_complete_is_one():
    """``global_efficiency(K_n) == 1.0`` (all pairs distance 1)."""
    g = fnx.complete_graph(5)
    assert _equiv(fnx.global_efficiency(g), 1.0)
