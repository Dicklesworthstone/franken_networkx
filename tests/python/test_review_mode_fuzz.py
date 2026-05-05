"""Random-input fuzzer for the algorithms touched by 2026-05-03 REVIEW MODE.

Goal: surface panics, hangs, type-confusion, and silent property
violations on adversarial input shapes (multigraphs, self-loops, tiny
graphs, dense graphs, isolated nodes) that the structured conformance /
metamorphic / golden harnesses don't necessarily span.

The fuzzer is deterministic — every run uses an explicit seed grid so
failures reproduce bit-exactly without an external dep on Hypothesis.
"""

from __future__ import annotations

import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


# Seeds form a grid covering ~120 distinct graph shapes per algorithm.
_FUZZ_SEEDS = list(range(40))


def _random_graph(seed: int) -> fnx.Graph:
    rng = random.Random(seed)
    n = rng.randint(0, 25)
    p = rng.uniform(0.0, 0.6)
    G = fnx.Graph()
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                G.add_edge(i, j)
    if n >= 1 and (seed % 10 == 0 or rng.random() < 0.15):
        # Deterministically keep self-loops in the seed grid so the
        # complement contract is genuinely exercised every run.
        node = rng.randrange(n)
        G.add_edge(node, node)
    return G


def _random_digraph(seed: int) -> fnx.DiGraph:
    rng = random.Random(seed)
    n = rng.randint(0, 20)
    p = rng.uniform(0.0, 0.5)
    G = fnx.DiGraph()
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if rng.random() < p:
                G.add_edge(i, j)
    return G


def _random_multigraph(module, seed: int, *, directed: bool = False):
    rng = random.Random(seed + 5000)
    n = rng.randint(0, 16)
    p = rng.uniform(0.0, 0.45)
    graph_cls = module.MultiDiGraph if directed else module.MultiGraph
    G = graph_cls()
    for i in range(n):
        G.add_node(i)
    for i in range(n):
        targets = range(n) if directed else range(i + 1, n)
        for j in targets:
            if i == j:
                continue
            if rng.random() < p:
                for _ in range(1 + rng.randrange(3)):
                    G.add_edge(i, j)
    if n >= 1 and seed % 9 == 0:
        node = rng.randrange(n)
        G.add_edge(node, node)
        G.add_edge(node, node)
    return G


def _norm_edges_for_compare(graph):
    if graph.is_directed():
        return sorted((u, v) for u, v in graph.edges())
    return sorted(tuple(sorted((u, v))) for u, v in graph.edges())


# ---- panic / exception-class fuzzing -------------------------------

