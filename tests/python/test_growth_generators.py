"""Tests for growth-model and degree-model generator wrappers."""

import networkx as nx

import franken_networkx as fnx


def test_gnc_and_gnr_graph_shapes():
    gnc = fnx.gnc_graph(6, seed=1)
    gnr = fnx.gnr_graph(6, 0.5, seed=1)

    assert gnc.number_of_nodes() == 6
    assert gnr.number_of_nodes() == 6
    assert gnc.number_of_edges() > 0
    assert gnr.number_of_edges() > 0


def test_fast_gnp_random_graph_is_reproducible():
    left = fnx.fast_gnp_random_graph(8, 0.3, seed=7)
    right = fnx.fast_gnp_random_graph(8, 0.3, seed=7)

    assert sorted(left.edges()) == sorted(right.edges())


def test_directed_degree_sequence_generators():
    config = fnx.directed_configuration_model([0, 1], [1, 0], seed=1)
    hakimi = fnx.directed_havel_hakimi_graph([0, 1, 1], [1, 1, 0])

    assert config.is_directed()
    assert config.number_of_edges() == 1
    assert hakimi.is_directed()
    assert sorted(hakimi.in_degree[node] for node in hakimi.nodes()) == [0, 1, 1]
    assert sorted(hakimi.out_degree[node] for node in hakimi.nodes()) == [0, 1, 1]


def test_joint_degree_generators():
    undirected = fnx.joint_degree_graph({1: {2: 2}, 2: {1: 2}}, seed=1)
    directed = fnx.directed_joint_degree_graph([0, 1], [1, 0], {1: {1: 1}}, seed=1)

    assert undirected.number_of_nodes() == 3
    assert undirected.number_of_edges() == 2
    assert directed.is_directed()
    assert sorted(directed.edges()) == [(0, 1)]


def test_expected_degree_graph_returns_graph():
    graph = fnx.expected_degree_graph([1.0, 1.5, 2.0], seed=1, selfloops=False)

    assert graph.number_of_nodes() == 3


def test_native_gnc_and_gnr_graphs_do_not_fallback_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "gnc_graph", fail)
    monkeypatch.setattr(nx, "gnr_graph", fail)

    gnc = fnx.gnc_graph(6, seed=1)
    gnr = fnx.gnr_graph(6, 0.5, seed=1)

    assert sorted(gnc.edges()) == [(1, 0), (2, 0), (3, 0), (3, 1), (4, 0), (5, 0), (5, 1), (5, 3)]
    assert sorted(gnr.edges()) == [(1, 0), (2, 0), (3, 1), (4, 3), (5, 0)]


