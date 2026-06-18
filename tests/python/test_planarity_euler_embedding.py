"""Planarity: Kuratowski closed forms + Euler's formula on the embedding.

check_planarity returns a combinatorial embedding for a planar graph. A valid
embedding of a CONNECTED planar graph satisfies Euler's formula V - E + F = 2,
where F is the number of faces (counted by traversing each face once via
mark_half_edges). This embedding-validity invariant, plus the Kuratowski closed
forms (K5 / K_{3,3} non-planar, K4 planar) and boolean parity with networkx,
pins the planarity machinery.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _count_faces(emb):
    """Number of faces: traverse each face once, marking its half-edges."""
    visited = set()
    faces = 0
    for v in emb:
        for w in emb[v]:
            if (v, w) in visited:
                continue
            emb.traverse_face(v, w, mark_half_edges=visited)
            faces += 1
    return faces


def test_kuratowski_closed_forms():
    assert fnx.check_planarity(fnx.complete_graph(4))[0] is True
    assert fnx.check_planarity(fnx.complete_graph(5))[0] is False
    assert fnx.check_planarity(fnx.complete_bipartite_graph(3, 3))[0] is False
    assert fnx.check_planarity(fnx.complete_bipartite_graph(2, 4))[0] is True
    assert fnx.check_planarity(fnx.petersen_graph())[0] is False


@pytest.mark.parametrize("seed", range(40))
def test_planarity_boolean_parity(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    assert fnx.check_planarity(fg)[0] == nx.check_planarity(ng)[0]


@pytest.mark.parametrize("seed", range(40))
def test_embedding_satisfies_euler_formula(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    is_planar, emb = fnx.check_planarity(fg)
    if not (is_planar and fnx.is_connected(fg) and fg.number_of_edges() > 0):
        pytest.skip("not connected planar with edges")
    v, e = fg.number_of_nodes(), fg.number_of_edges()
    f = _count_faces(emb)
    # Euler's formula for a connected planar embedding.
    assert v - e + f == 2
