"""MultiGraph operation parity with networkx (parallel edges + self-loops).

Multigraphs add edge-key and multiplicity complexity that simple-graph tests
don't reach: degree counts parallel edges, self-loops count twice in the
(undirected) degree, several clustering functions are deliberately
NotImplemented. This pins fnx == networkx across that surface, including the
exception contract.

No mocks: real fnx and real networkx on identically-built multigraphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_multigraph(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    spec = [(r.randrange(n), r.randrange(n)) for _ in range(r.randint(n, 2 * n))]
    fm = fnx.MultiGraph(); fm.add_nodes_from(range(n)); fm.add_edges_from(spec)
    nm = nx.MultiGraph(); nm.add_nodes_from(range(n)); nm.add_edges_from(spec)
    return fm, nm, n


@pytest.mark.parametrize("seed", range(40))
def test_multigraph_structural_parity(seed):
    fm, nm, n = _identical_multigraph(seed)
    assert dict(fm.degree()) == dict(nm.degree())
    assert fm.number_of_edges() == nm.number_of_edges()
    assert fnx.number_of_selfloops(fm) == nx.number_of_selfloops(nm)
    assert fnx.is_connected(fm) == nx.is_connected(nm)
    assert fnx.number_connected_components(fm) == nx.number_connected_components(nm)
    assert fnx.degree_histogram(fm) == nx.degree_histogram(nm)
    assert round(fnx.density(fm), 9) == round(nx.density(nm), 9)
    assert int(fnx.adjacency_matrix(fm).sum()) == int(nx.adjacency_matrix(nm).sum())
    assert fnx.is_eulerian(fm) == nx.is_eulerian(nm)


@pytest.mark.parametrize("seed", range(40))
def test_multigraph_triangles_value_parity(seed):
    fm, nm, n = _identical_multigraph(seed)
    # triangles IS defined on multigraphs (ignores multiplicity); values match.
    assert dict(fnx.triangles(fm)) == dict(nx.triangles(nm))


def test_clustering_family_not_implemented_on_multigraph():
    m = fnx.MultiGraph([(0, 1), (0, 1), (1, 2), (2, 0)])
    nm = nx.MultiGraph([(0, 1), (0, 1), (1, 2), (2, 0)])
    for name in ("clustering", "transitivity", "average_clustering"):
        f_raises = n_raises = False
        try:
            getattr(fnx, name)(m)
        except nx.NetworkXNotImplemented:
            f_raises = True
        try:
            getattr(nx, name)(nm)
        except nx.NetworkXNotImplemented:
            n_raises = True
        assert f_raises == n_raises is True