def test_native_random_generators_do_not_fallback_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "balanced_tree", fail)
    monkeypatch.setattr(nx, "barbell_graph", fail)
    monkeypatch.setattr(nx, "bull_graph", fail)
    monkeypatch.setattr(nx, "cubical_graph", fail)
    monkeypatch.setattr(nx, "desargues_graph", fail)
    monkeypatch.setattr(nx, "diamond_graph", fail)
    monkeypatch.setattr(nx, "dodecahedral_graph", fail)
    monkeypatch.setattr(nx, "empty_graph", fail)
    monkeypatch.setattr(nx, "complete_graph", fail)
    monkeypatch.setattr(nx, "cycle_graph", fail)
    monkeypatch.setattr(nx, "full_rary_tree", fail)
    monkeypatch.setattr(nx, "binomial_tree", fail)
    monkeypatch.setattr(nx, "chordal_cycle_graph", fail)
    monkeypatch.setattr(nx, "chvatal_graph", fail)
    monkeypatch.setattr(nx, "complete_bipartite_graph", fail)
    monkeypatch.setattr(nx, "circulant_graph", fail)
    monkeypatch.setattr(nx, "house_graph", fail)
    monkeypatch.setattr(nx, "house_x_graph", fail)
    monkeypatch.setattr(nx, "heawood_graph", fail)
    monkeypatch.setattr(nx, "circular_ladder_graph", fail)
    monkeypatch.setattr(nx, "complete_multipartite_graph", fail)
    monkeypatch.setattr(nx, "frucht_graph", fail)
    monkeypatch.setattr(nx, "generalized_petersen_graph", fail)
    monkeypatch.setattr(nx, "icosahedral_graph", fail)
    monkeypatch.setattr(nx, "krackhardt_kite_graph", fail)
    monkeypatch.setattr(nx, "ladder_graph", fail)
    monkeypatch.setattr(nx, "lollipop_graph", fail)
    monkeypatch.setattr(nx, "moebius_kantor_graph", fail)
    monkeypatch.setattr(nx, "null_graph", fail)
    monkeypatch.setattr(nx, "octahedral_graph", fail)
    monkeypatch.setattr(nx, "paley_graph", fail)
    monkeypatch.setattr(nx, "path_graph", fail)
    monkeypatch.setattr(nx, "petersen_graph", fail)
    monkeypatch.setattr(nx, "star_graph", fail)
    monkeypatch.setattr(nx, "tadpole_graph", fail)
    monkeypatch.setattr(nx, "truncated_cube_graph", fail)
    monkeypatch.setattr(nx, "truncated_tetrahedron_graph", fail)
    monkeypatch.setattr(nx, "tetrahedral_graph", fail)
    monkeypatch.setattr(nx, "trivial_graph", fail)
    monkeypatch.setattr(nx, "tutte_graph", fail)
    monkeypatch.setattr(nx, "wheel_graph", fail)
    monkeypatch.setattr(nx, "windmill_graph", fail)
    monkeypatch.setattr(nx, "grid_2d_graph", fail)
    monkeypatch.setattr(nx, "gnp_random_graph", fail)
    monkeypatch.setattr(nx, "erdos_renyi_graph", fail)
    monkeypatch.setattr(nx, "fast_gnp_random_graph", fail)
    monkeypatch.setattr(nx, "watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "barabasi_albert_graph", fail)
    monkeypatch.setattr(nx, "newman_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "connected_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "random_regular_graph", fail)
    monkeypatch.setattr(nx, "powerlaw_cluster_graph", fail)

    assert fnx.balanced_tree(2, 2).number_of_nodes() == 7
    assert fnx.barbell_graph(3, 2).number_of_nodes() == 8
    assert fnx.bull_graph().number_of_nodes() == 5
    assert fnx.chordal_cycle_graph(5).number_of_nodes() == 5
    assert fnx.chvatal_graph().number_of_nodes() == 12
    assert fnx.circulant_graph(6, [1, 2]).number_of_nodes() == 6
    assert fnx.complete_graph(4).number_of_nodes() == 4
    assert fnx.cycle_graph(4).number_of_nodes() == 4
    assert fnx.cubical_graph().number_of_nodes() == 8
    assert fnx.desargues_graph().number_of_nodes() == 20
    assert fnx.diamond_graph().number_of_nodes() == 4
    assert fnx.dodecahedral_graph().number_of_nodes() == 20
    assert fnx.empty_graph(4).number_of_nodes() == 4
    assert fnx.full_rary_tree(2, 7).number_of_nodes() == 7
    assert fnx.binomial_tree(3).number_of_nodes() == 8
    assert fnx.complete_bipartite_graph(2, 3).number_of_nodes() == 5
    assert fnx.complete_multipartite_graph(2, 3, 1).number_of_nodes() == 6
    assert fnx.frucht_graph().number_of_nodes() == 12
    assert fnx.generalized_petersen_graph(5, 2).number_of_nodes() == 10
    assert fnx.house_graph().number_of_nodes() == 5
    assert fnx.house_x_graph().number_of_nodes() == 5
    assert fnx.heawood_graph().number_of_nodes() == 14
    assert fnx.icosahedral_graph().number_of_nodes() == 12
    assert fnx.circular_ladder_graph(4).number_of_nodes() == 8
    assert fnx.krackhardt_kite_graph().number_of_nodes() == 10
    assert fnx.ladder_graph(4).number_of_nodes() == 8
    assert fnx.lollipop_graph(4, 3).number_of_nodes() == 7
    assert fnx.moebius_kantor_graph().number_of_nodes() == 16
    assert fnx.null_graph().number_of_nodes() == 0
    assert fnx.octahedral_graph().number_of_nodes() == 6
    assert fnx.paley_graph(5).number_of_nodes() == 5
    assert fnx.path_graph(4).number_of_nodes() == 4
    assert fnx.petersen_graph().number_of_nodes() == 10
    assert fnx.star_graph(3).number_of_nodes() == 4
    assert fnx.tadpole_graph(4, 3).number_of_nodes() == 7
    assert fnx.truncated_cube_graph().number_of_nodes() == 24
    assert fnx.truncated_tetrahedron_graph().number_of_nodes() == 12
    assert fnx.tetrahedral_graph().number_of_nodes() == 4
    assert fnx.trivial_graph().number_of_nodes() == 1
    assert fnx.tutte_graph().number_of_nodes() == 46
    assert fnx.wheel_graph(6).number_of_nodes() == 6
    assert fnx.windmill_graph(3, 4).number_of_nodes() == 10
    assert fnx.grid_2d_graph(2, 3).number_of_nodes() == 6
    assert fnx.gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.erdos_renyi_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.fast_gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.barabasi_albert_graph(8, 2, seed=42).number_of_nodes() == 8
    assert fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42).number_of_nodes() == 12
    assert fnx.random_regular_graph(2, 6, seed=42).number_of_nodes() == 6
    assert fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42).number_of_nodes() == 10
