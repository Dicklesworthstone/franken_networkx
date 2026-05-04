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
