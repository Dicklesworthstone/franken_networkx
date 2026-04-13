"""Tests for scale-free and preferential-attachment generator wrappers."""

from collections import Counter

import networkx as nx

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def test_dual_and_extended_barabasi_albert_match_networkx():
    dual = fnx.dual_barabasi_albert_graph(10, 1, 2, 0.4, seed=7)
    dual_nx = nx.dual_barabasi_albert_graph(10, 1, 2, 0.4, seed=7)

    extended = fnx.extended_barabasi_albert_graph(10, 2, 0.3, 0.2, seed=11)
    extended_nx = nx.extended_barabasi_albert_graph(10, 2, 0.3, 0.2, seed=11)

    assert sorted(_to_nx(dual).edges()) == sorted(dual_nx.edges())
    assert sorted(_to_nx(extended).edges()) == sorted(extended_nx.edges())


def test_dual_barabasi_albert_graph_does_not_delegate_to_networkx(monkeypatch):
    expected = nx.dual_barabasi_albert_graph(10, 1, 2, 0.4, seed=7)

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "dual_barabasi_albert_graph", fail)

    actual = fnx.dual_barabasi_albert_graph(10, 1, 2, 0.4, seed=7)
    assert sorted(_to_nx(actual).edges()) == sorted(expected.edges())


def test_scale_free_graph_matches_networkx_multiedges():
    graph = fnx.scale_free_graph(12, seed=5)
    graph_nx = nx.scale_free_graph(12, seed=5)

    assert graph.is_directed()
    assert Counter(list(_to_nx(graph).edges())) == Counter(list(graph_nx.edges()))


def test_random_powerlaw_tree_helpers_match_networkx():
    tree = fnx.random_powerlaw_tree(8, gamma=3, seed=3, tries=200)
    tree_nx = nx.random_powerlaw_tree(8, gamma=3, seed=3, tries=200)
    sequence = fnx.random_powerlaw_tree_sequence(8, gamma=3, seed=3, tries=200)

    assert sorted(_to_nx(tree).edges()) == sorted(tree_nx.edges())
    assert sum(sequence) == 2 * (len(sequence) - 1)
    assert all(degree >= 1 for degree in sequence)


def test_gn_graph_matches_networkx():
    graph = fnx.gn_graph(9, seed=13)
    graph_nx = nx.gn_graph(9, seed=13)

    assert graph.is_directed()
    assert sorted(_to_nx(graph).edges()) == sorted(graph_nx.edges())


def test_native_scale_free_and_gn_graphs_do_not_fallback_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "scale_free_graph", fail)
    monkeypatch.setattr(nx, "gn_graph", fail)

    gn_graph = fnx.gn_graph(6, seed=1)
    scale_free = fnx.scale_free_graph(6, seed=1)

    assert sorted(gn_graph.edges()) == [(1, 0), (2, 0), (3, 2), (4, 2), (5, 1)]
    assert scale_free.is_directed()
    assert scale_free.is_multigraph()
    assert Counter(list(scale_free.edges())) == Counter(
        [(0, 1), (1, 2), (1, 0), (2, 0), (2, 1), (3, 0), (3, 0), (3, 0), (4, 0), (5, 0)]
    )


def test_native_scale_free_graph_supports_initial_graph(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "scale_free_graph", fail)

    initial = fnx.MultiDiGraph()
    initial.add_edge(7, 8)
    graph = fnx.scale_free_graph(4, seed=1, initial_graph=initial)

    assert isinstance(graph, fnx.MultiDiGraph)
    assert Counter(list(graph.edges(keys=True))) == Counter(
        [(7, 8, 0), (9, 8, 0), (10, 8, 0)]
    )
