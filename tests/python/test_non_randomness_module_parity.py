"""Parity coverage for the ``franken_networkx.algorithms.non_randomness`` module."""

from __future__ import annotations

import importlib
import inspect
import types

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("non_randomness",)


def test_algorithms_non_randomness_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_non_randomness_attribute_remains_function_like_networkx():
    import networkx.algorithms as nx_algorithms

    importlib.import_module("franken_networkx.algorithms.non_randomness")
    importlib.import_module("networkx.algorithms.non_randomness")

    assert callable(fnx.algorithms.non_randomness)
    assert callable(nx_algorithms.non_randomness)
    assert not isinstance(fnx.algorithms.non_randomness, types.ModuleType)
    assert not isinstance(nx_algorithms.non_randomness, types.ModuleType)


def test_non_randomness_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")
    expected = importlib.import_module("networkx.algorithms.non_randomness")

    assert set(module.__all__) == set(expected.__all__)


def test_non_randomness_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")
    expected = importlib.import_module("networkx.algorithms.non_randomness")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_non_randomness_values_match_networkx():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")
    fnx_graph = fnx.karate_club_graph()
    nx_graph = nx.karate_club_graph()

    actual = module.non_randomness(fnx_graph, k=2)
    expected = nx.non_randomness(nx_graph, k=2)

    assert actual[0] == pytest.approx(expected[0])
    assert actual[1] == pytest.approx(expected[1])


def test_non_randomness_error_messages_match_networkx():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")

    with pytest.raises(nx.NetworkXError, match="not applicable to empty graphs"):
        module.non_randomness(fnx.Graph(), k=1)


def test_non_randomness_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.algorithms.non_randomness")
    graph = fnx.karate_club_graph()

    with pytest.raises(TypeError):
        module.non_randomness(graph, k=2, unsupported=True)
