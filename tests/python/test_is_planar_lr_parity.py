"""Parity for the native Left-Right planarity kernel (br-r37-c1-native-is-planar-boolean-zuxh1).

``is_planar`` previously routed through ``check_planarity(G)``, which delegated to
networkx (an O(n^2) fnx->nx conversion plus networkx's pure-Python Left-Right
planarity *embedding*). The gap to networkx GREW with n (1.6x slower at n=300 ->
4.4x slower at n=1000). It now calls a boolean-only Rust port of networkx's
``LRPlanarity`` (orientation + testing phases, de Fraysseix-Rosenstiehl / Brandes),
which is ~10x FASTER than networkx.

Planarity is a graph invariant, so the boolean is independent of node/adjacency
order and must match ``networkx.is_planar`` (and ``check_planarity(G)[0]``) exactly,
including the canonical non-planar graphs (K5, K3,3, Petersen, ...). Self-loops and
parallel edges never affect planarity and are ignored by the kernel.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def _agree(G):
    F = _cp(G)
    nx_ans = nx.is_planar(G)
    # is_planar (wrapper, routes to native LR), the raw binding, and
    # check_planarity must all agree with networkx.
    assert fnx.is_planar(F) == nx_ans
    assert fnx._fnx.is_planar_lr(F) == nx_ans
    assert fnx.check_planarity(F)[0] == nx_ans
    return nx_ans


def test_canonical_fixtures():
    nonplanar = [
        nx.complete_graph(5),  # K5
        nx.complete_graph(6),
        nx.complete_bipartite_graph(3, 3),  # K3,3
        nx.complete_bipartite_graph(4, 4),
        nx.petersen_graph(),
        nx.heawood_graph(),
        nx.moebius_kantor_graph(),
    ]
    planar = [
        nx.complete_graph(4),  # K4
        nx.complete_bipartite_graph(2, 3),
        nx.grid_2d_graph(5, 5),
        nx.octahedral_graph(),
        nx.dodecahedral_graph(),
        nx.icosahedral_graph(),
        nx.tutte_graph(),
        nx.frucht_graph(),
        nx.wheel_graph(20),
        nx.cycle_graph(50),
        nx.balanced_tree(3, 4),
    ]
    for g in nonplanar:
        assert _agree(nx.convert_node_labels_to_integers(g)) is False
    for g in planar:
        assert _agree(nx.convert_node_labels_to_integers(g)) is True


def test_random_gnp_matches_networkx():
    for seed in range(400):
        rnd = random.Random(seed)
        n = rnd.randint(0, 24)
        p = rnd.uniform(0.0, 0.55)
        _agree(nx.gnp_random_graph(n, p, seed=seed))


def test_grid_plus_chords_matches_networkx():
    # Grids are planar; random chords sometimes destroy planarity -> exercises
    # both branches of the LR test (not just the Euler short-circuit).
    for seed in range(200):
        rnd = random.Random(7000 + seed)
        k = rnd.randint(3, 9)
        G = nx.convert_node_labels_to_integers(nx.grid_2d_graph(k, k))
        for _ in range(rnd.randint(0, 6)):
            u = rnd.randrange(G.number_of_nodes())
            v = rnd.randrange(G.number_of_nodes())
            if u != v:
                G.add_edge(u, v)
        _agree(G)


def test_selfloops_and_parallel_edges_ignored():
    # K5 with self-loops is still non-planar; a planar graph with self-loops
    # stays planar. The kernel must ignore loops/parallel edges.
    G = nx.complete_graph(5)
    G.add_edge(0, 0)
    G.add_edge(2, 2)
    assert fnx._fnx.is_planar_lr(_cp(G)) is False
    H = nx.grid_2d_graph(4, 4)
    H = nx.convert_node_labels_to_integers(H)
    H.add_edge(0, 0)
    assert fnx._fnx.is_planar_lr(_cp(H)) is True


def test_disconnected_components():
    # Two disjoint K3,3 components -> non-planar; two disjoint planar -> planar.
    G = nx.disjoint_union(nx.complete_bipartite_graph(3, 3), nx.cycle_graph(6))
    assert _agree(G) is False
    H = nx.disjoint_union(nx.grid_2d_graph(3, 3), nx.complete_graph(4))
    H = nx.convert_node_labels_to_integers(H)
    assert _agree(H) is True
