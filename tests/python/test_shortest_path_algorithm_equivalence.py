"""Metamorphic equivalence: shortest-path algorithm output is invariant
across dijkstra and bellman-ford for non-negative-weight inputs.

Pairs with the existing tests/python/test_mst_algorithm_equivalence.py
which fixed MST algorithm-invariance. Now that
``all_shortest_paths(G, s, t, weight=..., method='bellman-ford')``
landed (br-r37-c1-xsi7c) on both undirected and directed graphs, the
two methods must agree on:

1. ``shortest_path_length(G, s, t, weight=..., method=METHOD)`` — a
   single scalar distance per (s, t) query.
2. ``all_shortest_paths(G, s, t, weight=..., method=METHOD)`` — the
   set of equally-shortest paths.

These properties are required by the bellman-ford correctness contract
(NetworkX raises only on negative cycles; otherwise the value matches
dijkstra). Catches regressions in the new fnx multi-predecessor
bellman-ford that would silently disagree with dijkstra on some graphs
(e.g. handling of equal-weight ties or unreachable targets).
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")

EPS = 1e-9

METHODS = ["dijkstra", "bellman-ford"]


def _seeded_weight_assignment(graph, seed, low=1.0, high=10.0):
    """Assign random weights to every edge.

    NOTE: We avoid ``graph[u][v]['weight'] = ...`` post-mutation because
    that path is invisible to the Rust algorithms (architectural bead
    br-r37-c1-sjf4t — Python edge dicts and Rust AttrMap are not kept in
    sync on mutation). Instead, re-add each edge with the weight as a
    kwarg, which propagates through ``add_edge_with_attrs`` and updates
    the Rust storage. add_edge merges attrs onto an existing edge, so
    this is idempotent and safe.
    """
    rng = random.Random(seed)
    edges = list(graph.edges())
    for u, v in edges:
        w = rng.uniform(low, high)
        graph.add_edge(u, v, weight=w)


# ---------------------------------------------------------------------------
# Connected fixtures (always have at least one path between any two nodes)
# ---------------------------------------------------------------------------

CONNECTED_UNDIRECTED_FIXTURES = [
    ("path-10", lambda: nx.path_graph(10), 1),
    ("cycle-12", lambda: nx.cycle_graph(12), 2),
    ("complete-6", lambda: nx.complete_graph(6), 3),
    ("balanced-tree-2-3", lambda: nx.balanced_tree(2, 3), 5),
    ("watts-15-0.5", lambda: nx.connected_watts_strogatz_graph(15, 4, 0.5, seed=6), 6),
    ("karate-club", lambda: nx.karate_club_graph(), 8),
]


def _build_fnx_undirected(nx_graph):
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    return f_graph


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "weight_seed"), CONNECTED_UNDIRECTED_FIXTURES
)
def test_dijkstra_and_bellman_ford_agree_on_path_length_undirected(
    name, builder, weight_seed
):
    """Shortest-path length must be method-invariant on positive weights."""
    nx_graph = builder()
    f_graph = _build_fnx_undirected(nx_graph)
    _seeded_weight_assignment(f_graph, weight_seed)

    nodes = list(f_graph.nodes())
    # Only sample a few (s, t) pairs to keep the matrix runtime sane;
    # iterating every pair would dominate the suite for n=34.
    rng = random.Random(weight_seed)
    pairs = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(min(10, len(nodes)))]

    for s, t in pairs:
        if s == t:
            continue
        d_dij = fnx.shortest_path_length(f_graph, s, t, weight="weight", method="dijkstra")
        d_bf = fnx.shortest_path_length(f_graph, s, t, weight="weight", method="bellman-ford")
        assert abs(d_dij - d_bf) < EPS, (
            f"{name}: dijkstra({s},{t})={d_dij} != bellman-ford({s},{t})={d_bf}"
        )


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "weight_seed"), CONNECTED_UNDIRECTED_FIXTURES
)
def test_all_shortest_paths_set_invariant_under_method_undirected(
    name, builder, weight_seed
):
    """``all_shortest_paths`` must return the same set of paths regardless
    of method (the order can differ, the underlying set cannot)."""
    nx_graph = builder()
    f_graph = _build_fnx_undirected(nx_graph)
    _seeded_weight_assignment(f_graph, weight_seed)

    nodes = list(f_graph.nodes())
    rng = random.Random(weight_seed)
    pairs = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(min(5, len(nodes)))]

    for s, t in pairs:
        if s == t:
            continue
        paths_dij = {
            tuple(p)
            for p in fnx.all_shortest_paths(f_graph, s, t, weight="weight", method="dijkstra")
        }
        paths_bf = {
            tuple(p)
            for p in fnx.all_shortest_paths(f_graph, s, t, weight="weight", method="bellman-ford")
        }
        assert paths_dij == paths_bf, (
            f"{name}: dijkstra path set {paths_dij} != bellman-ford {paths_bf} "
            f"for ({s}, {t})"
        )


# ---------------------------------------------------------------------------
# Directed fixtures (DAGs + general digraphs)
# ---------------------------------------------------------------------------

CONNECTED_DIRECTED_FIXTURES = [
    ("dag-binary-2-3", lambda: nx.balanced_tree(2, 3, create_using=nx.DiGraph), 21),
    ("scale-free-15", lambda: nx.scale_free_graph(15, seed=22).to_directed(), 22),
    ("complete-5-dir", lambda: nx.complete_graph(5, create_using=nx.DiGraph), 23),
]


def _build_fnx_directed(nx_graph):
    f_graph = fnx.DiGraph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    return f_graph


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "weight_seed"), CONNECTED_DIRECTED_FIXTURES
)
def test_all_shortest_paths_set_invariant_under_method_directed(
    name, builder, weight_seed
):
    """Same metamorphic invariant on DiGraphs."""
    nx_graph = builder()
    if isinstance(nx_graph, nx.MultiDiGraph):
        # scale_free_graph returns a multidigraph — collapse parallel edges
        # for this test (we want simple DiGraph since fnx.MultiDiGraph
        # delegates to nx for these methods anyway).
        simple = nx.DiGraph()
        simple.add_nodes_from(nx_graph.nodes(data=True))
        for u, v in set(nx_graph.edges()):
            simple.add_edge(u, v)
        nx_graph = simple
    f_graph = _build_fnx_directed(nx_graph)
    _seeded_weight_assignment(f_graph, weight_seed)

    nodes = list(f_graph.nodes())
    rng = random.Random(weight_seed)
    pairs = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(min(5, len(nodes)))]

    for s, t in pairs:
        if s == t:
            continue
        try:
            paths_dij = {
                tuple(p)
                for p in fnx.all_shortest_paths(
                    f_graph, s, t, weight="weight", method="dijkstra"
                )
            }
        except fnx.NetworkXNoPath:
            paths_dij = None

        try:
            paths_bf = {
                tuple(p)
                for p in fnx.all_shortest_paths(
                    f_graph, s, t, weight="weight", method="bellman-ford"
                )
            }
        except fnx.NetworkXNoPath:
            paths_bf = None

        assert paths_dij == paths_bf, (
            f"{name}: dijkstra path set {paths_dij} != bellman-ford {paths_bf} "
            f"for ({s}, {t})"
        )


# ---------------------------------------------------------------------------
# Negative-weight DiGraph: bellman-ford alone supports it, but the
# distance must equal a brute-force exhaustive enumeration of simple paths
# from s to t when the graph has no negative cycles.
# ---------------------------------------------------------------------------


def _brute_force_min_path_weight(digraph, s, t):
    """Return the minimum-weight simple s→t path's total weight, or None
    if no path exists. O(n!) enumeration so only safe for small fixtures.
    """
    best = None
    for path in nx.all_simple_paths(digraph, s, t):
        w = sum(
            digraph[path[i]][path[i + 1]]["weight"]
            for i in range(len(path) - 1)
        )
        if best is None or w < best:
            best = w
    return best


@needs_nx
def test_bellman_ford_negative_weight_directed_no_cycle_matches_brute_force():
    """On a small DiGraph with negative edges but no negative cycle,
    ``all_shortest_paths`` via bellman-ford must agree with the
    exhaustive simple-path-enumeration minimum."""
    edges = [
        ("s", "a", 1),
        ("s", "b", 4),
        ("a", "b", -2),
        ("b", "t", 1),
        ("a", "t", 5),
    ]
    f_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    for u, v, w in edges:
        f_graph.add_edge(u, v, weight=w)
        nx_graph.add_edge(u, v, weight=w)

    fnx_paths = list(
        fnx.all_shortest_paths(f_graph, "s", "t", weight="weight", method="bellman-ford")
    )
    nx_paths = list(
        nx.all_shortest_paths(nx_graph, "s", "t", weight="weight", method="bellman-ford")
    )
    assert sorted(fnx_paths) == sorted(nx_paths), f"fnx={fnx_paths} nx={nx_paths}"

    fnx_distance = sum(
        f_graph[fnx_paths[0][i]][fnx_paths[0][i + 1]]["weight"]
        for i in range(len(fnx_paths[0]) - 1)
    )
    expected = _brute_force_min_path_weight(nx_graph, "s", "t")
    assert abs(fnx_distance - expected) < EPS, (
        f"path weight {fnx_distance} != brute-force minimum {expected}"
    )


@needs_nx
def test_bellman_ford_negative_cycle_raises_unbounded():
    """Confirms br-r37-c1-xsi7c contract: directed negative cycle from
    source raises NetworkXUnbounded (matching nx)."""
    f_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    for u, v, w in [("a", "b", 1), ("b", "a", -3)]:
        f_graph.add_edge(u, v, weight=w)
        nx_graph.add_edge(u, v, weight=w)

    with pytest.raises(fnx.NetworkXUnbounded):
        list(
            fnx.all_shortest_paths(f_graph, "a", "b", weight="weight", method="bellman-ford")
        )
    with pytest.raises(nx.NetworkXUnbounded):
        list(
            nx.all_shortest_paths(nx_graph, "a", "b", weight="weight", method="bellman-ford")
        )
