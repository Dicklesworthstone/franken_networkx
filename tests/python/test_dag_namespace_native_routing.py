"""``franken_networkx.dag`` routes to fnx-native DAG functions.

``from networkx.algorithms.dag import *`` left topological_sort, ancestors,
descendants, is_directed_acyclic_graph, antichains, dag_longest_path and
friends bound to networkx's implementations rather than fnx's native ones.
These now route to the fnx top-level functions.

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
from franken_networkx import dag as fnx_dag

_NAMES = [
    "descendants", "ancestors", "topological_sort",
    "lexicographical_topological_sort", "all_topological_sorts",
    "topological_generations", "is_directed_acyclic_graph", "is_aperiodic",
    "antichains", "dag_longest_path", "dag_longest_path_length",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_dag_surface"
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
def test_dag_fn_is_not_networkx_version(name):
    fn = getattr(fnx_dag, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


@pytest.mark.parametrize("name", _NAMES)
def test_dag_module_signatures_match_legacy_networkx(name):
    legacy = _legacy_networkx()

    assert str(inspect.signature(getattr(fnx_dag, name))) == str(
        inspect.signature(getattr(legacy.algorithms.dag, name))
    )


def test_dag_values_match_networkx():
    g = fnx.DiGraph([(0, 1), (1, 2), (0, 2), (2, 3)])
    ng = nx.DiGraph([(0, 1), (1, 2), (0, 2), (2, 3)])
    assert list(fnx_dag.topological_sort(g)) == list(nx.topological_sort(ng))
    assert fnx_dag.ancestors(g, 2) == nx.ancestors(ng, 2)
    assert fnx_dag.descendants(g, 0) == nx.descendants(ng, 0)
    assert fnx_dag.is_directed_acyclic_graph(g) == nx.is_directed_acyclic_graph(ng)
    assert fnx_dag.dag_longest_path(g) == nx.dag_longest_path(ng)
    assert fnx_dag.dag_longest_path_length(g) == nx.dag_longest_path_length(ng)
    assert sorted(map(tuple, fnx_dag.all_topological_sorts(g))) == (
        sorted(map(tuple, nx.all_topological_sorts(ng)))
    )


def test_dag_cyclic_error_contract_matches_networkx():
    g = fnx.DiGraph([(0, 1), (1, 0)])
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.NetworkXUnfeasible):
        list(fnx_dag.topological_sort(g))
    with pytest.raises(nx.NetworkXUnfeasible):
        list(nx.topological_sort(ng))


def test_dag_module_cyclic_error_contract_matches_legacy_networkx():
    legacy = _legacy_networkx()
    graph = fnx.DiGraph([(0, 1), (1, 0)])

    with pytest.raises(legacy.NetworkXUnfeasible) as legacy_error:
        list(legacy.algorithms.dag.topological_sort(legacy.DiGraph([(0, 1), (1, 0)])))
    with pytest.raises(type(legacy_error.value)) as fnx_error:
        list(fnx_dag.topological_sort(graph))

    assert str(fnx_error.value) == str(legacy_error.value)
