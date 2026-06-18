"""Closed-form property tests on named graphs (ground-truth oracle).

Named graphs have mathematically known invariants — testing against those
constants (not against another implementation) catches off-by-one, scaling,
and definitional bugs independent of any reference library.

No mocks: real fnx against textbook values.

br-r37-c1-xm3i0
"""

from __future__ import annotations

import franken_networkx as fnx


def test_petersen_graph_properties():
    p = fnx.petersen_graph()
    assert p.number_of_nodes() == 10
    assert p.number_of_edges() == 15
    assert fnx.diameter(p) == 2
    assert fnx.radius(p) == 2
    assert fnx.node_connectivity(p) == 3      # 3-regular, 3-connected
    assert fnx.edge_connectivity(p) == 3
    assert sum(fnx.triangles(p).values()) // 3 == 0   # girth 5 → triangle-free
    assert max(len(c) for c in fnx.find_cliques(p)) == 2
    assert fnx.check_planarity(p)[0] is False          # Petersen is non-planar
    assert not fnx.is_bipartite(p)                     # odd girth → not bipartite


def test_complete_graph_properties():
    for n in (4, 5, 6, 7):
        k = fnx.complete_graph(n)
        assert k.number_of_edges() == n * (n - 1) // 2
        assert fnx.diameter(k) == 1
        assert fnx.node_connectivity(k) == n - 1
        assert fnx.edge_connectivity(k) == n - 1
        assert max(len(c) for c in fnx.find_cliques(k)) == n
        assert sum(fnx.triangles(k).values()) // 3 == n * (n - 1) * (n - 2) // 6
        # K_n planar iff n <= 4.
        assert fnx.check_planarity(k)[0] is (n <= 4)


def test_cycle_graph_properties():
    c5 = fnx.cycle_graph(5)
    assert fnx.diameter(c5) == 2
    assert fnx.node_connectivity(c5) == 2
    assert fnx.edge_connectivity(c5) == 2
    assert not fnx.is_bipartite(c5)            # odd cycle
    assert fnx.is_bipartite(fnx.cycle_graph(6))  # even cycle
    assert sum(fnx.triangles(c5).values()) == 0


def test_complete_bipartite_properties():
    b = fnx.complete_bipartite_graph(3, 3)
    assert b.number_of_edges() == 9
    assert fnx.is_bipartite(b)
    assert fnx.check_planarity(b)[0] is False   # K_{3,3} is non-planar
    assert fnx.check_planarity(fnx.complete_bipartite_graph(2, 3))[0] is True


def test_path_graph_eccentricity():
    p = fnx.path_graph(5)
    assert fnx.diameter(p) == 4
    assert fnx.radius(p) == 2
    assert sorted(fnx.center(p)) == [2]
    assert sorted(fnx.periphery(p)) == [0, 4]
