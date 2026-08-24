"""``franken_networkx.clique`` routes to fnx-native clique functions.

``from networkx.algorithms.clique import *`` left find_cliques,
enumerate_all_cliques, node_clique_number, max_weight_clique and friends
bound to networkx's implementations instead of fnx's native versions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import clique as fnx_clique

_NAMES = [
    "find_cliques", "find_cliques_recursive", "make_max_clique_graph",
    "node_clique_number", "number_of_cliques", "enumerate_all_cliques",
    "max_weight_clique",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_clique_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", _NAMES)
def test_clique_fn_is_not_networkx_version(name):
    fn = getattr(fnx_clique, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


@pytest.mark.parametrize("name", _NAMES)
def test_clique_module_signatures_match_legacy_networkx(name):
    legacy = _legacy_networkx()

    assert str(inspect.signature(getattr(fnx_clique, name))) == str(
        inspect.signature(getattr(legacy.algorithms.clique, name))
    )


def test_clique_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    assert sorted(map(sorted, fnx_clique.find_cliques(g))) == (
        sorted(map(sorted, nx.find_cliques(ng)))
    )
    assert fnx_clique.node_clique_number(g) == nx.node_clique_number(ng)
    assert sorted(map(sorted, fnx_clique.enumerate_all_cliques(g))) == (
        sorted(map(sorted, nx.enumerate_all_cliques(ng)))
    )
    weight, clique = fnx_clique.max_weight_clique(g, weight=None)
    nweight, nclique = nx.max_weight_clique(ng, weight=None)
    assert weight == nweight


def test_clique_module_error_contract_matches_legacy_networkx():
    legacy = _legacy_networkx()
    graph = fnx.path_graph(3)

    with pytest.raises(ValueError) as legacy_error:
        list(legacy.algorithms.clique.find_cliques(legacy.path_graph(3), nodes=[0, 2]))
    with pytest.raises(type(legacy_error.value)) as fnx_error:
        list(fnx_clique.find_cliques(graph, nodes=[0, 2]))

    assert str(fnx_error.value) == str(legacy_error.value)
