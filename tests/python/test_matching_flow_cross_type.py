"""br-r37-c1-0555d: matching/flow/clique/dominating-set/approximation
families accept nx graph args via boundary coercion."""

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
def test_is_matching_nx():
    assert fnx.is_matching(nx.path_graph(5), {(0, 1)}) is True


@needs_nx
def test_is_maximal_matching_nx():
    assert fnx.is_maximal_matching(nx.path_graph(5), {(0, 1), (2, 3)}) is True


@needs_nx
def test_is_perfect_matching_nx():
    g = nx.Graph([(0, 1), (2, 3)])
    assert fnx.is_perfect_matching(g, {(0, 1), (2, 3)}) is True


@needs_nx
def test_is_edge_cover_nx():
    g = nx.path_graph(5)
    assert fnx.is_edge_cover(g, {(0, 1), (1, 2), (2, 3), (3, 4)}) is True


@needs_nx
def test_maximum_flow_nx():
    g = nx.DiGraph([(0, 1, {"capacity": 10}), (1, 2, {"capacity": 5})])
    val, _ = fnx.maximum_flow(g, 0, 2)
    assert val == 5


@needs_nx
def test_maximum_flow_value_nx():
    g = nx.DiGraph([(0, 1, {"capacity": 10}), (1, 2, {"capacity": 5})])
    assert fnx.maximum_flow_value(g, 0, 2) == 5


@needs_nx
def test_minimum_cut_nx():
    g = nx.DiGraph([(0, 1, {"capacity": 10}), (1, 2, {"capacity": 5})])
    val, _ = fnx.minimum_cut(g, 0, 2)
    assert val == 5


@needs_nx
def test_minimum_cut_value_nx():
    g = nx.DiGraph([(0, 1, {"capacity": 10}), (1, 2, {"capacity": 5})])
    assert fnx.minimum_cut_value(g, 0, 2) == 5


@needs_nx
def test_node_connectivity_nx():
    assert fnx.node_connectivity(nx.path_graph(5), 0, 4) == 1


@needs_nx
def test_edge_connectivity_nx():
    assert fnx.edge_connectivity(nx.path_graph(5), 0, 4) == 1


@needs_nx
def test_number_of_spanning_trees_nx():
    assert fnx.number_of_spanning_trees(nx.cycle_graph(4)) == 4


@needs_nx
def test_enumerate_all_cliques_nx():
    cliques = list(fnx.enumerate_all_cliques(nx.path_graph(5)))
    assert len(cliques) > 0


@needs_nx
def test_chordal_graph_cliques_nx():
    cliques = list(fnx.chordal_graph_cliques(nx.complete_graph(3)))
    assert len(cliques) == 1


@needs_nx
def test_attracting_components_nx():
    comps = list(fnx.attracting_components(nx.DiGraph([(0, 1)])))
    assert len(comps) == 1


@needs_nx
def test_number_attracting_components_nx():
    assert fnx.number_attracting_components(nx.DiGraph([(0, 1)])) == 1


@needs_nx
def test_is_biconnected_nx():
    assert fnx.is_biconnected(nx.cycle_graph(4)) is True


@needs_nx
def test_is_semiconnected_nx():
    assert fnx.is_semiconnected(nx.DiGraph([(0, 1), (1, 2)])) is True


@needs_nx
def test_min_weighted_vertex_cover_nx():
    cover = fnx.min_weighted_vertex_cover(nx.path_graph(5))
    assert isinstance(cover, set)


@needs_nx
def test_maximum_independent_set_nx():
    iset = fnx.maximum_independent_set(nx.path_graph(5))
    assert isinstance(iset, set)


@needs_nx
def test_max_clique_nx():
    clq = fnx.max_clique(nx.complete_graph(4))
    assert len(clq) == 4


@needs_nx
def test_dominating_set_nx():
    ds = fnx.dominating_set(nx.path_graph(5))
    assert isinstance(ds, set)


@needs_nx
def test_is_dominating_set_nx():
    assert fnx.is_dominating_set(nx.path_graph(5), {0, 2, 4}) is True


@needs_nx
def test_number_of_isolates_nx():
    g = nx.Graph()
    g.add_node(0)
    g.add_edge(1, 2)
    assert fnx.number_of_isolates(g) == 1
