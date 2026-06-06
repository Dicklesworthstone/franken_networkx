"""Generators matrix 2026-06-06: adjacency-row ORDER parity for classic
generators. Root cause: rust_graph_to_py_standalone rebuilt graphs from
edges_ordered() (canonical-key SORTED), scrambling rows for any kernel
whose insertion order isn't sorted (tadpole's cycle-closing edge,
sudoku's three passes) and MASKING kernels with wrong emission order
that the sort happened to fix (petersen). Now: wholesale inner clone +
nx-exact kernel emission orders.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _rows(g):
    out = {repr(n): [repr(x) for x in g[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return out


GENS = [
    ("tadpole", lambda m: m.tadpole_graph(4, 3)),
    ("tadpole big", lambda m: m.tadpole_graph(7, 5)),
    ("sudoku2", lambda m: m.sudoku_graph(2)),
    ("sudoku3", lambda m: m.sudoku_graph(3)),
    ("petersen", lambda m: m.petersen_graph()),
    ("chvatal", lambda m: m.chvatal_graph()),
    ("wheel", lambda m: m.wheel_graph(7)),
    ("barbell", lambda m: m.barbell_graph(5, 3)),
    ("lollipop", lambda m: m.lollipop_graph(5, 3)),
    ("hypercube", lambda m: m.hypercube_graph(3)),
    ("mycielski", lambda m: m.mycielski_graph(4)),
    ("turan", lambda m: m.turan_graph(8, 3)),
    ("caveman", lambda m: m.caveman_graph(3, 4)),
    ("dorogovtsev", lambda m: m.dorogovtsev_goltsev_mendes_graph(2)),
]


@pytest.mark.parametrize("name,fn", GENS)
def test_generator_rows_match_nx(name, fn):
    assert _rows(fn(fnx)) == _rows(fn(nx)), name
