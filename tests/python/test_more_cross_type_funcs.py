"""br-r37-c1-rg8jh: regression — 15 more functions accept nx graph args."""

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
def test_has_path_nx():
    assert fnx.has_path(nx.path_graph(5), 0, 4) is True


@needs_nx
def test_harmonic_centrality_nx():
    assert len(fnx.harmonic_centrality(nx.path_graph(5))) == 5


@needs_nx
def test_degree_centrality_nx():
    assert len(fnx.degree_centrality(nx.path_graph(5))) == 5


@needs_nx
def test_in_degree_centrality_nx():
    assert len(fnx.in_degree_centrality(nx.DiGraph([(0, 1), (1, 2)]))) == 3


@needs_nx
def test_out_degree_centrality_nx():
    assert len(fnx.out_degree_centrality(nx.DiGraph([(0, 1), (1, 2)]))) == 3


@needs_nx
def test_wiener_index_nx():
    assert fnx.wiener_index(nx.path_graph(5)) == 20.0


@needs_nx
def test_barycenter_nx():
    assert fnx.barycenter(nx.path_graph(5)) == [2]


@needs_nx
def test_is_eulerian_nx():
    assert fnx.is_eulerian(nx.cycle_graph(4)) is True


@needs_nx
def test_has_eulerian_path_nx():
    assert fnx.has_eulerian_path(nx.cycle_graph(4)) is True


@needs_nx
def test_global_efficiency_nx():
    assert 0 < fnx.global_efficiency(nx.path_graph(5)) < 1


@needs_nx
def test_local_efficiency_nx():
    assert fnx.local_efficiency(nx.path_graph(5)) == 0.0


@needs_nx
def test_efficiency_nx():
    assert fnx.efficiency(nx.path_graph(5), 0, 4) == 0.25


@needs_nx
def test_is_arborescence_nx():
    assert fnx.is_arborescence(nx.DiGraph([(0, 1), (1, 2)])) is True


@needs_nx
def test_is_branching_nx():
    assert fnx.is_branching(nx.DiGraph([(0, 1), (1, 2)])) is True


@needs_nx
def test_isolates_nx():
    g = nx.Graph()
    g.add_node(0)
    g.add_edge(1, 2)
    assert list(fnx.isolates(g)) == [0]
