"""br-r37-c1-ykzzt: chains submodule import parity."""

from __future__ import annotations

import importlib
import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def test_chains_module_is_directly_importable():
    module = importlib.import_module("franken_networkx.chains")

    _expect(
        module.chain_decomposition is fnx.chain_decomposition,
        "chain_decomposition should use the fnx wrapper",
    )


def test_chains_module_public_surface_matches_networkx():
    fnx_chains = importlib.import_module("franken_networkx.chains")
    nx_chains = importlib.import_module("networkx.algorithms.chains")

    nx_public = {name for name in dir(nx_chains) if not name.startswith("_")}
    fnx_public = {name for name in dir(fnx_chains) if not name.startswith("_")}

    missing = nx_public - fnx_public
    _expect(not missing, f"franken_networkx.chains missing {sorted(missing)}")


def test_chains_module_signature_matches_networkx():
    fnx_chains = importlib.import_module("franken_networkx.chains")
    nx_chains = importlib.import_module("networkx.algorithms.chains")

    fnx_view = str(inspect.signature(fnx_chains.chain_decomposition))
    nx_view = str(inspect.signature(nx_chains.chain_decomposition))

    _expect(fnx_view == nx_view, f"fnx {fnx_view} != nx {nx_view}")


def test_chains_module_function_matches_networkx_values():
    fnx_graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)

    _expect(
        list(fnx.chains.chain_decomposition(fnx_graph))
        == list(nx.chain_decomposition(nx_graph)),
        "chain_decomposition values should match NetworkX",
    )


def test_algorithms_chains_path_uses_fnx_module():
    direct = importlib.import_module("franken_networkx.chains")
    through_algorithms = importlib.import_module("franken_networkx.algorithms.chains")

    _expect(through_algorithms is direct, "algorithms.chains should use the fnx module")
    _expect(
        list(through_algorithms.chain_decomposition(fnx.cycle_graph(4)))
        == list(nx.chain_decomposition(nx.cycle_graph(4))),
        "algorithms.chains should match NetworkX values",
    )
