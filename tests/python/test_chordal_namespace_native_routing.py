"""``franken_networkx.chordal`` routes to fnx-native chordal objects.

``from networkx.algorithms.chordal import *`` left is_chordal,
find_induced_nodes, chordal_graph_cliques, chordal_graph_treewidth and the
NetworkXTreewidthBoundExceeded exception bound to networkx's objects instead
of fnx's native versions. Functions route via call-time wrappers; the
exception class via direct alias (so ``except`` / isinstance work).

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import chordal as fnx_chordal

_FUNCS = [
    "is_chordal", "find_induced_nodes", "chordal_graph_cliques",
    "chordal_graph_treewidth",
]


@pytest.mark.parametrize("name", _FUNCS)
def test_chordal_fn_is_not_networkx_version(name):
    assert getattr(fnx_chordal, name) is not getattr(nx, name)


def test_treewidth_exception_class_is_fnx():
    assert fnx_chordal.NetworkXTreewidthBoundExceeded is (
        fnx.NetworkXTreewidthBoundExceeded
    )
    assert fnx_chordal.NetworkXTreewidthBoundExceeded is not (
        nx.NetworkXTreewidthBoundExceeded
    )


def test_chordal_values_match_networkx():
    # A 4-cycle with a chord is chordal; a plain 4-cycle is not.
    chordal_g = fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    n_chordal = nx.Graph(list(chordal_g.edges()))
    assert fnx_chordal.is_chordal(chordal_g) == nx.is_chordal(n_chordal)
    assert not fnx_chordal.is_chordal(fnx.cycle_graph(4))
    k4 = fnx.complete_graph(4)
    assert fnx_chordal.chordal_graph_treewidth(k4) == (
        nx.chordal_graph_treewidth(nx.complete_graph(4))
    )
