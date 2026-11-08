"""NetworkX conformance for the graph-similarity algorithm family.

Existing ``test_graph_edit_distance_signature_parity.py`` covers
function-signature parity. Add a behavioral conformance harness that
asserts algorithm OUTPUT (edit distance, edit paths, simrank
scores) parity across small fixtures.

Covered functions:

- ``graph_edit_distance(G1, G2, ...)`` — exact simple-graph GED,
  or the best complete cost found before a requested timeout.
- ``optimal_edit_paths(G1, G2)`` — collects optimal paths and their cost.
- ``optimize_edit_paths`` and ``optimize_graph_edit_distance`` —
  incremental improving results with bounded prefix consumption.
- ``simrank_similarity(G, source=, target=, ...)`` — recursive
  similarity scores.

Exact edit search can be exponential. Most exhaustive fixtures are small;
larger fixtures exercise prefix work and the former eight-node boundary.
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
# Small fixture pairs for bounded exhaustive comparisons
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

    paths, cost = fnx.optimal_edit_paths(fg_a, fg_b, edge_subst_cost=edge_subst_cost)
    assert cost == 2.0
    assert paths
    for _, edge_path in paths:
        # The reported cost must be realized by the returned operations.
        assert edge_path == [((0, 1), None), (None, (0, 1))]


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
# Incremental search, time limits, and larger simple graphs
# ---------------------------------------------------------------------------


def test_graph_edit_distance_beyond_former_eight_node_limit():
    g_a = fnx.path_graph(5)
    g_b = fnx.cycle_graph(5)
    expected = nx.graph_edit_distance(nx.path_graph(5), nx.cycle_graph(5))
    assert fnx.graph_edit_distance(g_a, g_b) == expected == 1.0
    assert fnx.optimal_edit_paths(g_a, g_b)[1] == expected
    assert list(fnx.optimize_graph_edit_distance(g_a, g_b))[-1] == expected


def test_edit_search_prefix_does_not_depend_on_python_recursion_limit():
    graph = fnx.path_graph(1200)
    paths = fnx.optimize_edit_paths(graph, graph)
    nodes, edges, cost = next(paths)
    assert cost == 0.0
    assert len(nodes) == 1200
    assert len(edges) == 1199
    paths.close()


@pytest.mark.parametrize("timeout", [0, -1])
def test_edit_search_timeout_validation_matches_networkx(timeout):
    for lib in (fnx, nx):
        graph = lib.path_graph(3)
        with pytest.raises(lib.NetworkXError, match="Timeout value must be greater than 0"):
            lib.graph_edit_distance(graph, graph, timeout=timeout)
        with pytest.raises(lib.NodeNotFound, match="Root node not in graph"):
            lib.graph_edit_distance(graph, graph, roots=(0, "absent"), timeout=timeout)


def test_edit_search_timeout_stops_after_a_complete_incumbent(monkeypatch):
    import time

    clock = [0.0]
    monkeypatch.setattr(time, "perf_counter", lambda: clock[0])
    left, right = fnx.path_graph(4), fnx.star_graph(3)
    paths = fnx.optimize_edit_paths(left, right, timeout=1)
    assert next(paths)[2] == 4.0
    clock[0] = 2.0
    assert list(paths) == []

    # Advance the controlled clock when the real search yields its first
    # complete script; the public distance API must return that incumbent.
    original = fnx.optimize_edit_paths

    def expire_after_first(*args, **kwargs):
        for result in original(*args, **kwargs):
            yield result
            clock[0] = 2.0

    clock[0] = 0.0
    monkeypatch.setattr(fnx, "optimize_edit_paths", expire_after_first)
    assert fnx.graph_edit_distance(left, right, timeout=1) == 4.0


def test_edit_search_timeout_before_any_result_returns_none(monkeypatch):
    import time

    calls = itertools.count()
    monkeypatch.setattr(time, "perf_counter", lambda: float(next(calls)))
    graph = fnx.path_graph(3)
    assert fnx.graph_edit_distance(graph, graph, timeout=0.5) is None
    assert list(fnx.optimize_edit_paths(graph, graph, timeout=0.5)) == []


def test_edit_search_callbacks_are_lazy_and_see_original_attribute_dicts():
    left, right = nx.path_graph(2), nx.path_graph(2)
    seen_nodes, seen_edges = [], []

    def node_cost(a, b):
        assert any(a is left.nodes[u] for u in left)
        assert any(b is right.nodes[u] for u in right)
        seen_nodes.append((id(a), id(b)))
        return 0

    def edge_cost(a, b):
        assert a is left.edges[0, 1]
        assert b is right.edges[0, 1]
        seen_edges.append((id(a), id(b)))
        return 0

    def unexpected_match(*args):
        raise AssertionError("explicit substitution costs take precedence")

    paths = fnx.optimize_edit_paths(
        left, right, node_match=unexpected_match, edge_match=unexpected_match,
        node_subst_cost=node_cost, edge_subst_cost=edge_cost,
    )
    assert not seen_nodes and not seen_edges
    assert next(paths)[2] == 0.0
    assert len(seen_nodes) == 4
    assert len(seen_edges) == 1
    paths.close()


@pytest.mark.parametrize("cost_kind", ["edge_ins_cost", "edge_del_cost"])
def test_edit_search_zero_edge_imbalance_with_infinite_cost(cost_kind):
    graph = fnx.path_graph(2)
    kwargs = {cost_kind: lambda attrs: math.inf}
    assert list(fnx.optimize_graph_edit_distance(graph, graph, **kwargs)) == [0.0]


@pytest.mark.parametrize("strict", [True, False])
def test_edit_search_upper_bound_and_equal_cost_paths(strict):
    left, right = fnx.cycle_graph(4), fnx.path_graph(4)
    paths = list(fnx.optimize_edit_paths(left, right, upper_bound=1, strictly_decreasing=strict))
    assert len(paths) == (1 if strict else 8)
    assert all(cost == 1.0 for _, _, cost in paths)
    assert list(fnx.optimize_edit_paths(left, right, upper_bound=0, strictly_decreasing=strict)) == []


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
