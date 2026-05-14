"""br-r37-c1-maq1r: regression — fnx.random_reference(seed=N) must
produce the same edge set as nx.random_reference(seed=N).

Before this fix, fnx.random_reference was *not* implementing the
Maslov-Sneppen random-reference rewiring at all — it was calling
``double_edge_swap`` (uniform-edge-pick, no connectivity check),
which is a completely different algorithm. nx's algorithm picks
source nodes weighted by degree via the degree CDF and rejects
swaps that would disconnect the graph when ``connectivity=True``.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
@pytest.mark.parametrize("seed", [42, 7, 100, 999])
@pytest.mark.parametrize("niter", [1, 2, 5])
def test_random_reference_edge_set_matches_nx(seed, niter):
    fg = fnx.random_reference(fnx.cycle_graph(10), niter=niter, seed=seed)
    ng = nx.random_reference(nx.cycle_graph(10), niter=niter, seed=seed)
    assert sorted(fg.edges()) == sorted(ng.edges())


@needs_nx
@pytest.mark.parametrize("seed", [42, 7, 100])
def test_random_reference_connectivity_false_matches_nx(seed):
    fg = fnx.random_reference(fnx.cycle_graph(10), niter=2, connectivity=False, seed=seed)
    ng = nx.random_reference(nx.cycle_graph(10), niter=2, connectivity=False, seed=seed)
    assert sorted(fg.edges()) == sorted(ng.edges())


@needs_nx
def test_random_reference_n_too_small_raises():
    with pytest.raises(fnx.NetworkXError, match=r"fewer than four nodes"):
        fnx.random_reference(fnx.path_graph(3))


@needs_nx
def test_random_reference_too_few_edges_raises():
    g = fnx.Graph()
    g.add_nodes_from([0, 1, 2, 3])
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXError, match=r"fewer that 2 edges"):
        fnx.random_reference(g)


@needs_nx
def test_random_reference_multigraph_not_implemented():
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.random_reference(fnx.MultiGraph([(0, 1), (1, 2), (2, 3), (3, 0)]))


@needs_nx
def test_random_reference_directed_not_implemented():
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.random_reference(fnx.DiGraph([(0, 1), (1, 2), (2, 3), (3, 0)]))
