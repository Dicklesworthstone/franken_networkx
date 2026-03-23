"""Tests for growth-model and degree-model generator wrappers."""

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
