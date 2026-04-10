"""Tests for stochastic-block-model generator wrappers."""

import pytest

import franken_networkx as fnx


def test_stochastic_block_model_reproducibility():
    sizes = [3, 2]
    probs = [[0.8, 0.1], [0.1, 0.7]]

    left = fnx.stochastic_block_model(sizes, probs, seed=3)
    right = fnx.stochastic_block_model(sizes, probs, seed=3)

    assert left.number_of_nodes() == 5
    assert sorted(left.edges()) == sorted(right.edges())


def test_planted_partition_and_random_partition_graph_sizes():
    planted = fnx.planted_partition_graph(2, 3, 0.9, 0.1, seed=2)
    partition = fnx.random_partition_graph([3, 2], 0.8, 0.2, seed=2)

    assert planted.number_of_nodes() == 6
    assert partition.number_of_nodes() == 5


def test_gaussian_random_partition_graph_is_directed_when_requested():
    graph = fnx.gaussian_random_partition_graph(10, 3, 1, 0.8, 0.1, directed=True, seed=4)

    assert graph.is_directed()
    assert graph.number_of_nodes() == 10


def test_relaxed_caveman_graph_size():
    graph = fnx.relaxed_caveman_graph(3, 4, 0.25, seed=5)

    assert graph.number_of_nodes() == 12
    assert graph.number_of_edges() > 0


def test_stochastic_block_model_default_uses_native_fast_path(monkeypatch):
    called = {}

    def fake(sizes, probs, seed=None):
        called["args"] = (sizes, probs, seed)
        return fnx.empty_graph(sum(sizes))

    monkeypatch.setattr(fnx, "_rust_stochastic_block_model", fake)

    graph = fnx.stochastic_block_model([2, 1], [[0.0, 1.0], [1.0, 0.0]], seed=7)

    assert called["args"] == ([2, 1], [[0.0, 1.0], [1.0, 0.0]], 7)
    assert graph.graph["partition"] == [{0, 1}, {2}]
    assert graph.graph["name"] == "stochastic_block_model"
    assert graph.nodes[0]["block"] == 0
    assert graph.nodes[2]["block"] == 1


def test_stochastic_block_model_fallback_preserves_nodelist_and_attrs(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("native fast path should not be used")

    monkeypatch.setattr(fnx, "_rust_stochastic_block_model", fail)

    graph = fnx.stochastic_block_model(
        [2, 1],
        [[0.0, 0.0], [0.0, 0.0]],
        nodelist=["left", "right", "solo"],
        seed=11,
    )

    assert list(graph.nodes()) == ["left", "right", "solo"]
    assert graph.graph["partition"] == [{"left", "right"}, {"solo"}]
    assert graph.graph["name"] == "stochastic_block_model"
    assert graph.nodes["left"]["block"] == 0
    assert graph.nodes["solo"]["block"] == 1


def test_stochastic_block_model_validates_probability_matrix():
    with pytest.raises(fnx.NetworkXError, match="'p' must be symmetric."):
        fnx.stochastic_block_model([1, 1], [[0.0, 1.0], [0.0, 0.0]])
