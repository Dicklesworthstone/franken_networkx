"""``franken_networkx.traversal`` routes to fnx-native BFS/DFS generators.

``from networkx.algorithms.traversal import *`` left bfs_edges, dfs_edges,
the labeled/predecessor/successor/layer generators, edge_bfs/edge_dfs and
descendants_at_distance bound to networkx's implementations instead of
fnx's native ones. These now route to the fnx top-level functions.

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
from franken_networkx import traversal as fnx_traversal

_NAMES = [
    "bfs_beam_edges", "bfs_edges", "bfs_labeled_edges", "bfs_layers",
    "bfs_predecessors", "bfs_successors", "descendants_at_distance",
    "dfs_edges", "dfs_labeled_edges", "dfs_postorder_nodes", "dfs_predecessors",
    "dfs_preorder_nodes", "dfs_successors", "edge_bfs", "edge_dfs",
    "generic_bfs_edges",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_traversal_surface"
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
def test_traversal_fn_is_not_networkx_version(name):
    fn = getattr(fnx_traversal, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


@pytest.mark.parametrize("name", _NAMES)
def test_traversal_module_signatures_match_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_traversal, name))) == str(
        inspect.signature(getattr(legacy.algorithms.traversal, name))
    )


@pytest.mark.parametrize("directed", [False, True])
def test_traversal_values_match_networkx(directed):
    edges = [(0, 1), (1, 2), (2, 3), (0, 3), (3, 4)]
    fg = (fnx.DiGraph if directed else fnx.Graph)(edges)
    ng = (nx.DiGraph if directed else nx.Graph)(edges)
    assert list(fnx_traversal.bfs_edges(fg, 0)) == list(nx.bfs_edges(ng, 0))
    assert list(fnx_traversal.dfs_edges(fg, 0)) == list(nx.dfs_edges(ng, 0))
    assert list(fnx_traversal.dfs_preorder_nodes(fg, 0)) == (
        list(nx.dfs_preorder_nodes(ng, 0))
    )
    assert [sorted(layer) for layer in fnx_traversal.bfs_layers(fg, 0)] == (
        [sorted(layer) for layer in nx.bfs_layers(ng, 0)]
    )
    assert dict(fnx_traversal.bfs_successors(fg, 0)) == dict(nx.bfs_successors(ng, 0))
    assert list(fnx_traversal.dfs_labeled_edges(fg, 0)) == (
        list(nx.dfs_labeled_edges(ng, 0))
    )
    assert fnx_traversal.descendants_at_distance(fg, 0, 1) == (
        nx.descendants_at_distance(ng, 0, 1)
    )


def test_traversal_module_missing_source_error_matches_legacy_networkx():
    legacy = _legacy_networkx()
    with pytest.raises(Exception) as legacy_error:
        list(legacy.algorithms.traversal.bfs_edges(legacy.path_graph(3), "missing"))
    with pytest.raises(type(legacy_error.value)) as fnx_error:
        list(fnx_traversal.bfs_edges(fnx.path_graph(3), "missing"))
    assert str(fnx_error.value) == str(legacy_error.value)
