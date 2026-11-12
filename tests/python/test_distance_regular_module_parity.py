"""Parity coverage for the ``franken_networkx.distance_regular`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_distance_regular",
    "is_strongly_regular",
    "intersection_array",
    "global_parameters",
)


def test_direct_distance_regular_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.distance_regular")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_distance_regular_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.distance_regular")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.distance_regular"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.distance_regular is direct


def test_distance_regular_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.distance_regular")
    expected = importlib.import_module("networkx.algorithms.distance_regular")

    assert set(module.__all__) == set(expected.__all__)


def test_distance_regular_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.distance_regular")
    expected = importlib.import_module("networkx.algorithms.distance_regular")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize(
    "fnx_graph,nx_graph",
    [
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.path_graph(4), nx.path_graph(4)),
        (fnx.complete_graph(5), nx.complete_graph(5)),
    ],
)
def test_distance_regular_predicates_match_networkx(fnx_graph, nx_graph):
    module = importlib.import_module("franken_networkx.distance_regular")

    assert module.is_distance_regular(fnx_graph) == nx.is_distance_regular(nx_graph)
    assert module.is_strongly_regular(fnx_graph) == nx.is_strongly_regular(nx_graph)


@pytest.mark.parametrize(
    "fnx_graph,nx_graph",
    [
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.complete_graph(5), nx.complete_graph(5)),
    ],
)
def test_intersection_array_and_global_parameters_match_networkx(
    fnx_graph, nx_graph
):
    module = importlib.import_module("franken_networkx.distance_regular")

    actual_b, actual_c = module.intersection_array(fnx_graph)
    expected_b, expected_c = nx.intersection_array(nx_graph)

    assert (actual_b, actual_c) == (expected_b, expected_c)
    assert list(module.global_parameters(actual_b, actual_c)) == list(
        nx.global_parameters(expected_b, expected_c)
    )


def test_distance_regular_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.distance_regular")
    graph = fnx.cycle_graph(6)

    with pytest.raises(TypeError):
        module.is_distance_regular(graph, unsupported=True)


# br-r37-c1-64xcg: networkx raises "Graph is not distance regular." when G is
# not regular / not connected / too wide, and "Graph is not distance regular"
# (no period) when an intersection number disagrees - whichever its pair loop
# meets first. fnx raised the first message for every rejected graph.
@pytest.mark.parametrize(
    "build",
    [
        lambda L: L.path_graph(4), lambda L: L.cycle_graph(6), lambda L: L.petersen_graph(),
        lambda L: L.complete_bipartite_graph(3, 3), lambda L: L.circular_ladder_graph(5),
        lambda L: L.disjoint_union(L.complete_graph(3), L.complete_graph(3)), lambda L: L.hypercube_graph(3),
        lambda L: L.dodecahedral_graph(), lambda L: L.cycle_graph(12), lambda L: L.frucht_graph(),
        lambda L: L.moebius_kantor_graph(), lambda L: L.complete_graph(1), lambda L: L.ladder_graph(4),
        lambda L: L.relabel_nodes(L.circular_ladder_graph(6), {i: f"n{i}" for i in range(12)}),
    ],
    ids=["path4", "cycle6", "petersen", "K33", "prism5", "two_triangles", "cube", "dodecahedral",
         "cycle12", "frucht", "moebius_kantor", "K1", "ladder4", "str_prism6"],
)
def test_intersection_array_answer_or_message_matches_networkx(build):
    def outcome(lib):
        try:
            return lib.intersection_array(build(lib))
        except Exception as exc:  # noqa: BLE001 - the exception is the outcome
            return type(exc).__name__, str(exc)

    assert outcome(fnx) == outcome(nx)
