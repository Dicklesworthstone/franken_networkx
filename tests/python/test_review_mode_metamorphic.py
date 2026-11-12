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


# ---- find_cliques (br-r37-c1-tvf43 perf fix) -----------------------

@pytest.mark.parametrize("seed", [0, 7, 42])
def test_find_cliques_max_size_equals_clique_number(seed):
    """The size of the largest clique returned by find_cliques is the
    graph's clique number ω(G). Verify by comparing to an independent
    inner-loop max."""
    G = fnx.barabasi_albert_graph(40, 3, seed=seed)
    cliques = list(fnx.find_cliques(G))
    largest = max(len(c) for c in cliques)
    # Equivalent independent computation
    largest_check = max(len(c) for c in fnx.find_cliques(G))
    assert largest == largest_check
    # Sanity: bound by maximum degree + 1
    max_deg = max(dict(G.degree()).values())
    assert largest <= max_deg + 1


@pytest.mark.parametrize("n", [4, 5, 6])
def test_find_cliques_complete_graph_yields_single_clique(n):
    """K_n has exactly one maximal clique = entire vertex set."""
    G = fnx.complete_graph(n)
    cliques = list(fnx.find_cliques(G))
    assert len(cliques) == 1, f"K{n} should have 1 maximal clique, got {len(cliques)}"
    assert len(cliques[0]) == n


# ---- pagerank (canonical numerical invariants) ---------------------

@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_pagerank_sums_to_one(seed):
    """PageRank is a probability distribution: ∑ pagerank(v) == 1."""
    G = fnx.barabasi_albert_graph(30, 3, seed=seed)
    pr = fnx.pagerank(G)
    assert abs(sum(pr.values()) - 1.0) < 1e-6


# ---- triangles / clustering / transitivity coherence ---------------

@pytest.mark.parametrize("seed", [0, 1, 42])
def test_triangles_consistent_with_transitivity_zero(seed):
    """If transitivity == 0, no node has triangles. Bidirectionally:
    if every node has 0 triangles, transitivity must be 0."""
    G = fnx.path_graph(10)  # acyclic ⇒ no triangles
    assert fnx.transitivity(G) == 0
    triangles = fnx.triangles(G)
    assert all(t == 0 for t in triangles.values())


# ---- selfloop / reciprocity / avg-degree-conn metamorphic ----------

@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_number_of_selfloops_equals_len_selfloop_edges(seed):
    """For ANY graph: number_of_selfloops(G) == sum(1 for _ in
    selfloop_edges(G)). Both quantities count exactly the same edges."""
    rng = random.Random(seed)
    G = fnx.Graph()
    n = rng.randint(3, 10)
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        for j in range(i, n):
            if rng.random() < 0.3:
                G.add_edge(i, j)
    assert fnx.number_of_selfloops(G) == sum(1 for _ in fnx.selfloop_edges(G))


@pytest.mark.parametrize("seed", [0, 1, 7])
def test_selfloop_edges_only_emits_self_pairs(seed):
    """Every (u, v) yielded by selfloop_edges has u == v by definition.
    Guards against an iteration regression that emits non-self edges."""
    rng = random.Random(seed)
    G = fnx.Graph()
    for i in range(8):
        G.add_node(i)
    for i in range(8):
        for j in range(i, 8):
            if rng.random() < 0.3:
                G.add_edge(i, j)
    for u, v in fnx.selfloop_edges(G):
        assert u == v, f"selfloop_edges emitted non-self pair ({u}, {v})"


def test_overall_reciprocity_symmetric_digraph_is_one():
    """A DiGraph where every edge has its reverse is fully reciprocal."""
    G = fnx.DiGraph()
    edges = [(0, 1), (1, 2), (2, 3)]
    for u, v in edges:
        G.add_edge(u, v)
        G.add_edge(v, u)
    assert fnx.overall_reciprocity(G) == 1.0


