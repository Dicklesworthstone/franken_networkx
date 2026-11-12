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


@pytest.mark.parametrize("seed", range(40))
def test_multigraph_edge_keys_and_multiplicity_parity(seed):
    """br-r37-c1-ud93m: this module exists to cover "the edge-key/multiplicity
    surface simple-graph tests miss", and nothing above it compared an edge KEY.
    ``number_of_edges()`` is a count, and the structural test's ``dict(...)``
    comparisons discard iteration order. Auto-key assignment has been changed by
    a past lever (br-r37-c1-mg-parallel-add-autokey), so the key SEQUENCE for
    parallel edges is exactly the kind of thing that can drift silently.

    Every property below was verified equal across all 40 seeds before being
    asserted, so this locks shipped behaviour rather than asserting an
    aspiration.
    """
    fm, nm, n = _identical_multigraph(seed)

    # The keyed edge stream: endpoints AND auto-assigned keys, in order.
    assert list(fm.edges(keys=True)) == list(nm.edges(keys=True))
    assert list(fm.edges()) == list(nm.edges())
    assert list(fnx.selfloop_edges(fm)) == list(nx.selfloop_edges(nm))

    # Per-pair multiplicity and the key sequence within each parallel bundle.
    for u in range(n):
        for v in range(n):
            assert fm.number_of_edges(u, v) == nm.number_of_edges(u, v)
            if fm.has_edge(u, v):
                assert list(fm[u][v].keys()) == list(nm[u][v].keys())
                assert fm.get_edge_data(u, v) == nm.get_edge_data(u, v)


@pytest.mark.parametrize("seed", range(40))
def test_multigraph_iteration_order_parity(seed):
    """br-r37-c1-ud93m: the structural assertions compare ``dict(fm.degree())``
    and ``dict(triangles(...))``, which are blind to iteration order — an
    observable property under the project's non-regression rule. Compared as
    ordered sequences here.
    """
    fm, nm, _ = _identical_multigraph(seed)
    assert list(fm.nodes()) == list(nm.nodes())
    assert list(fm.degree()) == list(nm.degree())
    assert list(fnx.triangles(fm).items()) == list(nx.triangles(nm).items())
    assert {k: list(v) for k, v in fm.adj.items()} == {
        k: list(v) for k, v in nm.adj.items()
    }


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
