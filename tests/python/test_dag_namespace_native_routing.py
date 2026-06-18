"""``franken_networkx.dag`` routes to fnx-native DAG functions.

``from networkx.algorithms.dag import *`` left topological_sort, ancestors,
descendants, is_directed_acyclic_graph, antichains, dag_longest_path and
friends bound to networkx's implementations rather than fnx's native ones.
These now route to the fnx top-level functions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import dag as fnx_dag

_NAMES = [
    "descendants", "ancestors", "topological_sort",
    "lexicographical_topological_sort", "all_topological_sorts",
    "topological_generations", "is_directed_acyclic_graph", "is_aperiodic",
    "antichains", "dag_longest_path", "dag_longest_path_length",
]


@pytest.mark.parametrize("name", _NAMES)
def test_dag_fn_is_not_networkx_version(name):
    fn = getattr(fnx_dag, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


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