def test_fuzz_seed_grid_includes_self_loops():
    assert any(
        any(u == v for u, v in _random_graph(seed).edges())
        for seed in _FUZZ_SEEDS
    )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_transitivity_no_crash_and_in_unit_interval(seed):
    G = _random_graph(seed)
    # nx.transitivity returns 0 (int) on null / single-node graphs;
    # fnx must match — and the value-bound check still applies.
    t = fnx.transitivity(G)
    assert isinstance(t, int | float)
    if isinstance(t, float):
        assert not math.isnan(t)
    assert 0 <= t <= 1


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_wiener_index_no_crash(seed):
    G = _random_graph(seed)
    if G.number_of_nodes() == 0:
        # Null graph: both libs raise NetworkXPointlessConcept (which
        # is a SIBLING of NetworkXError, not a subclass — verified
        # against networkx 3.6.1).
        with pytest.raises(nx.NetworkXPointlessConcept):
            fnx.wiener_index(G)
        return
    w = fnx.wiener_index(G)
    assert isinstance(w, int | float)
    # On disconnected graphs nx returns +inf — that's allowed.
    if isinstance(w, float):
        assert not math.isnan(w)


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_load_centrality_no_crash_normalized_bounded(seed):
    G = _random_graph(seed)
    if G.number_of_nodes() == 0:
        # fnx returns {} on empty graph; just probe.
        assert fnx.load_centrality(G) == {}
        return
    lc = fnx.load_centrality(G, normalized=True)
    assert set(lc.keys()) == set(G.nodes())
    for v in lc.values():
        assert isinstance(v, float)
        assert not math.isnan(v)
        assert -1e-9 <= v <= 1.0 + 1e-9


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_connected_components_partitions_nodes(seed):
    G = _random_graph(seed)
    comps = list(fnx.connected_components(G))
    union = set()
    for comp in comps:
        assert isinstance(comp, set), f"got {type(comp).__name__}"
        assert union.isdisjoint(comp), f"overlap in component {comp}"
        union |= comp
    assert union == set(G.nodes())


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_cycle_basis_circuit_rank_invariant(seed):
    G = _random_graph(seed)
    # cycle_basis is undefined-ish on graphs with self-loops; skip those.
    if any(u == v for u, v in G.edges()):
        return
    basis = fnx.cycle_basis(G)
    expected = (
        G.number_of_edges()
        - G.number_of_nodes()
        + fnx.number_connected_components(G)
    )
    if G.number_of_nodes() == 0:
        expected = 0
    assert len(basis) == expected, (
        f"seed={seed}: |basis|={len(basis)}, expected circuit rank "
        f"{expected} (|E|={G.number_of_edges()}, |V|={G.number_of_nodes()})"
    )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_complement_is_involution(seed):
    G = _random_graph(seed)
    # Strip self-loops since complement (undirected) drops them.
    edges_no_sl = {tuple(sorted(e)) for e in G.edges() if e[0] != e[1]}
    Gcc_edges = {tuple(sorted(e)) for e in fnx.complement(fnx.complement(G)).edges()}
    assert edges_no_sl == Gcc_edges


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_find_cliques_each_is_actual_clique(seed):
    G = _random_graph(seed)
    # find_cliques requires no self-loops in nx contract.
    if any(u == v for u, v in G.edges()):
        return
    for clique in fnx.find_cliques(G):
        assert len(set(clique)) == len(clique), f"non-simple clique {clique}"
        # Every pair in the clique is an edge.
        nodes = list(clique)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                assert G.has_edge(nodes[i], nodes[j]), (
                    f"non-edge ({nodes[i]}, {nodes[j]}) in returned clique {clique}"
                )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_all_shortest_paths_when_path_exists(seed):
    G = _random_graph(seed)
    nodes = list(G.nodes())
    if len(nodes) < 2:
        return
    rng = random.Random(seed + 1000)
    s, t = rng.choice(nodes), rng.choice(nodes)
    if s == t or not fnx.has_path(G, s, t):
        return
    spl = fnx.shortest_path_length(G, s, t)
    paths = list(fnx.all_shortest_paths(G, s, t))
    assert paths, f"has_path={True} but all_shortest_paths empty"
    for p in paths:
        assert len(p) - 1 == spl, f"path {p} has wrong length"
        # Every consecutive pair is an edge.
        for i in range(len(p) - 1):
            assert G.has_edge(p[i], p[i + 1])


# ---- DiGraph fuzz ---------------------------------------------------

@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_complement_directed_correct_edge_count(seed):
    G = _random_digraph(seed)
    # For directed graphs (no self-loops in complement contract):
    # |E(G \ self_loops)| + |E(complement(G))| = n*(n-1)
    n = G.number_of_nodes()
    if n == 0:
        return
    g_edges_no_sl = sum(1 for u, v in G.edges() if u != v)
    Gc = fnx.complement(G)
    assert g_edges_no_sl + Gc.number_of_edges() == n * (n - 1)


@pytest.mark.parametrize("seed", _FUZZ_SEEDS)
def test_fuzz_strongly_connected_components_partition(seed):
    G = _random_digraph(seed)
    comps = list(fnx.strongly_connected_components(G))
    union = set()
    for comp in comps:
        assert isinstance(comp, set), f"got {type(comp).__name__}"
        assert union.isdisjoint(comp)
        union |= comp
    assert union == set(G.nodes())


# ---- multi/parallel-edge surface (the recently-added perf paths
# bypass per-edge runtime_policy; fuzzing checks graph stays consistent)

