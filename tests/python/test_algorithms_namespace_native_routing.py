"""``franken_networkx.algorithms`` flattened names route to fnx natives.

``from networkx.algorithms import *`` flattens networkx's functions into the
``franken_networkx.algorithms`` namespace, so
``from franken_networkx.algorithms import connected_components`` resolved to
nx's implementation wherever fnx has a native ``fnx.connected_components``.
A dynamic routing pass now rebinds every such flattened name to fnx's native
(functions via call-time wrappers, classes via direct alias).

br-r37-c1-nhbni
"""

from __future__ import annotations

import inspect

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms

# Representative sample across domains.
_SAMPLE_FUNCS = [
    "connected_components", "adamic_adar_index", "wiener_index",
    "betweenness_centrality", "pagerank", "find_cliques", "is_chordal",
    "topological_sort", "maximum_flow", "node_connectivity",
    "transitivity", "triangles", "minimum_spanning_edges",
]
_CLASSES = [
    "ArborescenceIterator", "EdgePartition", "NetworkXTreewidthBoundExceeded",
    "SpanningTreeIterator",
]


def test_no_flattened_function_still_bound_to_networkx():
    # After routing, no flattened *function* in __all__ should still be nx's
    # while fnx has a native version. (Submodule references like
    # ``community``/``connectivity`` are modules, not functions, and are out of
    # scope for this function-level routing.)
    still = []
    for name in fnx_algorithms.__all__:
        if name.startswith("_"):
            continue
        fa = getattr(fnx_algorithms, name, None)
        fx = getattr(fnx, name, None)
        nxo = getattr(nx, name, None)
        if fa is None or fx is None or nxo is None:
            continue
        if inspect.ismodule(fx):
            continue
        if fa is nxo and fx is not nxo:
            still.append(name)
    assert still == [], f"still nx-bound: {still[:20]}"


@pytest.mark.parametrize("name", _SAMPLE_FUNCS)
def test_sample_function_routed(name):
    assert getattr(fnx_algorithms, name) is not getattr(nx, name)


@pytest.mark.parametrize("name", _CLASSES)
def test_class_routed_to_fnx(name):
    assert getattr(fnx_algorithms, name) is getattr(fnx, name)
    assert getattr(fnx_algorithms, name) is not getattr(nx, name)


def test_routed_function_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
    ng = nx.Graph(list(g.edges()))
    assert sorted(map(sorted, fnx_algorithms.connected_components(g))) == (
        sorted(map(sorted, nx.connected_components(ng)))
    )
    assert fnx_algorithms.wiener_index(fnx.complete_graph(4)) == (
        nx.wiener_index(nx.complete_graph(4))
    )
    assert fnx_algorithms.transitivity(g) == pytest.approx(nx.transitivity(ng))
