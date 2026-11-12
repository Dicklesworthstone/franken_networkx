"""Phase B certification: graph generators. Deterministic generators
must match nx edge-set AND node-iteration order exactly; seeded-random
generators must match nx edge-for-edge (proving identical RNG
consumption, not just structural equivalence). Zero divergences.
"""
import networkx as nx
import pytest

import franken_networkx as fnx


def _EE(g):
    return sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in g.edges())


def _NN(g):
    return [repr(n) for n in g.nodes()]


DETERMINISTIC = [
    ("complete_graph", lambda m: m.complete_graph(8)),
    ("cycle_graph", lambda m: m.cycle_graph(10)),
    ("path_graph", lambda m: m.path_graph(10)),
    ("star_graph", lambda m: m.star_graph(9)),
    ("wheel_graph", lambda m: m.wheel_graph(9)),
    ("complete_bipartite_graph", lambda m: m.complete_bipartite_graph(4, 5)),
    ("grid_2d_graph", lambda m: m.grid_2d_graph(4, 5)),
    ("hypercube_graph", lambda m: m.hypercube_graph(4)),
    ("circular_ladder_graph", lambda m: m.circular_ladder_graph(7)),
    ("ladder_graph", lambda m: m.ladder_graph(8)),
    ("lollipop_graph", lambda m: m.lollipop_graph(5, 4)),
    ("barbell_graph", lambda m: m.barbell_graph(5, 3)),
    ("balanced_tree", lambda m: m.balanced_tree(3, 3)),
    ("full_rary_tree", lambda m: m.full_rary_tree(3, 20)),
    ("turan_graph", lambda m: m.turan_graph(10, 3)),
    ("petersen_graph", lambda m: m.petersen_graph()),
    ("krackhardt_kite_graph", lambda m: m.krackhardt_kite_graph()),
    ("tutte_graph", lambda m: m.tutte_graph()),
    ("sedgewick_maze_graph", lambda m: m.sedgewick_maze_graph()),
    ("dorogovtsev_goltsev_mendes_graph", lambda m: m.dorogovtsev_goltsev_mendes_graph(3)),
]


@pytest.mark.parametrize("name,gen", DETERMINISTIC, ids=[n for n, _ in DETERMINISTIC])
def test_deterministic_generator_edges_and_order(name, gen):
    assert _EE(gen(fnx)) == _EE(gen(nx)), (name, "edges")
    assert _NN(gen(fnx)) == _NN(gen(nx)), (name, "nodeorder")


SEEDED = [
    ("gnp_random_graph", lambda m: m.gnp_random_graph(40, 0.2, seed=42)),
    ("gnm_random_graph", lambda m: m.gnm_random_graph(40, 80, seed=42)),
    ("barabasi_albert_graph", lambda m: m.barabasi_albert_graph(40, 3, seed=42)),
    ("watts_strogatz_graph", lambda m: m.watts_strogatz_graph(40, 4, 0.3, seed=42)),
    ("random_regular_graph", lambda m: m.random_regular_graph(4, 40, seed=42)),
    ("powerlaw_cluster_graph", lambda m: m.powerlaw_cluster_graph(40, 3, 0.3, seed=42)),
]


@pytest.mark.parametrize("name,gen", SEEDED, ids=[n for n, _ in SEEDED])
def test_seeded_random_generator_edge_for_edge(name, gen):
    # Identical seed must reproduce nx's exact RNG consumption -> same edges.
    assert _EE(gen(fnx)) == _EE(gen(nx)), name
