"""Exact structure parity for deterministic graph generators.

Generators are construction code where off-by-one and node-labelling bugs hide
(grid/hypercube use tuple labels; named graphs have fixed edge lists). This
asserts fnx's deterministic generators produce byte-identical node and edge
sets to networkx.

No mocks: real fnx and real networkx generators.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _nodes(g):
    return sorted(map(str, g.nodes()))


def _edges(g):
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in g.edges())


_PARAMETRIC = [
    ("complete_graph", lambda L: L.complete_graph(6)),
    ("cycle_graph", lambda L: L.cycle_graph(7)),
    ("path_graph", lambda L: L.path_graph(5)),
    ("star_graph", lambda L: L.star_graph(5)),
    ("wheel_graph", lambda L: L.wheel_graph(6)),
    ("grid_2d_graph", lambda L: L.grid_2d_graph(3, 4)),
    ("hypercube_graph", lambda L: L.hypercube_graph(3)),
    ("complete_bipartite_graph", lambda L: L.complete_bipartite_graph(3, 4)),
    ("balanced_tree", lambda L: L.balanced_tree(2, 3)),
    ("lollipop_graph", lambda L: L.lollipop_graph(4, 3)),
    ("barbell_graph", lambda L: L.barbell_graph(4, 2)),
    ("circular_ladder_graph", lambda L: L.circular_ladder_graph(5)),
    ("ladder_graph", lambda L: L.ladder_graph(5)),
    ("binomial_tree", lambda L: L.binomial_tree(4)),
    ("turan_graph", lambda L: L.turan_graph(7, 3)),
]

_NAMED = [
    "petersen_graph", "krackhardt_kite_graph", "tutte_graph",
    "sedgewick_maze_graph", "dodecahedral_graph", "frucht_graph",
    "house_graph", "bull_graph", "diamond_graph", "chvatal_graph",
    "desargues_graph", "heawood_graph", "moebius_kantor_graph",
    "octahedral_graph", "pappus_graph",
]


@pytest.mark.parametrize("name,builder", _PARAMETRIC)
def test_parametric_generator_exact_structure(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    assert _nodes(fg) == _nodes(ng)
    assert _edges(fg) == _edges(ng)


@pytest.mark.parametrize("name", _NAMED)
def test_named_graph_exact_structure(name):
    fg = getattr(fnx, name)()
    ng = getattr(nx, name)()
    assert _nodes(fg) == _nodes(ng)
    assert _edges(fg) == _edges(ng)