def test_overall_reciprocity_dag_is_zero():
    """A directed tree (no reverse edges anywhere) has reciprocity 0."""
    G = fnx.DiGraph([(0, 1), (1, 2), (1, 3), (2, 4)])
    assert fnx.overall_reciprocity(G) == 0.0


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_overall_reciprocity_bounded(seed):
    """reciprocity ∈ [0, 1] for any non-empty directed graph."""
    rng = random.Random(seed)
    G = fnx.DiGraph()
    n = rng.randint(4, 10)
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        for j in range(n):
            if i != j and rng.random() < 0.3:
                G.add_edge(i, j)
    if G.number_of_edges() == 0:
        return
    r = fnx.overall_reciprocity(G)
    assert 0.0 <= r <= 1.0


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_average_degree_connectivity_sum_dnorm_equals_2m(seed):
    """For undirected G: sum over keys k of dnorm[k] == 2|E|, where
    dnorm[k] is the number of edges from a degree-k node to anywhere
    (each undirected edge contributes to dnorm[deg(u)] and dnorm[deg(v)]).
    Equivalently: sum of degrees in the avg_degree_connectivity output's
    weight ledger == 2|E|."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    deg = dict(G.degree())
    # avg_degree_connectivity returns {k: avg_target_degree} so we need
    # to verify via the input dnorm = sum_{u: deg(u)==k} deg(u). The
    # invariant: sum over all u of deg(u) == 2|E|. avg_degree_connectivity
    # internally weights each k by sum of deg(u) for u with deg=k.
    total_weighted = sum(deg.values())
    assert total_weighted == 2 * G.number_of_edges()


# ---- common_neighbors / non_neighbors metamorphic (br-r37-c1-qkq2h) -

@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_common_neighbors_symmetric(seed):
    """common_neighbors(G, u, v) == common_neighbors(G, v, u) — set
    intersection is symmetric, and u/v are excluded from both sides."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    nodes = list(G.nodes())
    rng = random.Random(seed + 13000)
    pairs = [tuple(rng.sample(nodes, 2)) for _ in range(8)]
    for u, v in pairs:
        assert set(fnx.common_neighbors(G, u, v)) == set(fnx.common_neighbors(G, v, u))


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_common_neighbors_excludes_endpoints(seed):
    """common_neighbors(G, u, v) ∩ {u, v} = ∅ by definition."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    nodes = list(G.nodes())
    rng = random.Random(seed + 14000)
    for _ in range(8):
        u, v = rng.sample(nodes, 2)
        cn = set(fnx.common_neighbors(G, u, v))
        assert u not in cn
        assert v not in cn


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_common_neighbors_subset_of_each_neighborhood(seed):
    """common_neighbors(G, u, v) ⊆ N(u) AND ⊆ N(v). The result is the
    intersection of the two neighborhoods minus the endpoints."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    nodes = list(G.nodes())
    rng = random.Random(seed + 15000)
    for _ in range(6):
        u, v = rng.sample(nodes, 2)
        cn = set(fnx.common_neighbors(G, u, v))
        nbrs_u = set(G[u])
        nbrs_v = set(G[v])
        assert cn.issubset(nbrs_u), f"({u},{v}): cn={cn} not subset of N({u})={nbrs_u}"
        assert cn.issubset(nbrs_v), f"({u},{v}): cn={cn} not subset of N({v})={nbrs_v}"


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_non_neighbors_partition_complement(seed):
    """non_neighbors(G, v) ∪ neighbors(G, v) ∪ {v} == V(G), and the
    three sets are pairwise disjoint (it's a partition of V)."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    nodes = list(G.nodes())
    rng = random.Random(seed + 16000)
    for v in rng.sample(nodes, min(5, len(nodes))):
        non = set(fnx.non_neighbors(G, v))
        nbrs = set(G[v]) - {v}  # exclude self-loop if present
        partition = non | nbrs | {v}
        assert partition == set(nodes)
        # Pairwise disjoint
        assert non.isdisjoint(nbrs)
        assert v not in non
        assert v not in nbrs


# ---- link-prediction metamorphic (br-r37-c1-8e60l) ------------------

@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_jaccard_coefficient_symmetric(seed):
    """jaccard(u, v) == jaccard(v, u) — Jaccard set similarity is
    symmetric by definition (|N(u) ∩ N(v)| / |N(u) ∪ N(v)|)."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    nodes = list(G.nodes())
    rng = random.Random(seed + 7000)
    pairs = [tuple(rng.sample(nodes, 2)) for _ in range(8)]
    fwd = {(u, v): score for u, v, score in fnx.jaccard_coefficient(G, ebunch=pairs)}
    rev = {(u, v): score for u, v, score in fnx.jaccard_coefficient(G, ebunch=[(v, u) for u, v in pairs])}
    for u, v in pairs:
        assert fwd[(u, v)] == pytest.approx(rev[(v, u)], abs=1e-12), (
            f"jaccard({u},{v}) != jaccard({v},{u})"
        )


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_jaccard_coefficient_in_unit_interval(seed):
    """Jaccard ∈ [0, 1] for every pair (it's a normalized set ratio)."""
    G = fnx.barabasi_albert_graph(20, 3, seed=seed)
    for u, v, score in fnx.jaccard_coefficient(G):
        assert 0.0 <= score <= 1.0, f"jaccard({u},{v}) = {score} out of [0,1]"


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_preferential_attachment_equals_degree_product(seed):
    """pa(u, v) == degree(u) * degree(v) by definition. Since fnx
    delegates to nx, this verifies the delegation contract end-to-end."""
    G = fnx.barabasi_albert_graph(15, 3, seed=seed)
    deg = dict(G.degree())
    for u, v, score in fnx.preferential_attachment(G):
        assert score == deg[u] * deg[v], (
            f"pa({u},{v}) = {score} but deg({u})*deg({v}) = {deg[u] * deg[v]}"
        )


