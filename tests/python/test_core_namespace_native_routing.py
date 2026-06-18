"""``franken_networkx.core`` routes core_number / k_truss to fnx natives.

``from networkx.algorithms.core import *`` left ``core_number`` and
``k_truss`` bound to networkx's implementations instead of fnx's native
versions (``k_core`` was already overridden). These now route to the fnx
top-level functions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import core as fnx_core


@pytest.mark.parametrize("name", ["core_number", "k_truss"])
def test_core_fn_is_not_networkx_version(name):
    assert getattr(fnx_core, name) is not getattr(nx, name)


def test_core_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2), (0, 3)])
    ng = nx.Graph(list(g.edges()))
    assert fnx_core.core_number(g) == nx.core_number(ng)
    assert sorted(map(lambda e: tuple(sorted(e)), fnx_core.k_truss(g, 3).edges())) == (
        sorted(map(lambda e: tuple(sorted(e)), nx.k_truss(ng, 3).edges()))
    )


def test_k_truss_on_complete_graph():
    # In K_n every edge is in (n-2)-truss; k_truss(K5, 4) keeps all edges.
    g = fnx.complete_graph(5)
    ng = nx.complete_graph(5)
    assert sorted(map(lambda e: tuple(sorted(e)), fnx_core.k_truss(g, 4).edges())) == (
        sorted(map(lambda e: tuple(sorted(e)), nx.k_truss(ng, 4).edges()))
    )
