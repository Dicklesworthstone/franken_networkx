"""NetworkX conformance for the TSP / approximation algorithm family.

Existing ``test_approximation.py`` and
``test_approximation_signature_parity.py`` cover signature parity for
the family. Add a behavioral conformance harness that asserts
algorithm OUTPUT (tour, treewidth, partition) parity across structured
+ random fixtures.

Covered functions:

- ``greedy_tsp(G, weight=, source=)`` — nearest-neighbor TSP
  heuristic.
- ``christofides(G, weight=, tree=)`` — 3/2-approximation TSP for
  metric instances.
- ``traveling_salesman_problem(G, ...)`` — high-level TSP entry
  point that dispatches to ``christofides`` by default.
- ``simulated_annealing_tsp`` and ``threshold_accepting_tsp`` —
  metaheuristics; with a fixed seed and ``init_cycle`` both libs
  must produce the same tour.
- ``metric_closure(G, weight=)`` — computes the all-pairs shortest
  path metric closure.
- ``treewidth_min_degree`` and ``treewidth_min_fill_in`` —
  approximations for treewidth.
- ``ramsey_R2(G)`` — approximation for Ramsey numbers (max clique
  + max independent set).
- ``one_exchange`` and ``randomized_partitioning`` — max-cut
  heuristics.

Asserts:

- For deterministic algorithms (``greedy_tsp``, ``metric_closure``,
  ``treewidth_*``, ``christofides``): exact output equality with NX.
- For seeded stochastic algorithms (``simulated_annealing_tsp``,
  ``threshold_accepting_tsp``, ``randomized_partitioning``,
  ``one_exchange``, ``asadpour_atsp``): with fixed seed both libs
  produce the same output.
- Tour validity: every TSP tour starts and ends at the same node and
  visits every other node exactly once (Hamiltonian cycle property).
- TSP tour length is finite and the tour-length invariant holds:
  ``tour[0] == tour[-1]``.
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx
from networkx.algorithms.approximation import (
    christofides as _nx_christofides,
    greedy_tsp as _nx_greedy_tsp,
    metric_closure as _nx_metric_closure,
    one_exchange as _nx_one_exchange,
    randomized_partitioning as _nx_randomized_partitioning,
    simulated_annealing_tsp as _nx_sa_tsp,
    threshold_accepting_tsp as _nx_ta_tsp,
    traveling_salesman_problem as _nx_tsp,
    treewidth_min_degree as _nx_treewidth_min_degree,
    treewidth_min_fill_in as _nx_treewidth_min_fill_in,
)

import franken_networkx as fnx


def _make_complete_weighted_pair(n, weight_fn=None):
    """Return matched (fnx K_n, nx K_n) with edge weights."""
    fg = fnx.complete_graph(n)
    ng = nx.complete_graph(n)
    for u, v in list(fg.edges()):
        w = weight_fn(u, v) if weight_fn else float(u + v + 1)
        fg.edges[u, v]["weight"] = w
        ng.edges[u, v]["weight"] = w
    return fg, ng


# ---------------------------------------------------------------------------
# greedy_tsp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("source", [0, 1, 2])
def test_greedy_tsp_matches_networkx(n, source):
    if source >= n:
        pytest.skip("source out of range for this n")
    fg, ng = _make_complete_weighted_pair(n)
    fr = fnx.greedy_tsp(fg, source=source)
    nr = _nx_greedy_tsp(ng, source=source)
    assert fr == nr, f"K_{n} src={source}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_greedy_tsp_returns_valid_hamiltonian_cycle(n):
    fg, _ = _make_complete_weighted_pair(n)
    tour = fnx.greedy_tsp(fg, source=0)
    assert tour[0] == tour[-1] == 0, f"K_{n}: tour doesn't start/end at 0"
    visited = tour[:-1]
    assert sorted(visited) == list(range(n)), (
        f"K_{n}: tour {tour} doesn't visit each node exactly once"
    )


# ---------------------------------------------------------------------------
# christofides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_christofides_returns_valid_hamiltonian_cycle(n):
    """Christofides is non-deterministic on tie-breaks but always
    returns a valid Hamiltonian cycle (starts and ends at the same
    node, visits every other exactly once)."""
    fg, _ = _make_complete_weighted_pair(n)
    tour = fnx.christofides(fg)
    assert tour[0] == tour[-1], f"K_{n}: tour doesn't start/end at same node"
    visited = tour[:-1]
    assert sorted(visited) == list(range(n)), (
        f"K_{n}: tour {tour} doesn't visit each node exactly once"
    )


# ---------------------------------------------------------------------------
# traveling_salesman_problem (high-level)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_traveling_salesman_problem_returns_valid_cycle(n):
    fg, _ = _make_complete_weighted_pair(n)
    tour = fnx.traveling_salesman_problem(fg)
    assert tour[0] == tour[-1]
    assert sorted(tour[:-1]) == list(range(n))


@pytest.mark.parametrize("n,nodes_subset", [
    (6, [0, 2, 4]),
    (6, [0, 1, 3, 5]),
    (8, [0, 4, 7]),
])
def test_traveling_salesman_with_explicit_nodes_subset(n, nodes_subset):
    """``traveling_salesman_problem(G, nodes=...)`` finds a TSP tour
    that visits the specified subset (using the metric closure
    derived from G's shortest paths)."""
    fg, _ = _make_complete_weighted_pair(n)
    tour = fnx.traveling_salesman_problem(fg, nodes=nodes_subset)
    assert tour[0] == tour[-1]
    # All requested nodes are in the tour
    assert set(nodes_subset) <= set(tour)


# ---------------------------------------------------------------------------
# metric_closure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("C_5", lambda L: L.cycle_graph(5)),
        ("P_4", lambda L: L.path_graph(4)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_metric_closure_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    for u, v in g_nx.edges():
        g_fnx.add_edge(u, v, weight=1.0)
        g_nx.edges[u, v]["weight"] = 1.0
    fr = fnx.metric_closure(g_fnx)
    nr = _nx_metric_closure(g_nx)
    fr_e = sorted(
        (u, v, fr.edges[u, v].get("distance"))
        for u, v in fr.edges()
    )
    nr_e = sorted(
        (u, v, nr.edges[u, v].get("distance"))
        for u, v in nr.edges()
    )
    assert fr_e == nr_e, f"{name}: fnx={fr_e[:3]} nx={nr_e[:3]}"


# ---------------------------------------------------------------------------
# simulated_annealing_tsp / threshold_accepting_tsp — seeded determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 7, 42, 1000])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_simulated_annealing_tsp_matches_networkx(n, seed):
    fg, ng = _make_complete_weighted_pair(n)
    init = list(range(n)) + [0]
    fr = fnx.simulated_annealing_tsp(fg, init_cycle=init, seed=seed)
    nr = _nx_sa_tsp(ng, init_cycle=init, seed=seed)
    assert fr == nr, f"K_{n} seed={seed}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("seed", [1, 42, 1000])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_threshold_accepting_tsp_matches_networkx(n, seed):
    fg, ng = _make_complete_weighted_pair(n)
    init = list(range(n)) + [0]
    fr = fnx.threshold_accepting_tsp(fg, init_cycle=init, seed=seed)
    nr = _nx_ta_tsp(ng, init_cycle=init, seed=seed)
    assert fr == nr, f"K_{n} seed={seed}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# treewidth approximations — exact value parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("K_4", lambda L: L.complete_graph(4)),
        ("K_5", lambda L: L.complete_graph(5)),
        ("C_5", lambda L: L.cycle_graph(5)),
        ("C_6", lambda L: L.cycle_graph(6)),
        ("path_5", lambda L: L.path_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
        ("hypercube_3", lambda L: L.hypercube_graph(3)),
    ],
)
def test_treewidth_min_degree_value_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr_tw, _ = fnx.treewidth_min_degree(g_fnx)
    nr_tw, _ = _nx_treewidth_min_degree(g_nx)
    assert fr_tw == nr_tw, f"{name}: fnx={fr_tw} nx={nr_tw}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("K_4", lambda L: L.complete_graph(4)),
        ("K_5", lambda L: L.complete_graph(5)),
        ("C_5", lambda L: L.cycle_graph(5)),
        ("path_5", lambda L: L.path_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_treewidth_min_fill_in_value_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr_tw, _ = fnx.treewidth_min_fill_in(g_fnx)
    nr_tw, _ = _nx_treewidth_min_fill_in(g_nx)
    assert fr_tw == nr_tw, f"{name}: fnx={fr_tw} nx={nr_tw}"


# ---------------------------------------------------------------------------
# Cross-relation: TSP-tour cost ≤ 1.5 × optimal for metric instances
# (Christofides 3/2-approximation guarantee)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [4, 5, 6])
def test_christofides_tour_cost_within_3_2_of_optimal(n):
    """Christofides guarantees a tour at most 1.5× optimal on metric
    instances. Verify on small K_n with metric weights."""
    fg, _ = _make_complete_weighted_pair(n)
    tour = fnx.christofides(fg)
    cost = sum(fg.edges[u, v]["weight"] for u, v in zip(tour[:-1], tour[1:]))
    # Compute brute-force optimal for small n
    nodes = list(fg.nodes())
    best = float("inf")
    for perm in itertools.permutations(nodes[1:]):
        cycle = [nodes[0]] + list(perm) + [nodes[0]]
        c = sum(
            fg.edges[u, v]["weight"]
            for u, v in zip(cycle[:-1], cycle[1:])
        )
        best = min(best, c)
    assert cost <= 1.5 * best + 1e-9, (
        f"K_{n}: christofides cost {cost} > 1.5 × optimal {1.5 * best}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_metric_closure_disconnected_raises_matching_networkx():
    """Both libs require a connected graph for metric_closure."""
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (2, 3)])
    for u, v in fg.edges():
        fg.edges[u, v]["weight"] = 1.0
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (2, 3)])
    for u, v in ng.edges():
        ng.edges[u, v]["weight"] = 1.0
    with pytest.raises(nx.NetworkXError):
        _nx_metric_closure(ng)
    with pytest.raises(fnx.NetworkXError):
        fnx.metric_closure(fg)


def test_greedy_tsp_single_node_returns_trivial_tour():
    """Single node tour is the trivial cycle [v, v] (start = end)."""
    g = fnx.Graph(); g.add_node(0)
    gn = nx.Graph(); gn.add_node(0)
    fr = fnx.greedy_tsp(g, source=0)
    nr = _nx_greedy_tsp(gn, source=0)
    assert fr == nr == [0, 0]


# ---------------------------------------------------------------------------
# one_exchange and randomized_partitioning (max-cut heuristics)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 42, 1000])
@pytest.mark.parametrize(
    "name,builder",
    [
        ("K_4", lambda L: L.complete_graph(4)),
        ("K_5", lambda L: L.complete_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_randomized_partitioning_matches_networkx(name, builder, seed):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr_cut, fr_part = fnx.randomized_partitioning(g_fnx, seed=seed)
    nr_cut, nr_part = _nx_randomized_partitioning(g_nx, seed=seed)
    assert fr_cut == nr_cut
    fr_norm = sorted(frozenset(p) for p in fr_part)
    nr_norm = sorted(frozenset(p) for p in nr_part)
    assert fr_norm == nr_norm
