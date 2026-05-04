"""Metamorphic tests for the algorithms touched by 2026-05-03 REVIEW MODE.

Differential conformance (test_review_mode_regression_lock.py) compares
fnx against nx on the same input. Metamorphic tests are independent —
they exercise mathematical *properties* of the algorithm that must hold
regardless of which library produces the output. A regression that
silently breaks an invariant (without diverging from nx — e.g., because
nx has the same bug, or because the test input happens to mask it) will
trip a metamorphic test even when the conformance test stays green.

Each property is keyed to the algorithm whose recent fix risk-area it
guards.
"""

from __future__ import annotations

import math
import random

import pytest

import franken_networkx as fnx


# ---- complement (br-r37-c1-4jd8m) -----------------------------------

@pytest.mark.parametrize(
    "builder",
    [
        lambda: fnx.path_graph(5),
        lambda: fnx.cycle_graph(6),
        lambda: fnx.complete_graph(4),
        lambda: fnx.barabasi_albert_graph(20, 3, seed=7),
        lambda: fnx.erdos_renyi_graph(15, 0.4, seed=11),
    ],
    ids=["P5", "C6", "K4", "BA20", "ER15"],
)
def test_complement_is_involution(builder):
    """complement(complement(G)) == G as edge sets (no self-loops)."""
    G = builder()
    Gcc = fnx.complement(fnx.complement(G))
    orig_edges = {tuple(sorted(e)) for e in G.edges() if e[0] != e[1]}
    cc_edges = {tuple(sorted(e)) for e in Gcc.edges()}
    assert orig_edges == cc_edges
    assert set(G.nodes()) == set(Gcc.nodes())


@pytest.mark.parametrize(
    "n,p", [(10, 0.0), (10, 0.3), (10, 0.7), (10, 1.0)],
    ids=["empty", "sparse", "dense", "complete"],
)
def test_complement_edge_count_is_complementary(n, p):
    """|E(G)| + |E(complement(G))| == n*(n-1)/2 for simple undirected graphs."""
    G = fnx.erdos_renyi_graph(n, p, seed=2026)
    Gc = fnx.complement(G)
    assert G.number_of_edges() + Gc.number_of_edges() == n * (n - 1) // 2


# ---- cycle_basis (br-r37-c1-bix7h) ----------------------------------

@pytest.mark.parametrize(
    "builder",
    [
        lambda: fnx.cycle_graph(5),
        lambda: fnx.cycle_graph(20),
        lambda: fnx.complete_graph(5),
        lambda: fnx.barabasi_albert_graph(30, 3, seed=13),
        lambda: fnx.grid_2d_graph(4, 4),
    ],
    ids=["C5", "C20", "K5", "BA30", "grid_4x4"],
)
def test_cycle_basis_rank_equals_circuit_rank(builder):
    """For a connected undirected graph: |cycle_basis| == |E| - |V| + 1
    (the circuit rank / first Betti number). For disconnected: + (k-1)
    where k is the number of components."""
    G = builder()
    basis = fnx.cycle_basis(G)
    n_comps = fnx.number_connected_components(G)
    expected_rank = G.number_of_edges() - G.number_of_nodes() + n_comps
    assert len(basis) == expected_rank, (
        f"cycle_basis size {len(basis)} != circuit rank {expected_rank} "
        f"(|E|={G.number_of_edges()}, |V|={G.number_of_nodes()}, "
        f"components={n_comps})"
    )


def test_cycle_basis_each_cycle_is_actual_cycle():
    """Every cycle in the basis must be an actual closed walk in G with
    no repeated edges."""
    G = fnx.barabasi_albert_graph(30, 3, seed=42)
    basis = fnx.cycle_basis(G)
    for cycle in basis:
        # Each consecutive pair (and last-to-first) is an edge.
        for i in range(len(cycle)):
            u, v = cycle[i], cycle[(i + 1) % len(cycle)]
            assert G.has_edge(u, v), f"non-edge ({u}, {v}) in cycle {cycle}"
        # No repeated nodes (basis cycles are simple).
        assert len(set(cycle)) == len(cycle), f"non-simple cycle {cycle}"


# ---- connected_components (br-r37-c1-anace) -------------------------

@pytest.mark.parametrize("seed", [0, 1, 42, 2026])
def test_connected_components_partition_invariant(seed):
    """Components form a node-set partition — pairwise disjoint, union
    is V. This is invariant to traversal order or iteration impl."""
    G = fnx.erdos_renyi_graph(40, 0.05, seed=seed)
    comps = list(fnx.connected_components(G))
    union = set()
    for comp in comps:
        assert union.isdisjoint(comp), f"overlap on component {comp}"
        union |= comp
    assert union == set(G.nodes())


def test_connected_components_count_matches_separator():
    """Number of components from the iterator == number_connected_components."""
    G = fnx.erdos_renyi_graph(30, 0.1, seed=99)
    n_iter = sum(1 for _ in fnx.connected_components(G))
    n_count = fnx.number_connected_components(G)
    assert n_iter == n_count


# ---- transitivity (br-r37-c1-4jnwn) ---------------------------------

