"""Tests for scale-free and preferential-attachment generator wrappers."""

from collections import Counter

import networkx as nx
import pytest

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


def test_extended_barabasi_albert_graph_does_not_delegate_to_networkx(monkeypatch):
    cases = [
        (10, 2, 0.3, 0.2, 11),
        (12, 2, 0.0, 0.0, 5),
        (12, 2, 0.7, 0.0, 13),
        (12, 2, 0.0, 0.7, 17),
    ]
    expected = [
        (case, nx.extended_barabasi_albert_graph(*case[:4], seed=case[4]))
        for case in cases
    ]

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "extended_barabasi_albert_graph", fail)

    for (n, m, p, q, seed), expected_graph in expected:
        actual = fnx.extended_barabasi_albert_graph(n, m, p, q, seed=seed)
        assert sorted(_to_nx(actual).edges()) == sorted(expected_graph.edges())


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


def test_gn_graph_nonpositive_seed_graph_matches_networkx():
    for n in (-2, -1, 0, False):
        graph = fnx.gn_graph(n)
        graph_nx = nx.gn_graph(n)
        assert graph.is_directed()
        assert sorted(_to_nx(graph).nodes()) == sorted(graph_nx.nodes())
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


def _growth_seed(kind):
    import random

    import numpy as np

    return {
        "int": lambda: 7,
        "negative int": lambda: -12345,
        "int above 2**64": lambda: 2**70 + 9,
        "random.Random": lambda: random.Random(5),
        "RandomState": lambda: np.random.RandomState(5),
        "Generator": lambda: np.random.default_rng(5),
        "float": lambda: 1.5,
        "str": lambda: "x",
        "numpy int": lambda: np.int64(3),
    }[kind]()


def _growth_outcome(call, lib, kind):
    try:
        g = call(lib, _growth_seed(kind))
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        return type(exc).__name__, str(exc)
    kw = {"keys": True} if g.is_multigraph() else {}
    return (
        type(g).__name__,
        list(g.nodes(data=True)),
        list(g.edges(data=True, **kw)),
        [list(g.adj[u]) for u in g],
        dict(g.graph),
    )


# br-r37-c1-cdf1v: gnc_graph, gnr_graph and scale_free_graph handed the seed to
# kernels that take a u64: a random.Random or numpy RNG raised TypeError, a
# negative or > 2**64 int OverflowError, a float TypeError. They now run
# networkx's body on networkx's seed handling for anything the kernel cannot
# reproduce (seed=None keeps the kernel: br-r37-c1-ols3t).
@pytest.mark.parametrize(
    "kind",
    ["int", "negative int", "int above 2**64", "random.Random", "RandomState", "Generator",
     "float", "str", "numpy int"],
)
@pytest.mark.parametrize(
    "call",
    [
        lambda lib, s: lib.gnc_graph(17, seed=s),
        lambda lib, s: lib.gnc_graph(6, create_using=lib.MultiDiGraph, seed=s),
        lambda lib, s: lib.gnr_graph(17, 0.45, seed=s),
        lambda lib, s: lib.gnr_graph(1, 0.45, seed=s),
        lambda lib, s: lib.scale_free_graph(30, seed=s),
        lambda lib, s: lib.scale_free_graph(20, 0.3, 0.4, 0.3, 0.0, 0.7, seed=s),
        lambda lib, s: lib.scale_free_graph(10, -1, 0.5, 0.5, seed=s),
    ],
    ids=["gnc", "gnc_multidigraph", "gnr", "gnr_one_node", "scale_free", "scale_free_deltas",
         "scale_free_bad_alpha"],
)
def test_growth_generators_take_every_networkx_seed(call, kind):
    assert _growth_outcome(call, fnx, kind) == _growth_outcome(call, nx, kind)


# br-r37-c1-cdf1v: networkx grows the MultiDiGraph it is handed and returns that
# object, and raises NetworkXError("initial_graph must be a MultiDiGraph.") for
# any other graph - before checking alpha..delta_out. The kernel copied (so the
# caller's graph was untouched), converted a Graph, and returned a string-
# labelled graph's nodes as internal keys ('str:1:a').
@pytest.mark.parametrize(
    "initial",
    [
        lambda lib: lib.MultiDiGraph([(0, 1), (1, 2), (2, 0), (2, 3)]),
        lambda lib: lib.MultiDiGraph([("a", "b"), ("b", "c"), ("c", "a")]),
        lambda lib: lib.MultiDiGraph([(0.5, "q"), ("q", 3), (3, 0.5)]),
        lambda lib: lib.Graph([(0, 1), (1, 2)]),
        lambda lib: [1, 2],
    ],
    ids=["int_labels", "str_labels", "mixed_labels", "graph", "not_a_graph"],
)
@pytest.mark.parametrize("alpha", [0.41, -1])
def test_scale_free_grows_the_initial_graph_it_is_given(initial, alpha):
    def outcome(lib):
        start = initial(lib)
        try:
            g = lib.scale_free_graph(12, alpha, 0.54 if alpha > 0 else 0.5, 0.05 if alpha > 0 else 0.5,
                                     seed=3, initial_graph=start)
        except Exception as exc:  # noqa: BLE001 - the exception is the outcome
            return type(exc).__name__, str(exc)
        return g is start, list(g.nodes()), list(g.edges(keys=True))

    assert outcome(fnx) == outcome(nx)


def test_scale_free_grows_a_networkx_initial_graph_as_networkx_does():
    start = nx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    grown = fnx.scale_free_graph(12, seed=3, initial_graph=start)
    expected = nx.scale_free_graph(12, seed=3, initial_graph=nx.MultiDiGraph([(0, 1), (1, 2), (2, 0)]))
    assert grown is start
    assert list(grown.edges(keys=True)) == list(expected.edges(keys=True))
