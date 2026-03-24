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

    monkeypatch.setattr(nx, "gnp_random_graph", fail)
    monkeypatch.setattr(nx, "erdos_renyi_graph", fail)
    monkeypatch.setattr(nx, "fast_gnp_random_graph", fail)
    monkeypatch.setattr(nx, "watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "barabasi_albert_graph", fail)
    monkeypatch.setattr(nx, "newman_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "connected_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "random_regular_graph", fail)
    monkeypatch.setattr(nx, "powerlaw_cluster_graph", fail)

    assert fnx.gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.erdos_renyi_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.fast_gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.barabasi_albert_graph(8, 2, seed=42).number_of_nodes() == 8
    assert fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42).number_of_nodes() == 12
    assert fnx.random_regular_graph(2, 6, seed=42).number_of_nodes() == 6
    assert fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42).number_of_nodes() == 10