@pytest.mark.parametrize("n", [4, 5, 7, 10])
def test_transitivity_complete_graph_is_one(n):
    """K_n has all possible triangles; transitivity must equal 1.0."""
    assert fnx.transitivity(fnx.complete_graph(n)) == pytest.approx(1.0)


@pytest.mark.parametrize("n", [4, 6, 8])
def test_transitivity_bipartite_complete_is_zero(n):
    """K_{n,n} has no triangles (bipartite); transitivity must equal 0."""
    G = fnx.complete_bipartite_graph(n, n)
    assert fnx.transitivity(G) == 0


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_transitivity_in_unit_interval(seed):
    """Transitivity is a probability — must be in [0, 1] for any graph."""
    G = fnx.erdos_renyi_graph(25, 0.3, seed=seed)
    t = fnx.transitivity(G)
    assert 0.0 <= t <= 1.0


# ---- wiener_index (br-r37-c1-t26b4) ---------------------------------

@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_wiener_index_path_closed_form(n):
    """Wiener index of P_n = n(n^2-1)/6 (closed-form known result)."""
    actual = fnx.wiener_index(fnx.path_graph(n))
    expected = n * (n * n - 1) / 6
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_wiener_index_complete_graph_closed_form(n):
    """Wiener index of K_n = n(n-1)/2 (each pair has distance 1)."""
    assert fnx.wiener_index(fnx.complete_graph(n)) == pytest.approx(n * (n - 1) / 2)


def test_wiener_index_disconnected_is_inf():
    """Disconnected pair contributes +inf in nx convention."""
    G = fnx.Graph([(0, 1), (2, 3)])
    assert math.isinf(fnx.wiener_index(G))


# ---- load_centrality (br-r37-c1-3wzcj) ------------------------------

@pytest.mark.parametrize(
    "n", [4, 5, 7], ids=lambda n: f"K{n}",
)
def test_load_centrality_complete_graph_uniform(n):
    """K_n is vertex-transitive — every node has identical load."""
    lc = fnx.load_centrality(fnx.complete_graph(n))
    values = list(lc.values())
    if values:
        v0 = values[0]
        for v in values[1:]:
            assert v == pytest.approx(v0)


def test_load_centrality_normalized_in_unit_interval():
    """Normalized load is bounded in [0, 1]."""
    G = fnx.barabasi_albert_graph(40, 3, seed=7)
    lc = fnx.load_centrality(G, normalized=True)
    for v in lc.values():
        assert 0.0 <= v <= 1.0 + 1e-9


# ---- katz_centrality (br-r37-c1-ua4i8) ------------------------------

def test_katz_centrality_normalized_unit_l2_norm():
    """Normalized Katz centrality vector has unit L2 norm (nx convention)."""
    G = fnx.karate_club_graph()
    kc = fnx.katz_centrality(G)
    norm_sq = sum(v * v for v in kc.values())
    assert math.sqrt(norm_sq) == pytest.approx(1.0, abs=1e-6)


# ---- all_shortest_paths (br-r37-c1-6atv8) ---------------------------

@pytest.mark.parametrize(
    "builder", [
        lambda: fnx.complete_graph(5),
        lambda: fnx.cycle_graph(6),
        lambda: fnx.barabasi_albert_graph(20, 3, seed=4),
    ], ids=["K5", "C6", "BA20"],
)
def test_all_shortest_paths_have_uniform_length(builder):
    """Every path returned must have the same length (the shortest-path
    length); also matches ``shortest_path_length(G, s, t)``."""
    G = builder()
    nodes = list(G.nodes())
    s, t = nodes[0], nodes[-1]
    paths = list(fnx.all_shortest_paths(G, s, t))
    assert paths, "expected at least one path"
    lengths = {len(p) for p in paths}
    assert len(lengths) == 1, f"non-uniform path lengths: {lengths}"
    spl = fnx.shortest_path_length(G, s, t)
    # path length (#nodes) - 1 == edge-count == shortest_path_length
    assert (lengths.pop() - 1) == spl


def test_all_shortest_paths_are_simple_paths():
    """Each returned path must have no repeated nodes."""
    G = fnx.barabasi_albert_graph(15, 3, seed=8)
    nodes = list(G.nodes())
    for s, t in [(nodes[0], nodes[-1]), (nodes[1], nodes[-2])]:
        for path in fnx.all_shortest_paths(G, s, t):
            assert len(set(path)) == len(path), f"non-simple path {path}"


# ---- random graph fuzz: cross-property consistency ------------------

@pytest.mark.parametrize("seed", [0, 7, 42, 99, 2026])
def test_components_complement_consistency(seed):
    """If G has k > 1 components, complement(G) must be connected
    (a classical theorem). Stress-test on random graphs."""
    rng = random.Random(seed)
    n = rng.randint(8, 20)
    p = rng.uniform(0.05, 0.25)  # keep sparse → likely disconnected
    G = fnx.erdos_renyi_graph(n, p, seed=seed)
    if fnx.number_connected_components(G) <= 1:
        pytest.skip("G is connected; theorem is vacuous")
    Gc = fnx.complement(G)
    assert fnx.number_connected_components(Gc) == 1, (
        f"complement of disconnected graph (n={n}, p={p:.2f}, "
        f"k={fnx.number_connected_components(G)}) is also disconnected"
    )
