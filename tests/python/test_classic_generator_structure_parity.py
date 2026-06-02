"""Exact-structure parity for the classic / small / parametric named generators.

``test_classic_generators.py`` asserts only ``number_of_nodes()`` /
``number_of_edges()`` for these generators — a generator that produced the
right *count* but wrong *edges* (or relabelled nodes) would pass. The lattice
generators get exact-edge-set checks in ``test_lattice_generators.py``, but the
classic/small/parametric families do not. This harness closes that gap: for
each generator it asserts the full node set and (canonicalized) edge set match
networkx exactly.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _node_set(g):
    return sorted(map(repr, g.nodes()))


def _edge_set(g):
    if g.is_directed():
        return sorted((repr(u), repr(v)) for u, v in g.edges())
    return sorted(tuple(sorted((repr(u), repr(v)))) for u, v in g.edges())


# name -> lambda(module) -> graph. Skipped automatically if absent on either lib.
_GENERATORS = {
    # small named graphs
    "bull": lambda m: m.bull_graph(),
    "chvatal": lambda m: m.chvatal_graph(),
    "cubical": lambda m: m.cubical_graph(),
    "desargues": lambda m: m.desargues_graph(),
    "diamond": lambda m: m.diamond_graph(),
    "dodecahedral": lambda m: m.dodecahedral_graph(),
    "frucht": lambda m: m.frucht_graph(),
    "heawood": lambda m: m.heawood_graph(),
    "house": lambda m: m.house_graph(),
    "house_x": lambda m: m.house_x_graph(),
    "icosahedral": lambda m: m.icosahedral_graph(),
    "krackhardt_kite": lambda m: m.krackhardt_kite_graph(),
    "moebius_kantor": lambda m: m.moebius_kantor_graph(),
    "octahedral": lambda m: m.octahedral_graph(),
    "pappus": lambda m: m.pappus_graph(),
    "petersen": lambda m: m.petersen_graph(),
    "sedgewick_maze": lambda m: m.sedgewick_maze_graph(),
    "tetrahedral": lambda m: m.tetrahedral_graph(),
    "truncated_cube": lambda m: m.truncated_cube_graph(),
    "truncated_tetrahedron": lambda m: m.truncated_tetrahedron_graph(),
    "tutte": lambda m: m.tutte_graph(),
    "null": lambda m: m.null_graph(),
    "trivial": lambda m: m.trivial_graph(),
    # parametric families (deterministic structure)
    "complete_8": lambda m: m.complete_graph(8),
    "complete_bipartite_3_4": lambda m: m.complete_bipartite_graph(3, 4),
    "complete_multipartite_232": lambda m: m.complete_multipartite_graph(2, 3, 2),
    "turan_7_3": lambda m: m.turan_graph(7, 3),
    "circulant_8_13": lambda m: m.circulant_graph(8, [1, 3]),
    "cycle_7": lambda m: m.cycle_graph(7),
    "path_7": lambda m: m.path_graph(7),
    "star_6": lambda m: m.star_graph(6),
    "wheel_6": lambda m: m.wheel_graph(6),
    "ladder_5": lambda m: m.ladder_graph(5),
    "circular_ladder_5": lambda m: m.circular_ladder_graph(5),
    "barbell_4_2": lambda m: m.barbell_graph(4, 2),
    "lollipop_4_3": lambda m: m.lollipop_graph(4, 3),
    "balanced_tree_2_3": lambda m: m.balanced_tree(2, 3),
    "full_rary_tree_3_13": lambda m: m.full_rary_tree(3, 13),
    "binomial_tree_4": lambda m: m.binomial_tree(4),
    "dorogovtsev_3": lambda m: m.dorogovtsev_goltsev_mendes_graph(3),
    "windmill_4_3": lambda m: m.windmill_graph(4, 3),
    "LCF_14": lambda m: m.LCF_graph(14, [5, -5], 7),
    "hypercube_4": lambda m: m.hypercube_graph(4),
}


def _resolve(name):
    fn = _GENERATORS[name]
    try:
        gn = fn(nx)
        gf = fn(fnx)
    except (AttributeError, TypeError):
        pytest.skip(f"{name} unavailable on one library")
    return gn, gf


@pytest.mark.parametrize("name", sorted(_GENERATORS))
def test_generator_node_set_matches_networkx(name):
    gn, gf = _resolve(name)
    assert _node_set(gf) == _node_set(gn)


@pytest.mark.parametrize("name", sorted(_GENERATORS))
def test_generator_edge_set_matches_networkx(name):
    gn, gf = _resolve(name)
    assert _edge_set(gf) == _edge_set(gn)
    assert gf.number_of_edges() == gn.number_of_edges()
    assert gf.is_directed() == gn.is_directed()
