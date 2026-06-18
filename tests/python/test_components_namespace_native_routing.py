"""``franken_networkx.components`` routes to fnx-native connectivity fns.

``from networkx.algorithms.components import *`` left the connectivity
predicates and component listers bound to networkx's implementations, so
``fnx.components.connected_components`` (and the strongly/weakly/biconnected
variants, ``is_connected``, counts, ...) silently resolved to nx's instead
of fnx's native versions. These now route to the fnx top-level functions.
Object-identity + value checks (routing is build-independent).

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import components as fnx_components

_NAMES = [
    "articulation_points", "attracting_components", "biconnected_component_edges",
    "biconnected_components", "connected_components", "is_attracting_component",
    "is_biconnected", "is_connected", "is_semiconnected", "is_strongly_connected",
    "is_weakly_connected", "kosaraju_strongly_connected_components",
    "node_connected_component", "number_attracting_components",
    "number_connected_components", "number_strongly_connected_components",
    "number_weakly_connected_components", "strongly_connected_components",
    "weakly_connected_components",
]


@pytest.mark.parametrize("name", _NAMES)
def test_component_fn_is_not_networkx_version(name):
    fn = getattr(fnx_components, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_undirected_component_values_match_fnx_and_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (3, 4)])
    ng = nx.Graph([(0, 1), (1, 2), (3, 4)])
    assert sorted(map(sorted, fnx_components.connected_components(g))) == (
        sorted(map(sorted, nx.connected_components(ng)))
    )
    assert fnx_components.number_connected_components(g) == 2
    assert fnx_components.is_connected(fnx.Graph([(0, 1), (1, 2)]))
    assert fnx_components.node_connected_component(g, 0) == {0, 1, 2}


def test_directed_component_values_match_networkx():
    dg = fnx.DiGraph([(0, 1), (1, 0), (1, 2), (3, 4)])
    ndg = nx.DiGraph([(0, 1), (1, 0), (1, 2), (3, 4)])
    assert sorted(map(sorted, fnx_components.strongly_connected_components(dg))) == (
        sorted(map(sorted, nx.strongly_connected_components(ndg)))
    )
    assert fnx_components.number_weakly_connected_components(dg) == (
        nx.number_weakly_connected_components(ndg)
    )
    assert fnx_components.is_strongly_connected(
        fnx.DiGraph([(0, 1), (1, 0)])
    ) == nx.is_strongly_connected(nx.DiGraph([(0, 1), (1, 0)]))