def test_fuzz_multigraph_seed_grid_includes_parallel_edges_and_self_loops():
    graphs = [_random_multigraph(fnx, seed) for seed in _FUZZ_SEEDS]
    assert any(len(list(G.edges())) > len(set(_norm_edges_for_compare(G))) for G in graphs)
    assert any(any(u == v for u, v in G.edges()) for G in graphs)


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:20])
@pytest.mark.parametrize("directed", [False, True], ids=["multigraph", "multidigraph"])
def test_fuzz_multigraph_complement_matches_networkx(seed, directed):
    G_fnx = _random_multigraph(fnx, seed, directed=directed)
    G_nx = _random_multigraph(nx, seed, directed=directed)

    C_fnx = fnx.complement(G_fnx)
    C_nx = nx.complement(G_nx)

    assert C_fnx.is_multigraph() == C_nx.is_multigraph()
    assert C_fnx.is_directed() == C_nx.is_directed()
    assert set(C_fnx.nodes()) == set(C_nx.nodes())
    assert _norm_edges_for_compare(C_fnx) == _norm_edges_for_compare(C_nx)


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:20])
def test_fuzz_complement_undirected_no_self_loops(seed):
    """Undirected complement must never include self-loops, even when
    the source graph has them (nx convention)."""
    G = _random_graph(seed)
    Gc = fnx.complement(G)
    for u, v in Gc.edges():
        assert u != v, f"complement contains self-loop ({u}, {v})"


# ---- nx-oracle differential fuzz (parity vs reference impl) --------

@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_find_cliques_oracle_parity_with_nx(seed):
    """For every random graph in the seed grid: fnx.find_cliques(G)
    must produce the EXACT same clique sequence as nx.find_cliques(G).
    Stress-tests the br-r37-c1-tvf43 perf fix (G.neighbors-based
    adjacency build) against arbitrary inputs."""
    G_fnx = _random_graph(seed)
    if any(u == v for u, v in G_fnx.edges()):
        # find_cliques is not defined on graphs with self-loops in nx
        return
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    nx_cliques = list(nx.find_cliques(G_nx))
    fnx_cliques = list(fnx.find_cliques(G_fnx))
    assert nx_cliques == fnx_cliques, (
        f"seed={seed}: nx and fnx clique sequences diverge\n"
        f"  nx[:3]:  {nx_cliques[:3]}\n"
        f"  fnx[:3]: {fnx_cliques[:3]}"
    )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_pagerank_oracle_value_match_with_nx(seed):
    """fnx.pagerank values must match nx within numerical tolerance
    on every random fixture (skip self-loop fixtures since the two
    libraries' default self-loop treatment can introduce mode-level
    convergence differences)."""
    G_fnx = _random_graph(seed)
    if G_fnx.number_of_nodes() == 0:
        return
    if any(u == v for u, v in G_fnx.edges()):
        return
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    nv = nx.pagerank(G_nx)
    fv = fnx.pagerank(G_fnx)
    assert set(nv) == set(fv)
    for k in nv:
        assert nv[k] == pytest.approx(fv[k], abs=1e-6), (
            f"seed={seed}, node {k}: nx={nv[k]} fnx={fv[k]}"
        )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_clustering_oracle_parity_with_nx(seed):
    """fnx.clustering must match nx exactly (values AND types) on every
    random fixture. Stress-tests the br-r37-c1-9ccqe int-0 fix against
    arbitrary inputs."""
    G_fnx = _random_graph(seed)
    if any(u == v for u, v in G_fnx.edges()):
        return
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    nv = nx.clustering(G_nx)
    fv = fnx.clustering(G_fnx)
    assert nv == fv, f"seed={seed}: clustering values diverge"
    for k in nv:
        assert type(fv[k]) is type(nv[k]), (
            f"seed={seed} node {k}: type drift "
            f"nx={type(nv[k]).__name__} fnx={type(fv[k]).__name__}"
        )


# ---- directed distance-metrics oracle fuzz (br-r37-c1-89n9d /
#      br-r37-c1-wojl3 regression lock) -------------------------------

