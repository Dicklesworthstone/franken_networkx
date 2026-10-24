"""Namespace routings survive submodule imports (import-order stability).

The 2qsqf namespace routings rebind fnx submodule functions to fnx natives. A
later import of an algorithms submodule must NOT revert them to networkx's
implementation (the algorithms package re-runs aliasing on import — the same
mechanism that caused the dispersion clobber, 0ouoj). This pins routing
stability across submodule imports.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import importlib

import pytest
import networkx as nx
import franken_networkx as fnx

# (submodule, routed function) pairs from the 2qsqf namespace sweep.
_ROUTED = [
    ("linalg", "adjacency_matrix"),
    ("components", "connected_components"),
    ("clique", "find_cliques"),
    ("core", "core_number"),
    ("chordal", "is_chordal"),
    ("traversal", "bfs_tree"),
    ("dag", "topological_sort"),
    ("connectivity", "node_connectivity"),
]


def _is_routed(submodule, fn):
    mod = importlib.import_module(f"franken_networkx.{submodule}")
    return getattr(mod, fn) is not getattr(nx, fn)


@pytest.mark.parametrize("submodule,fn", _ROUTED)
def test_routing_holds_at_baseline(submodule, fn):
    assert _is_routed(submodule, fn)


@pytest.mark.parametrize("submodule,fn", _ROUTED)
def test_routing_survives_algorithms_submodule_imports(submodule, fn):
    # Importing several algorithms submodules re-runs the aliasing machinery.
    for sub in ("centrality", "isomorphism", "components", "flow", "tree",
                "operators", "traversal", "connectivity"):
        try:
            importlib.import_module(f"franken_networkx.algorithms.{sub}")
        except ImportError:
            pass
    # The routing must still point at the fnx native, not networkx's.
    assert _is_routed(submodule, fn)


def test_flattened_algorithms_routing_survives_imports():
    import franken_networkx.algorithms as fa
    for fn in ("connected_components", "find_cliques", "core_number",
               "node_connectivity", "is_chordal"):
        assert getattr(fa, fn) is not getattr(nx, fn)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cutoff", [0, 2, 10])
@pytest.mark.parametrize("function,node", [
    ("single_source_shortest_path", 4),
    ("single_source_shortest_path_length", 4),
    ("single_target_shortest_path", 0),
    ("single_target_shortest_path_length", 0),
])
def test_bounded_reverse_paths_work_after_package_initialization(
    graph_type, cutoff, function, node
):
    reference = nx.path_graph(5, create_using=getattr(nx, graph_type))
    graph = fnx.path_graph(5, create_using=getattr(fnx, graph_type))
    expected = getattr(nx, function)(reference.reverse(copy=False), node, cutoff=cutoff)
    actual = getattr(fnx, function)(graph.reverse(copy=False), node, cutoff=cutoff)
    assert actual == expected


@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph", "view"])
@pytest.mark.parametrize("native_input", [False, True])
def test_common_neighbors_work_after_package_initialization(graph_type, native_input):
    module = fnx if native_input else nx
    if graph_type == "view":
        graph = module.path_graph(3).subgraph([0, 1, 2])
    else:
        graph = module.path_graph(3, create_using=getattr(module, graph_type))
    assert set(fnx.common_neighbors(graph, 0, 2)) == {1}
