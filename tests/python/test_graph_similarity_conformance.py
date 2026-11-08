"""NetworkX conformance for the graph-similarity algorithm family.

Existing ``test_graph_edit_distance_signature_parity.py`` covers
function-signature parity. Add a behavioral conformance harness that
asserts algorithm OUTPUT (edit distance, edit paths, simrank
scores) parity across small fixtures.

Covered functions:

- ``graph_edit_distance(G1, G2, ...)`` — exact simple/multigraph GED,
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

from collections import Counter
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
# Parallel-edge assignments and keyed edit scripts
# ---------------------------------------------------------------------------


def _edit_script_cost(left, right, nodes, edges, **costs):
    """Check coverage/endpoints independently and sum the reported operations."""
    left_edges = list(left.edges(keys=True) if left.is_multigraph() else left.edges())
    right_edges = list(right.edges(keys=True) if right.is_multigraph() else right.edges())
    assert Counter(a for a, _ in nodes if a is not None) == Counter(left)
    assert Counter(b for _, b in nodes if b is not None) == Counter(right)
    assert Counter(a for a, _ in edges if a is not None) == Counter(left_edges)
    assert Counter(b for _, b in edges if b is not None) == Counter(right_edges)
    mapping = {a: b for a, b in nodes if a is not None and b is not None}
    total = 0.0
    for a, b in nodes:
        if a is None:
            total += costs.get("node_ins_cost", lambda d: 1)(right.nodes[b])
        elif b is None:
            total += costs.get("node_del_cost", lambda d: 1)(left.nodes[a])
        else:
            total += costs.get("node_subst_cost", lambda x, y: 0)(left.nodes[a], right.nodes[b])
    for a, b in edges:
        if a is None:
            total += costs.get("edge_ins_cost", lambda d: 1)(right.get_edge_data(*b))
        elif b is None:
            total += costs.get("edge_del_cost", lambda d: 1)(left.get_edge_data(*a))
        else:
            mapped = mapping[a[0]], mapping[a[1]]
            assert mapped == b[:2] or (not left.is_directed() and mapped == b[:2][::-1])
            total += costs.get("edge_subst_cost", lambda x, y: 0)(
                left.get_edge_data(*a), right.get_edge_data(*b)
            )
    return total


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "foreign"])
@pytest.mark.parametrize("counts", [(0, 0), (2, 1), (1, 3), (2, 2)])
def test_multigraph_edit_api_family_matches_networkx(graph_type, library, counts):
    left, right = getattr(library, graph_type)(), getattr(library, graph_type)()
    for graph, count, side in ((left, counts[0], "left"), (right, counts[1], "right")):
        graph.add_nodes_from([0, 1])
        for key in range(count):
            graph.add_edge(0, 1, key=(side, key))
    expected = abs(counts[0] - counts[1])
    oracle_left, oracle_right = getattr(nx, graph_type)(left), getattr(nx, graph_type)(right)
    assert nx.graph_edit_distance(oracle_left, oracle_right) == expected
    assert fnx.graph_edit_distance(left, right) == expected
    paths, cost = fnx.optimal_edit_paths(left, right)
    assert cost == expected
    assert paths
    for nodes, edges in paths:
        assert _edit_script_cost(left, right, nodes, edges) == cost
    improving = list(fnx.optimize_edit_paths(left, right))
    assert improving[-1][2] == expected
    for nodes, edges, value in improving:
        assert _edit_script_cost(left, right, nodes, edges) == value
    estimates = list(fnx.optimize_graph_edit_distance(left, right))
    assert estimates[-1] == expected
    assert all(a > b for a, b in zip(estimates, estimates[1:]))


@pytest.mark.parametrize("types", [("Graph", "MultiGraph"), ("DiGraph", "MultiDiGraph")])
@pytest.mark.parametrize("reverse", [False, True])
def test_graph_edit_mixed_simple_multigraph_preserves_edge_shape(types, reverse):
    left, right = getattr(nx, types[0])(), getattr(fnx, types[1])()
    left.add_edge("u", "v")
    right.add_edge("u", "v", key="first")
    right.add_edge("u", "v", key=("second", 2))
    if reverse:
        left, right = right, left
    paths, cost = fnx.optimal_edit_paths(left, right)
    assert cost == 1
    for nodes, edges in paths:
        assert _edit_script_cost(left, right, nodes, edges) == cost


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("large_baseline", [False, True])
def test_multigraph_edit_uses_global_parallel_edge_assignment(graph_type, large_baseline):
    left, right = getattr(fnx, graph_type)(), getattr(fnx, graph_type)()
    for graph in (left, right):
        graph.add_nodes_from([(0, {"rank": 0}), (1, {"rank": 1})])
        graph.add_edge(0, 1, key="a", rank=0)
        graph.add_edge(0, 1, key="b", rank=1)
    matrix = [[2, 1], [1, 2]] if large_baseline else [[1, 2], [2, 100]]
    baseline = 1e20 if large_baseline else 50
    costs = {
        "node_subst_cost": lambda a, b: 0 if a["rank"] == b["rank"] else baseline,
        "node_del_cost": lambda a: baseline,
        "node_ins_cost": lambda a: baseline,
        "edge_subst_cost": lambda a, b: matrix[a["rank"]][b["rank"]],
        "edge_del_cost": lambda a: baseline,
        "edge_ins_cost": lambda a: baseline,
    }
    expected = 2 if large_baseline else 4
    nodes, edges, value = list(fnx.optimize_edit_paths(left, right, **costs))[-1]
    assert value == expected
    assert _edit_script_cost(left, right, nodes, edges, **costs) == value
    assert {(a[2], b[2]) for a, b in edges} == {("a", "b"), ("b", "a")}
    assert fnx.graph_edit_distance(left, right, **costs) == expected


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_edit_prefers_deletion_and_insertion_to_expensive_substitution(graph_type):
    left, right = getattr(fnx, graph_type)(), getattr(fnx, graph_type)()
    for key in ("a", "b"):
        left.add_edge(0, 1, key=key)
        right.add_edge(0, 1, key=key)
    costs = {"edge_subst_cost": lambda a, b: 5}
    paths, value = fnx.optimal_edit_paths(left, right, **costs)
    assert value == 4
    for nodes, edges in paths:
        assert len(edges) == 4
        assert all(a is None or b is None for a, b in edges)
        assert _edit_script_cost(left, right, nodes, edges, **costs) == value


@pytest.mark.parametrize("infinite", ["delete", "insert", "both"])
def test_multigraph_edit_infinite_costs_still_admit_finite_substitutions(infinite):
    left, right = fnx.MultiGraph(), fnx.MultiGraph()
    for graph in (left, right):
        graph.add_edge(0, 1, key="a")
        graph.add_edge(0, 1, key="b")
    costs = {}
    if infinite in ("delete", "both"):
        costs["edge_del_cost"] = lambda a: math.inf
    if infinite in ("insert", "both"):
        costs["edge_ins_cost"] = lambda a: math.inf
    nodes, edges, value = next(fnx.optimize_edit_paths(left, right, **costs))
    assert value == 0
    assert _edit_script_cost(left, right, nodes, edges, **costs) == value


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_edit_callbacks_see_individual_original_dictionaries(graph_type):
    left, right = getattr(nx, graph_type)(), getattr(nx, graph_type)()
    for graph in (left, right):
        graph.add_edge(0, 1, key="a", color="red")
        graph.add_edge(0, 1, key="b", color="blue")
    left_attrs = [left.edges[e] for e in left.edges(keys=True)]
    right_attrs = [right.edges[e] for e in right.edges(keys=True)]
    calls = []

    def substitution(a, b):
        assert any(a is data for data in left_attrs)
        assert any(b is data for data in right_attrs)
        calls.append((a, b))
        return int(a["color"] != b["color"])

    def overridden_match(a, b):
        raise AssertionError("explicit edge cost overrides edge_match")

    paths = fnx.optimize_edit_paths(left, right, edge_subst_cost=substitution, edge_match=overridden_match)
    assert calls == []
    assert next(paths)[2] == 0
    assert len(calls) == 4
    paths.close()


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "foreign"])
def test_multigraph_edit_views_remain_live_until_first_advance(graph_type, library):
    left, right = getattr(library, graph_type)(), getattr(library, graph_type)()
    left.add_edge(0, 1, key="a", color="red")
    right.add_edge(0, 1, key="other", color="red")
    view = left.subgraph([0, 1])
    paths = fnx.optimize_edit_paths(view, right, edge_match=lambda a, b: a["color"] == b["color"])
    left.add_edge(0, 1, key="b", color="blue")
    nodes, edges, value = next(paths)
    assert value == 1
    assert len(edges) == 2
    assert any(a[2] == "a" and b[2] == "other" for a, b in edges if b is not None)
    paths.close()


@pytest.mark.parametrize("graph_type", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_edit_scripts_cover_parallel_self_loops(graph_type):
    left, right = getattr(fnx, graph_type)(), getattr(fnx, graph_type)()
    left.add_edge("root", "root", key="a")
    left.add_edge("root", "root", key="b")
    right.add_edge("root", "root", key="x")
    # NetworkX 3.6.1 omits singleton loops in some edit scripts. Assert valid
    # operations directly instead of treating that omission as an oracle.
    nodes, edges, value = next(fnx.optimize_edit_paths(left, right, roots=("root", "root")))
    assert value == 1
    assert _edit_script_cost(left, right, nodes, edges) == value


def test_multigraph_edit_preserves_unorderable_node_and_key_objects():
    a, b, key = object(), object(), object()
    left, right = nx.MultiGraph(), fnx.MultiGraph()
    for graph in (left, right):
        graph.add_edge(a, b, key=key)
        graph.add_edge(a, b, key=("tuple", 1))
    nodes, edges, value = next(fnx.optimize_edit_paths(left, right, roots=(a, a)))
    assert value == 0
    assert any(x is a and y is a for x, y in nodes)
    assert any(x[2] is key and y[2] is key for x, y in edges)
    assert _edit_script_cost(left, right, nodes, edges) == value


@pytest.mark.parametrize("strict", [False, True])
def test_multigraph_edit_roots_bounds_and_equal_cost_paths(strict):
    left, right = fnx.MultiDiGraph(), fnx.MultiDiGraph()
    left.add_nodes_from([0, 1])
    right.add_nodes_from([0, 1])
    left.add_edge(0, 1, key="a")
    left.add_edge(0, 1, key="b")
    right.add_edge(1, 0, key="c")
    assert fnx.graph_edit_distance(left, right) == 1
    assert fnx.graph_edit_distance(left, right, roots=(0, 0)) == 3
    assert fnx.graph_edit_distance(left, right, roots=(0, 1)) == 1
    assert fnx.graph_edit_distance(left, right, upper_bound=0) is None
    assert fnx.optimal_edit_paths(left, right, upper_bound=0) == ([], None)
    assert list(fnx.optimize_edit_paths(left, right, upper_bound=0, strictly_decreasing=strict)) == []
    results = list(fnx.optimize_edit_paths(left, right, upper_bound=1, strictly_decreasing=strict))
    assert results and all(value == 1 for _, _, value in results)


def test_multigraph_edit_prefix_scales_with_parallel_edges_and_can_close():
    graph = fnx.MultiGraph()
    for key in range(1500):
        graph.add_edge(0, 1, key=key)
    paths = fnx.optimize_edit_paths(graph, graph)
    nodes, edges, value = next(paths)
    assert value == 0
    assert len(nodes) == 2
    assert len(edges) == 1500
    paths.close()


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