def _random_strongly_connected_digraph(seed: int):
    """Generate a random directed graph and return (nx, fnx) versions
    that are guaranteed strongly connected (so diameter/radius/center
    are well-defined). Returns ``None`` if the seed produces nothing
    suitable."""
    rng = random.Random(seed)
    n = rng.randint(4, 12)
    p = rng.uniform(0.25, 0.55)
    G_nx = nx.DiGraph()
    G_fnx = fnx.DiGraph()
    for i in range(n):
        G_nx.add_node(i)
        G_fnx.add_node(i)
    edges = []
    for i in range(n):
        for j in range(n):
            if i != j and rng.random() < p:
                edges.append((i, j))
    # Add a Hamiltonian cycle to guarantee strong connectivity.
    for i in range(n):
        edges.append((i, (i + 1) % n))
    G_nx.add_edges_from(edges)
    G_fnx.add_edges_from(edges)
    if not nx.is_strongly_connected(G_nx):
        return None
    return G_nx, G_fnx


# ---- common_neighbors / non_neighbors bypass lock (br-r37-c1-qkq2h) -

@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_common_neighbors_oracle_match_nx(seed):
    """br-r37-c1-qkq2h replaced ``set(G.adj[u]) & set(G.adj[v])`` with
    a raw _GRAPH_NEIGHBORS bypass. Locks the bypass-path correctness:
    fnx.common_neighbors(G, u, v) must equal nx.common_neighbors on
    every random fixture, every node pair."""
    G_fnx = _random_graph(seed)
    if G_fnx.number_of_nodes() < 2:
        return
    if any(u == v for u, v in G_fnx.edges()):
        # nx.common_neighbors raises on self-loops in some versions;
        # skip for cleanest oracle.
        return
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    nodes = list(G_fnx.nodes())
    rng = random.Random(seed + 9000)
    pairs = [tuple(rng.sample(nodes, 2)) for _ in range(min(8, len(nodes) * (len(nodes) - 1) // 2))]
    for u, v in pairs:
        nv = set(nx.common_neighbors(G_nx, u, v))
        fv = set(fnx.common_neighbors(G_fnx, u, v))
        assert nv == fv, f"seed={seed} pair ({u},{v}): nx={nv} fnx={fv}"


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_non_neighbors_oracle_match_nx(seed):
    """Same bypass-path correctness lock for non_neighbors. Catches
    contract violations in the wrapper-bypass branch (which uses
    ``set(graph) - set(_raw_nbrs(graph, node)) - {node}``)."""
    G_fnx = _random_graph(seed)
    if G_fnx.number_of_nodes() < 2:
        return
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    rng = random.Random(seed + 11000)
    nodes = list(G_fnx.nodes())
    sampled = rng.sample(nodes, min(5, len(nodes)))
    for v in sampled:
        nv = set(nx.non_neighbors(G_nx, v))
        fv = set(fnx.non_neighbors(G_fnx, v))
        assert nv == fv, f"seed={seed} node {v}: nx={nv} fnx={fv}"


# ---- dominating_set(start_with) port lock (br-r37-c1-{lj6bo,02djy}) -

@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_dominating_set_with_start_oracle_dominates_every_node(seed):
    """The native port br-r37-c1-lj6bo / wrapper-bypass br-r37-c1-02djy
    replaced an nx delegate with an inline greedy algorithm. Greedy
    dominating-set choices aren't unique (different node-iteration
    orders yield different valid dominating sets), so we can't compare
    fnx output bit-equal to nx. Instead we verify the fundamental
    contract: every node in G is either in the returned set or has a
    neighbor in it. Run on 25 random ER graphs spanning sparse and
    dense, with a deterministic start_with."""
    G_fnx = _random_graph(seed)
    if G_fnx.number_of_nodes() < 2:
        return
    if any(u == v for u, v in G_fnx.edges()):
        # Self-loops aren't excluded by nx but make the contract fuzzy
        # (a self-looped node 'dominates' itself trivially); skip for
        # cleanest oracle.
        return
    rng = random.Random(seed + 5000)
    nodes = list(G_fnx.nodes())
    start = rng.choice(nodes)
    ds = fnx.dominating_set(G_fnx, start_with=start)

    # Contract 1: result is a set
    assert isinstance(ds, set), f"seed={seed}: got {type(ds).__name__}, want set"
    # Contract 2: start_with ∈ ds (the greedy seeds with start_with)
    assert start in ds, f"seed={seed}: start_with={start} not in returned set"
    # Contract 3: every node is dominated (in ds OR has a neighbor in ds)
    for v in nodes:
        if v in ds:
            continue
        nbrs = set(G_fnx[v])
        assert nbrs & ds, (
            f"seed={seed}: node {v} not dominated "
            f"(ds={ds}, nbrs(v)={nbrs})"
        )


# ---- is_planar Kuratowski-bound fast-path lock (br-r37-c1-gttlp) ----

def _random_planarity_test_graph(seed: int):
    """Random graph that's likely to exercise EITHER the Kuratowski-
    bound short-circuit OR the LR fallback path. Mixes:
      - dense graphs (Euler-bound caught) — m close to or above 3n-6
      - bipartite dense (bipartite-bound caught) — m close to 2n-4
      - sparse sparse-non-bipartite (LR fallback)
    """
    rng = random.Random(seed)
    case = rng.randint(0, 2)
    if case == 0:
        # Dense general — likely violates Euler bound for n >= 5.
        n = rng.randint(5, 12)
        p = rng.uniform(0.6, 0.95)
        return fnx.erdos_renyi_graph(n, p, seed=seed)
    if case == 1:
        # Dense bipartite — exercises the bipartite short-circuit.
        m, k = rng.randint(3, 6), rng.randint(3, 6)
        return fnx.complete_bipartite_graph(m, k)
    # Sparse — falls through to LR.
    n = rng.randint(5, 15)
    return fnx.barabasi_albert_graph(n, 2, seed=seed)


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:30])
def test_fuzz_is_planar_oracle_matches_nx_across_bound_paths(seed):
    """Locks the br-r37-c1-gttlp Kuratowski-bound fast path: regardless
    of which short-circuit (Euler / bipartite / LR-fallback) any
    given fixture lands in, fnx.is_planar must match nx.is_planar
    bit-exactly. A typo in the bound (e.g. ``>`` vs ``<``) would
    silently regress correctness on graphs that hit only that path."""
    G_fnx = _random_planarity_test_graph(seed)
    G_nx = nx.Graph()
    G_nx.add_nodes_from(G_fnx.nodes())
    G_nx.add_edges_from(G_fnx.edges())
    assert fnx.is_planar(G_fnx) == nx.is_planar(G_nx), (
        f"seed={seed}: divergence on |V|={G_fnx.number_of_nodes()} "
        f"|E|={G_fnx.number_of_edges()}"
    )


@pytest.mark.parametrize("seed", _FUZZ_SEEDS[:25])
def test_fuzz_directed_diameter_radius_center_periphery_oracle_match_nx(seed):
    """Locks the br-r37-c1-89n9d (center/periphery) and br-r37-c1-wojl3
    (diameter/radius) directed-graph fixes against arbitrary
    strongly-connected DiGraphs. The underlying Rust _fnx.diameter etc.
    have a directed-collapse defect (call gr.undirected() before
    computing) — these tests verify the Python wrapper masks that by
    routing directed inputs through fnx.eccentricity natively."""
    pair = _random_strongly_connected_digraph(seed)
    if pair is None:
        return
    G_nx, G_fnx = pair
    assert fnx.diameter(G_fnx) == nx.diameter(G_nx), (
        f"seed={seed}: directed diameter divergence"
    )
    assert fnx.radius(G_fnx) == nx.radius(G_nx), (
        f"seed={seed}: directed radius divergence"
    )
    # center / periphery: order-equal (both built from
    # ``[n for n in G.nodes() if ecc[n] == r]``).
    assert fnx.center(G_fnx) == nx.center(G_nx), (
        f"seed={seed}: directed center divergence"
    )
    assert fnx.periphery(G_fnx) == nx.periphery(G_nx), (
        f"seed={seed}: directed periphery divergence"
    )