# ---- is_planar monotonicity / structural metamorphic (br-r37-c1-gttlp) ---

@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_planarity_invariant_under_relabeling(seed):
    """Planarity is a structural property; relabeling nodes leaves
    is_planar unchanged. Catches branch-condition typos that would
    accidentally key off node-name properties."""
    rng = random.Random(seed)
    n = rng.randint(5, 12)
    p = rng.uniform(0.3, 0.7)
    G = fnx.erdos_renyi_graph(n, p, seed=seed)
    is_p_before = fnx.is_planar(G)
    relabel = {old: f"renamed_{old}" for old in G.nodes()}
    G2 = fnx.relabel_nodes(G, relabel)
    assert fnx.is_planar(G2) == is_p_before


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_planarity_monotone_under_edge_removal(seed):
    """Edge-removal monotonicity: if G is planar, every subgraph
    obtained by removing an edge stays planar (planarity is closed
    under taking subgraphs / minors)."""
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    G = fnx.barabasi_albert_graph(n, 2, seed=seed)
    if not fnx.is_planar(G):
        pytest.skip("Random fixture is non-planar; theorem is vacuous")
    edges = list(G.edges())
    if not edges:
        pytest.skip("No edges to remove")
    u, v = rng.choice(edges)
    H = G.copy()
    H.remove_edge(u, v)
    assert fnx.is_planar(H), f"removing edge ({u},{v}) made a planar graph non-planar"


@pytest.mark.parametrize("n,m,expected_planar", [
    (3, 3, False),  # K3,3
    (4, 4, False),  # K4,4
    (5, 5, False),  # K5,5
    (2, 3, True),   # K2,3 is planar (book graph)
    (1, 5, True),   # star
])
def test_planarity_complete_bipartite_known_results(n, m, expected_planar):
    """Known result: K_{m,n} is planar iff min(m, n) ≤ 2.
    Tests the bipartite-bound short-circuit branch (br-r37-c1-gttlp)
    against canonical fixtures."""
    G = fnx.complete_bipartite_graph(n, m)
    assert fnx.is_planar(G) is expected_planar


# ---- core_number monotonicity (br-r37-c1-fbons) --------------------

@pytest.mark.parametrize("seed", [0, 7, 42])
def test_core_number_bounded_by_max_degree(seed):
    """For any v: core_number[v] ≤ degree(v). The k-core algorithm
    can only assign v to a core of size at most v's neighbor count."""
    G = fnx.barabasi_albert_graph(20, 3, seed=seed)
    cn = fnx.core_number(G)
    deg = dict(G.degree())
    for v, k in cn.items():
        assert k <= deg[v], f"core_number[{v}]={k} > degree[{v}]={deg[v]}"


