import networkx as nx
import pytest

import franken_networkx as fnx

from franken_networkx.backend import _fnx_to_nx as _to_nx


def test_random_labeled_tree_matches_networkx_seeded_edges():
    graph = fnx.random_labeled_tree(5, seed=42)
    expected = nx.random_labeled_tree(5, seed=42)

    assert fnx.is_tree(graph)
    assert sorted(graph.edges()) == sorted(expected.edges())


def test_random_labeled_tree_rejects_null_graph():
    with pytest.raises(fnx.NetworkXPointlessConcept, match="null graph is not a tree"):
        fnx.random_labeled_tree(0, seed=42)


def test_triad_graph_matches_networkx_for_all_named_triads():
    triads = (
        "003",
        "012",
        "102",
        "021D",
        "021U",
        "021C",
        "111D",
        "111U",
        "030T",
        "030C",
        "201",
        "120D",
        "120U",
        "120C",
        "210",
        "300",
    )
    for triad_name in triads:
        graph = fnx.triad_graph(triad_name)
        expected = nx.triad_graph(triad_name)

        assert sorted(graph.nodes()) == sorted(expected.nodes())
        assert sorted(graph.edges()) == sorted(expected.edges())


def test_triad_graph_invalid_name_matches_networkx_contract():
    with pytest.raises(ValueError, match="unknown triad name"):
        fnx.triad_graph("999")


def test_random_powerlaw_tree_sequence_matches_networkx_seeded_output():
    assert fnx.random_powerlaw_tree_sequence(8, gamma=3, seed=3, tries=200) == nx.random_powerlaw_tree_sequence(
        8,
        gamma=3,
        seed=3,
        tries=200,
    )


def test_barabasi_albert_with_initial_graph_matches_networkx_without_fallback(monkeypatch):
    initial = fnx.path_graph(3)
    expected_initial = nx.path_graph(3)
    real_barabasi_albert_graph = nx.barabasi_albert_graph

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "barabasi_albert_graph", fail)

    graph = fnx.barabasi_albert_graph(6, 1, seed=42, initial_graph=initial)
    expected = real_barabasi_albert_graph(6, 1, seed=42, initial_graph=expected_initial)

    assert sorted(graph.edges()) == sorted(expected.edges())


def test_random_unlabeled_rooted_forest_matches_networkx_roots_and_edges():
    graph = fnx.random_unlabeled_rooted_forest(3, q=2, seed=1)
    expected = nx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["roots"] == expected.graph["roots"]


def test_random_unlabeled_rooted_forest_uses_local_sampler_without_networkx_fallback(monkeypatch):
    expected = nx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "random_unlabeled_rooted_forest", fail)

    graph = fnx.random_unlabeled_rooted_forest(3, q=2, seed=1)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["roots"] == expected.graph["roots"]


def test_random_unlabeled_rooted_forest_supports_number_of_forests():
    forests = fnx.random_unlabeled_rooted_forest(3, q=2, number_of_forests=2, seed=1)

    assert len(forests) == 2
    assert all(isinstance(graph, fnx.Graph) for graph in forests)


def test_random_unlabeled_rooted_forest_matches_networkx_with_random_instance_seed():
    import random

    fnx_forests = fnx.random_unlabeled_rooted_forest(
        6,
        q=3,
        number_of_forests=3,
        seed=random.Random(7),
    )
    expected_forests = nx.random_unlabeled_rooted_forest(
        6,
        q=3,
        number_of_forests=3,
        seed=random.Random(7),
    )

    assert [
        (sorted(_to_nx(graph).edges()), graph.graph["roots"]) for graph in fnx_forests
    ] == [(sorted(graph.edges()), graph.graph["roots"]) for graph in expected_forests]


def test_random_unlabeled_rooted_tree_matches_networkx_root_and_edges():
    graph = fnx.random_unlabeled_rooted_tree(5, seed=42)
    expected = nx.random_unlabeled_rooted_tree(5, seed=42)

    assert sorted(_to_nx(graph).edges()) == sorted(expected.edges())
    assert graph.graph["root"] == expected.graph["root"]


def test_random_unlabeled_rooted_tree_supports_number_of_trees():
    trees = fnx.random_unlabeled_rooted_tree(4, number_of_trees=2, seed=3)

    assert len(trees) == 2
    assert all(isinstance(graph, fnx.Graph) for graph in trees)
    assert all(graph.graph["root"] == 0 for graph in trees)


def test_random_unlabeled_rooted_tree_rejects_null_graph():
    with pytest.raises(fnx.NetworkXPointlessConcept, match="null graph is not a tree"):
        fnx.random_unlabeled_rooted_tree(0, seed=1234)


def test_random_unlabeled_rooted_tree_matches_networkx_with_random_instance_seed():
    import random

    fnx_trees = fnx.random_unlabeled_rooted_tree(6, number_of_trees=3, seed=random.Random(7))
    expected_trees = nx.random_unlabeled_rooted_tree(6, number_of_trees=3, seed=random.Random(7))

    assert [(sorted(_to_nx(graph).edges()), graph.graph["root"]) for graph in fnx_trees] == [
        (sorted(graph.edges()), graph.graph["root"]) for graph in expected_trees
    ]


def test_random_unlabeled_rooted_tree_supports_numpy_seed_adapter():
    numpy = pytest.importorskip("numpy")

    fnx_tree = fnx.random_unlabeled_rooted_tree(5, seed=numpy.random.default_rng(9))
    expected_tree = nx.random_unlabeled_rooted_tree(5, seed=numpy.random.default_rng(9))

    assert sorted(_to_nx(fnx_tree).edges()) == sorted(expected_tree.edges())
    assert fnx_tree.graph["root"] == expected_tree.graph["root"]
