"""Container-type parity for collection-returning functions.

networkx is specific about the container types it returns — connected
components yield ``set``, find_cliques yields ``list``, descendants returns
``set``, cycle_basis returns ``list`` of ``list``, etc. A function that returns
a ``list`` where nx returns a ``set`` (or a ``tuple`` where nx returns a
``list``) silently breaks downstream set operations, hashing, and indexing.
fnx has fixed several of these (node_connected_component -> set,
biconnected_components -> set, find_cliques -> list). This net pins the outer
and inner container types to networkx's across the collection-returning API.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _U(mod):
    return mod.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 4), (4, 5), (5, 3)])


def _D(mod):
    return mod.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])


def _outer_inner(x):
    """(outer type name, inner element type name or None)."""
    if isinstance(x, dict):
        items = list(x.values())
    elif isinstance(x, (list, tuple, set, frozenset)):
        items = list(x)
    else:  # generator / iterator
        items = list(x)
        return ("list_materialized", type(items[0]).__name__ if items else None)
    return (type(x).__name__, type(items[0]).__name__ if items else None)


# label -> (nx_call, fnx_call). Compared as materialized (outer, inner) types.
_CASES = {
    "connected_components": (lambda: list(nx.connected_components(_U(nx))), lambda: list(fnx.connected_components(_U(fnx)))),
    "strongly_connected_components": (lambda: list(nx.strongly_connected_components(_D(nx))), lambda: list(fnx.strongly_connected_components(_D(fnx)))),
    "weakly_connected_components": (lambda: list(nx.weakly_connected_components(_D(nx))), lambda: list(fnx.weakly_connected_components(_D(fnx)))),
    "biconnected_components": (lambda: list(nx.biconnected_components(_U(nx))), lambda: list(fnx.biconnected_components(_U(fnx)))),
    "attracting_components": (lambda: list(nx.attracting_components(_D(nx))), lambda: list(fnx.attracting_components(_D(fnx)))),
    "node_connected_component": (lambda: nx.node_connected_component(_U(nx), 0), lambda: fnx.node_connected_component(_U(fnx), 0)),
    "find_cliques": (lambda: list(nx.find_cliques(_U(nx))), lambda: list(fnx.find_cliques(_U(fnx)))),
    "enumerate_all_cliques": (lambda: list(nx.enumerate_all_cliques(_U(nx))), lambda: list(fnx.enumerate_all_cliques(_U(fnx)))),
    "descendants": (lambda: nx.descendants(_D(nx), 0), lambda: fnx.descendants(_D(fnx), 0)),
    "ancestors": (lambda: nx.ancestors(_D(nx), 4), lambda: fnx.ancestors(_D(fnx), 4)),
    "descendants_at_distance": (lambda: nx.descendants_at_distance(_D(nx), 0, 2), lambda: fnx.descendants_at_distance(_D(fnx), 0, 2)),
    "cycle_basis": (lambda: nx.cycle_basis(_U(nx)), lambda: fnx.cycle_basis(_U(fnx))),
    "simple_cycles": (lambda: list(nx.simple_cycles(_D(nx))), lambda: list(fnx.simple_cycles(_D(fnx)))),
    "all_simple_paths": (lambda: list(nx.all_simple_paths(_U(nx), 0, 5)), lambda: list(fnx.all_simple_paths(_U(fnx), 0, 5))),
    "all_shortest_paths": (lambda: list(nx.all_shortest_paths(_U(nx), 0, 5)), lambda: list(fnx.all_shortest_paths(_U(fnx), 0, 5))),
    "shortest_path_single": (lambda: nx.shortest_path(_U(nx), 0, 5), lambda: fnx.shortest_path(_U(fnx), 0, 5)),
    "single_source_shortest_path": (lambda: nx.single_source_shortest_path(_U(nx), 0), lambda: fnx.single_source_shortest_path(_U(fnx), 0)),
    "dominating_set": (lambda: nx.dominating_set(_U(nx)), lambda: fnx.dominating_set(_U(fnx))),
    "maximal_independent_set": (lambda: nx.maximal_independent_set(_U(nx), [0]), lambda: fnx.maximal_independent_set(_U(fnx), [0])),
    "find_cycle": (lambda: nx.find_cycle(_D(nx), 0), lambda: fnx.find_cycle(_D(fnx), 0)),
    "bridges": (lambda: list(nx.bridges(_U(nx))), lambda: list(fnx.bridges(_U(fnx)))),
}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_container_type_matches_networkx(name):
    nx_fn, fnx_fn = _CASES[name]
    assert _outer_inner(nx_fn()) == _outer_inner(fnx_fn()), name


def test_voronoi_cells_values_are_sets():
    vn = {k: type(v).__name__ for k, v in nx.voronoi_cells(_U(nx), {0, 5}).items()}
    vf = {k: type(v).__name__ for k, v in fnx.voronoi_cells(_U(fnx), {0, 5}).items()}
    assert vn == vf


def test_k_components_inner_are_sets():
    kn = {k: [type(s).__name__ for s in v] for k, v in nx.k_components(_U(nx)).items()}
    kf = {k: [type(s).__name__ for s in v] for k, v in fnx.k_components(_U(fnx)).items()}
    assert kn == kf
