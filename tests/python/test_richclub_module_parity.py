"""Parity coverage for the ``franken_networkx.richclub`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("rich_club_coefficient",)


def test_direct_richclub_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.richclub")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_richclub_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.richclub")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.richclub")

    assert via_algorithms is direct
    assert fnx.algorithms.richclub is direct


def test_richclub_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    expected = importlib.import_module("networkx.algorithms.richclub")

    assert set(module.__all__) == set(expected.__all__)


def test_richclub_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    expected = importlib.import_module("networkx.algorithms.richclub")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_rich_club_coefficient_values_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    fnx_graph = fnx.complete_graph(5)
    nx_graph = nx.complete_graph(5)

    assert module.rich_club_coefficient(
        fnx_graph,
        normalized=False,
    ) == nx.rich_club_coefficient(nx_graph, normalized=False)


def test_rich_club_coefficient_path_values_match_networkx():
    module = importlib.import_module("franken_networkx.richclub")
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    assert module.rich_club_coefficient(
        fnx_graph,
        normalized=False,
    ) == nx.rich_club_coefficient(nx_graph, normalized=False)


def test_rich_club_coefficient_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.richclub")
    graph = fnx.complete_graph(4)

    with pytest.raises(TypeError):
        module.rich_club_coefficient(graph, normalized=False, unsupported=True)


def _rich_club_seed(kind):
    import random

    import numpy as np

    if kind == "int":
        return 12345
    if kind == "negative int":
        return -1
    if kind == "random.Random":
        return random.Random(3)
    if kind == "RandomState":
        return np.random.RandomState(4)
    if kind == "Generator":
        return np.random.default_rng(4)
    if kind == "float":
        return 1.5
    random.seed(7)
    np.random.seed(7)
    return None


def _rich_club_outcome(lib, build, Q, kind):
    try:
        return lib.rich_club_coefficient(build(lib), Q=Q, seed=_rich_club_seed(kind))
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        return (type(exc).__name__, str(exc))


# br-r37-c1-cdf1v: networkx randomises R = G.copy(), and copy() re-adds the edges
# in adjacency-iteration order, so the neighbour order seed.choice indexes is
# copy()'s, not G's (karate's node 33 lists 22 after 20, not last). fnx replayed
# the swaps on G's order, so a seed drew another graph as soon as a choice landed
# on a reordered row - every seed kind, ints included; it also resolved the seed
# after double_edge_swap's graph checks.
@pytest.mark.parametrize(
    "kind",
    ["int", "negative int", "random.Random", "RandomState", "Generator", "float", "global None"],
)
@pytest.mark.parametrize(
    "build",
    [
        lambda lib: lib.karate_club_graph(),
        lambda lib: lib.barabasi_albert_graph(60, 3, seed=2),
        lambda lib: lib.relabel_nodes(
            lib.gnp_random_graph(25, 0.25, seed=9), {i: f"n{(i * 7) % 25}" for i in range(25)}
        ),
        lambda lib: lib.path_graph(3),
    ],
    ids=["karate", "barabasi_albert", "str_labels", "three_nodes"],
)
@pytest.mark.parametrize("Q", [1, 5])
def test_rich_club_coefficient_normalized_matches_networkx_for_every_seed_kind(build, Q, kind):
    assert _rich_club_outcome(fnx, build, Q, kind) == _rich_club_outcome(nx, build, Q, kind)
