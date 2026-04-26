"""Metamorphic equivalence: MST total weight is algorithm-invariant.

Bead br-r37-c1-00zcu. For any connected weighted undirected graph,
``boruvka``, ``kruskal``, and ``prim`` must all return spanning trees
with identical total weight. The actual edge sets may differ when the
graph has weight ties (a property nx documents), but the total weight
is canonical.

This test exercises the three native edge iterators added in
br-wjv9o (boruvka_mst_edges, kruskal_mst_edges, prim_mst_edges) on a
matrix of fixtures (random gnp graphs, path/cycle/complete/balanced-
tree) and asserts:

1. All three fnx algorithms return the same total weight.
2. That total matches networkx's reference (nx.minimum_spanning_edges).
3. Each result is a spanning tree (n-1 edges, connected, acyclic).

Catches regressions where an iterator silently drops edges or picks
suboptimal ones.
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

ALGORITHMS = ["boruvka", "kruskal", "prim"]


def _seeded_weight_assignment(graph, seed):
    rng = random.Random(seed)
    for u, v in list(graph.edges()):
        graph[u][v]["weight"] = rng.uniform(1.0, 10.0)


def _mst_total_weight(graph, algorithm):
    fn = getattr(fnx, f"{algorithm}_mst_edges")
    if algorithm == "boruvka":
        edges = list(fn(graph, data=True))
    else:
        # kruskal/prim require positional `minimum` flag
        edges = list(fn(graph, True, data=True))
    return sum(e[2].get("weight", 1) for e in edges), edges


def _nx_mst_total_weight(graph, algorithm):
    edges = list(
        nx.minimum_spanning_edges(graph, algorithm=algorithm, data=True)
    )
    return sum(e[2].get("weight", 1) for e in edges)


# ---------------------------------------------------------------------------
# Connected fixtures (always have a spanning tree)
# ---------------------------------------------------------------------------

CONNECTED_FIXTURES = [
    ("path-10", lambda: nx.path_graph(10), 1),
    ("cycle-12", lambda: nx.cycle_graph(12), 2),
    ("complete-6", lambda: nx.complete_graph(6), 3),
    ("complete-8", lambda: nx.complete_graph(8), 4),
    ("balanced-tree-2-3", lambda: nx.balanced_tree(2, 3), 5),
    ("gnp-15-0.5", lambda: nx.connected_watts_strogatz_graph(15, 4, 0.5, seed=6), 6),
    ("gnp-25-0.4", lambda: nx.connected_watts_strogatz_graph(25, 4, 0.4, seed=7), 7),
    ("karate-club", lambda: nx.karate_club_graph(), 8),
]


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "weight_seed"), CONNECTED_FIXTURES
)
def test_three_algorithms_agree_on_total_weight(name, builder, weight_seed):
    nx_graph = builder()
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))

    _seeded_weight_assignment(f_graph, weight_seed)
    # Mirror weights into the nx graph for the baseline check
    for u, v in nx_graph.edges():
        nx_graph[u][v]["weight"] = f_graph[u][v]["weight"]

    totals = {}
    edge_counts = {}
    for algo in ALGORITHMS:
        total, edges = _mst_total_weight(f_graph, algo)
        totals[algo] = total
        edge_counts[algo] = len(edges)

    # Algorithm-invariant: all three totals identical (within fp epsilon).
    base = totals[ALGORITHMS[0]]
    for algo in ALGORITHMS[1:]:
        assert abs(totals[algo] - base) < EPS, (
            f"{name}: {algo} total {totals[algo]} != {ALGORITHMS[0]} total {base}"
        )

    # Spanning property: n-1 edges in a connected graph.
    expected_edges = nx_graph.number_of_nodes() - 1
    for algo in ALGORITHMS:
        assert edge_counts[algo] == expected_edges, (
            f"{name}: {algo} returned {edge_counts[algo]} edges, "
            f"expected {expected_edges}"
        )


@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "weight_seed"), CONNECTED_FIXTURES
)
def test_total_weight_matches_networkx_baseline(name, builder, weight_seed):
    nx_graph = builder()
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))

    _seeded_weight_assignment(f_graph, weight_seed)
    for u, v in nx_graph.edges():
        nx_graph[u][v]["weight"] = f_graph[u][v]["weight"]

    fnx_total, _ = _mst_total_weight(f_graph, "kruskal")
    for algo in ALGORITHMS:
        nx_total = _nx_mst_total_weight(nx_graph, algo)
        assert abs(fnx_total - nx_total) < EPS, (
            f"{name}: fnx total {fnx_total} != nx {algo} total {nx_total}"
        )


# ---------------------------------------------------------------------------
# Spanning property checks (no cycles, all nodes covered)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_mst_is_acyclic_tree(algorithm):
    nx_graph = nx.connected_watts_strogatz_graph(20, 4, 0.3, seed=11)
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    _seeded_weight_assignment(f_graph, 11)

    _, edges = _mst_total_weight(f_graph, algorithm)
    # Build the MST as a fresh graph; check tree property
    H = fnx.Graph()
    H.add_nodes_from(f_graph.nodes())
    for e in edges:
        u, v = e[0], e[1]
        H.add_edge(u, v)
    assert H.number_of_edges() == H.number_of_nodes() - 1
    assert fnx.is_tree(H)


@needs_nx
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_mst_covers_all_nodes(algorithm):
    nx_graph = nx.complete_graph(10)
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes())
    f_graph.add_edges_from(nx_graph.edges())
    _seeded_weight_assignment(f_graph, 13)

    _, edges = _mst_total_weight(f_graph, algorithm)
    seen = set()
    for e in edges:
        seen.add(e[0])
        seen.add(e[1])
    assert seen == set(f_graph.nodes())


# ---------------------------------------------------------------------------
# Edge case: disconnected graph — MST iterators return a spanning forest
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_disconnected_graph_returns_spanning_forest(algorithm):
    """For disconnected graphs, the iterators return a spanning forest:
    one tree per connected component."""
    nx_graph = nx.disjoint_union(nx.path_graph(5), nx.cycle_graph(4))
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes())
    f_graph.add_edges_from(nx_graph.edges())
    _seeded_weight_assignment(f_graph, 17)

    _, edges = _mst_total_weight(f_graph, algorithm)
    # 5+4 nodes, 2 components → 9 - 2 = 7 edges in spanning forest
    assert len(edges) == 7


# ---------------------------------------------------------------------------
# Tie-breaking: equal weights should still produce a valid MST
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_uniform_weights_total_equals_n_minus_1(algorithm):
    """When every edge has weight 1, MST total = n-1."""
    G = fnx.complete_graph(8)
    for u, v in list(G.edges()):
        G[u][v]["weight"] = 1.0

    total, edges = _mst_total_weight(G, algorithm)
    assert abs(total - 7.0) < EPS
    assert len(edges) == 7
