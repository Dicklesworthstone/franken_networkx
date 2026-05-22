"""br-r37-c1-0faxm: asteroidal submodule import parity."""

from __future__ import annotations

import importlib
import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def test_asteroidal_module_is_directly_importable():
    module = importlib.import_module("franken_networkx.asteroidal")

    _expect(module.is_at_free is fnx.is_at_free, "is_at_free should use the fnx wrapper")
    _expect(
        module.find_asteroidal_triple is fnx.find_asteroidal_triple,
        "find_asteroidal_triple should use the fnx wrapper",
    )


def test_asteroidal_module_public_surface_matches_networkx():
    fnx_asteroidal = importlib.import_module("franken_networkx.asteroidal")
    nx_asteroidal = importlib.import_module("networkx.algorithms.asteroidal")

    nx_public = {name for name in dir(nx_asteroidal) if not name.startswith("_")}
    fnx_public = {name for name in dir(fnx_asteroidal) if not name.startswith("_")}

    missing = nx_public - fnx_public
    _expect(not missing, f"franken_networkx.asteroidal missing {sorted(missing)}")


def test_asteroidal_module_signatures_match_networkx():
    fnx_asteroidal = importlib.import_module("franken_networkx.asteroidal")
    nx_asteroidal = importlib.import_module("networkx.algorithms.asteroidal")

    for name in ("is_at_free", "find_asteroidal_triple"):
        fnx_view = str(inspect.signature(getattr(fnx_asteroidal, name)))
        nx_view = str(inspect.signature(getattr(nx_asteroidal, name)))
        _expect(fnx_view == nx_view, f"{name}: fnx {fnx_view} != nx {nx_view}")


def test_asteroidal_module_functions_match_networkx_values():
    fnx_graph = fnx.cycle_graph(6)
    nx_graph = nx.cycle_graph(6)

    _expect(
        fnx.asteroidal.is_at_free(fnx_graph) == nx.is_at_free(nx_graph),
        "is_at_free values should match NetworkX",
    )
    _expect(
        fnx.asteroidal.find_asteroidal_triple(fnx_graph)
        == nx.find_asteroidal_triple(nx_graph),
        "find_asteroidal_triple values should match NetworkX",
    )


def test_algorithms_asteroidal_path_uses_fnx_module():
    direct = importlib.import_module("franken_networkx.asteroidal")
    through_algorithms = importlib.import_module("franken_networkx.algorithms.asteroidal")

    _expect(through_algorithms is direct, "algorithms.asteroidal should use the fnx module")
    _expect(
        through_algorithms.find_asteroidal_triple(fnx.cycle_graph(6))
        == nx.find_asteroidal_triple(nx.cycle_graph(6)),
        "algorithms.asteroidal should match NetworkX values",
    )