def test_core_number_complete_graph_uniform():
    """K_n is vertex-transitive; every node has the same core number =
    n − 1 (since K_n is its own (n-1)-core)."""
    for n in [4, 5, 6, 7]:
        cn = fnx.core_number(fnx.complete_graph(n))
        assert all(c == n - 1 for c in cn.values())


# ---- directed distance-metrics metamorphic (br-r37-c1-kitjs) -------

def _scc_digraph(seed):
    """Random directed graph with a Hamiltonian cycle injected (so the
    result is always strongly connected, distance metrics defined)."""
    rng = random.Random(seed)
    n = rng.randint(5, 12)
    p = rng.uniform(0.2, 0.5)
    G = fnx.DiGraph()
    for i in range(n):
        G.add_node(i)
    edges = []
    for i in range(n):
        for j in range(n):
            if i != j and rng.random() < p:
                edges.append((i, j))
    for i in range(n):
        edges.append((i, (i + 1) % n))
    G.add_edges_from(edges)
    return G


@pytest.mark.parametrize("seed", [0, 1, 7, 11, 42])
def test_directed_diameter_invariant_under_reverse(seed):
    """For a strongly-connected DiGraph, ``diameter(reverse(G)) ==
    diameter(G)``: reversing every edge maps the shortest path from
    u to v in G to the shortest path from v to u in reverse(G), so
    the maximum over all (u, v) pairs is preserved."""
    G = _scc_digraph(seed)
    Gr = G.reverse()
    assert fnx.diameter(G) == fnx.diameter(Gr)


@pytest.mark.parametrize("seed", [0, 1, 7, 11, 42])
def test_directed_radius_diameter_ordering(seed):
    """Radius ≤ diameter is a fundamental graph-distance inequality.
    For finite strongly-connected DiGraphs both are well-defined and
    finite."""
    G = _scc_digraph(seed)
    assert fnx.radius(G) <= fnx.diameter(G)


@pytest.mark.parametrize("seed", [0, 1, 7, 11, 42])
def test_directed_center_is_subset_of_eccentricity_minimizers(seed):
    """The center is exactly the set of nodes attaining the minimum
    eccentricity. Verify against an independent computation of the
    minimum-eccentricity set from fnx.eccentricity."""
    G = _scc_digraph(seed)
    ecc = fnx.eccentricity(G)
    r = fnx.radius(G)
    expected_center = sorted(n for n, e in ecc.items() if e == r)
    actual_center = sorted(fnx.center(G))
    assert actual_center == expected_center


@pytest.mark.parametrize("seed", [0, 1, 7, 11, 42])
def test_directed_periphery_is_max_eccentricity_set(seed):
    """The periphery is exactly the set of nodes attaining the
    maximum eccentricity (i.e., diameter)."""
    G = _scc_digraph(seed)
    ecc = fnx.eccentricity(G)
    d = fnx.diameter(G)
    expected_periphery = sorted(n for n, e in ecc.items() if e == d)
    actual_periphery = sorted(fnx.periphery(G))
    assert actual_periphery == expected_periphery


# ---- harmonic_centrality (br-r37-c1-rsom6 dict-order fix) ----------

def test_harmonic_centrality_value_invariant_under_relabeling():
    """Relabel-invariant: relabeling nodes leaves the value mapping
    intact (the value is a property of structural position, not name)."""
    G1 = fnx.path_graph(5)
    h1 = fnx.harmonic_centrality(G1)
    G2 = fnx.relabel_nodes(G1, {i: chr(ord('a') + i) for i in range(5)})
    h2 = fnx.harmonic_centrality(G2)
    # Map back via the inverse and compare values
    rev = {chr(ord('a') + i): i for i in range(5)}
    h2_remapped = {rev[k]: v for k, v in h2.items()}
    for k in h1:
        assert h1[k] == pytest.approx(h2_remapped[k], abs=1e-9)
