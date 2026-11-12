"""Parity coverage for the ``franken_networkx.graphical`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_graphical",
    "is_multigraphical",
    "is_pseudographical",
    "is_digraphical",
    "is_valid_degree_sequence_erdos_gallai",
    "is_valid_degree_sequence_havel_hakimi",
)


def test_direct_graphical_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.graphical")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_graphical_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.graphical")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.graphical")

    assert via_algorithms is direct
    assert fnx.algorithms.graphical is direct


def test_graphical_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.graphical")
    expected = importlib.import_module("networkx.algorithms.graphical")

    assert set(module.__all__) == set(expected.__all__)


def test_graphical_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.graphical")
    expected = importlib.import_module("networkx.algorithms.graphical")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize("sequence", [[2, 2, 2], [3, 3, 1], [4, 1, 1, 1, 1]])
def test_graphical_predicates_match_networkx(sequence):
    module = importlib.import_module("franken_networkx.graphical")

    assert module.is_graphical(sequence) == nx.is_graphical(sequence)
    assert module.is_graphical(sequence, method="hh") == nx.is_graphical(
        sequence, method="hh"
    )
    assert module.is_multigraphical(sequence) == nx.is_multigraphical(sequence)
    assert module.is_pseudographical(sequence) == nx.is_pseudographical(sequence)
    assert module.is_valid_degree_sequence_erdos_gallai(
        sequence
    ) == nx.is_valid_degree_sequence_erdos_gallai(sequence)
    assert module.is_valid_degree_sequence_havel_hakimi(
        sequence
    ) == nx.is_valid_degree_sequence_havel_hakimi(sequence)


@pytest.mark.parametrize(
    "in_sequence,out_sequence",
    [
        ([1, 1, 1], [1, 1, 1]),
        ([2, 1, 0], [0, 1, 2]),
        ([2, 2, 2], [1, 1, 1]),
    ],
)
def test_is_digraphical_matches_networkx(in_sequence, out_sequence):
    module = importlib.import_module("franken_networkx.graphical")

    assert module.is_digraphical(in_sequence, out_sequence) == nx.is_digraphical(
        in_sequence, out_sequence
    )


def test_graphical_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.graphical")

    with pytest.raises(TypeError):
        module.is_graphical([2, 2, 2], unsupported=True)
