"""NetworkX conformance for the graph-similarity algorithm family.

Existing ``test_graph_edit_distance_signature_parity.py`` covers
function-signature parity. Add a behavioral conformance harness that
asserts algorithm OUTPUT (edit distance, edit paths, simrank
scores) parity across small fixtures.

Covered functions:

- ``graph_edit_distance(G1, G2, ...)`` — exact GED via local
  Python implementation (bounded to small graphs; fnx caps total
  nodes at 8 by design and raises ``NetworkXNotImplemented`` past
  that).
- ``optimal_edit_paths(G1, G2)`` — yields (path, cost) tuples.
- ``simrank_similarity(G, source=, target=, ...)`` — recursive
  similarity scores.

Documented fnx limit: ``graph_edit_distance`` raises
``NetworkXNotImplemented("local optimal_edit_paths is bounded to
small simple graphs")`` when ``G1.number_of_nodes() +
G2.number_of_nodes() > 8`` — the local Python solver is exponential.
NX's iterative variant handles larger graphs but is also slow.
Harness respects the documented limit.
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _equiv(a, b, tol=1e-9):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) < tol
    return a == b


# ---------------------------------------------------------------------------
# Fixture pairs — total nodes ≤ 8 to stay within fnx's documented limit
# ---------------------------------------------------------------------------


GED_FIXTURES = [
    ("identical_K2",
     lambda L: L.complete_graph(2),
     lambda L: L.complete_graph(2)),
    ("identical_K3",
     lambda L: L.complete_graph(3),
     lambda L: L.complete_graph(3)),
    ("identical_K4",
     lambda L: L.complete_graph(4),
     lambda L: L.complete_graph(4)),
    ("K2_vs_K3",
     lambda L: L.complete_graph(2),
     lambda L: L.complete_graph(3)),
    ("K3_vs_K4",
     lambda L: L.complete_graph(3),
     lambda L: L.complete_graph(4)),
    ("P_3_vs_C_3",
     lambda L: L.path_graph(3),
     lambda L: L.cycle_graph(3)),
    ("P_3_vs_S_2",
     lambda L: L.path_graph(3),
     lambda L: L.star_graph(2)),
    ("P_4_vs_C_4",
     lambda L: L.path_graph(4),
     lambda L: L.cycle_graph(4)),
    ("S_3_vs_P_3",
     lambda L: L.star_graph(3),
     lambda L: L.path_graph(3)),
    ("C_3_vs_S_3",
     lambda L: L.cycle_graph(3),
     lambda L: L.star_graph(3)),
    ("empty_vs_K_2",
     lambda L: L.empty_graph(2),
     lambda L: L.complete_graph(2)),
    ("singleton_vs_singleton",
     lambda L: L.empty_graph(1),
     lambda L: L.empty_graph(1)),
    ("singleton_vs_K_2",
     lambda L: L.empty_graph(1),
     lambda L: L.complete_graph(2)),
]


def _build_pair(builder_a, builder_b):
    return builder_a(fnx), builder_a(nx), builder_b(fnx), builder_b(nx)


# ---------------------------------------------------------------------------
# graph_edit_distance — exact value parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,build_a,build_b", GED_FIXTURES,
                         ids=[fx[0] for fx in GED_FIXTURES])
def test_graph_edit_distance_matches_networkx(name, build_a, build_b):
    fg_a, ng_a, fg_b, ng_b = _build_pair(build_a, build_b)
    fr = fnx.graph_edit_distance(fg_a, fg_b)
    nr = nx.graph_edit_distance(ng_a, ng_b)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


def test_graph_edit_distance_edge_subst_cost_can_exceed_delete_insert_cost():
    fg_a = fnx.Graph()
    fg_b = fnx.Graph()
    ng_a = nx.Graph()
    ng_b = nx.Graph()
    for graph in (fg_a, ng_a):
        graph.add_edge(0, 1, kind="left")
    for graph in (fg_b, ng_b):
        graph.add_edge(0, 1, kind="right")

    def edge_subst_cost(left_attrs, right_attrs):
        return 0 if left_attrs.get("kind") == right_attrs.get("kind") else 5

    fr = fnx.graph_edit_distance(
        fg_a,
        fg_b,
        edge_subst_cost=edge_subst_cost,
    )
    nr = nx.graph_edit_distance(
        ng_a,
        ng_b,
        edge_subst_cost=edge_subst_cost,
    )
    assert _equiv(fr, nr)
    assert _equiv(fr, 2.0)


@pytest.mark.parametrize("name,build_a,build_b", GED_FIXTURES,
                         ids=[fx[0] for fx in GED_FIXTURES])
def test_graph_edit_distance_is_symmetric(name, build_a, build_b):
    """``ged(G1, G2) == ged(G2, G1)`` (the metric is symmetric)."""
    fg_a, _, fg_b, _ = _build_pair(build_a, build_b)
    fwd = fnx.graph_edit_distance(fg_a, fg_b)
    rev = fnx.graph_edit_distance(fg_b, fg_a)
    assert _equiv(fwd, rev), f"{name}: fwd={fwd} rev={rev}"


@pytest.mark.parametrize("name,builder", [
    ("K_3", lambda L: L.complete_graph(3)),
    ("P_4", lambda L: L.path_graph(4)),
    ("C_3", lambda L: L.cycle_graph(3)),
])
def test_graph_edit_distance_self_is_zero(name, builder):
    """``ged(G, G) == 0`` for any G."""
    g_fnx = builder(fnx)
    assert fnx.graph_edit_distance(g_fnx, g_fnx) == 0.0


# ---------------------------------------------------------------------------
# Documented limit: > 8 total nodes raises NetworkXNotImplemented
# ---------------------------------------------------------------------------


def test_graph_edit_distance_too_large_raises_matching_documented_limit():
    """fnx caps the local solver at 8 total nodes — past that, raise
    ``NetworkXNotImplemented`` with the documented wording."""
    g_a = fnx.path_graph(5)
    g_b = fnx.cycle_graph(5)
    # 5 + 5 = 10 > 8
    with pytest.raises(fnx.NetworkXNotImplemented) as exc:
        fnx.graph_edit_distance(g_a, g_b)
    assert "small simple graphs" in str(exc.value)


# ---------------------------------------------------------------------------
# optimal_edit_paths — cost parity (paths may differ between equivalent
# tie-broken solutions, but cost is unique)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,build_a,build_b", GED_FIXTURES,
                         ids=[fx[0] for fx in GED_FIXTURES])
def test_optimal_edit_paths_cost_matches_networkx(name, build_a, build_b):
    fg_a, ng_a, fg_b, ng_b = _build_pair(build_a, build_b)
    _, fr_cost = fnx.optimal_edit_paths(fg_a, fg_b)
    _, nr_cost = nx.optimal_edit_paths(ng_a, ng_b)
    assert _equiv(fr_cost, nr_cost), (
        f"{name}: fnx_cost={fr_cost} nx_cost={nr_cost}"
    )


@pytest.mark.parametrize("name,build_a,build_b", GED_FIXTURES,
                         ids=[fx[0] for fx in GED_FIXTURES])
def test_optimal_edit_paths_cost_equals_graph_edit_distance(
    name, build_a, build_b,
):
    """``optimal_edit_paths`` returns ``(paths, cost)`` where ``cost``
    must equal ``graph_edit_distance(G1, G2)``."""
    fg_a, _, fg_b, _ = _build_pair(build_a, build_b)
    _, paths_cost = fnx.optimal_edit_paths(fg_a, fg_b)
    ged = fnx.graph_edit_distance(fg_a, fg_b)
    assert _equiv(paths_cost, ged)


# ---------------------------------------------------------------------------
# simrank_similarity — full-matrix, single-source, single-pair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("C_5", lambda L: L.cycle_graph(5)),
        ("S_4_star", lambda L: L.star_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_simrank_similarity_all_pairs_matches_networkx(name, builder):
    g_fnx = builder(fnx)
    g_nx = builder(nx)
    fr = fnx.simrank_similarity(g_fnx)
    nr = nx.simrank_similarity(g_nx)
    # Both return dict-of-dicts mapping node -> dict of similarities.
    assert set(fr.keys()) == set(nr.keys())
    for u in fr:
        assert set(fr[u].keys()) == set(nr[u].keys())
        for v in fr[u]:
            assert _equiv(fr[u][v], nr[u][v], tol=1e-6), (
                f"{name}: simrank[{u}][{v}] fnx={fr[u][v]} nx={nr[u][v]}"
            )


@pytest.mark.parametrize(
    "name,builder,source",
    [
        ("path_5_src_0", lambda L: L.path_graph(5), 0),
        ("path_5_src_2", lambda L: L.path_graph(5), 2),
        ("K_4_src_1", lambda L: L.complete_graph(4), 1),
        ("petersen_src_0", lambda L: L.petersen_graph(), 0),
    ],
)
def test_simrank_similarity_single_source_matches_networkx(
    name, builder, source,
):
    g_fnx = builder(fnx)
    g_nx = builder(nx)
    fr = fnx.simrank_similarity(g_fnx, source=source)
    nr = nx.simrank_similarity(g_nx, source=source)
    assert set(fr.keys()) == set(nr.keys())
    for v in fr:
        assert _equiv(fr[v], nr[v], tol=1e-6), (
            f"{name}: simrank[{v}] fnx={fr[v]} nx={nr[v]}"
        )


@pytest.mark.parametrize(
    "name,builder,source,target",
    [
        ("path_5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("path_5_mid", lambda L: L.path_graph(5), 1, 3),
        ("K_4_two_nodes", lambda L: L.complete_graph(4), 0, 2),
        ("S_4_leaf_pair", lambda L: L.star_graph(4), 1, 2),
    ],
)
def test_simrank_similarity_single_pair_matches_networkx(
    name, builder, source, target,
):
    g_fnx = builder(fnx)
    g_nx = builder(nx)
    fr = fnx.simrank_similarity(g_fnx, source=source, target=target)
    nr = nx.simrank_similarity(g_nx, source=source, target=target)
    assert _equiv(fr, nr, tol=1e-6), (
        f"{name}: fnx={fr} nx={nr}"
    )


# ---------------------------------------------------------------------------
# simrank invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("C_6", lambda L: L.cycle_graph(6)),
    ],
)
def test_simrank_self_similarity_is_one(name, builder):
    """``simrank(u, u) == 1`` by definition."""
    g_fnx = builder(fnx)
    sim = fnx.simrank_similarity(g_fnx)
    for u in g_fnx.nodes():
        assert _equiv(sim[u][u], 1.0), (
            f"{name}: simrank[{u}][{u}] = {sim[u][u]} != 1.0"
        )


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("C_5", lambda L: L.cycle_graph(5)),
    ],
)
def test_simrank_is_symmetric(name, builder):
    """``simrank(u, v) == simrank(v, u)`` for undirected graphs."""
    g_fnx = builder(fnx)
    sim = fnx.simrank_similarity(g_fnx)
    nodes = list(g_fnx.nodes())
    for u in nodes:
        for v in nodes:
            assert _equiv(sim[u][v], sim[v][u], tol=1e-6), (
                f"{name}: simrank[{u}][{v}]={sim[u][v]} != "
                f"simrank[{v}][{u}]={sim[v][u]}"
            )
